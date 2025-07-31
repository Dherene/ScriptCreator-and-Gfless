"""Dialog to configure server login using gfless_api."""

from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QLabel, QComboBox, QPushButton
)
from gfless_api import (
    select_language,
    select_server,
    select_channel,
    select_character,
    click_start,
)

class ServerConfigDialog(QDialog):
    """Dialog to select language, server, channel and character."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Server Configuration")

        layout = QVBoxLayout(self)
        layout.addWidget(QLabel("Language"))
        self.lang_combo = QComboBox()
        self.lang_combo.addItems(["EN", "DE", "FR"])
        layout.addWidget(self.lang_combo)

        layout.addWidget(QLabel("Server"))
        self.server_combo = QComboBox()
        self.server_combo.addItems(["0", "1", "2", "3"])
        layout.addWidget(self.server_combo)

        layout.addWidget(QLabel("Channel"))
        self.channel_combo = QComboBox()
        self.channel_combo.addItems(["0", "1", "2", "3"])
        layout.addWidget(self.channel_combo)

        layout.addWidget(QLabel("Character"))
        self.char_combo = QComboBox()
        self.char_combo.addItems(["1", "2", "3", "4"])
        layout.addWidget(self.char_combo)

        confirm_button = QPushButton("Confirm")
        confirm_button.clicked.connect(self.apply)
        layout.addWidget(confirm_button)

    def apply(self):
        select_language(self.lang_combo.currentIndex())
        select_server(self.server_combo.currentIndex())
        select_channel(self.channel_combo.currentIndex())
        select_character(self.char_combo.currentIndex())
        click_start()
        self.accept()