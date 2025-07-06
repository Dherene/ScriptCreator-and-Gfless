from PyQt5.QtWidgets import QDialog, QVBoxLayout, QPushButton
from editor import Editor  # Assuming your Editor class is in a module named editor
from pathlib import Path
import inspect

class PlayerDialog(QDialog):
    def __init__(self, parent=None):
        super(PlayerDialog, self).__init__(parent)

        # Set up the layout
        layout = QVBoxLayout(self)

        # Create an instance of your Editor class
        self.editor = Editor(main_window=None, parent=self)

        # Get the path to the main script
        main_script_path = Path(__file__).resolve().parent

        # Construct the path to player.py
        player_file_path = main_script_path / "player.py"

        # Load the contents of player.py into the editor
        with open(player_file_path, "r") as file:
            player_contents = file.read()
            self.editor.setText(player_contents)

        # Import the player module dynamically
        import importlib
        player_module = importlib.import_module("player")

        # Get the source code of the player module
        player_source_code = inspect.getsource(player_module)

        # Set the editor text to the source code of the player module
        self.editor.setText(player_source_code)

        # Set the editor as read-only
        self.editor.setReadOnly(True)

        # Add the editor to the layout
        layout.addWidget(self.editor)

        # Add a button to close the dialog
        close_button = QPushButton("Close")
        close_button.clicked.connect(self.accept)
        layout.addWidget(close_button)
