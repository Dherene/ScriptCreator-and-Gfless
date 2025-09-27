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
    QApplication,
    QHBoxLayout,
    QScrollArea,
    QWidget,
)
from PyQt5.QtCore import Qt, QSettings, QSize, QTimer
from PyQt5.QtGui import QFont, QFontMetricsF, QColor, QIcon, QIntValidator
import os
import re
from itertools import chain
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

        self.settings = QSettings('PBapi', 'Script Creator')
        default_size = QSize(900, 420)
        self.max_dialog_height = default_size.height() * 2
        last_size = self.settings.value(
            "condition_creator_size", default_size, type=QSize
        )
        last_size = QSize(last_size)
        last_size.setHeight(min(last_size.height(), self.max_dialog_height))
        self.setMinimumSize(default_size)
        self.setMaximumHeight(self.max_dialog_height)
        self.resize(last_size.expandedTo(default_size))
        self.setSizeGripEnabled(True)

        self.sections = []

        self.main_layout = QVBoxLayout()
        self.setLayout(self.main_layout)

        self.scroll_area = QScrollArea()
        self.scroll_area.setWidgetResizable(True)
        self.scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.scroll_area.setFrameShape(QScrollArea.NoFrame)
        self.main_layout.addWidget(self.scroll_area)

        self.scroll_content = QWidget()
        self.scroll_area.setWidget(self.scroll_content)

        self.scroll_layout = QVBoxLayout()
        self.scroll_layout.setContentsMargins(0, 0, 0, 0)
        self.scroll_layout.setSpacing(12)
        self.scroll_content.setLayout(self.scroll_layout)

        self.sections_container = QWidget()
        self.sections_layout = QVBoxLayout()
        self.sections_layout.setContentsMargins(0, 0, 0, 0)
        self.sections_layout.setSpacing(12)
        self.sections_container.setLayout(self.sections_layout)
        self.scroll_layout.addWidget(self.sections_container)

        self.if_section = self._create_section('if', 1)
        self.sections.append(self.if_section)
        self.sections_layout.addWidget(self.if_section['container'])

        self.if_section['add_condition_button'].clicked.connect(self.add_new_condition)
        self.if_section['remove_condition_button'].clicked.connect(self.remove_last_condition)
        self.if_section['add_action_button'].clicked.connect(self.add_new_action)
        self.if_section['remove_action_button'].clicked.connect(self.remove_last_action)

        self._add_condition_row(self.if_section)
        self._add_action_group(self.if_section)

        self.elif_controls_layout = QHBoxLayout()
        self.add_elif_button = QPushButton("Add Elif")
        self.add_elif_button.clicked.connect(self.add_elif_section)
        self.remove_elif_button = QPushButton("Remove Elif")
        self.remove_elif_button.clicked.connect(self.remove_last_elif_section)
        self.remove_elif_button.setVisible(False)
        self.elif_controls_layout.addWidget(self.add_elif_button)
        self.elif_controls_layout.addWidget(self.remove_elif_button)
        self.elif_controls_layout.addStretch()
        self.scroll_layout.addLayout(self.elif_controls_layout)
        self.scroll_layout.addStretch()

        self.review_button = QPushButton("review")
        self.review_button.clicked.connect(self.review_condition)
        self.main_layout.addWidget(self.review_button)

        self.cond_helper_label = QLabel(
            "Tip: cond.on / cond.off require the target condition's number "
            "in the sequential conditions list. Use cond.off = 0 to disable "
            "all other active conditions while keeping the calling one running."
        )
        self.cond_helper_label.setWordWrap(True)
        self.main_layout.addWidget(self.cond_helper_label)

        self.update_dialog_geometry()

    @staticmethod
    def _is_valid_subgroup_name(name: str) -> bool:
        return bool(re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", name))

    @staticmethod
    def _show_warning(title: str, text: str) -> None:
        message_box = QMessageBox()
        message_box.setIcon(QMessageBox.Warning)
        message_box.setText(text)
        message_box.setStandardButtons(QMessageBox.Ok)
        message_box.setDefaultButton(QMessageBox.Ok)
        message_box.setWindowTitle(title)
        message_box.exec_()

    @staticmethod
    def _add_label_field(
        layout: QGridLayout,
        row: int,
        start_col: int,
        label_widget,
        field_widget,
        field_expands: bool = True,
    ) -> None:
        if isinstance(label_widget, QLabel):
            label_widget.setAlignment(Qt.AlignRight | Qt.AlignVCenter)

        layout.addWidget(label_widget, row, start_col)
        layout.addWidget(field_widget, row, start_col + 1)
        layout.setColumnStretch(start_col, 0)
        layout.setColumnStretch(start_col + 1, 1 if field_expands else 0)

    @staticmethod
    def _add_single(
        layout: QGridLayout, row: int, column: int, widget, expands: bool = False
    ) -> None:
        layout.addWidget(widget, row, column)
        layout.setColumnStretch(column, 1 if expands else 0)

    @staticmethod
    def _standardize_action_layout(layout: QGridLayout) -> None:
        """Ensure action editors keep a consistent proportion."""
        stretch_map = {0: 3, 1: 0, 2: 4, 3: 0, 4: 4, 5: 0, 6: 4}
        for column, stretch in stretch_map.items():
            layout.setColumnStretch(column, stretch)

        occupied_columns = set()
        for index in range(layout.count()):
            _, column, _, column_span = layout.getItemPosition(index)
            for col in range(column, column + column_span):
                occupied_columns.add(col)

        min_width_map = {0: 150, 1: 70, 2: 120, 3: 70, 4: 120, 5: 70, 6: 120}
        for column, minimum in min_width_map.items():
            layout.setColumnMinimumWidth(
                column, minimum if column in occupied_columns else 0
            )

    def _create_section(self, kind: str, index: int):
        title = "Conditions" if kind == 'if' else f"Elif Conditions {index}"
        container = QGroupBox(title)
        container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        container_layout = QVBoxLayout()
        container_layout.setContentsMargins(8, 8, 8, 8)
        container_layout.setSpacing(12)
        container.setLayout(container_layout)

        condition_layout = QGridLayout()
        condition_layout.setContentsMargins(0, 0, 0, 0)
        condition_layout.setHorizontalSpacing(4)
        container_layout.addLayout(condition_layout)

        condition_buttons_layout = QHBoxLayout()
        condition_buttons_layout.addStretch()
        remove_condition_button = QPushButton("-")
        remove_condition_button.setVisible(False)
        add_condition_button = QPushButton("+")
        condition_buttons_layout.addWidget(remove_condition_button)
        condition_buttons_layout.addWidget(add_condition_button)
        container_layout.addLayout(condition_buttons_layout)

        actions_layout = QVBoxLayout()
        actions_layout.setSpacing(10)
        container_layout.addLayout(actions_layout)

        action_buttons_layout = QHBoxLayout()
        action_buttons_layout.addStretch()
        remove_action_button = QPushButton("-")
        remove_action_button.setVisible(False)
        add_action_button = QPushButton("+")
        action_buttons_layout.addWidget(remove_action_button)
        action_buttons_layout.addWidget(add_action_button)
        container_layout.addLayout(action_buttons_layout)

        return {
            'kind': kind,
            'index': index,
            'container': container,
            'condition_layout': condition_layout,
            'condition_widgets': [],
            'add_condition_button': add_condition_button,
            'remove_condition_button': remove_condition_button,
            'actions_layout': actions_layout,
            'action_widgets': [],
            'action_group_boxes': [],
            'add_action_button': add_action_button,
            'remove_action_button': remove_action_button,
        }

    def _condition_labels(self, section):
        if section['condition_widgets']:
            return ["AND IF", "AND IF NOT"]
        if section['kind'] == 'if':
            return ["IF", "IF NOT"]
        return ["ELIF", "ELIF NOT"]

    def _refresh_condition_layout(self, section):
        layout = section['condition_layout']
        while layout.count():
            item = layout.takeAt(0)
            widget = item.widget()
            if widget is not None:
                widget.setParent(None)
        for row, widgets in enumerate(section['condition_widgets']):
            layout.addWidget(widgets[0], row, 0)
            layout.addWidget(widgets[1], row, 1)
            layout.addWidget(widgets[2], row, 2)
            layout.addWidget(widgets[3], row, 3)
            layout.addWidget(widgets[4], row, 4)
            layout.addWidget(widgets[8], row, 4)
            layout.addWidget(widgets[6], row, 5)
            layout.addWidget(widgets[5], row, 6)
            layout.addWidget(widgets[7], row, 7)
        layout.setColumnStretch(0, 0)
        layout.setColumnStretch(1, 0)
        layout.setColumnStretch(2, 0)
        layout.setColumnStretch(3, 0)
        layout.setColumnStretch(4, 1)
        layout.setColumnStretch(5, 0)
        layout.setColumnStretch(6, 0)
        layout.setColumnStretch(7, 1)

    def _add_condition_row(self, section):
        text_list = self._condition_labels(section)

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
            "make_party",
            ("Index of the subgroup member", "subgroup_member_index"),
            "subgroup_variable",
        ]
        for entry in elements_list:
            if isinstance(entry, tuple):
                text, data = entry
                combo_condition.addItem(text, data)
            else:
                combo_condition.addItem(entry)
        for i in range(1, 101):
            combo_condition.addItem(f"attr{i}")

        combo_operator = QComboBox()
        combo_operator.addItems(["startswith", "contains", "endswith", "equals"])

        var_type = QComboBox()
        var_type.addItems(["string", "int", "raw"])

        delimiter_combo = QComboBox()
        delimiter_combo.addItems([" ", "^", "#", "."])
        delimiter_combo.setVisible(False)

        index_combo = QComboBox()
        index_combo.addItems([f"{i}" for i in range(100)])
        index_combo.setVisible(False)

        text_edit_expression = QLineEdit()
        text_edit_expression.setPlaceholderText("value")
        text_edit_expression.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        make_party_state_combo = QComboBox()
        make_party_state_combo.addItem("incomplete", 0)
        make_party_state_combo.addItem("complete", 2)
        make_party_state_combo.setVisible(False)
        make_party_state_combo.setProperty("skip_export", True)

        def _sync_make_party_state(_index=None, *, combo=make_party_state_combo, editor=text_edit_expression):
            data = combo.currentData()
            if data is None:
                editor.clear()
            else:
                editor.setText(str(data))

        make_party_state_combo.currentIndexChanged.connect(_sync_make_party_state)
        _sync_make_party_state()

        subgroup_name_edit = QLineEdit()
        subgroup_name_edit.setPlaceholderText("variable name")
        subgroup_name_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        subgroup_name_edit.setVisible(False)

        index = len(section['condition_widgets'])
        combo_condition.currentIndexChanged.connect(
            lambda _, widgets=section['condition_widgets'], idx=index: self.update_condition_widgets(widgets, idx)
        )

        section['condition_widgets'].append([
            if_combobox,
            combo_condition,
            index_combo,
            combo_operator,
            text_edit_expression,
            delimiter_combo,
            var_type,
            subgroup_name_edit,
            make_party_state_combo,
        ])

        self._refresh_condition_layout(section)
        section['remove_condition_button'].setVisible(len(section['condition_widgets']) > 1)
        self.update_condition_widgets(section['condition_widgets'], index)
        self.update_dialog_geometry(maintain_current_height=True)

    def _remove_condition_row(self, section):
        if len(section['condition_widgets']) <= 1:
            return
        last_row = section['condition_widgets'].pop()
        for widget in last_row:
            widget.deleteLater()
        self._refresh_condition_layout(section)
        section['remove_condition_button'].setVisible(len(section['condition_widgets']) > 1)
        self.update_dialog_geometry()

    def _add_action_group(self, section):
        new_action_combobox = QComboBox()
        elements_list = [
            "wait", "walk_to_point", "send_packet", "recv_packet",
            "cond.on", "cond.off",
            "start_bot", "stop_bot", "continue_bot", "load_settings",
            "attack", "player_skill", "player_walk", "pets_walk",
            "start_minigame_bot", "stop_minigame_bot", "use_item", "put_item_in_trade",
            "auto_login", "relogin", "python_code", "delete_condition", "close_game",
            "invite_members", "make_party", "subgroup_variable"
        ]
        for i in range(1, 101):
            elements_list.append(f"attr{i}")
        new_action_combobox.setStyleSheet("QComboBox { combobox-popup: 0; }")
        new_action_combobox.addItems(elements_list)

        row_position = len(section['action_widgets']) + 1
        if section['kind'] == 'if':
            title_prefix = "Action"
        else:
            title_prefix = "Elif action"

        group_box = QGroupBox(f"{title_prefix} {row_position}")
        group_box.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        group_box_layout = QGridLayout()
        group_box_layout.setContentsMargins(8, 8, 8, 8)
        group_box_layout.setHorizontalSpacing(4)

        new_min_wait_label = QLabel("min:")
        new_min_wait = QLineEdit("0.75")
        new_min_wait.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        new_max_wait_label = QLabel("max:")
        new_max_wait = QLineEdit("1.5")
        new_max_wait.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        self._add_single(group_box_layout, 0, 0, new_action_combobox)
        self._add_label_field(group_box_layout, 0, 1, new_min_wait_label, new_min_wait)
        self._add_label_field(group_box_layout, 0, 3, new_max_wait_label, new_max_wait)
        group_box.setLayout(group_box_layout)

        section['actions_layout'].addWidget(group_box)

        index = len(section['action_widgets'])
        new_action_combobox.currentIndexChanged.connect(
            lambda _, sec=section, idx=index: self.update_action_widgets(sec, idx)
        )

        section['action_widgets'].append([
            new_action_combobox,
            new_min_wait,
            new_max_wait,
            new_min_wait_label,
            new_max_wait_label,
            group_box_layout,
        ])

        section['action_group_boxes'].append(group_box)

        if len(section['action_widgets']) > 1:
            section['remove_action_button'].setVisible(True)

        self._standardize_action_layout(group_box_layout)

        self.update_dialog_geometry(maintain_current_height=True, extra_height_ratio=0.1)

    def _remove_last_action(self, section):
        if not section['action_widgets']:
            return

        last_action_widgets = section['action_widgets'][-1]
        for widget_to_delete in last_action_widgets:
            if hasattr(widget_to_delete, "deleteLater"):
                widget_to_delete.deleteLater()

        section['action_group_boxes'][-1].deleteLater()
        section['action_group_boxes'].pop()
        section['action_widgets'].pop()

        if len(section['action_widgets']) < 2:
            section['remove_action_button'].setVisible(False)

        self.update_dialog_geometry()

    def add_new_condition(self):
        self._add_condition_row(self.if_section)

    def remove_last_condition(self):
        self._remove_condition_row(self.if_section)

    def add_new_action(self):
        self._add_action_group(self.if_section)

    def remove_last_action(self):
        self._remove_last_action(self.if_section)

    def add_elif_section(self):
        index = len(self.sections)
        section = self._create_section('elif', index)
        section['add_condition_button'].clicked.connect(
            lambda _, sec=section: self._add_condition_row(sec)
        )
        section['remove_condition_button'].clicked.connect(
            lambda _, sec=section: self._remove_condition_row(sec)
        )
        section['add_action_button'].clicked.connect(
            lambda _, sec=section: self._add_action_group(sec)
        )
        section['remove_action_button'].clicked.connect(
            lambda _, sec=section: self._remove_last_action(sec)
        )
        self.sections.append(section)
        self.sections_layout.addWidget(section['container'])
        self._add_condition_row(section)
        self._add_action_group(section)
        self.remove_elif_button.setVisible(len(self.sections) > 1)
        self.update_dialog_geometry(maintain_current_height=True, extra_height_ratio=0.15)
        QTimer.singleShot(0, lambda: self.scroll_area.ensureWidgetVisible(section['container']))

    def remove_last_elif_section(self):
        if len(self.sections) <= 1:
            return
        section = self.sections.pop()
        section['container'].deleteLater()
        self.remove_elif_button.setVisible(len(self.sections) > 1)
        self.update_dialog_geometry()

    def update_action_widgets(self, section, index):
        action_widgets = section['action_widgets']
        group_box_layout = action_widgets[index][-1]

        for i in range(1, len(action_widgets[index]) - 1):
            action_widgets[index][i].deleteLater()

        action_widgets[index] = [action_widgets[index][0]]

        condition = action_widgets[index][0].currentText()

        if condition == "wait":
            new_min_wait = QLineEdit("0.75")
            new_min_wait.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            new_min_wait_label = QLabel("min:")
            new_max_wait = QLineEdit("1.5")
            new_max_wait.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            new_max_wait_label = QLabel("max:")

            self._add_label_field(group_box_layout, 0, 1, new_min_wait_label, new_min_wait)
            self._add_label_field(group_box_layout, 0, 3, new_max_wait_label, new_max_wait)

            action_widgets[index].append(new_min_wait_label)
            action_widgets[index].append(new_min_wait)
            action_widgets[index].append(new_max_wait_label)
            action_widgets[index].append(new_max_wait)
        elif condition == "send_packet" or condition == "recv_packet":
            new_packet_label = QLabel("Packet:")
            new_packet = QLineEdit()
            new_packet.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            new_type_decision = QComboBox()
            new_type_decision.addItems(["string","int", "raw"])

            self._add_label_field(group_box_layout, 0, 1, new_packet_label, new_packet)
            self._add_single(group_box_layout, 0, 3, new_type_decision)

            action_widgets[index].append(new_packet_label)
            action_widgets[index].append(new_packet)
            action_widgets[index].append(new_type_decision)

        elif condition == "cond.on" or condition == "cond.off":
            index_label = QLabel("number:")
            index_input = QLineEdit()
            index_input.setValidator(QIntValidator(1, 9999, index_input))
            index_input.setPlaceholderText("Sequential list index")
            index_input.setToolTip(
                "Specify the condition number from the sequential list."
            )
            index_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

            self._add_label_field(group_box_layout, 0, 1, index_label, index_input)

            action_widgets[index].append(index_label)
            action_widgets[index].append(index_input)

        elif condition == "walk_to_point" or condition == "player_walk" or condition == "pets_walk":
            new_x = QLineEdit()
            new_x.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            new_x_label = QLabel("x:")
            new_y = QLineEdit()
            new_y.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            new_y_label = QLabel("y:")
            self._add_label_field(group_box_layout, 0, 1, new_x_label, new_x)
            self._add_label_field(group_box_layout, 0, 3, new_y_label, new_y)

            action_widgets[index].append(new_x_label)
            action_widgets[index].append(new_x)
            action_widgets[index].append(new_y_label)
            action_widgets[index].append(new_y)

            if condition == "walk_to_point":
                new_radius = QLineEdit("0")
                new_radius.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                new_radius_label = QLabel("radius:")
                new_radius.setToolTip("Numero de celdas alrededor del punto")
                new_radius.setPlaceholderText("celdas")

                self._add_label_field(group_box_layout, 0, 5, new_radius_label, new_radius)

                action_widgets[index].append(new_radius_label)
                action_widgets[index].append(new_radius)

                skip_timeout_checkbox = QCheckBox("custom")
                skip_label = QLabel("skip:")
                skip_input = QLineEdit("4")
                skip_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                timeout_label = QLabel("timeout:")
                timeout_input = QLineEdit("3")
                timeout_input.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

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

                self._add_single(group_box_layout, 0, 7, skip_timeout_checkbox)
                self._add_label_field(group_box_layout, 0, 8, skip_label, skip_input)
                self._add_label_field(group_box_layout, 0, 10, timeout_label, timeout_input)
                group_box_layout.setColumnStretch(12, 1)

                action_widgets[index].append(skip_timeout_checkbox)
                action_widgets[index].append(skip_label)
                action_widgets[index].append(skip_input)
                action_widgets[index].append(timeout_label)
                action_widgets[index].append(timeout_input)
        elif condition == "load_settings":
            new_settings_path_label = QLabel("Settings path:")
            new_settings_path = QLineEdit()
            new_settings_path.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

            self._add_label_field(group_box_layout, 0, 1, new_settings_path_label, new_settings_path)

            action_widgets[index].append(new_settings_path_label)
            action_widgets[index].append(new_settings_path)
        elif condition == "use_item":
            new_item_vnum_label = QLabel("VNUM: ")
            new_item_vnum = QLineEdit()
            new_item_vnum.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

            new_inventory_type = QComboBox()
            new_inventory_type.addItems(["equip","main", "etc"])

            self._add_label_field(group_box_layout, 0, 1, new_item_vnum_label, new_item_vnum)
            self._add_single(group_box_layout, 0, 3, new_inventory_type)

            action_widgets[index].append(new_item_vnum_label)
            action_widgets[index].append(new_item_vnum)
            action_widgets[index].append(new_inventory_type)
        elif condition == "put_item_in_trade":
            for n in range(10):
                inv_combo = QComboBox()
                inv_combo.addItems(["equip", "main", "etc"])
                v_label = QLabel(f"VNUM {n+1}:")
                v_edit = QLineEdit()
                v_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
                q_label = QLabel("qty:")
                q_edit = QLineEdit()
                q_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

                self._add_single(group_box_layout, n, 1, inv_combo)
                self._add_label_field(group_box_layout, n, 2, v_label, v_edit)
                self._add_label_field(group_box_layout, n, 4, q_label, q_edit)

                action_widgets[index].extend([inv_combo, v_label, v_edit, q_label, q_edit])
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

            self._add_label_field(group_box_layout, 0, 1, lang_label, lang_combo, field_expands=False)
            self._add_label_field(group_box_layout, 1, 1, server_label, server_combo, field_expands=False)
            self._add_label_field(group_box_layout, 2, 1, channel_label, channel_combo, field_expands=False)
            self._add_label_field(group_box_layout, 3, 1, char_label, char_combo, field_expands=False)

            action_widgets[index].extend([
                lang_label, lang_combo,
                server_label, server_combo,
                channel_label, channel_combo,
                char_label, char_combo,
            ])
        elif condition == "relogin":
            pid_label = QLabel("pid:")
            pid_edit = QLineEdit("pidnum")
            pid_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            self._add_label_field(group_box_layout, 0, 1, pid_label, pid_edit)
            action_widgets[index].append(pid_label)
            action_widgets[index].append(pid_edit)
        elif condition == "python_code":
            new_equals_label = QLabel("=")
            new_python_code = QLineEdit()
            new_python_code.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

            self._add_label_field(group_box_layout, 0, 1, new_equals_label, new_python_code)

            action_widgets[index].append(new_equals_label)
            action_widgets[index].append(new_python_code)
        elif condition == "make_party":
            pass
        elif condition == "subgroup_variable":
            name_label = QLabel("Name:")
            name_edit = QLineEdit()
            name_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            operation_label = QLabel("Action:")
            operation_combo = QComboBox()
            operation_combo.addItems(["Set Value", "Increase (+1)", "Decrease (-1)"])
            value_label = QLabel("Value:")
            value_edit = QLineEdit("0")
            value_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

            def toggle_value_field():
                needs_value = operation_combo.currentText() == "Set Value"
                value_label.setVisible(needs_value)
                value_edit.setVisible(needs_value)

            operation_combo.currentIndexChanged.connect(toggle_value_field)
            toggle_value_field()

            self._add_label_field(group_box_layout, 0, 1, name_label, name_edit)
            self._add_label_field(group_box_layout, 0, 3, operation_label, operation_combo, field_expands=False)
            self._add_label_field(group_box_layout, 0, 5, value_label, value_edit)

            action_widgets[index].extend([
                name_label,
                name_edit,
                operation_label,
                operation_combo,
                value_label,
                value_edit,
            ])
        elif condition.startswith("attr"):
            new_equals_label = QLabel("=")
            new_equals = QLineEdit()
            new_equals.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            new_str_or_raw = QComboBox()
            new_str_or_raw.addItems(["string","int", "raw"])

            self._add_label_field(group_box_layout, 0, 1, new_equals_label, new_equals)
            self._add_single(group_box_layout, 0, 3, new_str_or_raw)

            action_widgets[index].append(new_equals_label)
            action_widgets[index].append(new_equals)
            action_widgets[index].append(new_str_or_raw)
        elif condition == "attack":
            new_monster_id_label = QLabel("monster_id: ")
            new_monster_id = QLineEdit()
            new_monster_id.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

            self._add_label_field(group_box_layout, 0, 1, new_monster_id_label, new_monster_id)

            action_widgets[index].append(new_monster_id_label)
            action_widgets[index].append(new_monster_id)
        elif condition == "player_skill":
            new_monster_id_label = QLabel("monster_id: ")
            new_monster_id = QLineEdit()
            new_skill_id_label = QLabel("skill_id: ")
            new_skill_id = QLineEdit()
            new_monster_id.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
            new_skill_id.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

            self._add_label_field(group_box_layout, 0, 1, new_monster_id_label, new_monster_id)
            self._add_label_field(group_box_layout, 0, 3, new_skill_id_label, new_skill_id)

            action_widgets[index].append(new_monster_id_label)
            action_widgets[index].append(new_monster_id)
            action_widgets[index].append(new_skill_id_label)
            action_widgets[index].append(new_skill_id)
        elif condition == "close_game":
            # no additional widgets needed for closing the game
            pass

        action_widgets[index].append(group_box_layout)

        self._standardize_action_layout(group_box_layout)

        self.update_dialog_geometry()


    def _collect_conditions(self, widgets_list):
        conditions_array = []
        for row in widgets_list:
            new_row = []
            for widget in row:
                if widget.__class__.__name__ == "QLineEdit":
                    new_row.append(widget.text())
                if widget.__class__.__name__ == "QComboBox":
                    if widget.property("skip_export"):
                        continue
                    value = widget.currentData()
                    if value is None:
                        value = widget.currentText()
                    if not isinstance(value, str):
                        value = str(value)
                    new_row.append(value)
            conditions_array.append(new_row)
        return conditions_array

    def _collect_actions(self, action_widgets):
        actions_array = []
        for row in action_widgets:
            action_name = row[0].currentText()
            new_row = [action_name]
            if action_name == "auto_login":
                new_row.extend([
                    str(row[2].currentIndex()),
                    str(row[4].currentIndex()),
                    str(row[6].currentIndex()),
                    str(row[8].currentIndex() - 1),
                ])
            elif action_name == "walk_to_point":
                new_row.extend([row[2].text(), row[4].text()])
                new_row.append(row[6].text())
                if len(row) > 7 and isinstance(row[7], QCheckBox) and row[7].isChecked():
                    new_row.extend([row[9].text(), row[11].text()])
            elif action_name == "make_party":
                new_row.append("1")
            else:
                for widget in row[1:]:
                    if isinstance(widget, QLineEdit):
                        new_row.append(widget.text())
                    elif isinstance(widget, QComboBox):
                        value = widget.currentData()
                        if value is None:
                            value = widget.currentText()
                        if not isinstance(value, str):
                            value = str(value)
                        new_row.append(value)
            actions_array.append(new_row)
        return actions_array

    def _append_actions_to_script(self, script, actions_array, indent_level=1):
        indent = "\n" + "\t" * indent_level
        for action in actions_array:
            if not action:
                continue
            name = action[0]
            script += indent
            if name == "wait":
                script += f'time.sleep(self.randomize_delay({action[1]},{action[2]}))'
            elif name == "send_packet":
                if action[2] == "string":
                    script += f'self.api.send_packet("{action[1]}")'
                if action[2] == "raw":
                    script += f'self.api.send_packet({action[1]})'
            elif name == "recv_packet":
                if action[2] == "string":
                    script += f'self.api.recv_packet("{action[1]}")'
                if action[2] == "raw":
                    script += f'self.api.recv_packet({action[1]})'
            elif name in {"start_bot", "stop_bot", "continue_bot", "start_minigame_bot", "stop_minigame_bot"}:
                script += f'self.api.{name}()'
            elif name == "attack":
                script += f'self.api.attack({action[1]})'
            elif name == "player_skill":
                script += f'self.api.player_skill({action[1]}, {action[2]})'
            elif name == "load_settings":
                script += f'self.api.load_settings({action[1]})'
            elif name == "walk_to_point":
                if len(action) >= 6:
                    script += (
                        f'self.walk_to_point([{action[1]},{action[2]}], '
                        f'{action[3]}, skip={action[4]}, timeout={action[5]})'
                    )
                elif len(action) >= 4:
                    script += f'self.walk_to_point([{action[1]},{action[2]}], {action[3]})'
                else:
                    script += f'self.walk_to_point([{action[1]},{action[2]}])'
            elif name in {"player_walk", "pets_walk"}:
                script += f'self.api.{name}({action[1]}, {action[2]})'
            elif name == "use_item":
                script += f'self.use_item({int(action[1])}, "{action[2]}")'
            elif name == "put_item_in_trade":
                items = []
                inv_map = {"equip": 0, "main": 1, "etc": 2}
                for j in range(1, len(action), 3):
                    inv = action[j]
                    v = action[j + 1] if j + 1 < len(action) else ""
                    q = action[j + 2] if j + 2 < len(action) else ""
                    if inv and v and q:
                        inv_code = inv_map.get(inv, inv)
                        items.append((int(inv_code), int(v), int(q)))
                if items:
                    items_str = ", ".join(f"({inv}, {v}, {q})" for inv, v, q in items)
                    script += f'self.put_items_in_trade([{items_str}])'
            elif name == "auto_login":
                script += (
                    "# Save parameters and login (performs DLL injection)\n"
                    f"\tgfless_api.save_config(int({action[1]}), int({action[2]}), "
                    f"int({action[3]}), int({action[4]}))\n"
                    "\tgfless_api.close_login_pipe()\n"
                    f"\tgfless_api.login(int({action[1]}), int({action[2]}), "
                    f"int({action[3]}), int({action[4]}), pid=self.PIDnum, force_reinject=True)"
                )
            elif name == "relogin":
                script += f'gfless_api.inject_dll(pid=int({action[1]}))'
            elif name in {"cond.on", "cond.off"}:
                try:
                    number = int(action[1])
                except (TypeError, ValueError, IndexError):
                    number = 0
                attr = name.split(".")[-1]
                script += f'cond.{attr} = {number}'
            elif name == "python_code":
                script += f'{action[1]}'
            elif name == "delete_condition":
                script += 'raise ValueError("Intentional Exit By User")'
            elif name == "close_game":
                script += 'self.close_game()'
            elif name == "invite_members":
                script += 'self.invite_members()'
            elif name == "make_party":
                script += 'self.make_party(1)'
            elif name == "subgroup_variable":
                var_name = action[1].strip() if len(action) > 1 else ""
                operation = action[2] if len(action) > 2 else ""
                if operation == "Set Value":
                    try:
                        numeric_value = int(action[3]) if len(action) > 3 else 0
                    except (TypeError, ValueError):
                        numeric_value = 0
                    script += f'selfsubg.{var_name} = {numeric_value}'
                elif operation == "Increase (+1)":
                    script += f'selfsubg.{var_name} = int(selfsubg.{var_name}) + 1'
                else:
                    script += f'selfsubg.{var_name} = int(selfsubg.{var_name}) - 1'
            elif len(action) >= 3:
                if action[2] == "string":
                    script += f'self.{name} = "{action[1]}"'
                if action[2] == "raw":
                    script += f'self.{name} = {action[1]}'
        return script

    def review_condition(self):
        sections_data = []
        for section in self.sections:
            conditions_array = self._collect_conditions(section['condition_widgets'])
            if not conditions_array:
                continue
            condition_type = self.validate_script(conditions_array)
            if condition_type == 3:
                message_box = QMessageBox()
                message_box.setIcon(QMessageBox.Warning)
                message_box.setText(
                    "You cannot combine send_packet and recv_packet conditions together.\n"
                )
                message_box.setStandardButtons(QMessageBox.Ok)
                message_box.setDefaultButton(QMessageBox.Ok)
                message_box.setWindowTitle("Bad condition combination")
                message_box.exec_()
                return
            actions_array = self._collect_actions(section['action_widgets'])
            sections_data.append({
                'section': section,
                'conditions': conditions_array,
                'actions': actions_array,
                'condition_type': condition_type,
            })

        if not sections_data:
            return

        all_actions = list(chain.from_iterable(data['actions'] for data in sections_data))

        for action in all_actions:
            if action[0] in {"cond.on", "cond.off"}:
                if len(action) < 2 or not action[1]:
                    self._show_warning(
                        "Missing condition number",
                        "Please provide the sequential list number for cond.on / cond.off.\n",
                    )
                    return

        for data in sections_data:
            conditions_array = data['conditions']
            for condition in conditions_array:
                if len(condition) >= 2 and condition[1] == "make_party":
                    value_text = condition[4].strip() if len(condition) > 4 else ""
                    if not value_text:
                        self._show_warning(
                            "Missing make_party state",
                            "Please choose whether to check for state 0 or 2.",
                        )
                        return
                    try:
                        state_value = int(value_text)
                    except ValueError:
                        self._show_warning(
                            "Invalid make_party state",
                            "Make party conditions only accept the values 0 or 2.",
                        )
                        return
                    if state_value not in (0, 2):
                        self._show_warning(
                            "Unsupported make_party state",
                            "Make party conditions only support state 0 (waiting) or 2 (completed).",
                        )
                        return

            for condition in conditions_array:
                if len(condition) >= 2 and condition[1] == "subgroup_variable":
                    var_name = condition[7].strip() if len(condition) > 7 else ""
                    if not var_name:
                        self._show_warning(
                            "Missing subgroup variable",
                            "Please enter the subgroup variable name.",
                        )
                        return
                    if not self._is_valid_subgroup_name(var_name):
                        self._show_warning(
                            "Invalid subgroup variable",
                            "Subgroup variable names must start with a letter or underscore and contain only alphanumeric characters or underscores.",
                        )
                        return
                    value_text = condition[4].strip() if len(condition) > 4 else ""
                    if not value_text:
                        self._show_warning(
                            "Missing subgroup value",
                            "Please provide an integer value for the subgroup comparison.",
                        )
                        return
                    try:
                        int(value_text)
                    except ValueError:
                        self._show_warning(
                            "Invalid subgroup value",
                            "Subgroup comparisons only accept integers.",
                        )
                        return

            for condition in conditions_array:
                if len(condition) >= 2 and condition[1] == "subgroup_member_index":
                    value_text = condition[4].strip() if len(condition) > 4 else ""
                    if not value_text:
                        self._show_warning(
                            "Missing subgroup index",
                            "Please provide an integer value for the subgroup member index.",
                        )
                        return
                    try:
                        int(value_text)
                    except ValueError:
                        self._show_warning(
                            "Invalid subgroup index",
                            "Subgroup member index comparisons only accept integers.",
                        )
                        return

        for action in all_actions:
            if action[0] == "subgroup_variable":
                name_text = action[1].strip() if len(action) > 1 else ""
                if not name_text:
                    self._show_warning(
                        "Missing subgroup variable",
                        "Please enter the subgroup variable name for the action.",
                    )
                    return
                if not self._is_valid_subgroup_name(name_text):
                    self._show_warning(
                        "Invalid subgroup variable",
                        "Subgroup variable names must start with a letter or underscore and contain only alphanumeric characters or underscores.",
                    )
                    return
                operation = action[2] if len(action) > 2 else ""
                if operation not in {"Set Value", "Increase (+1)", "Decrease (-1)"}:
                    self._show_warning(
                        "Invalid subgroup action",
                        "Please choose a valid subgroup action.",
                    )
                    return
                if operation == "Set Value":
                    value_text = action[3].strip() if len(action) > 3 else ""
                    if not value_text:
                        self._show_warning(
                            "Missing subgroup value",
                            "Please provide an integer value to assign to the subgroup variable.",
                        )
                        return
                    try:
                        int(value_text)
                    except ValueError:
                        self._show_warning(
                            "Invalid subgroup value",
                            "Subgroup variables only accept integer values.",
                        )
                        return

        script = self.construct_script(sections_data)
        primary_type = sections_data[0]['condition_type']
        condition_review = ConditionReview(self.player, script, primary_type, self.cond_modifier, self)
        condition_review.exec_()

    def construct_script(self, sections_data):
        combined_actions = list(chain.from_iterable(data['actions'] for data in sections_data))
        need_import = any(action[0] in ("auto_login", "relogin") for action in combined_actions)
        script = ""
        if need_import:
            script += "import gfless_api\n"
        for idx, data in enumerate(sections_data):
            normalized_conditions = self._normalize_condition_labels(data['conditions'])
            keyword = "if" if idx == 0 else "elif"
            script = self._append_condition_clause(script, normalized_conditions, keyword)
            script = self._append_actions_to_script(script, data['actions'])
        return script

    @staticmethod
    def _normalize_condition_labels(conditions_array):
        normalized = []
        for row in conditions_array:
            new_row = list(row)
            if new_row and new_row[0].startswith("ELIF"):
                new_row[0] = new_row[0].replace("ELIF", "IF", 1)
            normalized.append(new_row)
        return normalized

    def _append_condition_clause(self, script, conditions_array, keyword):
        if script and not script.endswith("\n"):
            script += "\n"
        if conditions_array[0][0] == "IF":
            script += f"{keyword} "
        else:
            script += f"{keyword} not "

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
                        script += f'parts[int({split_index})] {operator} "{user_input_value}"'
                    elif user_input_type == "int":
                        script += f'int(parts[int({split_index})]) {operator} int({user_input_value})'
                    elif user_input_type == "raw":
                        script += f'parts[int({split_index})] {operator} {user_input_value}'
                if operator == "contains":
                    if user_input_type == "string":
                        script += f'"{user_input_value}" in parts[int({split_index})]'
                    elif user_input_type == "raw":
                        script += f'{user_input_value} in parts[int({split_index})]'
                if operator == "startswith" or operator == "endswith":
                    if user_input_type == "string":
                        script += f'parts[int({split_index})].{operator}("{user_input_value}")'
                    elif user_input_type == "raw":
                        script += f'parts[int({split_index})].{operator}({user_input_value})'
                if operator == "regex":
                    script += f're.search({user_input_value}, parts[int({split_index})])'
            elif argument == "pos_x" or argument == "pos_y" or argument == "level" or argument == "champion_level" or argument == "hp_percent" or argument == "mp_percent":
                script += f'int(self.{argument}) {operator} int({user_input_value})'
            elif argument == "id" or argument == "name" or argument == "map_id" or argument == "is_resting":
                if operator == "equals":
                    script += f'self.{argument} == "{user_input_value}"'
                elif operator == "startswith" or operator == "endswith" or operator == "contains":
                    script += f'self.{argument}.{operator}("{user_input_value}")'
                else:
                    script += f'self.{argument} {operator} {user_input_value}'
            elif argument == "time.cond":
                if user_input_type == "int":
                    left_expr = "int(time.cond)"
                else:
                    left_expr = "float(time.cond)"
                if user_input_type == "int":
                    right_expr = f"int({user_input_value})"
                elif user_input_type == "raw":
                    right_expr = user_input_value
                else:
                    right_expr = f"float({user_input_value})"
                script += f'{left_expr} {operator} {right_expr}'
            elif argument == "make_party":
                script += f'int(self.make_party_state) == {user_input_value}'
            elif argument == "subgroup_member_index":
                script += f'int(self.subgroup_member_index) {operator} int({user_input_value})'
            elif argument == "subgroup_variable":
                var_name = conditions_array[i][7].strip() if len(conditions_array[i]) > 7 else ""
                script += f'int(selfsubg.{var_name}) {operator} int({user_input_value})'
            elif argument.startswith("attr"):
                if user_input_type == "int":
                    if operator in {"startswith", "endswith"}:
                        script += (
                            f'str(int(self.{argument})).{operator}("{user_input_value}")'
                        )
                    elif operator == "contains":
                        script += (
                            f'"{user_input_value}" in str(int(self.{argument}))'
                        )
                    else:
                        script += (
                            f'int(self.{argument}) {operator} int({user_input_value})'
                        )
                elif user_input_type == "raw":
                    if operator in {"startswith", "endswith"}:
                        script += f'self.{argument}.{operator}({user_input_value})'
                    elif operator == "contains":
                        script += f'{user_input_value} in self.{argument}'
                    else:
                        script += f'self.{argument} {operator} {user_input_value}'
                else:
                    if operator in {"startswith", "endswith"}:
                        script += f'str(self.{argument}).{operator}("{user_input_value}")'
                    elif operator == "contains":
                        script += f'"{user_input_value}" in str(self.{argument})'
                    else:
                        script += f'str(self.{argument}) {operator} "{user_input_value}"'
            else:
                script += f'"{user_input_value}" in self.{argument}'
        script += ":"
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

        return send_packet + recv_packet

    def update_condition_widgets(self, widgets_list, index):
        cur_sender = self.sender()
        if not isinstance(cur_sender, QComboBox):
            cur_sender = widgets_list[index][1]
        selected_item = cur_sender.currentData()
        if selected_item is None:
            selected_item = cur_sender.currentText()
        operator_combo = widgets_list[index][3]
        value_type_combo = widgets_list[index][6]

        subgroup_name_edit = widgets_list[index][7]
        subgroup_name_edit.setVisible(False)

        state_selector = widgets_list[index][8]
        state_selector.setVisible(False)

        operator_combo.clear()
        operator_combo.setEnabled(True)
        operator_combo.setVisible(True)
        value_type_combo.clear()
        value_type_combo.setEnabled(True)
        value_type_combo.setVisible(True)
        value_input = widgets_list[index][4]
        value_input.setEnabled(True)
        value_input.setVisible(True)
        value_input.setPlaceholderText("value")
        if selected_item == "recv_packet" or selected_item == "send_packet":
            operator_combo.addItems(["startswith", "contains", "endswith", "equals"])
            value_type_combo.addItems(["string", "int", "raw"])
            value_type_combo.setCurrentIndex(0)
        elif selected_item == "time.cond":
            operator_combo.addItems(["==", "!=", ">", "<", ">=", "<="])
            value_type_combo.addItems(["int", "raw"])
            value_type_combo.setCurrentIndex(0)
        elif selected_item == "make_party":
            operator_combo.setVisible(False)
            value_type_combo.setVisible(False)
            value_input.setVisible(False)
            state_selector.setVisible(True)
            current_value = value_input.text().strip()
            if current_value == "2":
                state_selector.setCurrentIndex(1)
            else:
                state_selector.setCurrentIndex(0)
            selected_state = state_selector.currentData()
            if selected_state is not None:
                value_input.setText(str(selected_state))
        elif selected_item == "subgroup_member_index":
            operator_combo.addItems(["==", ">=", "<=", ">", "<"])
            value_type_combo.addItem("int")
            value_type_combo.setCurrentIndex(0)
            value_type_combo.setEnabled(False)
            value_input.setPlaceholderText("member index")
        elif selected_item == "subgroup_variable":
            operator_combo.addItems(["==", "!=", ">", "<", ">=", "<="])
            value_type_combo.addItem("int")
            value_type_combo.setCurrentIndex(0)
            value_type_combo.setEnabled(False)
            subgroup_name_edit.setVisible(True)
        else:
            operator_combo.addItems(["==", "!=", ">", "<", ">=", "<=", "startswith", "contains", "endswith"])
            value_type_combo.addItems(["string", "int", "raw"])
            value_type_combo.setCurrentIndex(0)

        if selected_item == "split_recv_packet" or selected_item == "split_send_packet":
            widgets_list[index][5].setVisible(True)
            widgets_list[index][2].setVisible(True)
        else:
            widgets_list[index][5].setVisible(False)
            widgets_list[index][2].setVisible(False)

    def update_dialog_geometry(
        self, maintain_current_height: bool = False, extra_height_ratio: float = 0.0
    ):
        layout = self.layout()
        if layout is None:
            return

        if hasattr(self, "scroll_content"):
            self.scroll_content.adjustSize()

        layout.invalidate()
        layout.activate()

        size_hint = layout.sizeHint()
        if not size_hint.isValid():
            size_hint = self.sizeHint()
        minimum_hint = layout.minimumSize()
        minimum_size_hint = self.minimumSizeHint()

        desired_width = max(
            self.minimumWidth(),
            minimum_hint.width(),
            minimum_size_hint.width(),
            size_hint.width(),
            self.width(),
        )
        desired_height = max(
            self.minimumHeight(),
            minimum_hint.height(),
            minimum_size_hint.height(),
            size_hint.height(),
        )

        if extra_height_ratio > 0:
            desired_height = int(desired_height * (1 + extra_height_ratio))

        if maintain_current_height:
            desired_height = max(desired_height, self.height())

        desired_height = min(desired_height, self.max_dialog_height)

        available_geometry = QApplication.desktop().availableGeometry(self)
        if available_geometry.width() > 0:
            desired_width = min(desired_width, available_geometry.width())
        if available_geometry.height() > 0:
            desired_height = min(desired_height, available_geometry.height())

        self.resize(desired_width, desired_height)

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
    