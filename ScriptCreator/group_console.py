"""Utilities for routing script output to per-group consoles."""

from __future__ import annotations

import builtins
import contextvars
import io
import sys
import time
from contextlib import contextmanager
from typing import Optional

from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont, QKeySequence, QTextCursor, QTextDocument
from PyQt5.QtWidgets import (
    QButtonGroup,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QPlainTextEdit,
    QPushButton,
    QRadioButton,
    QShortcut,
    QVBoxLayout,
    QWidget,
)

__all__ = [
    "GroupConsoleWindow",
    "install_console_routing",
    "push_group_console",
    "pop_group_console",
    "use_group_console",
    "console_print",
]


_console_context: contextvars.ContextVar[Optional["GroupConsoleWindow"]]
_console_context = contextvars.ContextVar("group_console_window", default=None)


class ConsoleRouter(io.TextIOBase):
    """Route text output to the active group console when available."""

    def __init__(self, fallback):
        super().__init__()
        self._fallback = fallback

    def write(self, data):  # type: ignore[override]
        if not data:
            return 0
        if isinstance(data, bytes):
            encoding = self.encoding or "utf-8"
            data = data.decode(encoding, errors="replace")

        console = _console_context.get()
        if console is None:
            self._fallback.write(data)
            if hasattr(self._fallback, "flush"):
                self._fallback.flush()
        else:
            console.append_text(data)
        return len(data)

    def flush(self):  # type: ignore[override]
        console = _console_context.get()
        if console is None and hasattr(self._fallback, "flush"):
            self._fallback.flush()

    def readable(self):  # type: ignore[override]
        return False

    def writable(self):  # type: ignore[override]
        return True

    def seekable(self):  # type: ignore[override]
        return False

    def fileno(self):  # type: ignore[override]
        if hasattr(self._fallback, "fileno"):
            return self._fallback.fileno()
        raise OSError("ConsoleRouter has no fileno")

    @property
    def encoding(self):  # type: ignore[override]
        return getattr(self._fallback, "encoding", "utf-8")


_stdout_router = ConsoleRouter(sys.__stdout__)
_stderr_router = ConsoleRouter(sys.__stderr__)


def install_console_routing() -> None:
    """Replace ``sys.stdout`` and ``sys.stderr`` with router instances."""

    sys.stdout = _stdout_router
    sys.stderr = _stderr_router


def push_group_console(console: Optional["GroupConsoleWindow"]):
    """Activate ``console`` for the current execution context."""

    return _console_context.set(console)


def pop_group_console(token) -> None:
    """Restore the previous console context using ``token``."""

    if token is not None:
        _console_context.reset(token)


@contextmanager
def use_group_console(console: Optional["GroupConsoleWindow"]):
    """Context manager that routes output to ``console`` when provided."""

    token = push_group_console(console)
    try:
        yield
    finally:
        pop_group_console(token)


def console_print(console: Optional["GroupConsoleWindow"], *args, **kwargs) -> None:
    """Print helper that writes directly to ``console`` when available.

    ``print`` accepts several keyword arguments that interact with arbitrary
    file-like objects.  When callers pass a custom ``file`` target we fall back
    to :func:`builtins.print` to preserve the original behaviour.  Otherwise the
    message is formatted using ``sep`` and ``end`` before being forwarded to the
    group console.  When no console is active the helper simply delegates to the
    standard print implementation so output continues to flow to the fallback
    terminal.
    """

    file_obj = kwargs.get("file")
    if file_obj not in (None, sys.stdout, sys.stderr):
        builtins.print(*args, **kwargs)
        return

    sep = kwargs.get("sep", " ")
    end = kwargs.get("end", "\n")
    if args:
        try:
            text = sep.join(map(str, args))
        except Exception:
            text = sep.join(str(arg) for arg in args)
    else:
        text = ""
    text += end

    flush = kwargs.get("flush", False)

    if console is None:
        if file_obj is None:
            builtins.print(text, end="", flush=flush)
        else:
            builtins.print(text, end="", file=file_obj, flush=flush)
        return

    console.append_text(text)
    if flush and hasattr(console, "flush"):
        console.flush()


