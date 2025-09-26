import sys
import os
import re
import ctypes
import win32gui
import win32con
import threading
import warnings
# Some PyQt5/QScintilla builds emit a deprecation warning regarding
# ``sipPyTypeDict``. The underlying code is part of the compiled
# extension and cannot be changed here, so hide this warning.
warnings.filterwarnings(
    "ignore",
    message=r".*sipPyTypeDict.*",
    category=DeprecationWarning,
)

from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QTabWidget,
    QWidget,
    QVBoxLayout,
    QPushButton,
    QHBoxLayout,
    QFileDialog,
    QDialog,
    QMenu,
    QAction,
    QMessageBox,
    QScrollArea,
    QSystemTrayIcon,
    QGridLayout,
    QLabel,
    QComboBox,
    QLineEdit,
    QInputDialog,
    QCheckBox,
)
from PyQt5.QtGui import (
    QColor,
    QPalette,
    QIcon,
    QStandardItemModel,
    QStandardItem,
)
from PyQt5.QtCore import Qt, QRectF, QLockFile, QSettings, QTimer
from PyQt5.Qsci import QsciScintilla

from license_manager import prompt_for_license

from player import Player, PeriodicCondition
from getports import returnAllPorts
from funcs import randomize_time
from conditioncreator import ConditionModifier
from editor import Editor
import gfless_api
from group_console import GroupConsoleWindow, install_console_routing, use_group_console

install_console_routing()


def value_to_bool(value, default: bool = False) -> bool:
    """Convert persisted setting values to booleans.

    ``QSettings`` stores values as strings by default, and older versions of the
    application saved a mixture of numeric and textual representations.  The
    helper normalises these values while gracefully handling unexpected input
    types.
    """
    if isinstance(value, bool):
        return value
    if value in (None, ""):
        return default
    if isinstance(value, str):
        value = value.strip().lower()
        if value in {"1", "true", "yes", "on"}:
            return True
        if value in {"0", "false", "no", "off"}:
            return False
        return default
    try:
        return bool(int(value))
    except (TypeError, ValueError):
        return bool(value)

class CheckableComboBox(QComboBox):
    """ComboBox that allows selecting multiple items using check boxes."""

    def __init__(self, parent=None, max_checked=None):
        super().__init__(parent)
        self.max_checked = max_checked
        self.setModel(QStandardItemModel(self))
        self.view().pressed.connect(self.handleItemPressed)
        self.setEditable(True)
        self.lineEdit().setReadOnly(True)
        self.lineEdit().setPlaceholderText("Select characters")
        self._changed = False

    def addItems(self, texts):
        for text in texts:
            item = QStandardItem(text)
            item.setFlags(Qt.ItemIsUserCheckable | Qt.ItemIsEnabled)
            item.setData(Qt.Unchecked, Qt.CheckStateRole)
            self.model().appendRow(item)

    def handleItemPressed(self, index):
        item = self.model().itemFromIndex(index)
        if item.checkState() == Qt.Checked:
            item.setCheckState(Qt.Unchecked)
        else:
            if self.max_checked is not None:
                checked = self.checkedIndices()
                if len(checked) >= self.max_checked:
                    if self.max_checked == 1:
                        for i in checked:
                            self.model().item(i).setCheckState(Qt.Unchecked)
                    else:
                        return
            item.setCheckState(Qt.Checked)
        self._changed = True
        self.updateText()

    def hidePopup(self):
        if not self._changed:
            super().hidePopup()
        self._changed = False

    def updateText(self):
        selected = []
        for i in range(self.model().rowCount()):
            item = self.model().item(i)
            if item.checkState() == Qt.Checked:
                selected.append(item.text())
        self.lineEdit().setText(", ".join(selected))

    def checkedIndices(self):
        indices = []
        for i in range(self.model().rowCount()):
            item = self.model().item(i)
            if item.checkState() == Qt.Checked:
                indices.append(i)
        return indices

    def checkedItems(self):
        texts = []
        for i in range(self.model().rowCount()):
            item = self.model().item(i)
            if item.checkState() == Qt.Checked:
                texts.append(item.text())
        return texts

    def selectAll(self):
        for i in range(self.model().rowCount()):
            item = self.model().item(i)
            item.setCheckState(Qt.Checked)
        self.updateText()

    def clear(self):
        row_count = self.model().rowCount()
        if row_count:
            self.model().removeRows(0, row_count)
        self.updateText()

    def setItems(self, texts):
        self.clear()
        self.addItems(texts)

    def removeItems(self, texts):
        to_remove = []
        for i in range(self.model().rowCount()):
            item = self.model().item(i)
            if item.text() in texts:
                to_remove.append(i)
        for index in reversed(to_remove):
            self.model().removeRow(index)
        self.updateText()

class saveFull(QDialog):
    def __init__(self, entries):
        super().__init__()

        self.entries = entries
        self.script_names = []
        self.scripts = []
        self.conditions = []

        for i in range(len(entries)):
            self.script_names.append(entries[i][0][0])
            self.scripts.append(entries[i][0][1])

        for entry in entries:
            for condition in entry[1]:
                if condition not in self.conditions:
                    self.conditions.append(condition)
            for condition in entry[2]:
                if condition not in self.conditions:
                    self.conditions.append(condition)
            for condition in entry[3]:
                if condition not in self.conditions:
                    self.conditions.append(condition)
        

        self.conditions_items = []

        for i in range(len(self.conditions)):
            self.conditions_items.append(self.conditions[i][0])

        self.setWindowIcon(QIcon('src/icon.png'))
        self.setWindowTitle("Save Full Setup")

        self.setup_widgets = []

        self.main_layout = QGridLayout()

        self.delete_last_setup_button = None
        self.add_new_setup_button = None
        self.save_button = None
        
        self.setLayout(self.main_layout)

        for i in range(len(entries)):
            self.addSetup(f"Setup{i+1}", entries[i][0][0], [entries[i][1], entries[i][2], entries[i][3]])

        self.build()

        # Create a scroll area
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)

        # Create a widget to hold the layout
        scroll_content = QWidget(scroll_area)
        scroll_content.setLayout(self.main_layout)

        # Set the widget for the scroll area
        scroll_area.setWidget(scroll_content)

        # Set the layout of the main dialog to a QVBoxLayout
        confirm_button = QPushButton("Confirm")
        confirm_button.clicked.connect(self.saveFullSetup)
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(scroll_area)
        main_layout.addWidget(confirm_button)

        self.setLayout(main_layout)
    
    def addSetup(self, setup_name, script_name, conditions):
        
        remove_setup_button = QPushButton("-")
        remove_setup_button.clicked.connect(self.removeSetup)
        setup_name_edit = QLineEdit(setup_name)
        scripts_combo = QComboBox()
        scripts_combo.addItems(self.script_names)
        scripts_combo.setCurrentText(script_name)

        widgets = []
        widgets.append(remove_setup_button)
        widgets.append(setup_name_edit)
        widgets.append(scripts_combo)

        for i in range(len(conditions)):
            for j in range(len(conditions[i])):
                cond = QComboBox()
                cond.addItems(self.conditions_items)
                cond.setCurrentText(conditions[i][j][0])
                remove_condition_button = QPushButton("-")
                remove_condition_button.clicked.connect(self.removeCondition)
                widgets.append(cond)
                widgets.append(remove_condition_button)
                remove_condition_button.setMaximumWidth(30)
                remove_condition_button.setMinimumWidth(30)

        add_condition_button = QPushButton("+")
        add_condition_button.clicked.connect(self.addCondition)
        widgets.append(add_condition_button)

        remove_setup_button.setMaximumWidth(30)
        remove_setup_button.setMinimumWidth(30)

        self.setup_widgets.append(widgets)

    def addSetupClicked(self):
        self.addSetup(f"Setup{len(self.setup_widgets)+1}", self.script_names[0], [])
        self.build()

    def removeSetup(self):
        if len(self.setup_widgets) > 1:
            sender_button = self.sender()

            for widget_row in self.setup_widgets:
                if sender_button in widget_row:
                    for widget in widget_row:
                        widget.deleteLater()
                    self.setup_widgets.pop(self.setup_widgets.index(widget_row))
                    self.build()
                    break

    def saveFullSetup(self):
        options = QFileDialog.Options()
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder", options=options)

        log_text_final = ""
        errors_amount = 0

        if folder_path:
            for setup in self.setup_widgets:
                log_text, errors = self.create_folder(setup[1].text(), folder_path)
                log_text_final += "\n"+log_text
                errors_amount += errors
                log_text, errors = self.create_folder("script", f"{folder_path}/{setup[1].text()}")
                log_text_final += "\n"+log_text
                errors_amount += errors
                log_text, errors = self.create_folder("conditions", f"{folder_path}/{setup[1].text()}")
                log_text_final += "\n"+log_text
                errors_amount += errors
                log_text, errors = self.create_text_file(f"{setup[1].text()}_script", self.scripts[setup[2].currentIndex()], f"{folder_path}/{setup[1].text()}\script")
                log_text_final += "\n"+log_text
                errors_amount += errors

                for i in range(3, len(setup)):
                    try:
                        cond = self.conditions[setup[i].currentIndex()]
                        text = cond[3]
                        if cond[2]:
                            text += "\n1\n"
                        else:
                            text += "\n0\n"
                        text += cond[1]
                        log_text, errors = +self.create_text_file(cond[0], text, f"{folder_path}\{setup[1].text()}/conditions")
                        log_text_final += "\n"+log_text
                        errors_amount += errors
                    except:
                        pass
            self.create_text_file(f"setup_creation_log", log_text_final, folder_path)
            QMessageBox.information(self, "Success", f"Setups with scripts and conditions created at \n{folder_path}\nwith {errors_amount} errors\nlog file was created at {folder_path}/setup_creation_log.txt")
            self.accept()
        else:
            print("User canceled folder selection.")
    
    def create_folder(self, folder_name, path):
        try:
            folder_path = os.path.join(path, folder_name)

            os.makedirs(folder_path)

            return f"Folder '{folder_name}' created successfully at {path}", 0
        except Exception as e:
            return f"An error occurred: {e}", 1

    def create_text_file(self, name, text, path):
        try:
            file_path = os.path.join(path, f"{name}.txt")

            # Check if the file already exists
            if os.path.exists(file_path):
                with open(file_path, 'w') as file:
                   file.write(text)
                return f"File '{name}.txt' already exists", 1

            with open(file_path, 'w') as file:
                file.write(text)

            return f"File '{name}.txt' created successfully at {path}", 0
        except Exception as e:
            return f"An error occurred: {e}", 1

    def removeCondition(self):
        for widget_row in self.setup_widgets:
            if self.sender() in widget_row:
                index = widget_row.index(self.sender())
                for i in range(2):
                    widget_row[index-1].deleteLater()
                    widget_row.pop(index-1)

        self.build()

    def addCondition(self):
        for widget_row in self.setup_widgets:
            if self.sender() in widget_row:
                cond = QComboBox()
                cond.addItems(self.conditions_items)
                remove_condition_button = QPushButton("-")
                remove_condition_button.clicked.connect(self.removeCondition)
                remove_condition_button.setMaximumWidth(30)
                remove_condition_button.setMinimumWidth(30)

                plus_button = widget_row[-1]

                widget_row.pop(-1)
                widget_row.append(cond)
                widget_row.append(remove_condition_button)
                widget_row.append(plus_button)
        
        self.build()

    def build(self):
        if self.delete_last_setup_button is not None:
            self.add_new_setup_button.deleteLater()

        column_plus_index = 0

        for i in range(len(self.setup_widgets)):
            for j in range(len(self.setup_widgets[i])):
                if j > 2:
                    if j == len(self.setup_widgets[i])-1:
                        self.main_layout.addWidget(self.setup_widgets[i][j], i+1+column_plus_index, 3, 1, 2)
                    elif j%2 == 1:
                        column_plus_index += 1
                        self.main_layout.addWidget(self.setup_widgets[i][j], i+column_plus_index, 3)
                    elif j%2 == 0:
                        self.main_layout.addWidget(self.setup_widgets[i][j], i+column_plus_index, 4)
                else:
                    self.main_layout.addWidget(self.setup_widgets[i][j], i+1+column_plus_index, j)
                #self.setup_widgets[i][j].setVisible(True)

        try:
            self.add_new_setup_button.deleteLater()
        except:
            pass

        self.add_new_setup_button = QPushButton("+")
        self.add_new_setup_button.clicked.connect(self.addSetupClicked)
        
        row_index = 3
        for row in self.setup_widgets:
            row_index += len(row)-2

        self.main_layout.addWidget(self.add_new_setup_button, row_index, 0, 1, 2)

