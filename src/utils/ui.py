'''
Utility Functions for UI
'''
# Standard Import
import logging

# PySide 6
from PySide6.QtWidgets import (
    QLabel, QWidget, QHBoxLayout, QSizePolicy, QKeySequenceEdit, QComboBox,
    QGroupBox, QCheckBox, QFormLayout, QLineEdit, QLabel, QWidget, QHBoxLayout
)
from PySide6.QtCore import Qt, QObject, Signal
from PySide6.QtGui import QKeySequence, QKeyEvent, QDoubleValidator, QIntValidator

# Local import
from src.utils.logger import logger

def validate_numerical_input(input_str: str, error_label: QLabel,
                              val_lowest: float, val_highest: float):
    try:
        val = float(input_str)
        if not (val_lowest <= val <= val_highest):
            raise ValueError
        error_label.setVisible(False)
        return True
    except ValueError:
        error_label.setText(f"请输入 {val_lowest} 到 {val_highest} 之间的数字")
        error_label.setVisible(True)
        logger.debug(f"Invalid numerical input: {input_str}")
        return False

def create_error_label():
    error_label = QLabel()
    error_label.setStyleSheet("color: red;")
    error_label.setVisible(False)
    return error_label

def create_field(label_text, field_widget):
    container = QWidget()
    layout = QHBoxLayout()
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(4)  # Slight spacing

    label = QLabel(label_text)
    layout.addWidget(label)
    layout.addWidget(field_widget)

    # Avoid expanding
    label.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)
    field_widget.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)

    layout.setAlignment(Qt.AlignLeft)
    container.setLayout(layout)
    container.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)

    return container

def clear_debug_canvas(canvas):
    '''
    Flush the debug window viz canvas
    '''
    canvas.clear()
    canvas.setText("按开始或 'F1' 启动脚本")
    canvas.setAlignment(Qt.AlignCenter)

class SingleKeyEdit(QKeySequenceEdit):
    def keyPressEvent(self, event: QKeyEvent):
        key = event.key()
        modifiers = event.modifiers()

        # Allow modifier-only keys
        if key in (Qt.Key_Shift, Qt.Key_Control, Qt.Key_Alt, Qt.Key_Meta):
            self.setKeySequence(QKeySequence(key))
            return

        # Otherwise, record only one key (replace previous)
        if modifiers:
            # This prevents combos like Ctrl+A
            self.setKeySequence(QKeySequence(key))
        else:
            self.setKeySequence(QKeySequence(key))

    def set_key(self, key_str):
        """
        Set the key sequence from string like 'A', 'F1', etc.
        """
        self.setKeySequence(QKeySequence(key_str))

    def get_key(self):
        """
        Return the currently set key as a string, like 'A', 'F1', etc.
        """
        seq = self.keySequence()
        return seq.toString(QKeySequence.NativeText).strip().lower()

class QtLogHandler(logging.Handler, QObject):
    '''
    QtLogHandler
    '''
    log_signal = Signal(str, int)  # message, level

    def __init__(self):
        logging.Handler.__init__(self)
        QObject.__init__(self)

    def emit(self, record):
        msg = self.format(record)
        self.log_signal.emit(msg, record.levelno)

def create_advance_setting_gbox(title, cfg, comments=None, comments_section=None):
    gbox = QGroupBox(title)
    form_layout = QFormLayout()
    gbox._field_refs = {}

    if comments_section and title in comments_section:
        gbox.setToolTip(comments_section[title])

    def get_comment(key):
        if comments and title in comments and key in comments[title]:
            return comments[title][key]
        return ""

    def add_field(key, value):
        tooltip = get_comment(key)

        if isinstance(value, bool):
            checkbox = QCheckBox()
            checkbox.setChecked(value)
            checkbox.setToolTip(tooltip)
            def update_checkbox(state):
                cfg[title][key] = Qt.CheckState(state) == Qt.Checked
            checkbox.stateChanged.connect(update_checkbox)
            form_layout.addRow(QLabel(key), checkbox)
            gbox._field_refs[key] = checkbox

        elif isinstance(value, list) or isinstance(value, tuple):
            hbox = QHBoxLayout()
            edits = []
            for v in value:
                line = QLineEdit(str(v))
                validator = QDoubleValidator() if isinstance(v, float) else QIntValidator()
                line.setValidator(validator)
                line.setToolTip(tooltip)
                edits.append(line)
                hbox.addWidget(line)

            def update_list():
                cfg[title][key] = [
                    float(e.text()) if isinstance(v, float) else int(e.text())
                    for e, v in zip(edits, value) if e.text() != ''
                ]

            for edit in edits:
                edit.textChanged.connect(update_list)

            form_layout.addRow(QLabel(key), hbox)
            gbox._field_refs[key] = edits

        elif isinstance(value, (int, float)):
            line = QLineEdit(str(value))
            validator = QDoubleValidator() if isinstance(value, float) else QIntValidator()
            line.setValidator(validator)
            line.setToolTip(tooltip)
            def update_value(val):
                if val != '':
                    cfg[title][key] = float(val) if isinstance(value, float) else int(val)
            line.textChanged.connect(update_value)
            form_layout.addRow(QLabel(key), line)
            gbox._field_refs[key] = line

        elif isinstance(value, str):
            if tooltip and "Options:" in tooltip:
                # Parse options from tooltip
                options_part = tooltip.split("Options:")[1]
                options = [opt.strip('" ') for opt in options_part.strip().split('"') if opt.strip()]

                # Create drop list
                combo = QComboBox()
                combo.addItems(options)
                if value in options:
                    combo.setCurrentText(value)
                combo.setToolTip(tooltip)

                combo.currentTextChanged.connect(lambda val: cfg[title].__setitem__(key, val))
                form_layout.addRow(QLabel(key), combo)
                gbox._field_refs[key] = combo
            else:
                line = QLineEdit(value)
                line.setToolTip(tooltip)
                line.textChanged.connect(lambda val: cfg[title].__setitem__(key, val))
                form_layout.addRow(QLabel(key), line)
                gbox._field_refs[key] = line

    for key, value in cfg[title].items():
        add_field(key, value)

    gbox.setLayout(form_layout)
    return gbox