class GroupConsoleWindow(QWidget):
    """Simple window displaying text output for a single group."""

    append_requested = pyqtSignal(str)
    closed = pyqtSignal()

    def __init__(self, leader_name: str, parent=None):
        super().__init__(parent, Qt.Window)
        self.setAttribute(Qt.WA_DeleteOnClose, True)
        self._is_closed = False

        self._text_edit = QPlainTextEdit(self)
        self._text_edit.setReadOnly(True)
        self._text_edit.setLineWrapMode(QPlainTextEdit.NoWrap)
        self._text_edit.verticalScrollBar().valueChanged.connect(self._on_scroll_value_changed)
        self._text_edit.cursorPositionChanged.connect(self._on_cursor_changed)
        self._text_edit.selectionChanged.connect(self._on_selection_changed)
        self._manual_scroll = False
        self._last_manual_scroll = 0.0
        self._selection_active = False
        self._auto_scroll_timer = QTimer(self)
        self._auto_scroll_timer.setInterval(1000)
        self._auto_scroll_timer.timeout.connect(self._maybe_resume_auto_scroll)

        font = QFont("Consolas")
        if not font.exactMatch():
            font = self._text_edit.font()
            font.setFamily("Courier New")
        self._text_edit.setFont(font)

        self._last_search_text = ""

        self._search_bar = QWidget(self)
        search_layout = QHBoxLayout(self._search_bar)
        search_layout.setContentsMargins(0, 0, 0, 0)

        self._search_input = QLineEdit(self._search_bar)
        self._search_input.setPlaceholderText("Buscar...")
        search_layout.addWidget(self._search_input)

        direction_label = QLabel("Dirección:", self._search_bar)
        search_layout.addWidget(direction_label)

        self._direction_group = QButtonGroup(self._search_bar)
        self._direction_up = QRadioButton("Arriba", self._search_bar)
        self._direction_down = QRadioButton("Abajo", self._search_bar)
        self._direction_down.setChecked(True)
        self._direction_group.addButton(self._direction_up)
        self._direction_group.addButton(self._direction_down)
        search_layout.addWidget(self._direction_up)
        search_layout.addWidget(self._direction_down)

        self._search_button = QPushButton("Buscar siguiente", self._search_bar)
        self._search_button.setAutoDefault(False)
        search_layout.addWidget(self._search_button)

        self._close_search_button = QPushButton("Cerrar", self._search_bar)
        self._close_search_button.setAutoDefault(False)
        search_layout.addWidget(self._close_search_button)

        self._search_bar.setVisible(False)

        layout = QVBoxLayout(self)
        layout.addWidget(self._search_bar)
        layout.addWidget(self._text_edit)

        self._find_shortcut = QShortcut(QKeySequence.Find, self)
        self._find_shortcut.activated.connect(self._show_search_bar)
        self._search_button.clicked.connect(self._find_next)
        self._close_search_button.clicked.connect(self._close_search_bar)
        self._search_input.returnPressed.connect(self._find_next)

        self.append_requested.connect(self._append_text)
        self.set_leader_name(leader_name)
        self._auto_scroll_timer.start()

    def set_leader_name(self, leader_name: str) -> None:
        self.setWindowTitle(f"Group Console - {leader_name}")

    def append_text(self, text: str) -> None:
        if not text or self._is_closed:
            return
        self.append_requested.emit(text)

    def clear(self) -> None:
        if self._is_closed:
            return
        self._text_edit.clear()

    def _show_search_bar(self) -> None:
        if self._is_closed:
            return
        if not self._search_bar.isVisible():
            selected = self._text_edit.textCursor().selectedText()
            if selected:
                self._search_input.setText(selected)
            elif self._last_search_text:
                self._search_input.setText(self._last_search_text)
            self._search_bar.setVisible(True)
        self._search_input.setFocus()
        self._search_input.selectAll()

    def _close_search_bar(self) -> None:
        if self._is_closed:
            return
        self._search_bar.setVisible(False)
        self._text_edit.setFocus()

    def _find_next(self) -> None:
        if self._is_closed:
            return
        pattern = self._search_input.text()
        if not pattern:
            return

        flags = QTextDocument.FindFlags()
        if self._direction_up.isChecked():
            flags |= QTextDocument.FindBackward

        cursor = self._text_edit.textCursor()
        if pattern != self._last_search_text:
            if flags & QTextDocument.FindBackward:
                cursor.movePosition(QTextCursor.End)
            else:
                cursor.movePosition(QTextCursor.Start)
            self._text_edit.setTextCursor(cursor)

        self._last_search_text = pattern

        if not self._text_edit.find(pattern, flags):
            cursor = self._text_edit.textCursor()
            if flags & QTextDocument.FindBackward:
                cursor.movePosition(QTextCursor.End)
            else:
                cursor.movePosition(QTextCursor.Start)
            self._text_edit.setTextCursor(cursor)
            self._text_edit.find(pattern, flags)

    def _append_text(self, text: str) -> None:
        if self._is_closed:
            return
        scrollbar = self._text_edit.verticalScrollBar()
        previous_value = scrollbar.value()
        previous_cursor = QTextCursor(self._text_edit.textCursor())
        insert_cursor = self._text_edit.textCursor()
        insert_cursor.movePosition(QTextCursor.End)
        insert_cursor.insertText(text)
        if not self._should_hold_scroll():
            self._text_edit.setTextCursor(insert_cursor)
            self._text_edit.ensureCursorVisible()
        else:
            self._text_edit.setTextCursor(previous_cursor)
            scrollbar.setValue(previous_value)

    def _on_selection_changed(self) -> None:
        if self._is_closed:
            return
        cursor = self._text_edit.textCursor()
        self._selection_active = cursor.hasSelection()
        if self._selection_active:
            self._manual_scroll = True
            self._last_manual_scroll = time.monotonic()

    def _on_cursor_changed(self) -> None:
        if self._is_closed:
            return
        if self._selection_active:
            self._manual_scroll = True
            self._last_manual_scroll = time.monotonic()

    def _on_scroll_value_changed(self, value: int) -> None:
        if self._is_closed:
            return
        scrollbar = self._text_edit.verticalScrollBar()
        if value < scrollbar.maximum():
            self._manual_scroll = True
            self._last_manual_scroll = time.monotonic()
        else:
            if not self._selection_active:
                self._manual_scroll = False
                self._last_manual_scroll = 0.0

    def _should_hold_scroll(self) -> bool:
        if self._selection_active:
            return True
        if not self._manual_scroll:
            return False
        return (time.monotonic() - self._last_manual_scroll) < 30.0

    def _maybe_resume_auto_scroll(self) -> None:
        if self._is_closed:
            return
        if self._should_hold_scroll():
            return
        cursor = self._text_edit.textCursor()
        cursor.movePosition(QTextCursor.End)
        self._text_edit.setTextCursor(cursor)
        self._text_edit.ensureCursorVisible()
        self._manual_scroll = False
        self._selection_active = False
        self._last_manual_scroll = 0.0

    def closeEvent(self, event):  # type: ignore[override]
        self._is_closed = True
        self._auto_scroll_timer.stop()
        self.closed.emit()
        super().closeEvent(event)