class loadFull(QDialog):
    def __init__(self, players, text_editors, folder_path):
        super().__init__()

        self.players = players
        self.text_editors = text_editors
        self.folder_path = folder_path

        self.setup_widgets = []
        self.character_names = []

        self.main_layout = QGridLayout()

        for player_cl in players:
            if not getattr(player_cl[0], "script_loaded", False):
                self.character_names.append(player_cl[0].name)

        folder_path_split = folder_path.split("/")
        self.setWindowTitle(f"Load Setup {folder_path_split[-1]}")
        self.setWindowIcon(QIcon('src/icon.png'))

        subfolders = [f.name for f in os.scandir(folder_path) if f.is_dir()]
        for subfolder in subfolders:
            setup_name_label = QLabel(subfolder)
            characters_combobox = CheckableComboBox()
            characters_combobox.addItems(self.character_names)
            characters_combobox.setMinimumWidth(200)
            select_all_button = QPushButton("All")
            select_all_button.clicked.connect(characters_combobox.selectAll)
            self.setup_widgets.append([
                setup_name_label,
                characters_combobox,
                select_all_button,
            ])

        setup_name_label = QLabel("Setup name")
        selected_chars_label = QLabel("Selected characters")
        select_all_header_label = QLabel("Select all")
        self.confirm_button = QPushButton("Confirm")
        self.confirm_button.clicked.connect(self.confirmLoadFullScript)

        self.main_layout.addWidget(setup_name_label, 0, 0)
        self.main_layout.addWidget(selected_chars_label, 0, 1)
        self.main_layout.addWidget(select_all_header_label, 0, 2)
        self.setMinimumWidth(400)

        self.setLayout(self.main_layout)

        self.build() 



    def confirmLoadFullScript(self):
         
        try:
            loaded_names = []
            for i in range(len(self.setup_widgets)):
                selected_names = self.setup_widgets[i][1].checkedItems()
                for name in selected_names:
                    index = next(
                        (j for j, p in enumerate(self.players) if p[0].name == name),
                        None,
                    )
                    if index is None:
                        continue
                    loaded_names.append(name)
                    self.players[index][0].recv_packet_conditions = []
                    self.players[index][0].send_packet_conditions = []
                    self.players[index][0].periodical_conditions = []
                    self.players[i][0].periodical_conditions = []
                    self.text_editors[i].setText("""import gfless_api
# Gets current player object
player = self.players[self.tab_widget.currentIndex()][0]


# Gets all The players and remove current player to get alts
alts = [sublist[0] if sublist[0] is not None else None for sublist in self.players]
alts.remove(player)

""")
                    self.players[index][0].script_loaded = True

                    # load scripts
                    script_files = os.listdir(f"{self.folder_path}/{self.setup_widgets[i][0].text()}/script")
                    script_txt_files = [file for file in script_files if file.endswith(".txt")]
                    if len(script_txt_files) > 0:
                        with open(f"{self.folder_path}/{self.setup_widgets[i][0].text()}/script/{script_txt_files[0]}", 'r') as file:
                            self.text_editors[index].setText(file.read())

                    # load conditions
                    conditions_files = os.listdir(f"{self.folder_path}/{self.setup_widgets[i][0].text()}/conditions")
                    conditions_txt_files = [file for file in conditions_files if file.endswith(".txt")]
                    for k in range(len(conditions_txt_files)):
                        cond_path = f"{self.folder_path}/{self.setup_widgets[i][0].text()}/conditions/{conditions_txt_files[k]}"
                        with open(cond_path, 'r') as file:
                            cond_type = file.readline().strip()
                            running = file.readline().strip()
                            script = file.read().strip()

                            running_bool = True if running == '1' else False
                            base_name = os.path.splitext(os.path.basename(cond_path))[0]

                            if cond_type == "recv_packet":
                                self.players[index][0].recv_packet_conditions.append([base_name, script, running_bool])
                            elif cond_type == "send_packet":
                                self.players[index][0].send_packet_conditions.append([base_name, script, running_bool])
                            else:
                                self.players[index][0].periodical_conditions.append(
                                    [base_name, script, running_bool, 1]
                                )

                if selected_names:
                    self.setup_widgets[i][1].removeItems(selected_names)

            # remove used names from all combos
            for name in set(loaded_names):
                for row in self.setup_widgets:
                    row[1].removeItems([name])
                if name in self.character_names:
                    self.character_names.remove(name)
            QMessageBox.information(self, "Load Full Setup Success", f"Full Setup succesfully loaded into script creator.")
            self.accept()
        except Exception as e:
            QMessageBox.warning(self, "Load Full Setup Failed", f"Loading Full setup failed with error: {e}")
    def build(self):
        for row in range(len(self.setup_widgets)):
            self.main_layout.addWidget(self.setup_widgets[row][0], row + 1, 0)
            self.main_layout.addWidget(self.setup_widgets[row][1], row + 1, 1)
            self.main_layout.addWidget(self.setup_widgets[row][2], row + 1, 2)

        self.main_layout.addWidget(self.confirm_button, len(self.setup_widgets) + 1, 0, 1, 3)
        self.main_layout.setColumnStretch(1, 1)

        if self.minimumHeight() - 28 > 0:
            self.setMaximumHeight(self.minimumHeight() - 28)

class LeaderSelectionDialog(QDialog):
    def __init__(self, player_names, current_leaders):
        super().__init__()
        self.setWindowTitle("Select Leaders")
        self.setWindowIcon(QIcon('src/icon.png'))
        self.combo = CheckableComboBox(max_checked=4)
        self.combo.addItems(player_names)
        for i in range(self.combo.model().rowCount()):
            item = self.combo.model().item(i)
            if item.text() in current_leaders:
                item.setCheckState(Qt.Checked)
        layout = QVBoxLayout()
        layout.addWidget(QLabel("Leaders"))
        layout.addWidget(self.combo)
        button_layout = QHBoxLayout()
        ok_button = QPushButton("OK")
        cancel_button = QPushButton("Cancel")
        ok_button.clicked.connect(self.accept)
        cancel_button.clicked.connect(self.reject)
        button_layout.addWidget(ok_button)
        button_layout.addWidget(cancel_button)
        layout.addLayout(button_layout)
        self.setLayout(layout)

    def selected_leaders(self):
        return self.combo.checkedItems()

