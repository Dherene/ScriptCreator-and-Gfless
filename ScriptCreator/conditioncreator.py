from PyQt5.QtWidgets import (
    QPushButton,
    QTableView,
    QFileDialog,
    QTableWidgetItem,
    QTableWidget,
    QPlainTextEdit,
    QCheckBox,
    QMessageBox,
    QGroupBox,
    QDialog,
    QVBoxLayout,
    QGridLayout,
    QLabel,
    QComboBox,
    QLineEdit,
    QSizePolicy,
)
from PyQt5.QtCore import QTimer, Qt, QSettings, QSize
from PyQt5.QtGui import QFont, QFontMetricsF, QColor, QIcon, QIntValidator
import os
import re
import gfless_api

from player import PeriodicCondition

class ConditionReview(QDialog):
    def __init__(self, player, script, condition_type, cond_modifier, cond_creator, replace_index = None, cond_name = None):
        super().__init__()
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.player = player
        self.condition_type = condition_type
        self.cond_modifier = cond_modifier
        self.cond_creator = cond_creator
        self.index_to_replace = replace_index

        self.setWindowIcon(QIcon('src/icon.png'))

        if condition_type == 0:
            self.setWindowTitle("Periodical Condition Review")
            condition_name = f"my periodical condition {len(self.player.periodical_conditions)+1}"
        elif condition_type == 1:
            self.setWindowTitle("Recv Packet Condition Review")
            condition_name = f"my recv packet condition {len(self.player.recv_packet_conditions)+1}"
        elif condition_type == 2:
            self.setWindowTitle("Send Packet Condition Review")
            condition_name = f"my send packet condition {len(self.player.send_packet_conditions)+1}"

        if cond_name is not None:
            condition_name = cond_name

        self.main_layout = QGridLayout()
        
        condition_name_label = QLabel("Name of your condition: ")
        self.main_layout.addWidget(condition_name_label, 0, 0, 1, 1)

        self.condition_name = QLineEdit(condition_name)
        if cond_name is not None:
            self.condition_name.setEnabled(False)
        self.main_layout.addWidget(self.condition_name, 0, 1, 1, 1)

        self.allow_edit_checkbox = QCheckBox("Allow editing")
        self.allow_edit_checkbox.stateChanged.connect(self.allow_edit)
        self.main_layout.addWidget(self.allow_edit_checkbox, 0, 2, 1, 1)

        self.generated_script = QPlainTextEdit()
        self.generated_script.setPlainText(script)
        self.generated_script.setReadOnly(True)

        # Set the line wrap mode to NoWrap
        self.generated_script.setLineWrapMode(QPlainTextEdit.NoWrap)

        font = QFont("Cascadia Code", 9)
        self.generated_script.setFont(font)
        # Set the stylesheet for the entire QPlainTextEdit
        self.generated_script.setStyleSheet("background-color: #201c1c; color: orange;")

        # Set the stylesheet for the vertical scrollbar
        self.generated_script.verticalScrollBar().setStyleSheet('''
            QTableWidget {
                background-color: rgb(32, 28, 28);
                color: rgb(255, 255, 255);
            }
        
            /* VERTICAL SCROLLBAR */
            QScrollBar:vertical {
                border: none;
                background: rgb(32, 28, 28);
                width: 14px;
            }
        
            /* HANDLE BAR VERTICAL */
            QScrollBar::handle:vertical {
                background-color: rgb(82, 81, 81);
                min-height: 30px;
            }
            QScrollBar::handle:vertical:hover {
                background-color: rgb(148, 148, 148);
            }
        
            /* HIDE ARROWS */
            QScrollBar::up-arrow:vertical, QScrollBar::down-arrow:vertical {
                image: none;
                background: rgb(32, 28, 28);
                                    
            }
        
            QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {
                background: rgb(32, 28, 28);
            }
        ''')
        
        self.generated_script.horizontalScrollBar().setStyleSheet('''
            QTableWidget {
                background-color: rgb(32, 28, 28);
                color: rgb(255, 255, 255);
            }
        
            /* HORIZONTAL SCROLLBAR */
            QScrollBar:horizontal {
                border: none;
                background: rgb(32, 28, 28);
                height: 14px;
            }
        
            /* HANDLE BAR HORIZONTAL */
            QScrollBar::handle:horizontal {
                background-color: rgb(82, 81, 81);
                min-width: 30px;
            }
            QScrollBar::handle:horizontal:hover {
                background-color: rgb(148, 148, 148);
            }
        
            /* HIDE ARROWS */
            QScrollBar::left-arrow:horizontal, QScrollBar::right-arrow:horizontal {
                image: none;
                background: rgb(32, 28, 28);
            }
        
            QScrollBar::add-page:horizontal, QScrollBar::sub-page:horizontal {
                background: rgb(32, 28, 28);
            }
        ''')

        fontMetrics = QFontMetricsF(font)
        spaceWidth = fontMetrics.width(' ')
        self.generated_script.setTabStopDistance(spaceWidth * 4)
        self.main_layout.addWidget(self.generated_script, 1, 0, 3, 3) 

        self.add_condition_button = QPushButton("Add Condition")
        self.add_condition_button.clicked.connect(self.add_condition)
        self.main_layout.addWidget(self.add_condition_button, 5, 0, 1, 1)

        self.add_and_run_condition_button = QPushButton("Add And Run Condition")
        self.add_and_run_condition_button.clicked.connect(self.add_and_run_condition)
        self.main_layout.addWidget(self.add_and_run_condition_button, 5, 1, 1, 1)

        self.modify_condition_button = QPushButton("Confirm condition changes")
        self.modify_condition_button.clicked.connect(self.modify_condition)
        self.main_layout.addWidget(self.modify_condition_button, 5, 0, 1, 1)

        if cond_name is None:
            self.modify_condition_button.setVisible(False)
        else:
            self.add_and_run_condition_button.setVisible(False)
            self.add_condition_button.setVisible(False)
            self.allow_edit_checkbox.setChecked(True)
        self.setLayout(self.main_layout)

    def modify_condition(self):
        script = self.generated_script.toPlainText()
        if self.condition_type == 1:
            self.player.recv_packet_conditions[self.index_to_replace][1] = script
        elif self.condition_type == 2:
            self.player.send_packet_conditions[self.index_to_replace][1] = script
        self.cond_modifier.refresh()
        self.accept()

    def add_condition(self):
        script = self.generated_script.toPlainText()
        if self.condition_type == 1:
            for i in range(len(self.player.recv_packet_conditions)):
                if self.player.recv_packet_conditions[i][0] == self.condition_name.text():
                    self.condition_name_already_exists_msg_box()
                    return
            self.player.recv_packet_conditions.append([self.condition_name.text(),script, False])
        elif self.condition_type == 2:
            for i in range(len(self.player.send_packet_conditions)):
                if self.player.send_packet_conditions[i][0] == self.condition_name.text():
                    self.condition_name_already_exists_msg_box()
                    return
            self.player.send_packet_conditions.append([self.condition_name.text(), script, False])
        else:
            for cond in self.player.periodical_conditions:
                if cond.name == self.condition_name.text():
                    self.condition_name_already_exists_msg_box()
                    return
            self.player.periodical_conditions.append(
                PeriodicCondition(self.condition_name.text(), script, False, 1)
            )
        # start condition checks if needed
        self.player.start_condition_loop()
        self.cond_modifier.refresh()
        self.cond_creator.accept()
        self.accept()

    def add_and_run_condition(self):
        script = self.generated_script.toPlainText()
        if self.condition_type == 1:
            for i in range(len(self.player.recv_packet_conditions)):
                if self.player.recv_packet_conditions[i][0] == self.condition_name.text():
                    self.condition_name_already_exists_msg_box()
                    return
            self.player.recv_packet_conditions.append([self.condition_name.text(), script, True])
        elif self.condition_type == 2:
            for i in range(len(self.player.send_packet_conditions)):
                if self.player.send_packet_conditions[i][0] == self.condition_name.text():
                    self.condition_name_already_exists_msg_box()
                    return
            self.player.send_packet_conditions.append([self.condition_name.text(), script, True])
        else:
            for cond in self.player.periodical_conditions:
                if cond.name == self.condition_name.text():
                    self.condition_name_already_exists_msg_box()
                    return
            self.player.periodical_conditions.append(
                PeriodicCondition(self.condition_name.text(), script, True, 1)
            )
        self.player.start_condition_loop()
        self.cond_modifier.refresh()
        self.cond_creator.accept()
        self.accept()

    def condition_name_already_exists_msg_box(self):
        message_box = QMessageBox()
        message_box.setIcon(QMessageBox.Warning)
        message_box.setText(f"Condition with this name already exists.\n")
        message_box.setStandardButtons(QMessageBox.Ok)
        message_box.setDefaultButton(QMessageBox.Ok)
        message_box.setWindowTitle("Wrong Condition Name")
        message_box.exec_()
        return

    def allow_edit(self):
        if self.allow_edit_checkbox.isChecked():
            self.generated_script.setReadOnly(False)
        else:
            self.generated_script.setReadOnly(True)

    def closeEvent(self, event):
        self.cond_modifier.refresh()
        event.accept()

