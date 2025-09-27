import sys
import os
import re
import builtins
import ctypes
import win32gui
import win32con
import threading
import warnings
from typing import Dict, NamedTuple, Optional, Set
from weakref import WeakKeyDictionary, proxy, ref
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
from group_console import (
    GroupConsoleWindow,
    console_print,
    install_console_routing,
    use_group_console,
)

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


class PlayerTabContext(NamedTuple):
    player: Player
    index: int
    container: QTabWidget
    widget: QWidget
    group_id: Optional[int]

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
player = self.players[index][0]


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

    @staticmethod
    def _normalize_group_id(value):
        """Return a positive integer identifier for the group."""

        try:
            numeric_value = int(value)
        except (TypeError, ValueError):
            numeric_value = 0
        return max(1, numeric_value)

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
        subgroup_size=0,
    ):
        super().__init__()

        self.players = players
        self.text_editors = text_editors
        self.leader_path = leader_path
        self.member_path = member_path
        self.group_id = self._normalize_group_id(group_id)
        # Predefined leaders to exclude from auto-selection and member listing
        self.leaders = leaders
        self.loaded_group_info = None
        self.mode = mode if mode in {"setup", "extend"} else "setup"
        self.existing_group = existing_group or {}
        self.available_member_names = available_member_names
        try:
            subgroup_value = int(subgroup_size)
        except (TypeError, ValueError):
            subgroup_value = 0
        self.subgroup_size = max(0, subgroup_value)
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

    def _coerce_pid_to_int(self, pid_value):
        if isinstance(pid_value, int):
            return pid_value
        if isinstance(pid_value, str):
            pid_value = pid_value.strip()
            if not pid_value:
                return None
            try:
                return int(pid_value, 10)
            except ValueError:
                digits = re.findall(r"\d+", pid_value)
                if digits:
                    try:
                        return int(digits[0], 10)
                    except ValueError:
                        return None
        return None

    def _member_sort_key(self, player_obj):
        if player_obj is None:
            return (2,)
        pid_value = self._coerce_pid_to_int(getattr(player_obj, "PIDnum", None))
        if pid_value is not None:
            return (0, pid_value, getattr(player_obj, "name", ""))
        name = (
            getattr(player_obj, "name", None)
            or getattr(player_obj, "display_name", None)
            or ""
        )
        return (1, tuple(self._natural_key(str(name))), str(name).lower())

    def _prepare_subgroup_assignment(
        self,
        leader_name,
        member_names,
        existing_member_names=None,
    ):
        assignments = {}
        skipped_members = set()
        if self.subgroup_size <= 0:
            return assignments, skipped_members, False

        combined_names = []
        if isinstance(existing_member_names, (list, tuple, set)):
            for name in existing_member_names:
                if isinstance(name, str) and name not in combined_names:
                    combined_names.append(name)
        for name in member_names:
            if isinstance(name, str) and name not in combined_names:
                combined_names.append(name)

        if not combined_names:
            return assignments, skipped_members, False

        member_objs = []
        seen = set()
        for player_obj, _ in self.players:
            name = getattr(player_obj, "name", None)
            if not isinstance(name, str):
                continue
            if name == leader_name:
                continue
            if name in combined_names and name not in seen:
                member_objs.append(player_obj)
                seen.add(name)

        member_objs.sort(key=self._member_sort_key)

        if not member_objs:
            return assignments, skipped_members, False

        subgroup_size = max(1, self.subgroup_size)
        total_members = len(member_objs)
        complete_members = (total_members // subgroup_size) * subgroup_size
        incomplete = total_members % subgroup_size != 0

        for idx, player_obj in enumerate(member_objs):
            name = getattr(player_obj, "name", None)
            if not isinstance(name, str):
                continue
            if idx >= complete_members:
                skipped_members.add(name)
                continue
            assignments[name] = (idx // subgroup_size) + 1

        return assignments, skipped_members, incomplete

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

        existing_names_for_assignment = []
        if self.mode == "extend":
            existing_names_for_assignment = list(
                self.existing_group.get("member_names", [])
            )

        assignments, skipped_members, incomplete_flag = self._prepare_subgroup_assignment(
            leader_name,
            list(member_names),
            existing_names_for_assignment,
        )

        if skipped_members:
            member_names = [name for name in member_names if name not in skipped_members]
            if not member_names:
                QMessageBox.warning(
                    self,
                    self.windowTitle(),
                    "No se pudo cargar el setup al ultimo subgrupo",
                )
                return

        if self.subgroup_size > 0:
            member_names = [name for name in member_names if name in assignments]
            if not member_names:
                QMessageBox.warning(
                    self,
                    self.windowTitle(),
                    "No se pudo cargar el setup al ultimo subgrupo",
                )
                return

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
                subgroup_index = assignments.get(player_obj.name)
                if subgroup_index is not None:
                    player_obj.subgroup_index = subgroup_index
                elif hasattr(player_obj, "subgroup_index"):
                    player_obj.subgroup_index = None
            player_obj.script_loaded = True
            player_obj.attr13 = 0

        if leader_obj is None:
            QMessageBox.warning(self, "Load Failed", "Unable to locate the selected leader.")
            return

        if hasattr(leader_obj, "subgroup_index"):
            leader_obj.subgroup_index = None

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
            if p is not None and hasattr(p, "prepare_group_console_output"):
                try:
                    p.prepare_group_console_output()
                except Exception:
                    pass

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
        if assignments:
            self.loaded_group_info["member_subgroups"] = assignments
        if skipped_members:
            self.loaded_group_info["skipped_members"] = list(skipped_members)
        if self.subgroup_size > 0:
            self.loaded_group_info["subgroup_size"] = self.subgroup_size
        if self.mode == "extend":
            self.loaded_group_info["new_member_names"] = list(member_names)

        success_message = "Setup successfully loaded."
        if self.mode == "extend":
            success_message = "Selected members have been added to the current group."

        QMessageBox.information(self, self.windowTitle(), success_message)
        if incomplete_flag:
            QMessageBox.warning(
                self,
                self.windowTitle(),
                "No se pudo cargar el setup al ultimo subgrupo",
            )
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
        subgroup_size,
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
            subgroup_size=subgroup_size,
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

        self.group_id = self._normalize_group_id(config.get("group_id", self.group_id))
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
        subgroup_value = self.settings.value("groupScriptSubgroupSize", 0)
        try:
            self.group_script_subgroup_size = int(subgroup_value)
        except (TypeError, ValueError):
            self.group_script_subgroup_size = 0
        if self.group_script_subgroup_size < 0:
            self.group_script_subgroup_size = 0
        self.group_script_group_counter = 1
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
        self._player_script_globals = WeakKeyDictionary()
        self._refreshing = False
        self.player_widgets: Dict[Player, QWidget] = {}
        self.widget_to_player: Dict[QWidget, Player] = {}
        self.player_tab_containers: Dict[Player, QTabWidget] = {}
        self.player_to_group: Dict[Player, Optional[int]] = {}
        self.group_tab_infos: Dict[int, Dict[str, object]] = {}
        self._group_widget_to_id: Dict[QWidget, int] = {}
        self._inner_tab_to_group: Dict[QTabWidget, int] = {}
        self._current_player_index: int = -1

        self.setWindowTitle("Script Creator by Stradiveri")
        self.setWindowIcon(QIcon('src/icon.png'))

        # Create the main widget and set it as the central widget
        main_widget = QWidget(self)
        self.setCentralWidget(main_widget)

        # Create a layout for the main widget
        layout = QVBoxLayout(main_widget)

        # Create the tab widget
        self.tab_widget = QTabWidget(self)
        self.tab_widget.currentChanged.connect(self._on_main_tab_changed)
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
        subgroupSizeAction = QAction('Number of members per subgroup', self)
        subgroupSizeAction.triggered.connect(self.set_group_script_subgroup_size)
        groupMenu.addAction(subgroupSizeAction)
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

    def _on_main_tab_changed(self, _index):
        self._update_current_player_index()

    def _on_group_member_changed(self, _group_id, _index):
        self._update_current_player_index()

    def _update_current_player_index(self):
        context = self._get_current_player_context()
        self._current_player_index = context.index if context else -1

    def current_player_index(self):
        return self._current_player_index

    def _find_player_index(self, player_obj):
        for idx, (player, _thread) in enumerate(self.players):
            if player is player_obj:
                return idx
        return None

    def _get_current_player_context(self) -> Optional[PlayerTabContext]:
        current_index = self.tab_widget.currentIndex()
        if current_index < 0:
            return None
        current_widget = self.tab_widget.widget(current_index)
        group_id = self._group_widget_to_id.get(current_widget)
        if group_id is not None:
            group_info = self.group_tab_infos.get(group_id)
            if not group_info:
                return None
            inner_tabs = group_info.get("tabs")
            if not isinstance(inner_tabs, QTabWidget):
                return None
            member_widget = inner_tabs.currentWidget()
            if member_widget is None:
                return None
            player_obj = self.widget_to_player.get(member_widget)
            if player_obj is None:
                return None
            index = self._find_player_index(player_obj)
            if index is None:
                return None
            return PlayerTabContext(player_obj, index, inner_tabs, member_widget, group_id)
        player_obj = self.widget_to_player.get(current_widget)
        if player_obj is None:
            return None
        index = self._find_player_index(player_obj)
        if index is None:
            return None
        return PlayerTabContext(player_obj, index, self.tab_widget, current_widget, None)

    def _register_player_widget(self, player_obj, widget):
        self.player_widgets[player_obj] = widget
        self.widget_to_player[widget] = player_obj
        self.player_tab_containers[player_obj] = self.tab_widget
        self.player_to_group[player_obj] = None

    def _set_tab_text_for_player(self, player_obj, text):
        container = self.player_tab_containers.get(player_obj)
        widget = self.player_widgets.get(player_obj)
        if not container or not widget:
            return
        index = container.indexOf(widget)
        if index != -1:
            container.setTabText(index, text)
            if container is not self.tab_widget:
                group_id = self._inner_tab_to_group.get(container)
                if group_id is not None:
                    self._update_group_tab_labels(group_id)

    def _set_tab_color_for_player(self, player_obj, color):
        container = self.player_tab_containers.get(player_obj)
        widget = self.player_widgets.get(player_obj)
        if not container or not widget:
            return
        index = container.indexOf(widget)
        if index == -1:
            return
        if not isinstance(color, QColor):
            color = QColor(color)
        container.tabBar().setTabTextColor(index, color)

    def _set_tab_color_by_index(self, index, color):
        if 0 <= index < len(self.players):
            self._set_tab_color_for_player(self.players[index][0], color)

    def _coerce_pid_to_int(self, pid_value):
        if isinstance(pid_value, int):
            return pid_value
        if isinstance(pid_value, str):
            pid_value = pid_value.strip()
            if not pid_value:
                return None
            try:
                return int(pid_value, 10)
            except ValueError:
                digits = re.findall(r"\d+", pid_value)
                if digits:
                    try:
                        return int(digits[0], 10)
                    except ValueError:
                        return None
        return None

    def _player_group_sort_key(self, player_obj):
        if player_obj is None:
            return (2,)
        pid_value = self._coerce_pid_to_int(getattr(player_obj, "PIDnum", None))
        if pid_value is not None:
            return (0, pid_value, getattr(player_obj, "name", ""))
        name = (
            getattr(player_obj, "name", None)
            or getattr(player_obj, "display_name", None)
            or ""
        )
        return (1, tuple(GroupScriptDialog._natural_key(str(name))), str(name).lower())

    def _compute_subgroup_assignments(self, leader_obj, member_objs, subgroup_size=None):
        assignments = {}
        skipped_members = set()
        if subgroup_size is None:
            subgroup_size = getattr(self, "group_script_subgroup_size", 0)
        try:
            subgroup_size = int(subgroup_size)
        except (TypeError, ValueError):
            subgroup_size = 0
        if subgroup_size <= 0:
            return assignments, False, skipped_members
        valid_members = [m for m in member_objs if m is not None and m is not leader_obj]
        if not valid_members:
            return assignments, False, skipped_members
        valid_members.sort(key=self._player_group_sort_key)
        subgroup_size = max(1, subgroup_size)
        total_members = len(valid_members)
        complete_members = (total_members // subgroup_size) * subgroup_size
        incomplete = total_members % subgroup_size != 0
        for idx, member in enumerate(valid_members):
            if idx >= complete_members:
                skipped_members.add(member)
                continue
            assignments[member] = (idx // subgroup_size) + 1
        return assignments, incomplete, skipped_members

    def _reapply_subgroup_assignments(self):
        for console, info in list(self.console_groups.items()):
            if not isinstance(info, dict):
                continue
            leader_obj = info.get("leader")
            members = set(info.get("members", set()))
            member_objs = [m for m in members if m is not None and m is not leader_obj]
            name_mapping = {}
            if self.group_script_subgroup_size > 0 and member_objs:
                assignments, _incomplete, _skipped = self._compute_subgroup_assignments(
                    leader_obj,
                    member_objs,
                    self.group_script_subgroup_size,
                )
                for member in member_objs:
                    subgroup_index = assignments.get(member)
                    if subgroup_index is not None:
                        member.subgroup_index = subgroup_index
                        if isinstance(member.name, str):
                            name_mapping[member.name] = subgroup_index
                    elif hasattr(member, "subgroup_index"):
                        member.subgroup_index = None
                if name_mapping:
                    info["subgroup_assignments"] = name_mapping
                else:
                    info.pop("subgroup_assignments", None)
                info["subgroup_size"] = self.group_script_subgroup_size
            else:
                info.pop("subgroup_assignments", None)
                info.pop("subgroup_size", None)
                for member in member_objs:
                    if hasattr(member, "subgroup_index"):
                        member.subgroup_index = None
            if leader_obj is not None and hasattr(leader_obj, "subgroup_index"):
                leader_obj.subgroup_index = None
            group_id = info.get("group_id")
            if group_id is None:
                continue
            group_info = self.group_tab_infos.get(group_id)
            if isinstance(group_info, dict):
                group_info["leader"] = leader_obj
                if name_mapping and self.group_script_subgroup_size > 0:
                    group_info["subgroup_assignments"] = dict(name_mapping)
                else:
                    group_info.pop("subgroup_assignments", None)
                self._sort_group_tabs(group_id)

    def _sort_group_tabs(self, group_id):
        group_info = self.group_tab_infos.get(group_id)
        if not group_info:
            return
        target_tabs = group_info.get("tabs")
        if not isinstance(target_tabs, QTabWidget):
            return
        leader_obj = group_info.get("leader") if isinstance(group_info, dict) else None
        entries = []
        for idx in range(target_tabs.count()):
            widget = target_tabs.widget(idx)
            player_obj = self.widget_to_player.get(widget)
            base_key = self._player_group_sort_key(player_obj)
            if leader_obj is not None and player_obj is leader_obj:
                sort_key = (0,)
            else:
                sort_key = (1,) + tuple(base_key)
            entries.append((sort_key, widget))
        entries.sort(key=lambda item: item[0])
        tab_bar = target_tabs.tabBar()
        for desired_index, (_key, widget) in enumerate(entries):
            current_index = target_tabs.indexOf(widget)
            if current_index == -1 or current_index == desired_index:
                continue
            tab_bar.moveTab(current_index, desired_index)
        self._update_group_tab_labels(group_id)

    def _resort_player_group(self, player_obj):
        if player_obj is None:
            return
        group_id = self.player_to_group.get(player_obj)
        if group_id is None:
            return
        self._sort_group_tabs(group_id)

    def _update_group_tab_labels(self, group_id):
        group_info = self.group_tab_infos.get(group_id)
        if not group_info:
            return
        target_tabs = group_info.get("tabs")
        if not isinstance(target_tabs, QTabWidget):
            return
        leader_obj = group_info.get("leader") if isinstance(group_info, dict) else None
        tab_bar = target_tabs.tabBar()
        for idx in range(target_tabs.count()):
            widget = target_tabs.widget(idx)
            player_obj = self.widget_to_player.get(widget)
            if player_obj is None:
                continue
            base_text = getattr(player_obj, "display_name", None) or getattr(player_obj, "name", "Unknown")
            if leader_obj is not None and player_obj is leader_obj:
                tab_bar.setTabText(idx, f"{base_text} |")
            else:
                subgroup_index = getattr(player_obj, "subgroup_index", None)
                if isinstance(subgroup_index, int) and subgroup_index > 0:
                    tab_bar.setTabText(idx, f"{base_text} [{subgroup_index}]")
                else:
                    tab_bar.setTabText(idx, base_text)

    def _set_player_pid(self, player_obj, pid_value):
        if player_obj is None:
            return
        current_pid = getattr(player_obj, "PIDnum", None)
        if current_pid == pid_value:
            return
        player_obj.PIDnum = pid_value
        self._resort_player_group(player_obj)

    def _format_group_tab_title(self, group_key):
        if isinstance(group_key, int):
            return f"Group: {group_key + 1}"
        return f"Group: {group_key}"

    def _ensure_group_container(self, group_id):
        try:
            group_key = int(group_id)
        except (TypeError, ValueError):
            group_key = group_id
        if group_key in self.group_tab_infos:
            existing_info = self.group_tab_infos[group_key]
            widget = existing_info.get("widget") if isinstance(existing_info, dict) else None
            if isinstance(widget, QWidget):
                tab_index = self.tab_widget.indexOf(widget)
                if tab_index != -1:
                    self.tab_widget.setTabText(tab_index, self._format_group_tab_title(group_key))
            return existing_info
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        inner_tabs = QTabWidget(container)
        layout.addWidget(inner_tabs)
        inner_tabs.currentChanged.connect(lambda idx, gid=group_key: self._on_group_member_changed(gid, idx))
        group_info = {"widget": container, "tabs": inner_tabs, "members": set()}
        self.group_tab_infos[group_key] = group_info
        self._group_widget_to_id[container] = group_key
        self._inner_tab_to_group[inner_tabs] = group_key
        self.tab_widget.addTab(container, self._format_group_tab_title(group_key))
        return group_info

    def _organize_group_tabs(self, group_id, leader_obj, member_objs, subgroup_assignments=None):
        if leader_obj is None:
            return
        group_info = self._ensure_group_container(group_id)
        if isinstance(group_info, dict):
            group_info["leader"] = leader_obj
            if subgroup_assignments and isinstance(subgroup_assignments, dict):
                group_info["subgroup_assignments"] = dict(subgroup_assignments)
            else:
                group_info.pop("subgroup_assignments", None)
        participants = [leader_obj]
        participants.extend([m for m in member_objs if m is not None])
        for player_obj in participants:
            display_name = getattr(player_obj, "display_name", None) or getattr(player_obj, "name", "Unknown")
            self._move_player_to_group(player_obj, group_id)
            self._set_tab_text_for_player(player_obj, display_name)
        self._sort_group_tabs(group_id)
        group_widget = group_info.get("widget")
        if isinstance(group_widget, QWidget):
            self.tab_widget.setCurrentWidget(group_widget)
        leader_widget = self.player_widgets.get(leader_obj)
        inner_tabs = group_info.get("tabs")
        if isinstance(inner_tabs, QTabWidget) and leader_widget is not None:
            leader_index = inner_tabs.indexOf(leader_widget)
            if leader_index != -1:
                inner_tabs.setCurrentIndex(leader_index)
        self._update_current_player_index()

    def _move_player_to_group(self, player_obj, group_id):
        widget = self.player_widgets.get(player_obj)
        if widget is None:
            return
        group_info = self._ensure_group_container(group_id)
        target_tabs = group_info.get("tabs")
        if not isinstance(target_tabs, QTabWidget):
            return
        current_container = self.player_tab_containers.get(player_obj)
        if current_container is target_tabs:
            group_info["members"].add(player_obj)
            self.player_to_group[player_obj] = group_id
            return
        if isinstance(current_container, QTabWidget):
            current_index = current_container.indexOf(widget)
            if current_index != -1:
                current_container.removeTab(current_index)
            if current_container is not self.tab_widget:
                old_group_id = self._inner_tab_to_group.get(current_container)
                if old_group_id is not None:
                    old_info = self.group_tab_infos.get(old_group_id)
                    if old_info:
                        old_info["members"].discard(player_obj)
                        if not old_info["members"]:
                            self._remove_group_container(old_group_id)
        display_name = getattr(player_obj, "display_name", None) or getattr(player_obj, "name", "Unknown")
        target_tabs.addTab(widget, display_name)
        group_info["members"].add(player_obj)
        self.player_tab_containers[player_obj] = target_tabs
        self.player_to_group[player_obj] = group_id
        self._sort_group_tabs(group_id)

    def _move_player_to_main_tab(self, player_obj):
        widget = self.player_widgets.get(player_obj)
        if widget is None:
            return
        container = self.player_tab_containers.get(player_obj)
        if container is self.tab_widget:
            display_name = getattr(player_obj, "display_name", None) or getattr(player_obj, "name", "Unknown")
            self._set_tab_text_for_player(player_obj, display_name)
            return
        if isinstance(container, QTabWidget):
            tab_index = container.indexOf(widget)
            if tab_index != -1:
                container.removeTab(tab_index)
            group_id = self._inner_tab_to_group.get(container)
            if group_id is not None:
                group_info = self.group_tab_infos.get(group_id)
                if group_info:
                    group_info["members"].discard(player_obj)
                    if not group_info["members"]:
                        self._remove_group_container(group_id)
        display_name = getattr(player_obj, "display_name", None) or getattr(player_obj, "name", "Unknown")
        self.tab_widget.addTab(widget, display_name)
        self.player_tab_containers[player_obj] = self.tab_widget
        self.player_to_group[player_obj] = None
        if hasattr(player_obj, "subgroup_index"):
            player_obj.subgroup_index = None

    def _remove_group_container(self, group_id):
        group_info = self.group_tab_infos.pop(group_id, None)
        if not group_info:
            return
        container_widget = group_info.get("widget")
        inner_tabs = group_info.get("tabs")
        if isinstance(inner_tabs, QTabWidget):
            self._inner_tab_to_group.pop(inner_tabs, None)
        if isinstance(container_widget, QWidget):
            self._group_widget_to_id.pop(container_widget, None)
            tab_index = self.tab_widget.indexOf(container_widget)
            if tab_index != -1:
                self.tab_widget.removeTab(tab_index)
        self._update_current_player_index()

    def _remove_player_widget(self, player_obj):
        widget = self.player_widgets.pop(player_obj, None)
        container = self.player_tab_containers.pop(player_obj, None)
        self.player_to_group.pop(player_obj, None)
        if widget is not None:
            self.widget_to_player.pop(widget, None)
        if isinstance(container, QTabWidget) and widget is not None:
            tab_index = container.indexOf(widget)
            if tab_index != -1:
                container.removeTab(tab_index)
            if container is not self.tab_widget:
                group_id = self._inner_tab_to_group.get(container)
                if group_id is not None:
                    group_info = self.group_tab_infos.get(group_id)
                    if group_info:
                        group_info["members"].discard(player_obj)
                        if not group_info["members"]:
                            self._remove_group_container(group_id)

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

        self._remove_player_widget(player)
        self.open_tabs_names.pop(index)
        self.players.pop(index)
        self.text_editors.pop(index)
        self.start_stop_buttons.pop(index)

        # Ensure remaining players have up-to-date party information
        if should_refresh:
            self.refresh()
        else:
            self._update_current_player_index()

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
            subgroup_size=self.group_script_subgroup_size,
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

    def set_group_script_subgroup_size(self):
        current_value = max(0, int(getattr(self, "group_script_subgroup_size", 0)))
        value, ok = QInputDialog.getInt(
            self,
            "Number of members per subgroup",
            "Select the number of members for each subgroup (0 to disable):",
            current_value,
            0,
            24,
        )
        if not ok:
            return
        self.group_script_subgroup_size = value
        self.settings.setValue("groupScriptSubgroupSize", value)
        self._reapply_subgroup_assignments()

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
            self._set_player_pid(player_obj, pid)

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
            self.group_script_subgroup_size,
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

        incoming_assignments = {}
        if isinstance(group_info, dict):
            provided_assignments = group_info.get("member_subgroups")
            if isinstance(provided_assignments, dict):
                for name, value in provided_assignments.items():
                    if not isinstance(name, str):
                        continue
                    try:
                        subgroup_index = int(value)
                    except (TypeError, ValueError):
                        continue
                    if subgroup_index > 0:
                        incoming_assignments[name] = subgroup_index
        subgroup_size_override = None
        if isinstance(group_info, dict) and "subgroup_size" in group_info:
            try:
                subgroup_size_override = int(group_info.get("subgroup_size"))
            except (TypeError, ValueError):
                subgroup_size_override = None
            if subgroup_size_override is not None and subgroup_size_override < 0:
                subgroup_size_override = None

        new_members = set(member_objs)
        new_members.add(leader_obj)

        existing = self.console_groups.get(console)
        old_members = set()
        if existing:
            old_members = set(existing.get("members", set()))
        for player_obj in old_members - new_members:
            player_obj.group_console = None
            self._refresh_player_script_print(player_obj)

        console.set_leader_name(leader_obj.name)
        console.clear()

        for player_obj in new_members:
            player_obj.group_console = console
            self._refresh_player_script_print(player_obj)

        subgroup_assignments_by_name = {}
        if incoming_assignments:
            for player_obj in member_objs:
                index_value = incoming_assignments.get(player_obj.name)
                if isinstance(index_value, int) and index_value > 0:
                    subgroup_assignments_by_name[player_obj.name] = index_value
        if not subgroup_assignments_by_name:
            computed_assignments, _incomplete, _skipped = self._compute_subgroup_assignments(
                leader_obj,
                member_objs,
                subgroup_size_override,
            )
            for player_obj, subgroup_index in computed_assignments.items():
                name = getattr(player_obj, "name", None)
                if isinstance(name, str) and subgroup_index is not None:
                    subgroup_assignments_by_name[name] = subgroup_index

        if leader_obj is not None and hasattr(leader_obj, "subgroup_index"):
            leader_obj.subgroup_index = None
        for player_obj in member_objs:
            subgroup_index = subgroup_assignments_by_name.get(player_obj.name)
            if subgroup_index is not None:
                player_obj.subgroup_index = subgroup_index
            elif hasattr(player_obj, "subgroup_index"):
                player_obj.subgroup_index = None

        group_record = dict(existing) if isinstance(existing, dict) else {}
        group_record.update({"leader": leader_obj, "members": new_members})
        member_names = [p.name for p in member_objs]
        group_record["member_names"] = member_names
        if subgroup_assignments_by_name:
            group_record["subgroup_assignments"] = dict(subgroup_assignments_by_name)
        else:
            group_record.pop("subgroup_assignments", None)
        if subgroup_size_override is not None and subgroup_size_override > 0:
            group_record["subgroup_size"] = subgroup_size_override
        for key in ("group_id", "leader_path", "member_path"):
            if isinstance(group_info, dict) and key in group_info and group_info[key] is not None:
                group_record[key] = group_info[key]
        self.console_groups[console] = group_record
        self.leader_to_console[leader_obj] = console

        group_id = group_record.get("group_id")
        if group_id is None and isinstance(group_info, dict):
            group_id = group_info.get("group_id")
        if group_id is None:
            group_id = self.group_script_group_counter
        self._organize_group_tabs(group_id, leader_obj, member_objs, subgroup_assignments_by_name)

        for player_obj in new_members:
            if hasattr(player_obj, "flush_group_console_buffer"):
                try:
                    player_obj.flush_group_console_buffer()
                except Exception:
                    pass

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
                self._refresh_player_script_print(player_obj)

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
                if hasattr(player_obj, "reset_group_runtime"):
                    player_obj.reset_group_runtime()
            except Exception:
                pass

            try:
                self.start_stop_buttons[index][0].show()
                self.start_stop_buttons[index][1].hide()
            except Exception:
                pass

            try:
                self._set_tab_color_by_index(index, "white")
            except Exception:
                pass

            try:
                player_obj.reset_attrs()
            except Exception:
                pass
            player_obj.partyname = []
            player_obj.partyID = []
            if hasattr(player_obj, "subgroup_index"):
                player_obj.subgroup_index = None
            if hasattr(self, "_player_script_globals"):
                self._player_script_globals.pop(player_obj, None)
            try:
                self._move_player_to_main_tab(player_obj)
            except Exception:
                pass
            changed = True

        if changed:
            self.update_group_party_info()
            self._update_current_player_index()

    def _detach_player_console(self, player_obj):
        for console, info in list(self.console_groups.items()):
            members = set(info.get("members", set()))
            if player_obj not in members:
                continue

            members.discard(player_obj)
            info["members"] = members
            self.console_groups[console] = info
            if hasattr(player_obj, "subgroup_index"):
                player_obj.subgroup_index = None
            if info.get("leader") is player_obj:
                player_obj.group_console = None
                console.close()
                self._refresh_player_script_print(player_obj)
            else:
                if getattr(player_obj, "group_console", None) is console:
                    player_obj.group_console = None
                    self._refresh_player_script_print(player_obj)
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
                    self._set_player_pid(player_obj, pid)
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
                self.add_tab(info)
                # Ensure future refreshes match by PID for already-loaded scripts
                if self.players:
                    player_obj = self.players[-1][0]
                    self._set_player_pid(player_obj, pid)
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
                self._set_player_pid(player_obj, pid)
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
        self._update_current_player_index()

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

        player_obj = None
        if index < len(self.players):
            player_obj = self.players[index][0]
            self._set_tab_text_for_player(player_obj, new_name)
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
                player_obj = self.players[idx][0]
                self._set_tab_text_for_player(player_obj, current_name)
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

    def add_tab(self, char_info):
        # Create a new tab and add it to the tab widget
        self.no_client_found_label.setVisible(False)
        self.tab_widget.setVisible(True)
        tab = QWidget()
        display_name = char_info.get("display_name") or "Unknown"
        raw_name = char_info.get("raw_name")
        pid = char_info.get("pid")
        legacy_port = char_info.get("api_port")
        new_port = char_info.get("new_port")
        is_login_state = bool(char_info.get("is_login_state"))

        try:
            legacy_port_int = int(legacy_port) if legacy_port is not None else None
        except (TypeError, ValueError):
            legacy_port_int = None

        try:
            new_port_int = int(new_port) if new_port is not None else None
        except (TypeError, ValueError):
            new_port_int = None

        self.tab_widget.addTab(tab, display_name)
        self.open_tabs_names += [display_name]

        player_name = raw_name if raw_name else display_name
        player = Player(
            player_name,
            on_disconnect=self.player_disconnected,
            api_port=legacy_port_int,
            pid=pid,
            new_api_port=new_port_int,
        )
        player.display_name = display_name
        player.last_known_name = raw_name or display_name
        player.is_in_login_state = is_login_state
        player.condition_logging_enabled = self._condition_logging_enabled
        if legacy_port_int is not None:
            player.api_port = str(legacy_port_int)
            player.port = legacy_port_int
        if new_port_int is not None:
            player.new_api_port = str(new_port_int)
        else:
            player.new_api_port = None
        if pid is not None:
            self._set_player_pid(player, pid)
        player.is_connected = True
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

        self._register_player_widget(self.players[-1][0], tab)
        self._update_current_player_index()

    def start_script_clicked(self):
        context = self._get_current_player_context()
        if context is None:
            return

        text_editor = self.text_editors[context.index]
        script = text_editor.text()
        if script.strip():
            t = thread_with_trace(target=self.run_script, args=[script, context.index])
            t.start()
            self.players[context.index][0].stop_script = False
            self.players[context.index][1] = t
            self.start_stop_buttons[context.index][0].hide()
            self.start_stop_buttons[context.index][1].show()
        else:
            print("empty")

    def _iter_shared_script_globals(self):
        """Yield module-level globals that should be visible to scripts."""

        excluded = {"__builtins__", "__name__", "__package__", "__loader__", "__spec__", "__doc__"}
        for key, value in globals().items():
            if key not in excluded:
                yield key, value

    def _ensure_player_script_namespace(self, player_obj):
        """Return the persistent globals mapping used when executing scripts."""

        namespace = self._player_script_globals.get(player_obj)
        if namespace is None:
            namespace = {}
            self._player_script_globals[player_obj] = namespace

        for key, value in self._iter_shared_script_globals():
            namespace.setdefault(key, value)
        namespace["__builtins__"] = builtins.__dict__
        return namespace

    def _create_player_print(self, player_obj):
        """Create a ``print`` wrapper that targets ``player_obj``'s console."""

        player_ref = ref(player_obj)

        def player_print(*args, **kwargs):
            target = player_ref()
            if target is not None:
                target._console_print(*args, **kwargs)
            else:
                console_print(None, *args, **kwargs)

        return player_print

    def _refresh_player_script_print(self, player_obj):
        """Update the ``print`` binding for an existing player namespace."""

        namespace = self._player_script_globals.get(player_obj)
        if not namespace:
            return
        namespace["print"] = self._create_player_print(player_obj)

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

        context = self._get_current_player_context()
        if context is None:
            return

        player_obj = context.player
        thread = self.players[context.index][1]
        if thread:
            try:
                player_obj.stop_script = True
                thread.kill()
            except Exception:
                pass
            self.players[context.index][1] = None

        self.start_stop_buttons[context.index][0].show()
        self.start_stop_buttons[context.index][1].hide()
        self._set_tab_color_for_player(player_obj, "#e88113")
        
    def run_script(self, script, index=None):
        if index is None:
            context = self._get_current_player_context()
            if context is None:
                return
            index = context.index
        player = self.players[index][0]
        console = player.get_console_for_output()
        namespace = self._ensure_player_script_namespace(player)
        namespace["self"] = self
        namespace["player"] = proxy(player)
        namespace["index"] = index
        namespace["print"] = self._create_player_print(player)
        with use_group_console(console):
            try:
                # Execute the Python script in the context of this player
                self._set_tab_color_by_index(index, "green")
                exec(script, namespace, namespace)
                self._set_tab_color_by_index(index, "#e88113")
            except Exception as e:
                # Handle any exceptions that occur during execution
                print(f"Error executing script: {e}")
                self._set_tab_color_by_index(index, "red")

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
        self.start_stop_buttons[index][0].show()
        self.start_stop_buttons[index][1].hide()
        self.players[index][1] = None

    def open_condition_modifier(self):
        context = self._get_current_player_context()
        if context is None:
            return
        condition_editor = ConditionModifier(context.player)
        condition_editor.exec_()

    def save_script(self):
        file_dialog = QFileDialog()
        file_name, _ = file_dialog.getSaveFileName(self, "Save Script", "", "Text Files (*.txt);;All Files (*)")
        if file_name:
            context = self._get_current_player_context()
            if context is None:
                return
            with open(file_name, 'w') as file:
                text_editor = self.text_editors[context.index]
                file.write(text_editor.text())

    def load_script(self):
        file_dialog = QFileDialog()
        file_name, _ = file_dialog.getOpenFileName(self, "Load Script", "", "Text Files (*.txt);;All Files (*)")
        if file_name:
            context = self._get_current_player_context()
            if context is None:
                return
            with open(file_name, 'r') as file:
                text_editor = self.text_editors[context.index]
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