class GroupScriptDialog(QDialog):
    @staticmethod
    def _natural_key(text: str):
        parts = re.split(r"(\d+)", text)
        return [int(part) if part.isdigit() else part.lower() for part in parts]

    def __init__(
        self,
        players,
        text_editors,
        leader_path,
        member_path,
        group_id,
        leaders,
        max_total_members=9,
        *,
        mode="setup",
        existing_group=None,
        available_member_names=None,
        title=None,
    ):
        super().__init__()

        self.players = players
        self.text_editors = text_editors
        self.leader_path = leader_path
        self.member_path = member_path
        self.group_id = group_id
        # Predefined leaders to exclude from auto-selection and member listing
        self.leaders = leaders
        self.loaded_group_info = None
        self.mode = mode if mode in {"setup", "extend"} else "setup"
        self.existing_group = existing_group or {}
        self.available_member_names = available_member_names
        if title:
            self.setWindowTitle(title)
        try:
            total_members = int(max_total_members)
        except (TypeError, ValueError):
            total_members = 9
        self.max_group_members = max(1, total_members)
        if self.mode == "extend":
            existing_count = 0
            existing_members = self.existing_group.get("member_names")
            if isinstance(existing_members, (list, tuple, set)):
                existing_count = len([m for m in existing_members if isinstance(m, str)])
            self.member_limit = max(0, self.max_group_members - (existing_count + 1))
        else:
            self.member_limit = max(0, self.max_group_members - 1)

        if not title:
            self.setWindowTitle("Group Script Setup")
        self.setWindowIcon(QIcon('src/icon.png'))
        self.settings = QSettings('PBapi', 'Script Creator')

        leader_names = self.leaders
        if isinstance(self.available_member_names, (list, tuple)):
            member_names = list(self.available_member_names)
        else:
            member_names = [
                p[0].name
                for p in players
                if p[0].name not in leader_names and not p[0].script_loaded
            ]

        self.leader_combo = CheckableComboBox(max_checked=1)
        self.leader_combo.addItems(leader_names)
        self.leader_combo.setMinimumWidth(200)

        members_max_checked = self.member_limit if self.member_limit > 0 else 0
        self.members_combo = CheckableComboBox(max_checked=members_max_checked)
        self.members_combo.addItems(member_names)
        self.members_combo.setMinimumWidth(200)

        layout = QGridLayout()
        layout.addWidget(QLabel("Leader"), 0, 0)
        layout.addWidget(self.leader_combo, 0, 1)
        if self.member_limit == 1:
            members_label_text = "Members (max 1)"
        else:
            members_label_text = f"Members (max {self.member_limit})"
        self.members_label = QLabel(members_label_text)
        layout.addWidget(self.members_label, 1, 0)
        layout.addWidget(self.members_combo, 1, 1)

        info_text = (
            f"Total allowed (including leader): {self.max_group_members}"
        )
        info_label = QLabel(info_text)
        layout.addWidget(info_label, 2, 0, 1, 2)

        self.manual_login_checkbox = QCheckBox("Select manual login?")
        layout.addWidget(self.manual_login_checkbox, 3, 0, 1, 2)

        self.manual_login_widget = QWidget()
        manual_layout = QGridLayout(self.manual_login_widget)
        manual_layout.setContentsMargins(0, 0, 0, 0)

        manual_layout.addWidget(QLabel("Language"), 0, 0)
        self.manual_lang_combo = QComboBox()
        self.manual_lang_combo.addItems([
            "International/English",
            "German",
            "French",
            "Italian",
            "Polish",
            "Spanish",
        ])
        manual_layout.addWidget(self.manual_lang_combo, 0, 1)

        manual_layout.addWidget(QLabel("Server"), 1, 0)
        self.manual_server_combo = QComboBox()
        self.manual_server_combo.addItems([str(i) for i in range(1, 5)])
        manual_layout.addWidget(self.manual_server_combo, 1, 1)

        manual_layout.addWidget(QLabel("Channel"), 2, 0)
        self.manual_channel_combo = QComboBox()
        self.manual_channel_combo.addItems([str(i) for i in range(1, 8)])
        manual_layout.addWidget(self.manual_channel_combo, 2, 1)

        manual_layout.addWidget(QLabel("Character"), 3, 0)
        self.manual_character_combo = QComboBox()
        self.manual_character_combo.addItem("Stay at character selection")
        self.manual_character_combo.addItems([str(i) for i in range(1, 5)])
        manual_layout.addWidget(self.manual_character_combo, 3, 1)

        self.manual_sequential_checkbox = QCheckBox("Use sequential conditions")
        manual_layout.addWidget(self.manual_sequential_checkbox, 4, 0, 1, 2)

        self.manual_condition_logging_checkbox = QCheckBox(
            "View text of enabled and disabled conditions"
        )
        manual_layout.addWidget(self.manual_condition_logging_checkbox, 5, 0, 1, 2)
        manual_layout.setColumnStretch(1, 1)

        layout.addWidget(self.manual_login_widget, 4, 0, 1, 2)

        load_button = QPushButton("Load")
        load_button.clicked.connect(self.load_setup)
        all_button = QPushButton("All")
        all_button.clicked.connect(self.select_all_members)
        layout.addWidget(load_button, 5, 0)
        layout.addWidget(all_button, 5, 1)

        self.manual_login_checkbox.toggled.connect(self._on_manual_login_toggled)
        self._load_manual_login_settings()
        if self.mode == "extend" and self.leader_combo.model().rowCount() == 1:
            leader_item = self.leader_combo.model().item(0)
            if leader_item:
                leader_item.setCheckState(Qt.Checked)
                self.leader_combo.updateText()
        self._on_manual_login_toggled(self.manual_login_checkbox.isChecked())

        self.setLayout(layout)

    def select_all_members(self):
        selected_leaders = set(self.leader_combo.checkedItems())
        leaders = set(self.leaders) | selected_leaders
        if self.mode == "extend" and isinstance(self.available_member_names, (list, tuple)):
            eligible = [name for name in self.available_member_names if name not in leaders]
        else:
            eligible = [
                p[0].name
                for p in self.players
                if not p[0].script_loaded and p[0].name not in leaders
            ]
        # Respect maximum allowed members
        max_allowed = self.members_combo.max_checked
        if max_allowed is not None:
            eligible = eligible[: max_allowed]
        for i in range(self.members_combo.model().rowCount()):
            item = self.members_combo.model().item(i)
            if item.text() in eligible:
                item.setCheckState(Qt.Checked)
            else:
                item.setCheckState(Qt.Unchecked)
        self.members_combo.updateText()

    def _set_member_limit(self, new_limit: int):
        limit = max(0, int(new_limit))
        self.member_limit = limit
        if hasattr(self, "members_combo") and self.members_combo is not None:
            self.members_combo.max_checked = limit if limit > 0 else 0
        if hasattr(self, "members_label") and self.members_label is not None:
            if limit == 1:
                text = "Members (max 1)"
            else:
                text = f"Members (max {limit})"
            self.members_label.setText(text)

    def load_setup(self):
        leader_names = self.leader_combo.checkedItems()
        member_names = self.members_combo.checkedItems()

        manual_login_enabled, manual_args = self._prepare_manual_settings()

        if len(leader_names) != 1:
            QMessageBox.warning(self, "Invalid Selection", "Please select exactly one leader.")
            return

        leader_name = leader_names[0]

        if leader_name in member_names:
            QMessageBox.warning(self, "Invalid Selection", "Leader cannot be selected as member.")
            return

        if self.mode == "extend":
            if self.member_limit == 0 and member_names:
                QMessageBox.warning(
                    self,
                    "Invalid Selection",
                    "This group is already at the maximum number of members.",
                )
                return
            if self.member_limit is not None and len(member_names) > self.member_limit:
                QMessageBox.warning(
                    self,
                    "Invalid Selection",
                    f"You can only add up to {self.member_limit} more members to this group.",
                )
                return
            if not member_names:
                QMessageBox.information(
                    self,
                    self.windowTitle(),
                    "Select at least one member to add to the group.",
                )
                return
        else:
            if len(member_names) + 1 > self.max_group_members:
                max_members_allowed = max(0, self.max_group_members - 1)
                member_label = (
                    "1 member" if max_members_allowed == 1 else f"{max_members_allowed} members"
                )
                QMessageBox.warning(
                    self,
                    "Invalid Selection",
                    (
                        f"Please select up to {member_label} "
                        f"(total {self.max_group_members} including leader)."
                    ),
                )
                return

        roles = {leader_name: (self.leader_path, "leader")}
        for m in member_names:
            roles[m] = (self.member_path, "member")

        leader_obj = None
        member_objs = []

        existing_member_names = []
        existing_member_objs = []
        if self.mode == "extend":
            existing_member_names = [
                name
                for name in self.existing_group.get("member_names", [])
                if isinstance(name, str) and name != leader_name
            ]
            existing_lookup = set(existing_member_names)
            for player_obj, _ in self.players:
                if player_obj.name in existing_lookup:
                    existing_member_objs.append(player_obj)

        for idx, (player_obj, _) in enumerate(self.players):
            if player_obj.name not in roles:
                continue

            setup_path, role = roles[player_obj.name]

            if role == "leader" and self.mode == "extend":
                leader_obj = player_obj
                continue

            player_obj.reset_attrs()

            script_dir = os.path.join(setup_path, "script")
            cond_dir = os.path.join(setup_path, "conditions")

            if not os.path.isdir(script_dir) or not os.path.isdir(cond_dir):
                QMessageBox.warning(self, "Load Failed", f"Invalid setup folder: {setup_path}")
                return

            script_files = sorted(
                [f for f in os.listdir(script_dir) if f.endswith('.txt')],
                key=self._natural_key,
            )
            if not script_files:
                QMessageBox.warning(self, "Load Failed", f"No scripts found in {script_dir}")
                return

            if role == "leader":
                chosen = next((s for s in script_files if "setup1" in s.lower() or "leader" in s.lower()), script_files[0])
            else:
                chosen = next((s for s in script_files if "follow" in s.lower() or "member" in s.lower()), script_files[0])

            with open(os.path.join(script_dir, chosen), "r") as file:
                script_text = file.read()
            if manual_login_enabled and manual_args is not None:
                script_text = self._apply_manual_login_overrides(script_text, manual_args)

            cond_files = sorted(
                [f for f in os.listdir(cond_dir) if f.endswith('.txt')],
                key=self._natural_key,
            )
            cond_data = []
            for cf in cond_files:
                with open(os.path.join(cond_dir, cf), "r") as cfile:
                    c_type = cfile.readline().strip()
                    running = cfile.readline().strip()
                    script = cfile.read().strip()
                if manual_login_enabled and manual_args is not None:
                    script = self._apply_manual_login_overrides(script, manual_args)
                cond_data.append((os.path.splitext(cf)[0], c_type, script, running))

            self.text_editors[idx].setText(script_text)
            if 0 <= idx < len(self.players):
                self.players[idx][1] = None
            player_obj.recv_packet_conditions = []
            player_obj.send_packet_conditions = []
            player_obj.periodical_conditions = []
            if hasattr(player_obj, "_compiled_recv_conditions"):
                player_obj._compiled_recv_conditions.clear()
            if hasattr(player_obj, "_compiled_send_conditions"):
                player_obj._compiled_send_conditions.clear()
            if hasattr(player_obj, "_condition_state"):
                player_obj._condition_state = {
                    "recv_packet": set(),
                    "send_packet": set(),
                    "periodical": set(),
                }
            if hasattr(player_obj, "_condition_activity_by_name"):
                player_obj._condition_activity_by_name.clear()

            for name, ctype, cscript, running in cond_data:
                running_bool = True if running == "1" else False
                if ctype == "recv_packet":
                    player_obj.recv_packet_conditions.append([name, cscript, running_bool])
                elif ctype == "send_packet":
                    player_obj.send_packet_conditions.append([name, cscript, running_bool])
                else:
                    player_obj.periodical_conditions.append(PeriodicCondition(name, cscript, running_bool, 1))

            if role == "leader":
                player_obj.attr19 = 0
                player_obj.attr20 = player_obj.name
                player_obj.leadername = player_obj.name
                player_obj.leaderID = player_obj.id
                leader_obj = player_obj
            else:
                player_obj.attr19 = self.group_id
                player_obj.attr20 = leader_name
                player_obj.leadername = leader_name
                member_objs.append(player_obj)
            player_obj.script_loaded = True
            player_obj.attr13 = 0

        if leader_obj is None:
            QMessageBox.warning(self, "Load Failed", "Unable to locate the selected leader.")
            return

        if self.mode == "extend":
            combined_member_names = []
            for name in existing_member_names + member_names:
                if name not in combined_member_names:
                    combined_member_names.append(name)
            seen_ids = {id(obj) for obj in member_objs}
            preserved_existing = []
            for obj in existing_member_objs:
                if id(obj) not in seen_ids:
                    preserved_existing.append(obj)
            member_party_objs = preserved_existing + member_objs
        else:
            combined_member_names = list(member_names)
            member_party_objs = list(member_objs)

        leader_obj.attr51 = combined_member_names
        leader_id = leader_obj.id
        member_ids = [m.id for m in member_party_objs]
        party_names = [leader_obj.name] + [m.name for m in member_party_objs]
        party_ids = [leader_id] + member_ids

        for participant in [leader_obj] + member_party_objs:
            participant.partyname = party_names
            participant.partyID = party_ids
        leader_obj.leaderID = leader_id
        for m in member_party_objs:
            m.leaderID = leader_id

        participants = [leader_obj] + member_objs
        if self.mode == "extend":
            participants = list(member_objs)

        for p in participants:
            if p is not None:
                threading.Thread(target=p.start_condition_loop, daemon=True).start()

        self.loaded_group_info = {
            "leader_name": leader_obj.name,
            "member_names": combined_member_names,
            "group_id": self.group_id,
            "leader_path": self.leader_path,
            "member_path": self.member_path,
        }
        if self.mode == "extend":
            self.loaded_group_info["new_member_names"] = list(member_names)

        success_message = "Setup successfully loaded."
        if self.mode == "extend":
            success_message = "Selected members have been added to the current group."

        QMessageBox.information(self, self.windowTitle(), success_message)
        self.accept()

    def _prepare_manual_settings(self):
        manual_login_enabled = self.manual_login_checkbox.isChecked()
        manual_args = self._get_manual_login_arguments() if manual_login_enabled else None
        manual_use_sequential = self.manual_sequential_checkbox.isChecked()
        manual_show_condition_logs = self.manual_condition_logging_checkbox.isChecked()

        self._save_manual_login_settings()

        parent = self.parent()
        if parent and hasattr(parent, "set_condition_logging_enabled"):
            try:
                parent.set_condition_logging_enabled(manual_show_condition_logs)
            except Exception:
                pass

        if manual_login_enabled:
            self.settings.setValue("useSequentialConditions", int(manual_use_sequential))
            if parent and hasattr(parent, "set_sequential_conditions_enabled"):
                try:
                    parent.set_sequential_conditions_enabled(manual_use_sequential)
                except Exception:
                    pass

        return manual_login_enabled, manual_args

    def _on_manual_login_toggled(self, checked: bool) -> None:
        self.manual_login_widget.setVisible(checked)

    def _get_manual_login_arguments(self):
        lang = self.manual_lang_combo.currentIndex()
        server = self.manual_server_combo.currentIndex()
        channel = self.manual_channel_combo.currentIndex()
        character = self.manual_character_combo.currentIndex() - 1
        return lang, server, channel, character

    def _load_manual_login_settings(self) -> None:
        try:
            default_lang, default_server, default_channel, default_character = gfless_api.load_config()
        except Exception:
            default_lang, default_server, default_channel, default_character = 0, 0, 0, -1

        self.manual_lang_combo.setCurrentIndex(
            self._read_index("groupManualLoginLang", default_lang, self.manual_lang_combo.count())
        )
        self.manual_server_combo.setCurrentIndex(
            self._read_index("groupManualLoginServer", default_server, self.manual_server_combo.count())
        )
        self.manual_channel_combo.setCurrentIndex(
            self._read_index("groupManualLoginChannel", default_channel, self.manual_channel_combo.count())
        )
        default_character_index = max(0, min(default_character + 1, self.manual_character_combo.count() - 1))
        self.manual_character_combo.setCurrentIndex(
            self._read_index(
                "groupManualLoginCharacterIndex",
                default_character_index,
                self.manual_character_combo.count(),
            )
        )

        sequential_default = self._value_to_bool(
            self.settings.value("useSequentialConditions"), True
        )
        sequential_enabled = self._value_to_bool(
            self.settings.value("groupManualLoginSequential"), sequential_default
        )
        self.manual_sequential_checkbox.setChecked(sequential_enabled)

        logging_default = self._value_to_bool(
            self.settings.value("conditionLoggingEnabled"), True
        )
        logging_enabled = self._value_to_bool(
            self.settings.value("groupManualConditionLogging"), logging_default
        )
        self.manual_condition_logging_checkbox.setChecked(logging_enabled)

        manual_enabled = self._value_to_bool(
            self.settings.value("groupManualLoginEnabled"), False
        )
        self.manual_login_checkbox.setChecked(manual_enabled)

    def _save_manual_login_settings(self) -> None:
        self.settings.setValue("groupManualLoginEnabled", int(self.manual_login_checkbox.isChecked()))
        self.settings.setValue("groupManualLoginLang", self.manual_lang_combo.currentIndex())
        self.settings.setValue("groupManualLoginServer", self.manual_server_combo.currentIndex())
        self.settings.setValue("groupManualLoginChannel", self.manual_channel_combo.currentIndex())
        self.settings.setValue(
            "groupManualLoginCharacterIndex", self.manual_character_combo.currentIndex()
        )
        self.settings.setValue(
            "groupManualLoginSequential", int(self.manual_sequential_checkbox.isChecked())
        )
        self.settings.setValue(
            "groupManualConditionLogging",
            int(self.manual_condition_logging_checkbox.isChecked()),
        )
        self.settings.setValue(
            "conditionLoggingEnabled",
            int(self.manual_condition_logging_checkbox.isChecked()),
        )

    def _read_index(self, key, default, count):
        value = self.settings.value(key, default)
        try:
            idx = int(value)
        except (TypeError, ValueError):
            try:
                idx = int(default)
            except (TypeError, ValueError):
                idx = 0
        if count <= 0:
            return 0
        if idx < 0:
            return 0
        if idx >= count:
            return count - 1
        return idx

    @staticmethod
    def _value_to_bool(value, default=False):
        return value_to_bool(value, default)

    def _apply_manual_login_overrides(self, text: str, manual_args) -> str:
        if not text or "gfless_api" not in text:
            return text

        lang, server, channel, character = manual_args
        replacements = [
            f"int({lang})",
            f"int({server})",
            f"int({channel})",
            f"int({character})",
        ]
        updated = self._replace_call_args(text, "save_config", replacements)
        updated = self._replace_call_args(updated, "login", replacements)
        return updated

    def _replace_call_args(self, text: str, func_name: str, new_values) -> str:
        target = f"gfless_api.{func_name}"
        idx = 0
        result = []
        while idx < len(text):
            start = text.find(target, idx)
            if start == -1:
                result.append(text[idx:])
                break
            result.append(text[idx:start])
            paren_index = text.find("(", start + len(target))
            if paren_index == -1:
                result.append(text[start:])
                break
            args_str, end_idx = self._extract_call_arguments(text, paren_index)
            if args_str is None:
                result.append(text[start:])
                break
            result.append(text[start:paren_index])
            result.append("(")
            result.append(self._replace_arguments_in_string(args_str, new_values))
            result.append(")")
            idx = end_idx + 1
        return "".join(result)

    def _extract_call_arguments(self, text: str, open_paren_index: int):
        depth = 1
        idx = open_paren_index + 1
        in_string = False
        string_char = ""
        escape = False
        while idx < len(text):
            char = text[idx]
            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == string_char:
                    in_string = False
            else:
                if char in {'"', "'"}:
                    in_string = True
                    string_char = char
                elif char in "([{":
                    depth += 1
                elif char in ")]}":
                    depth -= 1
                    if depth == 0:
                        return text[open_paren_index + 1 : idx], idx
            idx += 1
        return None, None

    def _split_arguments_with_spans(self, args_str: str):
        segments = []
        depth = 0
        in_string = False
        string_char = ""
        escape = False
        last_index = 0
        for idx, char in enumerate(args_str):
            if in_string:
                if escape:
                    escape = False
                elif char == "\\":
                    escape = True
                elif char == string_char:
                    in_string = False
                continue
            if char in {'"', "'"}:
                in_string = True
                string_char = char
            elif char in "([{":
                depth += 1
            elif char in ")]}" and depth > 0:
                depth -= 1
            elif char == "," and depth == 0:
                segments.append((last_index, idx))
                last_index = idx + 1
        segments.append((last_index, len(args_str)))
        return [
            (args_str[start:end], start, end)
            for start, end in segments
            if start <= end
        ]

    def _replace_arguments_in_string(self, args_str: str, new_values) -> str:
        segments = self._split_arguments_with_spans(args_str)
        if not segments:
            return args_str
        result = []
        current_index = 0
        for idx, (segment_text, start, end) in enumerate(segments):
            if start > current_index:
                result.append(args_str[current_index:start])
            if idx < len(new_values):
                replacement = self._compose_segment(segment_text, new_values[idx])
            else:
                replacement = segment_text
            result.append(replacement)
            current_index = end
        if current_index < len(args_str):
            result.append(args_str[current_index:])
        return "".join(result)

    def _compose_segment(self, original_segment: str, new_value: str) -> str:
        if not original_segment:
            return new_value
        leading_len = len(original_segment) - len(original_segment.lstrip())
        trailing_len = len(original_segment) - len(original_segment.rstrip())
        if trailing_len:
            core = original_segment[leading_len:-trailing_len]
        else:
            core = original_segment[leading_len:]
        if not core:
            core_replacement = new_value
        elif "=" in core and not core.strip().startswith("**"):
            name, _, _ = core.partition("=")
            core_replacement = f"{name.strip()}={new_value}"
        else:
            core_replacement = new_value
        prefix = original_segment[:leading_len]
        suffix = original_segment[-trailing_len:] if trailing_len else ""
        return f"{prefix}{core_replacement}{suffix}"

    def get_loaded_group(self):
        return self.loaded_group_info


