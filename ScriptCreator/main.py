import sys
import os
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
)
from PyQt5.QtGui import (
    QColor,
    QPalette,
    QIcon,
    QStandardItemModel,
    QStandardItem,
)
from PyQt5.QtCore import Qt, QRectF, QLockFile, QSettings
from PyQt5.Qsci import QsciScintilla

from license_manager import prompt_for_license

from player import Player
from getports import returnAllPorts
from funcs import randomize_time
from conditioncreator import ConditionModifier
from editor import Editor

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
    def __init__(self, players, text_editors, leader_path, member_path, group_id, leaders):
        super().__init__()

        self.players = players
        self.text_editors = text_editors
        self.leader_path = leader_path
        self.member_path = member_path
        self.group_id = group_id
        # Predefined leaders to exclude from auto-selection and member listing
        self.leaders = leaders

        self.setWindowTitle("Group Script Setup")
        self.setWindowIcon(QIcon('src/icon.png'))

        leader_names = self.leaders
        member_names = [
            p[0].name
            for p in players
            if p[0].name not in leader_names and not p[0].script_loaded
        ]

        self.leader_combo = CheckableComboBox(max_checked=1)
        self.leader_combo.addItems(leader_names)
        self.leader_combo.setMinimumWidth(200)

        self.members_combo = CheckableComboBox(max_checked=8)
        self.members_combo.addItems(member_names)
        self.members_combo.setMinimumWidth(200)

        layout = QGridLayout()
        layout.addWidget(QLabel("Leader"), 0, 0)
        layout.addWidget(self.leader_combo, 0, 1)
        layout.addWidget(QLabel("Members"), 1, 0)
        layout.addWidget(self.members_combo, 1, 1)

        load_button = QPushButton("Load")
        load_button.clicked.connect(self.load_setup)
        all_button = QPushButton("All")
        all_button.clicked.connect(self.select_all_members)
        layout.addWidget(load_button, 2, 0)
        layout.addWidget(all_button, 2, 1)

        self.setLayout(layout)

    def select_all_members(self):
        selected_leaders = set(self.leader_combo.checkedItems())
        leaders = set(self.leaders) | selected_leaders
        eligible = [p[0].name for p in self.players if not p[0].script_loaded and p[0].name not in leaders]
        # Respect maximum allowed members
        eligible = eligible[: self.members_combo.max_checked]
        for i in range(self.members_combo.model().rowCount()):
            item = self.members_combo.model().item(i)
            if item.text() in eligible:
                item.setCheckState(Qt.Checked)
            else:
                item.setCheckState(Qt.Unchecked)
        self.members_combo.updateText()

    def load_setup(self):
        leader_names = self.leader_combo.checkedItems()
        member_names = self.members_combo.checkedItems()

        if len(leader_names) != 1:
            QMessageBox.warning(self, "Invalid Selection", "Please select exactly one leader.")
            return
        if len(member_names) > 8:
            QMessageBox.warning(self, "Invalid Selection", "Please select up to eight members.")
            return
        if leader_names[0] in member_names:
            QMessageBox.warning(self, "Invalid Selection", "Leader cannot be selected as member.")
            return

        leader_name = leader_names[0]

        roles = {leader_name: (self.leader_path, "leader")}
        for m in member_names:
            roles[m] = (self.member_path, "member")

        leader_obj = None

        for idx, (player_obj, _) in enumerate(self.players):
            if player_obj.name not in roles:
                continue

            player_obj.reset_attrs()

            setup_path, role = roles[player_obj.name]
            script_dir = os.path.join(setup_path, "script")
            cond_dir = os.path.join(setup_path, "conditions")

            if not os.path.isdir(script_dir) or not os.path.isdir(cond_dir):
                QMessageBox.warning(self, "Load Failed", f"Invalid setup folder: {setup_path}")
                return

            script_files = sorted([f for f in os.listdir(script_dir) if f.endswith('.txt')])
            if not script_files:
                QMessageBox.warning(self, "Load Failed", f"No scripts found in {script_dir}")
                return

            if role == "leader":
                chosen = next((s for s in script_files if "setup1" in s.lower() or "leader" in s.lower()), script_files[0])
            else:
                chosen = next((s for s in script_files if "follow" in s.lower() or "member" in s.lower()), script_files[0])

            with open(os.path.join(script_dir, chosen), "r") as file:
                script_text = file.read()

            cond_files = sorted([f for f in os.listdir(cond_dir) if f.endswith('.txt')])
            cond_data = []
            for cf in cond_files:
                with open(os.path.join(cond_dir, cf), "r") as cfile:
                    c_type = cfile.readline().strip()
                    running = cfile.readline().strip()
                    script = cfile.read().strip()
                cond_data.append((os.path.splitext(cf)[0], c_type, script, running))

            self.text_editors[idx].setText(script_text)
            player_obj.recv_packet_conditions = []
            player_obj.send_packet_conditions = []
            player_obj.periodical_conditions = []

            for name, ctype, cscript, running in cond_data:
                running_bool = True if running == "1" else False
                if ctype == "recv_packet":
                    player_obj.recv_packet_conditions.append([name, cscript, running_bool])
                elif ctype == "send_packet":
                    player_obj.send_packet_conditions.append([name, cscript, running_bool])
                else:
                    player_obj.periodical_conditions.append([name, cscript, running_bool, 1])

            if role == "leader":
                player_obj.attr19 = 0
                player_obj.attr20 = player_obj.name
                leader_obj = player_obj
            else:
                player_obj.attr19 = self.group_id
                player_obj.attr20 = leader_name
                player_obj.script_loaded = True
            player_obj.attr13 = 0

        if leader_obj:
            leader_obj.attr51 = member_names

        QMessageBox.information(self, "Group Script Setup", "Setup successfully loaded.")
        self.accept()

class MyWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.settings = QSettings('PBapi', 'Script Creator')
        windowScreenGeometry = self.settings.value("windowScreenGeometry")
        self.colorTheme = self.settings.value("colorTheme")
        # Default to showing the console when no previous preference exists
        self.console = int(self.settings.value("console", 1))
        self.group_leader_setup_path = self.settings.value("groupLeaderSetupPath")
        self.group_member_setup_path = self.settings.value("groupMemberSetupPath")
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
                periodic_conds.append([condition[0], condition[1], condition[2], "periodical"])

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
        try:
            index = next(i for i, p in enumerate(self.players) if p[0] == player)
        except StopIteration:
            return

        player.recv_packet_conditions = []
        player.send_packet_conditions = []
        player.periodical_conditions = []
        player.script_loaded = False

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
        )
        if dlg.exec_():
            self.group_script_group_counter += 1

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

    def refresh(self):
        all_chars = returnAllPorts()
        all_chars = sorted(all_chars, key=lambda x: x[0])
        for i in range(len(all_chars)):
            if all_chars[i][0] not in self.open_tabs_names:
                self.add_tab(all_chars[i][0])

        current_names = [p[0] for p in all_chars]
        self.group_leaders = [name for name in self.group_leaders if name in current_names]
        
        tabs_to_remove = []
        for i in range(len(self.open_tabs_names)):
            if self.open_tabs_names[i] not in [player[0] for player in all_chars]:
                tabs_to_remove.append(i)

        for i in tabs_to_remove[::-1]:
            self.open_tabs_names.pop(i)
            self.tab_widget.removeTab(i)
            self.players.pop(i)
        
        if len(all_chars) == 0:
            self.no_client_found_label.setVisible(True)
            self.tab_widget.setVisible(False)
            self.loadAction.setEnabled(False)
            self.saveAction.setEnabled(False)
        else:
            self.loadAction.setEnabled(True)
            self.saveAction.setEnabled(True)

    def add_tab(self, char_name):
        # Create a new tab and add it to the tab widget
        self.no_client_found_label.setVisible(False)
        self.tab_widget.setVisible(True)
        tab = QWidget()
        self.tab_widget.addTab(tab, char_name)
        self.open_tabs_names += [char_name]

        player = Player(char_name, on_disconnect=self.player_disconnected)
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
        index = self.tab_widget.currentIndex()
        try:
            # Execute the Python script
            self.tab_widget.tabBar().setTabTextColor(index, QColor("green"))
            exec(script)
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

