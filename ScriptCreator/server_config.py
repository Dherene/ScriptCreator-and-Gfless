"""Dialog to configure server login using gfless_api."""

from PyQt5.QtWidgets import (
    QDialog,
    QVBoxLayout,
    QLabel,
    QComboBox,
    QPushButton,
    QLineEdit,
    QCheckBox,
)
from PyQt5.QtCore import QSettings
import gfless_api


def _to_bool(value, default=False):
    if isinstance(value, bool):
        return value
    if value in {None, ""}:
        return default
    if isinstance(value, str):
        return value.lower() in {"1", "true", "yes", "on"}
    return bool(value)


class ServerConfigDialog(QDialog):
    """Dialog to select language, server, channel and character."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Server Configuration")

        # ``pid`` is stored separately so we use our own settings object
        self.settings = QSettings('PBapi', 'Script Creator')

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Language"))
        self.lang_combo = QComboBox()
        self.lang_combo.addItems([
            "International/English",
            "German",
            "French",
            "Italian",
            "Polish",
            "Spanish",
        ])
        layout.addWidget(self.lang_combo)

        layout.addWidget(QLabel("Server"))
        self.server_combo = QComboBox()
        self.server_combo.addItems([str(i) for i in range(1, 5)])
        layout.addWidget(self.server_combo)

        layout.addWidget(QLabel("Channel"))
        self.channel_combo = QComboBox()
        self.channel_combo.addItems([str(i) for i in range(1, 8)])
        layout.addWidget(self.channel_combo)

        layout.addWidget(QLabel("Character"))
        self.char_combo = QComboBox()
        self.char_combo.addItem("Stay at character selection")
        self.char_combo.addItems([str(i) for i in range(1, 5)])
        layout.addWidget(self.char_combo)

        layout.addWidget(QLabel("PID (optional)"))
        self.pid_edit = QLineEdit()
        self.pid_edit.setPlaceholderText("auto")
        layout.addWidget(self.pid_edit)

        self.sequential_checkbox = QCheckBox("Use sequential conditions")
        layout.addWidget(self.sequential_checkbox)

        self.confirm_button = QPushButton("Confirm")
        self.confirm_button.clicked.connect(self.apply)
        layout.addWidget(self.confirm_button)

        self.load_settings()

    def apply(self):
        pid_text = self.pid_edit.text().strip()
        pid = int(pid_text) if pid_text else None
        lang = self.lang_combo.currentIndex()
        server = self.server_combo.currentIndex()
        channel = self.channel_combo.currentIndex()
        char = self.char_combo.currentIndex() - 1
        use_sequential = self.sequential_checkbox.isChecked()

        gfless_api.save_config(lang, server, channel, char)
        # persist the last used PID for convenience
        self.settings.setValue("pid", pid_text)
        self.settings.setValue("useSequentialConditions", int(use_sequential))

        parent = self.parent()
        if parent and hasattr(parent, "set_sequential_conditions_enabled"):
            try:
                parent.set_sequential_conditions_enabled(use_sequential)
            except Exception:
                pass

        gfless_api.close_login_pipe()
        try:
            gfless_api.login(
                lang,
                server,
                channel,
                char,
                pid=pid,
                force_reinject=True,
            )
        except Exception as exc:
            self._login_failed(str(exc))
            return
        self.accept()

    def load_settings(self):
        lang, server, channel, char = gfless_api.load_config()
        pid = self.settings.value("pid", "")
        use_sequential = _to_bool(self.settings.value("useSequentialConditions", False))

        self.lang_combo.setCurrentIndex(lang)
        self.server_combo.setCurrentIndex(server)
        self.channel_combo.setCurrentIndex(channel)
        self.char_combo.setCurrentIndex(char + 1)
        if pid:
            self.pid_edit.setText(str(pid))
        self.sequential_checkbox.setChecked(use_sequential)

    def _login_failed(self, message: str) -> None:
        """Handle a failed background login."""
        from PyQt5.QtWidgets import QMessageBox

        QMessageBox.critical(self, "Login failed", message)