class AddGroupMembersDialog(GroupScriptDialog):
    """Extended dialog used to add new members to an existing group."""

    def __init__(
        self,
        players,
        text_editors,
        default_leader_path,
        default_member_path,
        group_configs,
        leader_names,
        max_total_members,
    ):
        self.group_configs = group_configs or {}
        self.default_leader_path = default_leader_path
        self.default_member_path = default_member_path
        leaders_list = list(leader_names or [])
        initial_group_id = 0
        for config in self.group_configs.values():
            potential_id = config.get("group_id")
            if isinstance(potential_id, int):
                initial_group_id = potential_id
                break
        super().__init__(
            players,
            text_editors,
            default_leader_path,
            default_member_path,
            initial_group_id,
            leaders_list,
            max_total_members,
            mode="extend",
            existing_group={},
            available_member_names=[],
            title="Add players to current group",
        )
        self.leader_combo.model().itemChanged.connect(self._on_leader_selection_changed)
        self._on_leader_selection_changed(None)

    def _on_leader_selection_changed(self, _item):
        selected = self.leader_combo.checkedItems()
        leader_name = selected[0] if selected else None
        self._populate_members_for_leader(leader_name)

    def _populate_members_for_leader(self, leader_name):
        available_names = []
        member_limit = self.max_group_members - 1
        if leader_name and leader_name in self.group_configs:
            config = self.group_configs[leader_name]
            available_names = list(config.get("available_member_names", []))
            existing_names = config.get("existing_member_names", [])
            existing_count = len(existing_names)
            member_limit = self.max_group_members - (existing_count + 1)
            self.available_member_names = available_names
        else:
            self.available_member_names = []
            member_limit = 0
        self.members_combo.setItems(available_names)
        self._set_member_limit(member_limit)

    def load_setup(self):
        leader_names = self.leader_combo.checkedItems()
        if len(leader_names) != 1:
            QMessageBox.warning(self, "Invalid Selection", "Please select exactly one leader.")
            return

        leader_name = leader_names[0]
        config = self.group_configs.get(leader_name)
        if not config:
            QMessageBox.information(
                self,
                self.windowTitle(),
                "The selected leader has not created any group yet.",
            )
            return

        self.group_id = config.get("group_id", self.group_id)
        self.leader_path = config.get("leader_path", self.default_leader_path)
        self.member_path = config.get("member_path", self.default_member_path)
        existing_names = list(config.get("existing_member_names", []))
        self.existing_group = {
            "leader_name": leader_name,
            "member_names": existing_names,
        }
        available_member_names = list(config.get("available_member_names", []))
        self.available_member_names = available_member_names
        member_limit = self.max_group_members - (len(existing_names) + 1)
        if member_limit <= 0:
            QMessageBox.information(
                self,
                self.windowTitle(),
                "This group already has the maximum number of members.",
            )
            return
        if not available_member_names:
            QMessageBox.information(
                self,
                self.windowTitle(),
                "There are no additional connected characters that can be added to this group.",
            )
            return
        self._set_member_limit(member_limit)

        super().load_setup()

class MyWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings('PBapi', 'Script Creator')
        condition_logging_value = self.settings.value("conditionLoggingEnabled")
        self._condition_logging_enabled = value_to_bool(
            condition_logging_value, True
        )
        windowScreenGeometry = self.settings.value("windowScreenGeometry")
        self.colorTheme = self.settings.value("colorTheme")
        # Default to showing the console when no previous preference exists
        self.console = int(self.settings.value("console", 1))
        self.group_leader_setup_path = self.settings.value("groupLeaderSetupPath")
        self.group_member_setup_path = self.settings.value("groupMemberSetupPath")
        max_members_value = self.settings.value("groupScriptMaxMembers", 9)
        try:
            self.group_script_max_members = int(max_members_value)
        except (TypeError, ValueError):
            self.group_script_max_members = 9
        if self.group_script_max_members < 1:
            self.group_script_max_members = 1
        self.group_script_group_counter = 0
        self.group_leaders = []

        if windowScreenGeometry:
            self.restoreGeometry( windowScreenGeometry )
        else:
            self.left = 100
            self.top = 100
            self.width = 800
            self.height = 600
            self.setGeometry(self.left, self.top, self.width, self.height)

        if self.colorTheme == 1:
            setLightTheme()
        else:
            setDarkTheme()

        if self.console == 1:
            self.show_console()
        else:
            self.hide_console()

        self.open_tabs_names = []
        self.players = []
        self.start_stop_buttons = []
        self.text_editors = []
        self.console_groups = {}
        self.leader_to_console = {}
        self._refreshing = False

        self.setWindowTitle("Script Creator by Stradiveri")
        self.setWindowIcon(QIcon('src/icon.png'))

        # Create the main widget and set it as the central widget
        main_widget = QWidget(self)
        self.setCentralWidget(main_widget)

        # Create a layout for the main widget
        layout = QVBoxLayout(main_widget)

        # Create the tab widget
        self.tab_widget = QTabWidget(self)
        layout.addWidget(self.tab_widget)

        self.no_client_found_label = QLabel("No Phoenix Bot Clients Found")
        self.no_client_found_label.setAlignment(Qt.AlignCenter)  # Center the label
        font = self.no_client_found_label.font()
        font.setPointSize(16)  # Set the font size to 16
        self.no_client_found_label.setFont(font)
        layout.addWidget(self.no_client_found_label)
        self.no_client_found_label.setVisible(False)

        self.tab_widget.setVisible(False)

        # Create a button to add new tabs
        refresh_button = QPushButton("Refresh", self)
        refresh_button.clicked.connect(self.refresh)
        layout.addWidget(refresh_button)

        # Periodically synchronize tab names with the underlying player objects.
        # Characters can be renamed by scripts (e.g. when creating a new member)
        # while the client session remains active.  The timer keeps the UI in
        # sync without requiring a manual refresh, and avoids reopening tabs for
        # characters that already have scripts/conditions loaded.
        self.name_sync_timer = QTimer(self)
        self.name_sync_timer.setInterval(1000)
        self.name_sync_timer.timeout.connect(self.sync_player_names)
        self.name_sync_timer.start()

        # Create system tray icon and menu
        self.tray_icon = QSystemTrayIcon(QIcon('src/icon.png'), self)
        self.tray_icon.setToolTip("Script Creator")
        self.tray_icon.setObjectName("Script Creator")
        self.tray_menu = QMenu(self)
        exit_action = self.tray_menu.addAction('Exit')
        exit_action.triggered.connect(self.exit_application)

        self.tray_icon.setContextMenu(self.tray_menu)
        self.tray_icon.activated.connect(self.onTrayIconActivated)

        menubar = self.menuBar()

        # Create File menu
        fileMenu = menubar.addMenu('Full Script')

        self.loadAction = QAction('Load', self)
        self.loadAction.triggered.connect(self.load_full_script)
        fileMenu.addAction(self.loadAction)

        self.saveAction = QAction('Save', self)
        self.saveAction.triggered.connect(self.save_full_script)
        fileMenu.addAction(self.saveAction)

        # Create Color Theme menu
        colorThemeMenu = menubar.addMenu('Color Theme')

        lightThemeAction = QAction('Light Theme', self)
        lightThemeAction.triggered.connect(self.setLightTheme)
        colorThemeMenu.addAction(lightThemeAction)

        darkThemeAction = QAction('Dark Theme', self)
        darkThemeAction.triggered.connect(self.setDarkTheme)
        colorThemeMenu.addAction(darkThemeAction)

        groupMenu = menubar.addMenu('Group Script')
        markLeadersAction = QAction('Mark Leaders', self)
        markLeadersAction.triggered.connect(self.mark_group_leaders)
        groupMenu.addAction(markLeadersAction)
        loadGroupAction = QAction('Load Setup', self)
        loadGroupAction.triggered.connect(self.load_group_script_setup)
        groupMenu.addAction(loadGroupAction)
        addGroupMembersAction = QAction('Add players to current group', self)
        addGroupMembersAction.triggered.connect(self.add_players_to_current_group)
        groupMenu.addAction(addGroupMembersAction)
        maxMembersAction = QAction('Max Members', self)
        maxMembersAction.triggered.connect(self.set_group_script_max_members)
        groupMenu.addAction(maxMembersAction)
        groupPathsAction = QAction('Set Setup Paths', self)
        groupPathsAction.triggered.connect(self.set_group_script_paths)
        groupMenu.addAction(groupPathsAction)

        consoleMenu = menubar.addMenu("Console")

        showConsoleAction = QAction('Show Console', self)
        showConsoleAction.triggered.connect(self.show_console)
        consoleMenu.addAction(showConsoleAction)

        hideConsoleAction = QAction('Hide Console', self)
        hideConsoleAction.triggered.connect(self.hide_console)
        consoleMenu.addAction(hideConsoleAction)

        clearConsoleAction = QAction("Clear Console", self)
        clearConsoleAction.triggered.connect(self.clear_console)
        consoleMenu.addAction(clearConsoleAction)

        serverMenu = menubar.addMenu('Server Config')
        serverAction = QAction('Select Server', self)
        serverAction.triggered.connect(self.open_server_config)
        serverMenu.addAction(serverAction)

        # initialize tabs
        self.refresh()
        self.tray_icon.show()

    def show_console(self):
        win32gui.ShowWindow(fg_window, win32con.SW_SHOW)
        self.settings.setValue("console", 1)
    
    def hide_console(self):
        win32gui.ShowWindow(fg_window , win32con.SW_HIDE)
        self.settings.setValue("console", 0)

    def clear_console(self):
        os.system('cls')

    def setDarkTheme(self):
        setDarkTheme()
        self.settings.setValue("colorTheme", 0)

    def setLightTheme(self):
        setLightTheme()
        self.settings.setValue("colorTheme", 1)

    def open_server_config(self):
        from server_config import ServerConfigDialog
        dialog = ServerConfigDialog(parent=self)
        dialog.exec_()

    def exit_application(self, event):
        self.settings.setValue("windowScreenGeometry", self.saveGeometry())
        QApplication.quit()

    def minimizeToTray(self):
        self.hide()
        self.tray_icon.show()

    def onTrayIconActivated(self, reason):
        if reason == QSystemTrayIcon.Trigger:
            self.showNormal()


    def closeEvent(self, event):
        event.ignore()
        self.minimizeToTray()

    def save_full_script(self):
        scripts_and_conds = []
        for i in range(len(self.players)):
            player = self.players[i][0]
            script = self.text_editors[i].text()
            recv_packet_conds = []
            send_packet_conds = []
            periodic_conds = []
            for condition in player.recv_packet_conditions:
                recv_packet_conds.append([condition[0], condition[1], condition[2], "recv_packet"])
            for condition in player.send_packet_conditions:
                send_packet_conds.append([condition[0], condition[1], condition[2], "send_packet"])
            for condition in player.periodical_conditions:
                periodic_conds.append([condition.name, condition.code, condition.active, "periodical"])

            scripts_and_conds.append([[player.name, script], recv_packet_conds, send_packet_conds, periodic_conds])

        unique_scripts_and_conds = []
        for entry in scripts_and_conds:
            if entry not in unique_scripts_and_conds and entry != ["", [], [], []]:
                unique_scripts_and_conds.append(entry)

        save_full = saveFull(unique_scripts_and_conds)
        save_full.exec_()

    def load_full_script(self):
        options = QFileDialog.Options()
        folder_path = QFileDialog.getExistingDirectory(self, "Select Folder", options=options)
        if folder_path:
            if all(p[0].script_loaded for p in self.players):
                QMessageBox.information(self, "Load Full Setup", "All characters already have a script loaded.")
                return
            load_full = loadFull(self.players, self.text_editors, folder_path)
            load_full.exec_()

    def player_disconnected(self, player):
        """Remove player tab and clear scripts when connection is lost."""
        should_refresh = not getattr(self, "_refreshing", False)
        try:
            index = next(i for i, p in enumerate(self.players) if p[0] == player)
        except StopIteration:
            return

        self._detach_player_console(player)

        player.recv_packet_conditions = []
        player.send_packet_conditions = []
        player.periodical_conditions = []
        player.script_loaded = False
        player.is_connected = False
        player.is_in_login_state = False
        player.stop_script = True

        try:
            if self.players[index][1]:
                self.players[index][1].kill()
        except Exception:
            pass

        self.tab_widget.removeTab(index)
        self.open_tabs_names.pop(index)
        self.players.pop(index)
        self.text_editors.pop(index)
        self.start_stop_buttons.pop(index)

        # Ensure remaining players have up-to-date party information
        if should_refresh:
            self.refresh()

    def mark_group_leaders(self):
        names = [p[0].name for p in self.players]
        dlg = LeaderSelectionDialog(names, self.group_leaders)
        if dlg.exec_():
            self.group_leaders = dlg.selected_leaders()

    def load_group_script_setup(self):
        self.group_leaders = [name for name in self.group_leaders if any(p[0].name == name for p in self.players)]
        if not self.group_leaders:
            QMessageBox.information(self, "Group Script Setup", "Please mark leaders first.")
            return

        if all(p[0].script_loaded for p in self.players if p[0].name not in self.group_leaders):
            QMessageBox.information(self, "Group Script Setup", "All characters already have a script loaded.")
            return

        if not self.group_leader_setup_path or not self.group_member_setup_path:
            self.set_group_script_paths()
            if not self.group_leader_setup_path or not self.group_member_setup_path:
                return

        dlg = GroupScriptDialog(
            self.players,
            self.text_editors,
            self.group_leader_setup_path,
            self.group_member_setup_path,
            self.group_script_group_counter,
            self.group_leaders,
            self.group_script_max_members,
        )
        if dlg.exec_():
            info = dlg.get_loaded_group()
            if info:
                self._assign_group_console(info)
            self.group_script_group_counter += 1
            # start all scripts for this group asynchronously
            self.start_group_scripts()

    def set_condition_logging_enabled(self, enabled: bool) -> None:
        enabled_bool = bool(enabled)
        self._condition_logging_enabled = enabled_bool
        self.settings.setValue("conditionLoggingEnabled", int(enabled_bool))
        for player_obj, _ in self.players:
            player_obj.condition_logging_enabled = enabled_bool

    def set_group_script_max_members(self):
        value, ok = QInputDialog.getInt(
            self,
            "Max Members",
            "Select the maximum number of characters to load (including leader):",
            self.group_script_max_members,
            1,
            24,
        )
        if ok:
            self.group_script_max_members = value
            self.settings.setValue("groupScriptMaxMembers", value)

    def set_group_script_paths(self):
        leader_path = QFileDialog.getExistingDirectory(self, "Select Leader Setup Folder")
        if not leader_path:
            return
        member_path = QFileDialog.getExistingDirectory(self, "Select Member Setup Folder")
        if not member_path:
            return
        self.group_leader_setup_path = leader_path
        self.group_member_setup_path = member_path
        self.settings.setValue("groupLeaderSetupPath", leader_path)
        self.settings.setValue("groupMemberSetupPath", member_path)
        QMessageBox.information(self, "Group Script Setup", "Setup paths saved.")

    def _load_group_script_for_player(
        self,
        player_obj,
        index,
        setup_path,
        role,
        leader_obj=None,
        group_id=None,
    ):
        script_dir = os.path.join(setup_path, "script")
        cond_dir = os.path.join(setup_path, "conditions")
        if not os.path.isdir(script_dir) or not os.path.isdir(cond_dir):
            raise RuntimeError(f"Invalid setup folder: {setup_path}")

        script_files = sorted(
            [f for f in os.listdir(script_dir) if f.endswith('.txt')],
            key=GroupScriptDialog._natural_key,
        )
        if not script_files:
            raise RuntimeError(f"No scripts found in {script_dir}")

        if role == "leader":
            chosen = next(
                (s for s in script_files if "setup1" in s.lower() or "leader" in s.lower()),
                script_files[0],
            )
        else:
            chosen = next(
                (s for s in script_files if "follow" in s.lower() or "member" in s.lower()),
                script_files[0],
            )

        with open(os.path.join(script_dir, chosen), "r", encoding="utf-8", errors="ignore") as file:
            script_text = file.read()

        self.text_editors[index].setText(script_text)

        pid = getattr(player_obj, "PIDnum", None)
        player_obj.reset_attrs()
        if pid is not None:
            player_obj.PIDnum = pid

        player_obj.recv_packet_conditions = []
        player_obj.send_packet_conditions = []
        player_obj.periodical_conditions = []
        if hasattr(player_obj, "_compiled_recv_conditions"):
            player_obj._compiled_recv_conditions.clear()
        if hasattr(player_obj, "_compiled_send_conditions"):
            player_obj._compiled_send_conditions.clear()
        if hasattr(player_obj, "_condition_state"):
            player_obj._condition_state = {
                "recv_packet": set(),
                "send_packet": set(),
                "periodical": set(),
            }
        if hasattr(player_obj, "_condition_activity_by_name"):
            player_obj._condition_activity_by_name.clear()

        cond_files = sorted(
            [f for f in os.listdir(cond_dir) if f.endswith('.txt')],
            key=GroupScriptDialog._natural_key,
        )
        for cf in cond_files:
            cond_path = os.path.join(cond_dir, cf)
            with open(cond_path, "r", encoding="utf-8", errors="ignore") as cfile:
                c_type = cfile.readline().strip()
                running = cfile.readline().strip()
                cond_script = cfile.read().strip()
            running_bool = running == "1"
            if c_type == "recv_packet":
                player_obj.recv_packet_conditions.append([os.path.splitext(cf)[0], cond_script, running_bool])
            elif c_type == "send_packet":
                player_obj.send_packet_conditions.append([os.path.splitext(cf)[0], cond_script, running_bool])
            else:
                player_obj.periodical_conditions.append(
                    PeriodicCondition(os.path.splitext(cf)[0], cond_script, running_bool, 1)
                )

        if role == "leader":
            player_obj.attr19 = 0
            player_obj.attr20 = player_obj.name
            player_obj.leadername = player_obj.name
            player_obj.leaderID = player_obj.id
        else:
            if group_id is not None:
                player_obj.attr19 = group_id
            if leader_obj is not None:
                player_obj.attr20 = leader_obj.name
                player_obj.leadername = leader_obj.name
                player_obj.leaderID = leader_obj.id

        player_obj.script_loaded = True
        player_obj.attr13 = 0
        player_obj.stop_script = False

    def add_players_to_current_group(self):
        if not self.players:
            QMessageBox.information(
                self,
                "Group Script Setup",
                "No connected characters are available.",
            )
            return

        group_configs = {}
        leader_names = set()

        for name in self.group_leaders:
            if isinstance(name, str):
                leader_names.add(name)

        for console, group_data in self.console_groups.items():
            leader_obj = group_data.get("leader")
            if leader_obj is None:
                continue
            leader_name = getattr(leader_obj, "name", None)
            if not leader_name:
                continue

            leader_names.add(leader_name)

            existing_members = set(group_data.get("members", set()))
            existing_member_names = [
                member.name
                for member in existing_members
                if hasattr(member, "name") and member is not leader_obj
            ]

            member_path = group_data.get("member_path") or self.group_member_setup_path
            if not member_path:
                member_path = self.group_member_setup_path

            leader_path = group_data.get("leader_path") or self.group_leader_setup_path

            group_id = group_data.get("group_id")
            if group_id is None:
                for player_obj in existing_members:
                    if player_obj is leader_obj:
                        continue
                    potential = getattr(player_obj, "attr19", None)
                    if isinstance(potential, int) and potential:
                        group_id = potential
                        break
                if group_id is None:
                    group_id = self.group_script_group_counter

            available_players = [
                p
                for p, _ in self.players
                if p not in existing_members
                and getattr(p, "group_console", None) in (None, console)
            ]

            group_configs[leader_name] = {
                "leader_obj": leader_obj,
                "existing_member_names": existing_member_names,
                "available_member_names": [p.name for p in available_players],
                "group_id": group_id,
                "leader_path": leader_path or self.group_leader_setup_path,
                "member_path": member_path,
            }

        sorted_leaders = sorted(leader_names)

        dlg = AddGroupMembersDialog(
            self.players,
            self.text_editors,
            self.group_leader_setup_path,
            self.group_member_setup_path,
            group_configs,
            sorted_leaders,
            self.group_script_max_members,
        )

        if not dlg.exec_():
            return

        info = dlg.get_loaded_group()
        if not info:
            return

        self._assign_group_console(info)
        self.update_group_party_info()
        self.start_group_scripts()

    def _assign_group_console(self, group_info):
        leader_name = group_info.get("leader_name")
        member_names = group_info.get("member_names", [])
        if not leader_name:
            return

        leader_obj = None
        member_objs = []
        for player_obj, _ in self.players:
            if player_obj.name == leader_name:
                leader_obj = player_obj
            if player_obj.name in member_names:
                member_objs.append(player_obj)

        if leader_obj is None:
            return

        console = self.leader_to_console.get(leader_obj)
        if console is None or console not in self.console_groups:
            console = GroupConsoleWindow(leader_obj.name, parent=self)
            console.closed.connect(lambda c=console: self._on_group_console_closed(c))

        new_members = set(member_objs)
        new_members.add(leader_obj)

        existing = self.console_groups.get(console)
        old_members = set()
        if existing:
            old_members = set(existing.get("members", set()))
        for player_obj in old_members - new_members:
            player_obj.group_console = None

        for player_obj in new_members:
            player_obj.group_console = console

        group_record = dict(existing) if isinstance(existing, dict) else {}
        group_record.update({"leader": leader_obj, "members": new_members})
        member_names = [p.name for p in member_objs]
        group_record["member_names"] = member_names
        for key in ("group_id", "leader_path", "member_path"):
            if isinstance(group_info, dict) and key in group_info and group_info[key] is not None:
                group_record[key] = group_info[key]
        self.console_groups[console] = group_record
        self.leader_to_console[leader_obj] = console

        console.set_leader_name(leader_obj.name)
        console.clear()
        console.show()
        console.raise_()
        console.activateWindow()

    def _on_group_console_closed(self, console):
        group_info = self.console_groups.pop(console, None)
        if not group_info:
            return

        members = list(group_info.get("members", set()))
        leader_obj = group_info.get("leader")
        if leader_obj and self.leader_to_console.get(leader_obj) is console:
            self.leader_to_console.pop(leader_obj, None)

        for player_obj in members:
            if getattr(player_obj, "group_console", None) is console:
                player_obj.group_console = None

        self._reset_group_players(members)

    def _reset_group_players(self, players):
        if not players:
            return

        changed = False
        for player_obj in players:
            if player_obj is None:
                continue
            try:
                index = next(i for i, (p, _) in enumerate(self.players) if p == player_obj)
            except StopIteration:
                continue

            thread = self.players[index][1]
            if thread:
                try:
                    player_obj.stop_script = True
                    thread.kill()
                except Exception:
                    pass
                self.players[index][1] = None

            try:
                editor_widget = self.text_editors[index]
                if hasattr(editor_widget, "reset_to_default_script"):
                    editor_widget.reset_to_default_script()
                else:
                    editor_widget.setText("")
            except Exception:
                pass

            try:
                self.start_stop_buttons[index][0].show()
                self.start_stop_buttons[index][1].hide()
            except Exception:
                pass

            try:
                self.tab_widget.tabBar().setTabTextColor(index, QColor("white"))
            except Exception:
                pass

            player_obj.recv_packet_conditions = []
            player_obj.send_packet_conditions = []
            player_obj.periodical_conditions = []
            if hasattr(player_obj, "_compiled_recv_conditions"):
                player_obj._compiled_recv_conditions.clear()
            if hasattr(player_obj, "_compiled_send_conditions"):
                player_obj._compiled_send_conditions.clear()
            player_obj.script_loaded = False
            player_obj.stop_script = True
            try:
                player_obj.reset_attrs()
            except Exception:
                pass
            player_obj.partyname = []
            player_obj.partyID = []
            changed = True

        if changed:
            self.update_group_party_info()

    def _detach_player_console(self, player_obj):
        for console, info in list(self.console_groups.items()):
            members = set(info.get("members", set()))
            if player_obj not in members:
                continue

            members.discard(player_obj)
            info["members"] = members
            self.console_groups[console] = info
            if info.get("leader") is player_obj:
                player_obj.group_console = None
                console.close()
            else:
                if getattr(player_obj, "group_console", None) is console:
                    player_obj.group_console = None
                if not members or info.get("leader") not in members:
                    console.close()
            break

    def _format_display_name(self, raw_name, pid):
        """Return a stable tab label for a character window."""

        if raw_name is not None:
            clean_name = str(raw_name).strip()
            if clean_name and any(ch.isalpha() for ch in clean_name):
                return clean_name
        return f"PID: {pid}"

    def refresh(self):
        if getattr(self, "_refreshing", False):
            return

        self._refreshing = True
        try:
            self._refresh_impl()
        finally:
            self._refreshing = False

    def _refresh_impl(self):
        raw_chars = returnAllPorts(include_new_api=True)
        char_infos = []
        for entry in raw_chars:
            try:
                name, api_port, pid, *maybe_new_port = entry
            except (TypeError, ValueError):
                continue
            display_name = self._format_display_name(name, pid)
            new_api_port = None
            is_login_state = False
            if maybe_new_port:
                new_api_port = maybe_new_port[0]
                if len(maybe_new_port) > 1:
                    is_login_state = bool(maybe_new_port[1])
            char_infos.append({
                "raw_name": name,
                "api_port": api_port,
                "pid": pid,
                "new_port": new_api_port,
                "display_name": display_name,
                "is_login_state": is_login_state,
            })

        char_infos.sort(key=lambda info: info["display_name"].casefold())

        pid_to_index = {}
        legacy_port_to_index = {}
        new_port_to_index = {}
        name_to_index = {}
        display_to_index = {}
        for idx, (player_obj, _) in enumerate(self.players):
            pid = getattr(player_obj, "PIDnum", None)
            if pid is not None:
                try:
                    pid_to_index[int(pid)] = idx
                except (TypeError, ValueError):
                    pid_to_index[pid] = idx

            legacy_port = getattr(player_obj, "api_port", None)
            if not legacy_port:
                legacy_port = getattr(player_obj, "port", None)
            if legacy_port:
                legacy_port_to_index[str(legacy_port)] = idx

            new_port = getattr(player_obj, "new_api_port", None)
            if new_port:
                new_port_to_index[str(new_port)] = idx

            current_name = getattr(player_obj, "name", None)
            if current_name:
                name_to_index.setdefault(current_name, idx)

            if idx < len(self.open_tabs_names):
                display_to_index.setdefault(self.open_tabs_names[idx], idx)
            else:
                display = getattr(player_obj, "display_name", None)
                if display:
                    display_to_index.setdefault(display, idx)

            setattr(player_obj, "is_connected", False)
            setattr(player_obj, "is_in_login_state", False)

        current_raw_names = [info["raw_name"] for info in char_infos if info["raw_name"]]

        for info in char_infos:
            raw_name = info["raw_name"]
            pid = info["pid"]
            display_name = info["display_name"]
            legacy_port = info.get("api_port")
            new_port = info.get("new_port")

            existing_index = pid_to_index.get(pid)
            if existing_index is None and legacy_port:
                existing_index = legacy_port_to_index.get(str(legacy_port))
            if existing_index is None and new_port:
                existing_index = new_port_to_index.get(str(new_port))
            if existing_index is None and raw_name:
                existing_index = name_to_index.get(raw_name)
            if existing_index is None:
                existing_index = display_to_index.get(display_name)

            if existing_index is not None:
                player_obj = self.players[existing_index][0]
                is_login_state = bool(info.get("is_login_state"))
                display_name_override = display_name
                if raw_name and not is_login_state:
                    player_obj.name = raw_name
                    player_obj.last_known_name = raw_name
                    display_name_override = raw_name
                elif is_login_state:
                    last_known = getattr(player_obj, "last_known_name", None)
                    if last_known:
                        player_obj.name = last_known
                        display_name_override = last_known
                    else:
                        prior_display = getattr(player_obj, "display_name", None)
                        if prior_display:
                            display_name_override = prior_display
                elif raw_name:
                    player_obj.name = raw_name
                    display_name_override = raw_name
                player_obj.display_name = display_name_override
                player_obj.is_in_login_state = is_login_state
                if getattr(player_obj, "PIDnum", None) != pid:
                    player_obj.PIDnum = pid
                if legacy_port:
                    player_obj.api_port = str(legacy_port)
                    try:
                        player_obj.port = int(legacy_port)
                    except (TypeError, ValueError):
                        pass
                if new_port:
                    player_obj.new_api_port = str(new_port)
                else:
                    player_obj.new_api_port = None
                player_obj.is_connected = True
                self._update_displayed_name(existing_index, display_name_override)
                continue

            if display_name not in self.open_tabs_names:
                self.add_tab(display_name)
                # Ensure future refreshes match by PID for already-loaded scripts
                if self.players:
                    player_obj = self.players[-1][0]
                    player_obj.PIDnum = pid
                    is_login_state = bool(info.get("is_login_state"))
                    display_name_override = display_name
                    if raw_name and not is_login_state:
                        player_obj.name = raw_name
                        player_obj.last_known_name = raw_name
                        display_name_override = raw_name
                    elif is_login_state:
                        last_known = getattr(player_obj, "last_known_name", None)
                        if last_known:
                            player_obj.name = last_known
                            display_name_override = last_known
                        else:
                            prior_display = getattr(player_obj, "display_name", None)
                            if prior_display:
                                display_name_override = prior_display
                    elif raw_name:
                        player_obj.name = raw_name
                        display_name_override = raw_name
                    player_obj.display_name = display_name_override
                    player_obj.is_in_login_state = is_login_state
                    player_obj.is_connected = True
                    if legacy_port:
                        player_obj.api_port = str(legacy_port)
                        try:
                            player_obj.port = int(legacy_port)
                        except (TypeError, ValueError):
                            pass
                    if new_port:
                        player_obj.new_api_port = str(new_port)
                    else:
                        player_obj.new_api_port = None
                    if display_name_override != display_name:
                        self._update_displayed_name(len(self.players) - 1, display_name_override)
            else:
                # Name matches but PID changed (e.g. client relaunch). Keep the
                # existing tab but update the stored PID for consistency.
                index = self.open_tabs_names.index(display_name)
                player_obj = self.players[index][0]
                player_obj.PIDnum = pid
                is_login_state = bool(info.get("is_login_state"))
                display_name_override = display_name
                if raw_name and not is_login_state:
                    player_obj.name = raw_name
                    player_obj.last_known_name = raw_name
                    display_name_override = raw_name
                elif is_login_state:
                    last_known = getattr(player_obj, "last_known_name", None)
                    if last_known:
                        player_obj.name = last_known
                        display_name_override = last_known
                    else:
                        prior_display = getattr(player_obj, "display_name", None)
                        if prior_display:
                            display_name_override = prior_display
                elif raw_name:
                    player_obj.name = raw_name
                    display_name_override = raw_name
                player_obj.display_name = display_name_override
                player_obj.is_in_login_state = is_login_state
                if legacy_port:
                    player_obj.api_port = str(legacy_port)
                    try:
                        player_obj.port = int(legacy_port)
                    except (TypeError, ValueError):
                        pass
                if new_port:
                    player_obj.new_api_port = str(new_port)
                else:
                    player_obj.new_api_port = None
                player_obj.is_connected = True
                if display_name_override != display_name:
                    self._update_displayed_name(index, display_name_override)

        disconnected_players = [
            player_obj
            for player_obj, _editor in list(self.players)
            if not getattr(player_obj, "is_connected", False)
        ]
        for player_obj in disconnected_players:
            self.player_disconnected(player_obj)

        known_names = set(current_raw_names)
        for player_obj, _editor in self.players:
            name = getattr(player_obj, "name", None)
            if name:
                known_names.add(name)
        self.group_leaders = [name for name in self.group_leaders if name in known_names]

        any_connected = any(getattr(p[0], "is_connected", False) for p in self.players)
        has_players = bool(self.players)

        self.no_client_found_label.setVisible(not any_connected)
        self.tab_widget.setVisible(has_players)
        self.loadAction.setEnabled(has_players)
        self.saveAction.setEnabled(has_players)

        self.update_group_party_info()

    def _update_displayed_name(self, index, new_name):
        """Update tab labels and bookkeeping when a player's name changes."""

        if index >= len(self.open_tabs_names):
            # Keep bookkeeping aligned in edge cases where a tab was created but
            # the list was not extended yet (e.g. during rapid refreshes).
            self.open_tabs_names.extend([None] * (index - len(self.open_tabs_names) + 1))

        old_name = self.open_tabs_names[index]
        if old_name == new_name:
            return False

        self.open_tabs_names[index] = new_name

        if index < self.tab_widget.count():
            self.tab_widget.setTabText(index, new_name)

        if index < len(self.players):
            player_obj = self.players[index][0]
            console = getattr(player_obj, "group_console", None)
            if console:
                group_info = self.console_groups.get(console)
                if group_info and group_info.get("leader") is player_obj:
                    console.set_leader_name(new_name)

        if old_name:
            self.group_leaders = [new_name if leader == old_name else leader for leader in self.group_leaders]

        return True

    def sync_player_names(self):
        """Ensure tab titles mirror the live names of connected players."""

        name_changed = False
        for idx, (player_obj, _) in enumerate(self.players):
            current_name = getattr(player_obj, "display_name", None)
            if not current_name:
                current_name = getattr(player_obj, "name", None)
            if not current_name:
                continue

            if idx >= len(self.open_tabs_names):
                self.open_tabs_names.append(current_name)
                if idx < self.tab_widget.count():
                    self.tab_widget.setTabText(idx, current_name)
                name_changed = True
                continue

            if self._update_displayed_name(idx, current_name):
                player_obj.display_name = current_name
                name_changed = True

        if name_changed:
            self.update_group_party_info()

    def update_group_party_info(self):
        """Synchronize party names and IDs for players with group scripts."""
        group_players = [p[0] for p in self.players if p[0].script_loaded]
        if not group_players:
            return

        leaders = [name for name in self.group_leaders if isinstance(name, str)]
        leader_set = set(leaders)

        groups: dict[str, list] = {}
        for player in group_players:
            leader_name = None
            if isinstance(player.attr20, str) and player.attr20:
                leader_name = player.attr20
            elif player.name in leader_set:
                leader_name = player.name
            elif isinstance(player.leadername, str) and player.leadername:
                leader_name = player.leadername

            if not leader_name:
                continue

            if leader_set and leader_name not in leader_set and player.name not in leader_set:
                continue

            groups.setdefault(leader_name, []).append(player)

        for leader_name, players in groups.items():
            leader_obj = next((p for p in players if p.name == leader_name), None)
            if leader_obj is None:
                leader_obj = next((p for p in players if p.name in leader_set), None)
            if leader_obj is None:
                continue

            member_objs = [p for p in players if p is not leader_obj]
            party_names = [leader_obj.name] + [m.name for m in member_objs]
            party_ids = [leader_obj.id] + [m.id for m in member_objs]

            for participant in [leader_obj] + member_objs:
                participant.partyname = party_names
                participant.partyID = party_ids

            leader_obj.attr51 = [m.name for m in member_objs]
            leader_obj.leaderID = leader_obj.id
            for member in member_objs:
                member.leaderID = leader_obj.id

    def add_tab(self, char_name):
        # Create a new tab and add it to the tab widget
        self.no_client_found_label.setVisible(False)
        self.tab_widget.setVisible(True)
        tab = QWidget()
        self.tab_widget.addTab(tab, char_name)
        self.open_tabs_names += [char_name]

        player = Player(char_name, on_disconnect=self.player_disconnected)
        player.display_name = char_name
        player.last_known_name = char_name
        player.is_in_login_state = False
        player.condition_logging_enabled = self._condition_logging_enabled
        self.players.append([player, None])

        # Create a layout for the tab
        tab_layout = QVBoxLayout(tab)
   
        # Create a text editor with light blue background
        text_editor = Editor(tab)
        self.text_editors.append(text_editor)
        # Set the initial font for the entire text
        tab_layout.addWidget(text_editor)

        # Create a horizontal layout for buttons
        button_layout = QHBoxLayout()

        player = self.players[self.tab_widget.currentIndex()][0]

        # Buttons at the bottom
        start_button = QPushButton("Start Script", tab)
        stop_button = QPushButton("Stop Script", tab)
        manage_conditions_button = QPushButton("Manage Conditions", tab)

        self.start_stop_buttons.append([start_button, stop_button])

        button_layout.addWidget(start_button)
        button_layout.addWidget(stop_button)
        button_layout.addWidget(manage_conditions_button)

        # Connect button signals to functions
        start_button.clicked.connect(self.start_script_clicked)
        stop_button.clicked.connect(self.stop_script_clicked)
        manage_conditions_button.clicked.connect(self.open_condition_modifier)

        tab_layout.addLayout(button_layout)

        # Save and Load buttons
        save_button = QPushButton("Save Script", tab)
        load_button = QPushButton("Load Script", tab)

        # Connect button signals to functions
        save_button.clicked.connect(self.save_script)
        load_button.clicked.connect(self.load_script)

        # Create another horizontal layout for save and load buttons
        save_load_layout = QHBoxLayout()
        save_load_layout.addWidget(save_button)
        save_load_layout.addWidget(load_button)

        start_button.show()
        
        stop_button.hide()

        tab_layout.addLayout(save_load_layout)

    def start_script_clicked(self):
        # Get the current text editor in the active tab
        text_editor = self.tab_widget.currentWidget().findChild(QsciScintilla)

        if text_editor.text() != "":
            # Get the Python script from the text editor
            #script = f"player = self.players[self.tab_widget.currentIndex()][0]\nindex = self.tab_widget.currentIndex()\n"
            script = text_editor.text()  # Use text() method instead of toPlainText()