class ConditionCreator(QDialog):
    def __init__(self, player, cond_modifier):
        super().__init__()
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.player = player
        self.cond_modifier = cond_modifier

        self.setWindowTitle("Condition Creator")
        self.setWindowIcon(QIcon('src/icon.png'))

        # Start with a larger resizable dialog and restore last size
        self.settings = QSettings('PBapi', 'Script Creator')
        last_size = self.settings.value(
            "condition_creator_size", QSize(650, 250), type=QSize
        )
        self.resize(last_size)
        self.setMinimumSize(650, 250)
        self.setSizeGripEnabled(True)

        self.condition_widgets = []
        self.condition_group_box = []

        self.action_widgets = []
        self.action_group_boxes = []

        # Create main layout
        self.main_layout = QGridLayout()
        for i in range(6):
            self.main_layout.setColumnStretch(i, 1)

        # Add a + button at the bottom
        self.add_condition_button = QPushButton("+")
        self.add_condition_button.clicked.connect(self.add_new_condition)
        self.main_layout.addWidget(self.add_condition_button, 2, 5, 1, 1)

        # Add a - button at the bottom
        self.remove_condition_button = QPushButton("-")
        self.remove_condition_button.clicked.connect(self.remove_last_condition)
        self.main_layout.addWidget(self.remove_condition_button, 2, 4, 1, 1)
        self.remove_condition_button.setVisible(False)

        # add a review button at the bottom
        self.review_button = QPushButton("review")
        self.review_button.clicked.connect(self.review_condition)
        self.main_layout.addWidget(self.review_button, 4, 0, 1, 3)

        # Add a + button at the bottom
        self.add_action_button = QPushButton("+")
        self.add_action_button.clicked.connect(self.add_new_action)
        self.main_layout.addWidget(self.add_action_button, 4, 5, 1, 1)

        # Add a - button at the bottom
        self.remove_action_button = QPushButton("-")
        self.remove_action_button.clicked.connect(self.remove_last_action)
        self.main_layout.addWidget(self.remove_action_button, 4, 4, 1, 1)
        self.remove_action_button.setVisible(False)

        # Create a vertical layout to hold the group boxes
        self.group_boxes_layout = QVBoxLayout()
        self.main_layout.addLayout(self.group_boxes_layout, 3, 0, 1, 6)

        self.cond_helper_label = QLabel(
            "Tip: cond.on / cond.off require the target condition's number "
            "in the sequential conditions list. Use cond.off = 0 to disable "
            "all other active conditions while keeping the calling one running."
        )
        self.cond_helper_label.setWordWrap(True)
        self.main_layout.addWidget(self.cond_helper_label, 5, 0, 1, 6)

        #self.setMaximumWidth(500)
        #self.setMinimumWidth(500)

        self.setLayout(self.main_layout)

        # Create a timer to call adjustSize every 0.01 seconds
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.adjust_size_periodically)
        self.timer.start(100)

        self.add_new_condition()
        self.add_new_action()

    def add_new_condition(self):
        try:
            self.condition_group_box.deleteLater()
            text_list = ["AND IF", "AND IF NOT"]
            self.remove_condition_button.setVisible(True)
        except:
            text_list = ["IF", "IF NOT"]

        # Create condition group box and set layout
        condition_group_box = QGroupBox("Conditions")
        condition_group_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)


        if_combobox = QComboBox()
        if_combobox.addItems(text_list)

        combo_condition = QComboBox()
        combo_condition.setStyleSheet("QComboBox { combobox-popup: 0; }")
        
        elements_list = [
            "recv_packet",
            "send_packet",
            "split_recv_packet",
            "split_send_packet",
            "pos_x",
            "pos_y",
            "id",
            "name",
            "map_id",
            "level",
            "champion_level",
            "hp_percent",
            "mp_percent",
            "is_resting",
            "time.cond",
        ]
        for i in range(1, 101):
            elements_list.append(f"attr{i}")
        combo_condition.addItems(elements_list)
        combo_condition.currentIndexChanged.connect(self.update_condition_widgets)
        combo_condition.setProperty("index", len(self.condition_widgets))

        combo_operator = QComboBox()
        combo_operator.addItems(["startswith", "contains", "endswith", "equals"])

        var_type = QComboBox()
        var_type.addItems(["string", "int", "raw"])

        delimeter_combo = QComboBox()
        delimeter_combo.addItems([" ", "^", "#", "."])
        delimeter_combo.setVisible(False)

        index_list = []
        index_combo = QComboBox()
        for i in range(100):
            index_list.append(f"{i}")
        index_combo.addItems(index_list)
        index_combo.setVisible(False)

        text_edit_expression = QLineEdit()

        self.condition_widgets.append([if_combobox, combo_condition, index_combo, combo_operator, text_edit_expression, delimeter_combo, var_type])
        self.condition_group_box = condition_group_box

        condition_layout = QGridLayout()

        for i in range(len(self.condition_widgets)):
            for j in range(len(self.condition_widgets[i])):
                condition_layout.addWidget(self.condition_widgets[i][j], i, j)
                condition_layout.setColumnStretch(j, 1)

        # Create condition group box and set layout
        condition_group_box.setLayout(condition_layout)

        # Add condition group box to the main layout
        self.main_layout.addWidget(condition_group_box, 0, 0, 1, 6)

    def remove_last_condition(self):
        for condition in self.condition_widgets[-1]:
            condition.deleteLater()
        
        self.condition_widgets.pop(-1)

        if len(self.condition_widgets) < 2:
            self.remove_condition_button.setVisible(False)

    def add_new_action(self):
        new_action_combobox = QComboBox()
        new_min_wait_label = QLabel("min:")
        new_min_wait = QLineEdit("0.75")
        new_max_wait_label = QLabel("max:")
        new_max_wait = QLineEdit("1.5")
        elements_list = [
            "wait", "walk_to_point", "send_packet", "recv_packet",
            "cond.on", "cond.off",
            "start_bot", "stop_bot", "continue_bot", "load_settings",
            "attack", "player_skill", "player_walk", "pets_walk",
            "start_minigame_bot", "stop_minigame_bot", "use_item", "put_item_in_trade", 
            "auto_login", "relogin", "python_code", "delete_condition", "close_game",
            "invite_members"
        ]
        for i in range(1, 101):
            elements_list.append(f"attr{i}")
        new_action_combobox.setStyleSheet("QComboBox { combobox-popup: 0; }")
        new_action_combobox.addItems(elements_list)
        row_position = len(self.action_widgets) + 1

        # Create a group box for the new set of widgets
        group_box = QGroupBox(f"action {row_position}")
        group_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        group_box_layout = QGridLayout()
        group_box_layout.addWidget(new_action_combobox, 0, 0)
        group_box_layout.addWidget(new_min_wait_label, 0, 1)
        group_box_layout.addWidget(new_min_wait, 0, 2)
        group_box_layout.addWidget(new_max_wait_label, 0, 3)
        group_box_layout.addWidget(new_max_wait, 0, 4)
        for col in range(5):
            group_box_layout.setColumnStretch(col, 1)
        group_box.setLayout(group_box_layout)

        # Add the group box to the main layout
        self.group_boxes_layout.addWidget(group_box)

        # Connect the currentIndexChanged signal of the new combo box to update_action_widgets function
        index = len(self.action_widgets)
        new_action_combobox.currentIndexChanged.connect(lambda: self.update_action_widgets(index))
        self.action_widgets.append([new_action_combobox, new_min_wait, new_max_wait, new_min_wait_label, new_max_wait_label, group_box_layout])
        
        if len(self.action_widgets) > 1:
            self.remove_action_button.setVisible(True)

        self.action_group_boxes.append(group_box)

    def remove_last_action(self):
        for i in range(len(self.action_widgets[-1])):
            last_action_widgets = self.action_widgets[-1]
            widget_to_delete = last_action_widgets[i]
            widget_to_delete.deleteLater()

        self.action_group_boxes[-1].deleteLater()
        self.action_group_boxes.pop(len(self.action_group_boxes)-1)
        self.action_widgets.pop(len(self.action_widgets)-1)

        if len(self.action_widgets) < 2:
            self.remove_action_button.setVisible(False)

    def update_action_widgets(self, index):
        group_box_layout = self.action_widgets[index][-1]

        for i in range(1, len(self.action_widgets[index])-1):
            self.action_widgets[index][i].deleteLater()

        self.action_widgets[index] = [self.action_widgets[index][0]]

        condition = self.action_widgets[index][0].currentText()

        if condition == "wait":
            new_min_wait = QLineEdit("0.75")
            new_min_wait_label = QLabel("min:")
            new_max_wait = QLineEdit("1.5")
            new_max_wait_label = QLabel("max:")

            group_box_layout.addWidget(new_min_wait_label, 0, 2)
            group_box_layout.addWidget(new_min_wait, 0, 3)
            group_box_layout.addWidget(new_max_wait_label, 0, 4)
            group_box_layout.addWidget(new_max_wait, 0, 5)

            self.action_widgets[index].append(new_min_wait_label)
            self.action_widgets[index].append(new_min_wait)
            self.action_widgets[index].append(new_max_wait_label)
            self.action_widgets[index].append(new_max_wait)
        elif condition == "send_packet" or condition == "recv_packet":
            new_packet_label = QLabel("Packet:")
            new_packet = QLineEdit()
            new_type_decision = QComboBox()
            new_type_decision.addItems(["string","int", "raw"])

            group_box_layout.addWidget(new_packet_label, 0, 2)
            group_box_layout.addWidget(new_packet, 0, 3)
            group_box_layout.addWidget(new_type_decision, 0, 4)

            self.action_widgets[index].append(new_packet_label)
            self.action_widgets[index].append(new_packet)
            self.action_widgets[index].append(new_type_decision)

        elif condition == "cond.on" or condition == "cond.off":
            index_label = QLabel("number:")
            index_input = QLineEdit()
            index_input.setValidator(QIntValidator(1, 9999, index_input))
            index_input.setPlaceholderText("Sequential list index")
            index_input.setToolTip(
                "Specify the condition number from the sequential list."
            )

            group_box_layout.addWidget(index_label, 0, 2)
            group_box_layout.addWidget(index_input, 0, 3)

            self.action_widgets[index].append(index_label)
            self.action_widgets[index].append(index_input)

        elif condition == "walk_to_point" or condition == "player_walk" or condition == "pets_walk":
            new_x = QLineEdit()
            new_x_label = QLabel("x:")
            new_y = QLineEdit()
            new_y_label = QLabel("y:")
            group_box_layout.addWidget(new_x_label, 0, 2)
            group_box_layout.addWidget(new_x, 0, 3)
            group_box_layout.addWidget(new_y_label, 0, 4)
            group_box_layout.addWidget(new_y, 0, 5)

            self.action_widgets[index].append(new_x_label)
            self.action_widgets[index].append(new_x)
            self.action_widgets[index].append(new_y_label)
            self.action_widgets[index].append(new_y)

            if condition == "walk_to_point":
                new_radius = QLineEdit("0")
                new_radius_label = QLabel("radius:")
                new_radius.setToolTip("Numero de celdas alrededor del punto")
                new_radius.setPlaceholderText("celdas")

                group_box_layout.addWidget(new_radius_label, 0, 6)
                group_box_layout.addWidget(new_radius, 0, 7)

                self.action_widgets[index].append(new_radius_label)
                self.action_widgets[index].append(new_radius)

                skip_timeout_checkbox = QCheckBox("custom")
                skip_label = QLabel("skip:")
                skip_input = QLineEdit("4")
                timeout_label = QLabel("timeout:")
                timeout_input = QLineEdit("3")

                skip_label.setEnabled(False)
                skip_input.setEnabled(False)
                timeout_label.setEnabled(False)
                timeout_input.setEnabled(False)

                def toggle_skip_timeout(state, s_label=skip_label, s_input=skip_input, t_label=timeout_label, t_input=timeout_input):
                    enabled = state == Qt.Checked
                    s_label.setEnabled(enabled)
                    s_input.setEnabled(enabled)
                    t_label.setEnabled(enabled)
                    t_input.setEnabled(enabled)

                skip_timeout_checkbox.stateChanged.connect(toggle_skip_timeout)

                group_box_layout.addWidget(skip_timeout_checkbox, 0, 8)
                group_box_layout.addWidget(skip_label, 0, 9)
                group_box_layout.addWidget(skip_input, 0, 10)
                group_box_layout.addWidget(timeout_label, 0, 11)
                group_box_layout.addWidget(timeout_input, 0, 12)

                self.action_widgets[index].append(skip_timeout_checkbox)
                self.action_widgets[index].append(skip_label)
                self.action_widgets[index].append(skip_input)
                self.action_widgets[index].append(timeout_label)
                self.action_widgets[index].append(timeout_input)
        elif condition == "load_settings":
            new_settings_path_label = QLabel("Settings path:")
            new_settings_path = QLineEdit()

            group_box_layout.addWidget(new_settings_path_label, 0, 2)
            group_box_layout.addWidget(new_settings_path, 0, 3)

            self.action_widgets[index].append(new_settings_path_label)
            self.action_widgets[index].append(new_settings_path)
        elif condition == "use_item":
            new_item_vnum_label = QLabel("VNUM: ")
            new_item_vnum = QLineEdit()

            new_inventory_type = QComboBox()
            new_inventory_type.addItems(["equip","main", "etc"])

            group_box_layout.addWidget(new_item_vnum_label, 0, 2)
            group_box_layout.addWidget(new_item_vnum, 0, 3)
            group_box_layout.addWidget(new_inventory_type, 0, 4)

            self.action_widgets[index].append(new_item_vnum_label)
            self.action_widgets[index].append(new_item_vnum)
            self.action_widgets[index].append(new_inventory_type)
        elif condition == "put_item_in_trade":
            for n in range(10):
                inv_combo = QComboBox()
                inv_combo.addItems(["equip", "main", "etc"])
                v_label = QLabel(f"VNUM {n+1}:")
                v_edit = QLineEdit()
                q_label = QLabel("qty:")
                q_edit = QLineEdit()

                group_box_layout.addWidget(inv_combo, n, 2)
                group_box_layout.addWidget(v_label, n, 3)
                group_box_layout.addWidget(v_edit, n, 4)
                group_box_layout.addWidget(q_label, n, 5)
                group_box_layout.addWidget(q_edit, n, 6)

                self.action_widgets[index].extend([inv_combo, v_label, v_edit, q_label, q_edit])
        elif condition == "auto_login":
            # Use comboboxes similar to the Server Configuration dialog
            lang_label = QLabel("Language:")
            lang_combo = QComboBox()
            lang_combo.addItems([
                "International/English",
                "German",
                "French",
                "Italian",
                "Polish",
                "Spanish",
            ])

            server_label = QLabel("Server:")
            server_combo = QComboBox()
            server_combo.addItems([str(i) for i in range(1, 5)])

            channel_label = QLabel("Channel:")
            channel_combo = QComboBox()
            channel_combo.addItems([str(i) for i in range(1, 8)])

            char_label = QLabel("Character:")
            char_combo = QComboBox()
            char_combo.addItem("Stay at character selection")
            char_combo.addItems([str(i) for i in range(1, 5)])

            widgets = [
                (lang_label, 0, 2), (lang_combo, 0, 3),
                (server_label, 1, 2), (server_combo, 1, 3),
                (channel_label, 2, 2), (channel_combo, 2, 3),
                (char_label, 3, 2), (char_combo, 3, 3),
            ]

            for w, r, c in widgets:
                group_box_layout.addWidget(w, r, c)

            group_box_layout.setColumnStretch(3, 1)

            self.action_widgets[index].extend([
                lang_label, lang_combo,
                server_label, server_combo,
                channel_label, channel_combo,
                char_label, char_combo,
            ])
        elif condition == "relogin":
            pid_label = QLabel("pid:")
            pid_edit = QLineEdit("pidnum")
            group_box_layout.addWidget(pid_label, 0, 2)
            group_box_layout.addWidget(pid_edit, 0, 3)
            self.action_widgets[index].append(pid_label)
            self.action_widgets[index].append(pid_edit)
        elif condition == "python_code":
            new_equals_label = QLabel("=")
            new_python_code = QLineEdit()

            group_box_layout.addWidget(new_equals_label, 0, 2)
            group_box_layout.addWidget(new_python_code, 0, 3)

            self.action_widgets[index].append(new_equals_label)
            self.action_widgets[index].append(new_python_code)
        elif condition.startswith("attr"):
            new_equals_label = QLabel("=")
            new_equals = QLineEdit()
            new_str_or_raw = QComboBox()
            new_str_or_raw.addItems(["string","int", "raw"])

            group_box_layout.addWidget(new_equals_label, 0, 2)
            group_box_layout.addWidget(new_equals, 0, 3)
            group_box_layout.addWidget(new_str_or_raw, 0, 4)

            self.action_widgets[index].append(new_equals_label)
            self.action_widgets[index].append(new_equals)
            self.action_widgets[index].append(new_str_or_raw)
        elif condition == "attack":
            new_monster_id_label = QLabel("monster_id: ")
            new_monster_id = QLineEdit()

            group_box_layout.addWidget(new_monster_id_label, 0, 2)
            group_box_layout.addWidget(new_monster_id, 0, 3)

            self.action_widgets[index].append(new_monster_id_label)
            self.action_widgets[index].append(new_monster_id)
        elif condition == "player_skill":
            new_monster_id_label = QLabel("monster_id: ")
            new_monster_id = QLineEdit()
            new_skill_id_label = QLabel("skill_id: ")
            new_skill_id = QLineEdit()

            group_box_layout.addWidget(new_monster_id_label, 0, 2)
            group_box_layout.addWidget(new_monster_id, 0, 3)
            group_box_layout.addWidget(new_skill_id_label, 0, 4)
            group_box_layout.addWidget(new_skill_id, 0, 5)

            self.action_widgets[index].append(new_monster_id_label)
            self.action_widgets[index].append(new_monster_id)
            self.action_widgets[index].append(new_skill_id_label)
            self.action_widgets[index].append(new_skill_id)
        elif condition == "close_game":
            # no additional widgets needed for closing the game
            pass

        self.action_widgets[index].append(group_box_layout)

    def review_condition(self):
        conditions_array = []

        for row in self.condition_widgets:
            new_row = []
            for i in range(len(row)):
                if row[i].__class__.__name__ == "QLineEdit":
                    new_row.append(row[i].text())
                if row[i].__class__.__name__ == "QComboBox":
                    new_row.append(row[i].currentText())
            conditions_array.append(new_row)

        condition_type = self.validate_script(conditions_array)

        if self.validate_script(conditions_array) == 3:
            message_box = QMessageBox()
            message_box.setIcon(QMessageBox.Warning)
            message_box.setText("You cannot combine send_packet and recv_packet conditions together.\n")
            message_box.setStandardButtons(QMessageBox.Ok)
            message_box.setDefaultButton(QMessageBox.Ok)
            message_box.setWindowTitle("Bad condition combination")
            message_box.exec_()
            return

        actions_array = []
        for row in self.action_widgets:
            action_name = row[0].currentText()
            new_row = [action_name]
            if action_name == "auto_login":
                # Collect indices from comboboxes: lang, server, channel, character
                new_row.extend([
                    str(row[2].currentIndex()),
                    str(row[4].currentIndex()),
                    str(row[6].currentIndex()),
                    str(row[8].currentIndex() - 1),
                ])
            elif action_name == "walk_to_point":
                new_row.extend([row[2].text(), row[4].text()])
                new_row.append(row[6].text())
                if row[7].isChecked():
                    new_row.extend([row[9].text(), row[11].text()])
            else:
                for widget in row[1:]:
                    if widget.__class__.__name__ == "QLineEdit":
                        new_row.append(widget.text())
                    elif widget.__class__.__name__ == "QComboBox":
                        new_row.append(widget.currentText())
            actions_array.append(new_row)

        for action in actions_array:
            if action[0] in {"cond.on", "cond.off"}:
                if len(action) < 2 or not action[1]:
                    message_box = QMessageBox()
                    message_box.setIcon(QMessageBox.Warning)
                    message_box.setText(
                        "Please provide the sequential list number for cond.on / cond.off.\n"
                    )
                    message_box.setStandardButtons(QMessageBox.Ok)
                    message_box.setDefaultButton(QMessageBox.Ok)
                    message_box.setWindowTitle("Missing condition number")
                    message_box.exec_()
                    return

        script = self.construct_script(conditions_array, actions_array)
        condition_review = ConditionReview(self.player, script, condition_type, self.cond_modifier, self)
        condition_review.exec_()

    def construct_script(self, conditions_array, actions_array):
        need_import = any(action[0] in ("auto_login", "relogin") for action in actions_array)
        script = ""
        if need_import:
            script += "import gfless_api\n"
        if conditions_array[0][0] == "IF":
            script += "if "
        else:
            script += "if not "

        for i in range(len(conditions_array)):
            if_condition = conditions_array[i][0]
            argument = conditions_array[i][1]
            split_index = conditions_array[i][2]
            operator = conditions_array[i][3]
            user_input_value = conditions_array[i][4]
            separator = conditions_array[i][5]
            user_input_type = conditions_array[i][6]
            if i != 0:
                if if_condition == "AND IF":
                    script += " and "
                else:
                    script += " and not "
            if argument == "send_packet" or argument == "recv_packet":
                if operator == "startswith" or operator == "endswith":
                    if user_input_type == "string":
                        script += f'packet.{operator}("{user_input_value}")'
                    elif user_input_type == "raw":
                        script += f'packet.{operator}({user_input_value})'
                if operator == "contains":
                    if user_input_type == "string":
                        script += f'"{user_input_value}" in packet'
                    elif user_input_type == "raw":
                        script += f'{user_input_value} in packet'
                if operator == "equals":
                    if user_input_type == "string":
                        script += f'packet == "{user_input_value}"'
                    elif user_input_type == "raw":
                        script += f'packet == {user_input_value}'
            elif argument == "split_send_packet" or argument == "split_recv_packet":
                classic_operators = ["==", "!=", ">", "<", ">=", "<="]
                if operator in classic_operators:
                    if user_input_type == "string":
                        script += f'self.split_packet(packet, "{separator}")[{split_index}] {operator} "{user_input_value}"'
                    elif user_input_type == "raw":
                        script += f'self.split_packet(packet, "{separator}")[{split_index}] {operator} {user_input_value}'
                    elif user_input_type == "int":
                        script += f'int(self.split_packet(packet, "{separator}")[{split_index}]) {operator} {user_input_value}'
                if operator == "startswith" or operator == "endswith":
                    if user_input_type == "string":
                        script += f'self.split_packet(packet, "{separator}"){split_index}.{operator}("{user_input_value}")'
                    elif user_input_type == "raw":
                        script += f'self.split_packet(packet, "{separator}"){split_index}.{operator}({user_input_value})'
                if operator == "contains":
                    if user_input_type == "string":
                        script += f'self.split_packet(packet, "{separator}"){split_index} in "{user_input_value}"'
                    elif user_input_type == "raw":
                        script += f'self.split_packet(packet, "{separator}"){split_index} in {user_input_value}'
                if operator == "equals":
                    if user_input_type == "string":
                        script += f'self.split_packet(packet, "{separator}"){split_index} == "{user_input_value}"'
                    elif user_input_type == "raw":
                        script += f'self.split_packet(packet, "{separator}"){split_index} == {user_input_value}'
            elif argument == "time.cond":
                classic_operators = ["==", "!=", ">", "<", ">=", "<="]
                if operator in classic_operators:
                    left_expr = "int(time.cond)" if user_input_type == "int" else "float(time.cond)"
                    if user_input_type == "string":
                        comparison_value = f'"{user_input_value}"'
                    else:
                        comparison_value = user_input_value
                    script += f'{left_expr} {operator} {comparison_value}'
            else:
                classic_operators = ["==", "!=", ">", "<", ">=", "<="]
                if operator in classic_operators:
                    if user_input_type == "string":
                        script += f'self.{argument} {operator} "{user_input_value}"'
                    elif user_input_type == "raw":
                        script += f'self.{argument} {operator} {user_input_value}'
                    elif user_input_type == "int":
                        script += f'int(self.{argument}) {operator} {user_input_value}'
                if operator == "startswith" or operator == "endswith":
                    if user_input_type == "string":
                        script += f'self.{argument}.{operator}("{user_input_value}")'
                    elif user_input_type == "raw":
                        script += f'self.{argument}.{operator}({user_input_value})'
                if operator == "contains":
                    if user_input_type == "string":
                        script += f'"{user_input_value}" in self.{argument}'
                    elif user_input_type == "raw":
                        script += f'{user_input_value} in self.{argument}'
        script += ":"

        for i in range(len(actions_array)):
            script += "\n\t"
            if actions_array[i][0] == "wait":
                script += f'time.sleep(self.randomize_delay({actions_array[i][1]},{actions_array[i][2]}))'
            elif actions_array[i][0] == "send_packet":
                if actions_array[i][2] == "string":
                    script += f'self.api.send_packet("{actions_array[i][1]}")'
                if actions_array[i][2] == "raw":
                    script += f'self.api.send_packet({actions_array[i][1]})'
            elif actions_array[i][0] == "recv_packet":
                if actions_array[i][2] == "string":
                    script += f'self.api.recv_packet("{actions_array[i][1]}")'
                if actions_array[i][2] == "raw":
                    script += f'self.api.recv_packet({actions_array[i][1]})'
            elif actions_array[i][0] == "start_bot" or actions_array[i][0] == "stop_bot" or actions_array[i][0] == "continue_bot" or actions_array[i][0] == "start_minigame_bot" or actions_array[i][0] == "stop_minigame_bot":
                script += f'self.api.{actions_array[i][0]}()'
            elif actions_array[i][0] == "attack":
                script+= f'self.api.attack({actions_array[i][1]})'
            elif actions_array[i][0] == "player_skill":
                script+= f'self.api.player_skill({actions_array[i][1]}, {actions_array[i][2]})'
            elif actions_array[i][0] == "load_settings":
                script += f'self.api.load_settings({actions_array[i][1]})'
            elif actions_array[i][0] == "walk_to_point":
                if len(actions_array[i]) >= 6:
                    script += (
                        f'self.walk_to_point([{actions_array[i][1]},{actions_array[i][2]}], '
                        f'{actions_array[i][3]}, skip={actions_array[i][4]}, timeout={actions_array[i][5]})'
                    )
                elif len(actions_array[i]) >= 4:
                    script += f'self.walk_to_point([{actions_array[i][1]},{actions_array[i][2]}], {actions_array[i][3]})'
                else:
                    script += f'self.walk_to_point([{actions_array[i][1]},{actions_array[i][2]}])'
            elif actions_array[i][0] == "player_walk" or actions_array[i][0] == "pets_walk":
                script += f'self.api.{actions_array[i][0]}({actions_array[i][1]}, {actions_array[i][2]})'
            elif actions_array[i][0] == "use_item":
                script += f'self.use_item({int(actions_array[i][1])}, "{actions_array[i][2]}")'
            elif actions_array[i][0] == "put_item_in_trade":
                items = []
                inv_map = {"equip": 0, "main": 1, "etc": 2}
                for j in range(1, len(actions_array[i]), 3):
                    inv = actions_array[i][j]
                    v = actions_array[i][j+1] if j+1 < len(actions_array[i]) else ""
                    q = actions_array[i][j+2] if j+2 < len(actions_array[i]) else ""
                    if inv and v and q:
                        inv_code = inv_map.get(inv, inv)
                        items.append((int(inv_code), int(v), int(q)))
                if items:
                    items_str = ", ".join(f"({inv}, {v}, {q})" for inv, v, q in items)
                    script += f'self.put_items_in_trade([{items_str}])'
            elif actions_array[i][0] == "auto_login":
                script += (
                    "# Save parameters and login (performs DLL injection)\n"
                    f"\tgfless_api.save_config(int({actions_array[i][1]}), int({actions_array[i][2]}), "
                    f"int({actions_array[i][3]}), int({actions_array[i][4]}))\n"
                    "\tgfless_api.close_login_pipe()\n"
                    f"\tgfless_api.login(int({actions_array[i][1]}), int({actions_array[i][2]}), "
                    f"int({actions_array[i][3]}), int({actions_array[i][4]}), pid=self.PIDnum, force_reinject=True)"
                )
            elif actions_array[i][0] == "relogin":
                script += f'gfless_api.inject_dll(pid=int({actions_array[i][1]}))'
            elif actions_array[i][0] == "cond.on" or actions_array[i][0] == "cond.off":
                try:
                    number = int(actions_array[i][1])
                except (TypeError, ValueError):
                    number = 0
                attr = actions_array[i][0].split(".")[-1]
                script += f'cond.{attr} = {number}'
            elif actions_array[i][0] == "python_code":
                script += f'{actions_array[i][1]}'
            elif actions_array[i][0] == "delete_condition":
                script += f'raise ValueError("Intentional Exit By User")'
            elif actions_array[i][0] == "close_game":
                script += 'self.close_game()'
            elif actions_array[i][0] == "invite_members":
                script += 'self.invite_members()'
            else:
                if actions_array[i][2] == "string":
                    script += f'self.{actions_array[i][0]} = "{actions_array[i][1]}"'
                if actions_array[i][2] == "raw":
                    script += f'self.{actions_array[i][0]} = {actions_array[i][1]}'

        return script

    def validate_script(self, conditions_array):
        send_packet = 0
        recv_packet = 0

        for condition in conditions_array:
            if "recv_packet" in condition[1]:
                recv_packet = 1
                break

        for condition in conditions_array:
            if "send_packet" in condition[1]:
                send_packet = 2
                break

        return send_packet+recv_packet

    def update_condition_widgets(self, ):
        cur_sender = self.sender()
        selected_item = cur_sender.currentText()
        index = cur_sender.property("index")
        operator_combo = self.condition_widgets[index][3]
        value_type_combo = self.condition_widgets[index][6]

        operator_combo.clear()
        value_type_combo.clear()
        if selected_item == "recv_packet" or selected_item == "send_packet":
            operator_combo.addItems(["startswith", "contains", "endswith", "equals"])
            value_type_combo.addItems(["string", "int", "raw"])
            value_type_combo.setCurrentIndex(0)
        elif selected_item == "time.cond":
            operator_combo.addItems(["==", "!=", ">", "<", ">=", "<="])
            value_type_combo.addItems(["int", "raw"])
            value_type_combo.setCurrentIndex(0)
        else:
            operator_combo.addItems(["==", "!=", ">", "<", ">=", "<=", "startswith", "contains", "endswith"])
            value_type_combo.addItems(["string", "int", "raw"])
            value_type_combo.setCurrentIndex(0)

        if selected_item == "split_recv_packet" or selected_item == "split_send_packet":
            self.condition_widgets[index][5].setVisible(True)
            self.condition_widgets[index][2].setVisible(True)
        else:
            self.condition_widgets[index][5].setVisible(False)
            self.condition_widgets[index][2].setVisible(False)

    def adjust_size_periodically(self):
        # Ensure the dialog can grow/shrink while keeping a sensible minimum height
        self.setMinimumHeight(len(self.action_group_boxes) * 65 + len(self.condition_widgets) * 26 + 107)

    def closeEvent(self, event):
        """Persist the user's chosen window size before closing."""
        self.settings.setValue("condition_creator_size", self.size())
        super().closeEvent(event)

