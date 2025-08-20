"""Dialog to configure server login using gfless_api."""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QComboBox, QPushButton, QLineEdit
)
from PyQt5.QtCore import QSettings, QThread, pyqtSignal
import gfless_api


class _LoginWorker(QThread):
    """Background worker that performs the login without blocking the UI."""

    success = pyqtSignal()
    error = pyqtSignal(str)

    def __init__(self, lang, server, channel, char, pid, parent=None):
        super().__init__(parent)
        self.lang = lang
        self.server = server
        self.channel = channel
        self.char = char
        self.pid = pid

    def run(self):
        try:
            gfless_api.login(self.lang, self.server, self.channel, self.char, pid=self.pid)
        except Exception as exc:  # capture any exception to notify the UI
            self.error.emit(str(exc))
        else:
            self.success.emit()

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
        self.char_combo.addItems([str(i) for i in range(1, 5)])
        layout.addWidget(self.char_combo)

        layout.addWidget(QLabel("PID (optional)"))
        self.pid_edit = QLineEdit()
        self.pid_edit.setPlaceholderText("auto")
        layout.addWidget(self.pid_edit)

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
        char = self.char_combo.currentIndex()

        gfless_api.save_config(lang, server, channel, char)
        # persist the last used PID for convenience
        self.settings.setValue("pid", pid_text)

        self.confirm_button.setEnabled(False)
        self.thread = _LoginWorker(lang, server, channel, char, pid, self)
        self.thread.success.connect(self.accept)
        self.thread.error.connect(self._login_failed)
        self.thread.finished.connect(lambda: self.confirm_button.setEnabled(True))
        self.thread.start()

    def load_settings(self):
        lang, server, channel, char = gfless_api.load_config()
        pid = self.settings.value("pid", "")

        self.lang_combo.setCurrentIndex(lang)
        self.server_combo.setCurrentIndex(server)
        self.channel_combo.setCurrentIndex(channel)
        self.char_combo.setCurrentIndex(char)
        if pid:
            self.pid_edit.setText(str(pid))

    def _login_failed(self, message: str) -> None:
        """Handle a failed background login."""
        from PyQt5.QtWidgets import QMessageBox

        QMessageBox.critical(self, "Login failed", message)