#
            #script += f'\nself.tab_widget.tabBar().setTabTextColor(index, QColor("#e88113"))'

            #t = threading.Thread(target=self.run_script, args=[script, ])
            #t.start()

            t = thread_with_trace(target=self.run_script, args=[script, ])
            t.start()

            for i in range(len(self.players)):
                if self.players[i][0] == self.players[self.tab_widget.currentIndex()][0]:
                    self.players[i][0].stop_script = False
                    self.players[i][1] = t
            # Hide the start button and show the stop button
            self.start_stop_buttons[self.tab_widget.currentIndex()][0].hide()
            self.start_stop_buttons[self.tab_widget.currentIndex()][1].show()
        else:
            print("empty")

    def start_group_scripts(self):
        """Launch scripts for all group members in parallel threads."""
        for idx, (player, thread) in enumerate(self.players):
            if player.script_loaded and (not thread or not thread.is_alive()):
                script = self.text_editors[idx].text()
                if script.strip():
                    t = thread_with_trace(target=self.run_script, args=[script, idx])
                    t.start()
                    player.stop_script = False
                    self.players[idx][1] = t
                    self.start_stop_buttons[idx][0].hide()
                    self.start_stop_buttons[idx][1].show()

    def stop_script_clicked(self):
        # Handle the stop script button click
        # You may want to perform some actions here when the script stops

        for i in range(len(self.players)):
            if self.players[i][0] == self.players[self.tab_widget.currentIndex()][0]:
                self.players[i][0].stop_script = True
                self.players[i][1].kill()
        
        #self.players[i][1].join()
        # Hide the stop button and show the start button
        self.start_stop_buttons[self.tab_widget.currentIndex()][0].show()
        self.start_stop_buttons[self.tab_widget.currentIndex()][1].hide()
        self.tab_widget.tabBar().setTabTextColor(self.tab_widget.currentIndex(), QColor("#e88113"))
        
    def run_script(self, script, index = None):
        if index is None:
            index = self.tab_widget.currentIndex()
        player = self.players[index][0]
        with use_group_console(getattr(player, "group_console", None)):
            try:
                # Execute the Python script in the context of this player
                self.tab_widget.tabBar().setTabTextColor(index, QColor("green"))
                exec(script, globals(), {"self": self, "player": player, "index": index})
                self.tab_widget.tabBar().setTabTextColor(index, QColor("#e88113"))
            except Exception as e:
                # Handle any exceptions that occur during execution
                print(f"Error executing script: {e}")
                self.tab_widget.tabBar().setTabTextColor(index, QColor("red"))

            """ not working properly atm, most likely due to running this in thread
            text = f"{e}"
            msg = QMessageBox() 
            msg.setIcon(QMessageBox.Warning) 

            # setting message for Message Box 
            msg.setText(text) 

            # setting Message box window title 
            msg.setWindowTitle("Script execution error") 

            # declaring buttons on Message Box 
            msg.setStandardButtons(QMessageBox.Ok) 

            msg.exec_() 
            """
        self.start_stop_buttons[self.tab_widget.currentIndex()][0].show()
        self.start_stop_buttons[self.tab_widget.currentIndex()][1].hide()

    def open_condition_modifier(self):
        condition_editor = ConditionModifier(self.players[self.tab_widget.currentIndex()][0])
        condition_editor.exec_()

    def save_script(self):
        file_dialog = QFileDialog()
        file_name, _ = file_dialog.getSaveFileName(self, "Save Script", "", "Text Files (*.txt);;All Files (*)")
        if file_name:
            with open(file_name, 'w') as file:
                text_editor = self.tab_widget.currentWidget().findChild(QsciScintilla)
                file.write(text_editor.toPlainText())

    def load_script(self):
        file_dialog = QFileDialog()
        file_name, _ = file_dialog.getOpenFileName(self, "Load Script", "", "Text Files (*.txt);;All Files (*)")
        if file_name:
            with open(file_name, 'r') as file:
                text_editor = self.tab_widget.currentWidget().findChild(QsciScintilla)
                text_editor.setText(file.read())