class ConditionModifier(QDialog):
    def __init__(self, player):
        super().__init__()
        self.setWindowFlags(self.windowFlags() & ~Qt.WindowContextHelpButtonHint)
        self.player = player

        self.settings = QSettings('PBapi', 'Script Creator')
        self.row_mapping = []

        self.setWindowTitle("Condition Manager")
        self.setWindowIcon(QIcon('src/icon.png'))

        self.main_layout = QGridLayout()

        # Create a QStandardItemModel with three columns
        self.table_widget = QTableWidget()
        self.table_widget.setColumnCount(2)
        self.table_widget.setSelectionBehavior(QTableView.SelectRows)
        self.table_widget.itemSelectionChanged.connect(self.on_selection_changed)
        self.table_widget.setHorizontalHeaderLabels(["Condition Type", "Name",])

        self.main_layout.addWidget(self.table_widget, 0, 0, 6, 5)

        self.create_condition_button = QPushButton("Create Condition")
        self.create_condition_button.clicked.connect(self.create_condition)
        self.main_layout.addWidget(self.create_condition_button, 0, 6, 1, 1)

        self.view_condition_button = QPushButton("View Condition")
        self.view_condition_button.clicked.connect(self.view_condition)
        self.main_layout.addWidget(self.view_condition_button, 1, 6, 1, 1)

        self.delete_condition_button = QPushButton("Delete Condition")
        self.delete_condition_button.clicked.connect(self.delete_condition)
        self.main_layout.addWidget(self.delete_condition_button, 2, 6, 1, 1)

        self.load_condition_button = QPushButton("Load Condition")
        self.load_condition_button.clicked.connect(self.load_condition)
        self.main_layout.addWidget(self.load_condition_button, 1, 6, 1, 1)

        self.save_condition_button = QPushButton("Save Condition")
        self.save_condition_button.clicked.connect(self.save_condition)
        self.main_layout.addWidget(self.save_condition_button, 3, 6, 1, 1)

        self.run_condition_button = QPushButton("Run Condition")
        self.run_condition_button.clicked.connect(self.run_condition)
        self.main_layout.addWidget(self.run_condition_button, 5, 6, 1, 1)

        self.pause_condition_button = QPushButton("Pause Condition")
        self.pause_condition_button.clicked.connect(self.pause_condition)
        self.main_layout.addWidget(self.pause_condition_button, 5, 6, 1, 1)

        self.sequential_checkbox = QCheckBox("Secuential Condition")
        sequential_default = self.settings.value(
            "condition_modifier_sequential", True, type=bool
        )
        self.sequential_checkbox.setChecked(sequential_default)
        self.sequential_checkbox.toggled.connect(self.on_sequential_toggled)
        self.main_layout.addWidget(self.sequential_checkbox, 4, 6, 1, 1)


        self.save_condition_button.setVisible(False)
        self.pause_condition_button.setVisible(False)
        self.run_condition_button.setVisible(False)
        self.delete_condition_button.setVisible(False)



        self.setLayout(self.main_layout)

        self.refresh()

        self.status_timer = QTimer(self)
        self.status_timer.setInterval(250)
        self.status_timer.timeout.connect(self.update_row_colors)
        self.status_timer.start()

    def on_sequential_toggled(self, checked):
        self.settings.setValue("condition_modifier_sequential", checked)
        self.refresh()

    def _selected_entry(self):
        row = self.table_widget.currentRow()
        if row < 0 or row >= len(self.row_mapping):
            return None
        return self.row_mapping[row]

    @staticmethod
    def _natural_key(text):
        parts = re.split(r'(\d+)', text)
        return [int(part) if part.isdigit() else part.lower() for part in parts]

    def _get_condition(self, entry):
        try:
            if entry["type"] == "recv_packet":
                cond = self.player.recv_packet_conditions[entry["index"]]
                return cond, cond[2]
            if entry["type"] == "send_packet":
                cond = self.player.send_packet_conditions[entry["index"]]
                return cond, cond[2]
            cond = self.player.periodical_conditions[entry["index"]]
            return cond, cond.active
        except (IndexError, KeyError):
            return None, False

    def save_condition(self):
        entry = self._selected_entry()
        if not entry:
            return

        script = ""
        condition_type = entry["type"]
        cond, active = self._get_condition(entry)
        if cond is None:
            return

        if condition_type == "recv_packet":
            script += "recv_packet"
            code = cond[1]
            name = cond[0]
        elif condition_type == "send_packet":
            script += "send_packet"
            code = cond[1]
            name = cond[0]
        else:
            script += "periodical"
            code = cond.code
            name = cond.name

        if active:
            script += "\n1\n"
        else:
            script += "\n0\n"

        script += code

        file_dialog = QFileDialog()
        file_name, _ = file_dialog.getSaveFileName(self, "Save Condition", name, "Text Files (*.txt);;All Files (*)")
        if file_name:
            with open(file_name, 'w') as file:
                file.write(script)

    def load_condition(self):
        file_dialog = QFileDialog()
        file_dialog.setFileMode(QFileDialog.ExistingFiles)
        file_dialog.setNameFilter("Text Files (*.txt);;All Files (*)")

        file_names, _ = file_dialog.getOpenFileNames(self, "Load Conditions", "", "Text Files (*.txt);;All Files (*)")

        for file_name in file_names:
            if file_name:
                with open(file_name, 'r') as file:
                    cond_type = file.readline().strip()
                    running = file.readline().strip()
                    script = file.read().strip()

                    running_bool = True if running == '1' else False
                    base_name = os.path.splitext(os.path.basename(file_name))[0]

                    if cond_type == "recv_packet":
                        self.player.recv_packet_conditions.append([base_name, script, running_bool])
                    elif cond_type == "send_packet":
                        self.player.send_packet_conditions.append([base_name, script, running_bool])
                    else:
                        self.player.periodical_conditions.append(
                            PeriodicCondition(base_name, script, running_bool, 1)
                        )

        self.refresh()

    def refresh(self):
        selected_key = None
        if 0 <= self.table_widget.currentRow() < len(self.row_mapping):
            current_entry = self.row_mapping[self.table_widget.currentRow()]
            selected_key = (current_entry["type"], current_entry["name"])

        self.table_widget.blockSignals(True)
        self.table_widget.setRowCount(0)

        entries = []
        for idx, cond in enumerate(self.player.recv_packet_conditions):
            entries.append({
                "type": "recv_packet",
                "name": cond[0],
                "index": idx,
                "active": cond[2],
            })
        for idx, cond in enumerate(self.player.send_packet_conditions):
            entries.append({
                "type": "send_packet",
                "name": cond[0],
                "index": idx,
                "active": cond[2],
            })
        for idx, cond in enumerate(self.player.periodical_conditions):
            entries.append({
                "type": "periodical",
                "name": cond.name,
                "index": idx,
                "active": cond.active,
            })

        if self.sequential_checkbox.isChecked():
            entries.sort(key=lambda item: self._natural_key(item["name"]))

        self.row_mapping = entries

        for row, entry in enumerate(entries):
            self.table_widget.insertRow(row)

            cond_type = QTableWidgetItem()
            cond_type.setText(entry["type"])
            cond_type.setFlags(cond_type.flags() & ~Qt.ItemIsEditable)
            cond_type.setForeground(QColor(0, 0, 0))
            self.table_widget.setItem(row, 0, cond_type)

            cond_name = QTableWidgetItem()
            cond_name.setText(entry["name"])
            cond_name.setFlags(cond_name.flags() & ~Qt.ItemIsEditable)
            cond_name.setForeground(QColor(0, 0, 0))
            self.table_widget.setItem(row, 1, cond_name)

            self._apply_condition_status(
                row,
                entry["type"],
                entry["name"],
                entry["active"],
            )

        self.table_widget.blockSignals(False)

        reselected = False
        if selected_key:
            for idx, entry in enumerate(self.row_mapping):
                if (entry["type"], entry["name"]) == selected_key:
                    self.table_widget.selectRow(idx)
                    reselected = True
                    break
        if not reselected:
            self.table_widget.clearSelection()

        self.on_selection_changed()
        self.update_row_colors()

    def set_row_background_color(self, row, color):
        for column in range(self.table_widget.columnCount()):
            item = self.table_widget.item(row, column)
            item.setBackground(color)

    def update_row_colors(self):
        row_count = min(len(self.row_mapping), self.table_widget.rowCount())
        for row in range(row_count):
            entry = self.row_mapping[row]
            cond, active = self._get_condition(entry)
            fallback_active = active if cond is not None else entry.get("active", False)
            entry["active"] = fallback_active
            self._apply_condition_status(
                row,
                entry["type"],
                entry["name"],
                fallback_active,
            )

    def _apply_condition_status(self, row, cond_type, name, fallback_active):
        status = self.player.get_condition_status(cond_type, name)
        if status == "current":
            color = QColor(255, 244, 141)
        else:
            is_active = fallback_active or status in {"window", "always"}
            color = QColor(127, 250, 160) if is_active else QColor(214, 139, 139)
        self.set_row_background_color(row, color)

    def closeEvent(self, event):
        if hasattr(self, "status_timer"):
            self.status_timer.stop()
        super().closeEvent(event)

    def create_condition(self):
        condition_editor = ConditionCreator(self.player, self)
        condition_editor.exec_()

    def view_condition(self):
        entry = self._selected_entry()
        if not entry:
            return

        condition_type = entry["type"]
        cond, _ = self._get_condition(entry)
        if cond is None:
            return

        if condition_type == "recv_packet":
            condition_review = ConditionReview(self.player, cond[1], 1, self, None, entry["index"], cond[0])
        elif condition_type == "send_packet":
            condition_review = ConditionReview(self.player, cond[1], 2, self, None, entry["index"], cond[0])
        else:
            condition_review = ConditionReview(self.player, cond.code, 0, self, None, entry["index"], cond.name)
        condition_review.exec_()

        #self.refresh()

    def delete_condition(self):
        entry = self._selected_entry()
        if not entry:
            return

        try:
            if entry["type"] == "recv_packet":
                cond = self.player.recv_packet_conditions.pop(entry["index"])
                self.player._compiled_recv_conditions.pop(cond[0], None)
            elif entry["type"] == "send_packet":
                cond = self.player.send_packet_conditions.pop(entry["index"])
                self.player._compiled_send_conditions.pop(cond[0], None)
            else:
                cond = self.player.periodical_conditions.pop(entry["index"])
                if getattr(cond, "task", None):
                    cond.task.cancel()
        except Exception:
            pass
        self.refresh()

    def run_condition(self):
        entry = self._selected_entry()
        if not entry:
            return

        try:
            if entry["type"] == "recv_packet":
                self.player.recv_packet_conditions[entry["index"]][2] = True
            elif entry["type"] == "send_packet":
                self.player.send_packet_conditions[entry["index"]][2] = True
            else:
                self.player.periodical_conditions[entry["index"]].active = True
        except Exception:
            pass
        self.refresh()

    def pause_condition(self):
        entry = self._selected_entry()
        if not entry:
            return

        try:
            if entry["type"] == "recv_packet":
                self.player.recv_packet_conditions[entry["index"]][2] = False
            elif entry["type"] == "send_packet":
                self.player.send_packet_conditions[entry["index"]][2] = False
            else:
                self.player.periodical_conditions[entry["index"]].active = False
        except Exception:
            pass
        self.refresh()

    def on_selection_changed(self):
        entry = self._selected_entry()
        if not entry:
            self.load_condition_button.setVisible(True)
            self.save_condition_button.setVisible(False)
            self.pause_condition_button.setVisible(False)
            self.run_condition_button.setVisible(False)
            self.delete_condition_button.setVisible(False)
            self.view_condition_button.setVisible(False)
            return

        self.delete_condition_button.setVisible(True)
        self.view_condition_button.setVisible(True)
        self.save_condition_button.setVisible(True)
        self.load_condition_button.setVisible(False)

        _, active = self._get_condition(entry)
        if entry["type"] == "recv_packet" or entry["type"] == "send_packet":
            if active:
                self.pause_condition_button.setVisible(True)
                self.run_condition_button.setVisible(False)
            else:
                self.pause_condition_button.setVisible(False)
                self.run_condition_button.setVisible(True)
        else:
            if active:
                self.pause_condition_button.setVisible(True)
                self.run_condition_button.setVisible(False)
            else:
                self.pause_condition_button.setVisible(False)
         