class thread_with_trace(threading.Thread):
  def __init__(self, *args, **keywords):
    threading.Thread.__init__(self, *args, **keywords)
    self.killed = False
 
  def start(self):
    self.__run_backup = self.run
    self.run = self.__run      
    threading.Thread.start(self)
 
  def __run(self):
    sys.settrace(self.globaltrace)
    self.__run_backup()
    self.run = self.__run_backup
 
  def globaltrace(self, frame, event, arg):
    if event == 'call':
      return self.localtrace
    else:
      return None
 
  def localtrace(self, frame, event, arg):
    if self.killed:
      if event == 'line':
        raise SystemExit()
    return self.localtrace
 
  def kill(self):
    self.killed = True
 
def setLightTheme():
    light_palette = QPalette()
    light_palette.setColor(QPalette.Window, Qt.white)
    light_palette.setColor(QPalette.WindowText, Qt.black)
    light_palette.setColor(QPalette.Base, QColor(280, 280, 280))
    light_palette.setColor(QPalette.AlternateBase, Qt.white)
    light_palette.setColor(QPalette.ToolTipBase, Qt.black)
    light_palette.setColor(QPalette.ToolTipText, Qt.black)
    light_palette.setColor(QPalette.Text, Qt.black)
    light_palette.setColor(QPalette.Button, Qt.white)
    light_palette.setColor(QPalette.ButtonText, Qt.black)
    light_palette.setColor(QPalette.BrightText, Qt.red)
    light_palette.setColor(QPalette.Link, QColor(42, 130, 218))
    light_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    light_palette.setColor(QPalette.HighlightedText, Qt.white)
    app.setPalette(light_palette)
    app.setStyleSheet("QToolTip { color: #000000; background-color: #2a82da; border: 1px solid black; }")

def setDarkTheme():
    dark_palette = QPalette()
    dark_palette.setColor(QPalette.Window, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.WindowText, Qt.white)
    dark_palette.setColor(QPalette.Base, QColor(32, 28, 28))
    dark_palette.setColor(QPalette.AlternateBase, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ToolTipBase, Qt.white)
    dark_palette.setColor(QPalette.ToolTipText, Qt.white)
    dark_palette.setColor(QPalette.Text, Qt.white)
    dark_palette.setColor(QPalette.Button, QColor(53, 53, 53))
    dark_palette.setColor(QPalette.ButtonText, Qt.white)
    dark_palette.setColor(QPalette.BrightText, Qt.red)
    dark_palette.setColor(QPalette.Link, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.Highlight, QColor(42, 130, 218))
    dark_palette.setColor(QPalette.HighlightedText, Qt.black)
    app.setPalette(dark_palette)
    app.setStyleSheet("QToolTip { color: #ffffff; background-color: #2a82da; border: 1px solid white; }")

if __name__ == "__main__":
    try:
        app_object = QApplication(sys.argv)
        lock_file = QLockFile("src/Script Creator.lock")
        

        if lock_file.tryLock():
            app_name = 'Script Creator by Stradiveri'
            fg_window = win32gui.GetForegroundWindow()

            app = QApplication(sys.argv)
            app.setStyle('Fusion')
            if not prompt_for_license():
                sys.exit(0)
            window = MyWindow()
            window.show()
            sys.exit(app.exec_())
        else:
            error_message = QMessageBox()
            error_message.setIcon(QMessageBox.Warning)
            error_message.setWindowTitle("Error")
            error_message.setText("Script Creator is already running!")
            error_message.setStandardButtons(QMessageBox.Ok)
            error_message.exec()
    finally:
        lock_file.unlock()

