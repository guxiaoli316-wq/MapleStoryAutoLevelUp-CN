'''
UI main
'''
# Standard import
import sys
import os
import json
import copy
import logging

# PySide 6
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QLabel, QVBoxLayout, QWidget,
    QCheckBox, QListWidget, QFileDialog, QHBoxLayout, QLineEdit,
    QPlainTextEdit, QTabWidget, QGroupBox, QFormLayout,
    QSizePolicy, QComboBox, QListWidgetItem, QScrollArea
)
from PySide6.QtGui import QTextCharFormat, QColor, QTextCursor, QPixmap, QImage, QIcon
from PySide6.QtCore import Qt, Signal

# Local import
from src.utils.logger import logger
from src.utils.ui import (
    validate_numerical_input, clear_debug_canvas,
    create_error_label, SingleKeyEdit, QtLogHandler, create_advance_setting_gbox,
)
from src.utils.common import (
    load_yaml, override_cfg, is_mac, save_yaml, get_cfg_diff, load_yaml_with_comments
)

# window size for each tab
if is_mac():
    TAB_WINDOW_SIZE = {
        '主界面': (700, 800),
        '高级设置': (750, 800),
        '游戏画面': (850, 430), # smaller for macbook screen
        '路线地图': (400, 400),
    }
else:
    TAB_WINDOW_SIZE = {
        '主界面': (700, 800),
        '高级设置': (750, 800),
        '游戏画面': (1502, 844),
        '路线地图': (800, 800),
    }

ADV_SETTINGS_HIDE = ['key', 'bot'] # cfg tile here will not shown in advanced settings tabs

class MainWindow(QMainWindow):
    '''
    MainWindow
    '''
    request_close = Signal()

    def __init__(self, controller=None):
        super().__init__()

        # UI window Icon
        self.setWindowIcon(QIcon("media/icon.png"))

        self.controller = controller # autoBotController
        self.prev_tab_window_size = None
        #
        self.selected_map = ""

        # Load default yaml and platform yaml as base config
        _, self.comments, self.comments_section = load_yaml_with_comments("config/config_default.yaml")
        self.cfg_base = load_yaml("config/config_default.yaml")
        if is_mac():
            self.cfg_base = override_cfg(self.cfg_base,
                                         load_yaml("config/config_macOS.yaml"))
        self.cfg = copy.deepcopy(self.cfg_base)
        self.path_cfg_custom = "config/config_custom.yaml" # Custom config path

        # Load database
        self.data = load_yaml("config/config_data.yaml")

        # Window Settings
        self.setWindowTitle("冒险岛怀旧服 - 自动练级")
        self.setMinimumSize(1, 1)
        self.resize(TAB_WINDOW_SIZE['主界面'][0],
                    TAB_WINDOW_SIZE['主界面'][1])

        # Setup tabs
        self.tabs = QTabWidget()
        self.tab_main = self.setup_main_tab()
        self.tab_advance_setting = self.setup_advance_setting_tab()
        self.tab_game_window_viz = self.setup_game_window_viz_tab()
        self.tab_route_map_viz = self.setup_route_map_viz_tab()

        # Add tabs to tab widget
        self.tabs.addTab(self.tab_main, "主界面")
        self.tabs.addTab(self.tab_advance_setting, "高级设置")
        self.tabs.addTab(self.tab_game_window_viz, "游戏画面")
        self.tabs.addTab(self.tab_route_map_viz, "路线地图")

        # Change tabs signals
        self.tabs.currentChanged.connect(self.on_tab_changed)

        # Put tab widget to layout
        layout = QVBoxLayout()
        layout.addWidget(self.tabs)
        container = QWidget()
        container.setLayout(layout)
        self.setCentralWidget(container)

        # Load previous stored UI state
        self.load_ui_state()

        # Signal
        self.request_close.connect(self.close)

    def setup_main_tab(self):
        '''
        Init Main Tab with scrollable area
        '''
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)

        scroll_widget = QWidget()
        scroll_layout = QVBoxLayout(scroll_widget)

        # Control group box
        self.control_gbox = self.create_control_gbox()
        scroll_layout.addWidget(self.control_gbox)

        # Attack setting group box
        self.attack_gbox = self.create_attack_gbox()
        scroll_layout.addWidget(self.attack_gbox)

        # Key bindings group box
        self.key_binding_gbox = self.create_key_binding_gbox()
        scroll_layout.addWidget(self.key_binding_gbox)

        # Pet function group box
        self.pet_skill_gbox = self.create_pet_skill_gbox()
        scroll_layout.addWidget(self.pet_skill_gbox)

        # Map selection group box
        self.map_selection_gbox = self.create_map_selection_gbox()
        scroll_layout.addWidget(self.map_selection_gbox)

        # Logger output window
        self.log_gbox = self.create_log_gbox()
        scroll_layout.addWidget(self.log_gbox)

        scroll_area.setWidget(scroll_widget)

        tab_main = QWidget()
        layout = QVBoxLayout(tab_main)
        layout.addWidget(scroll_area)

        return tab_main

    def setup_advance_setting_tab(self):
        tab_advance_setting = QWidget()

        # Two vertical layouts side-by-side
        left_col = QVBoxLayout()
        right_col = QVBoxLayout()

        # Distribute group boxes evenly between columns
        self.advance_settings_gboxes = {}  # store title -> QGroupBox mapping
        for idx, title in enumerate(self.cfg):
            # Skip hide settings
            if title in ADV_SETTINGS_HIDE:
                continue
            gbox = create_advance_setting_gbox(title, self.cfg,
                                               self.comments,
                                               self.comments_section)
            self.advance_settings_gboxes[title] = gbox
            if idx % 2 == 0:
                left_col.addWidget(gbox)
            else:
                right_col.addWidget(gbox)

        # Wrap columns in a horizontal layout
        row_layout = QHBoxLayout()
        row_layout.addLayout(left_col)
        row_layout.addLayout(right_col)

        # Make it scrollable (recommended for lots of settings)
        scroll_area = QScrollArea()
        container = QWidget()
        container.setLayout(row_layout)
        scroll_area.setWidget(container)
        scroll_area.setWidgetResizable(True)

        # Final layout for the tab
        final_layout = QVBoxLayout()
        final_layout.addWidget(scroll_area)
        tab_advance_setting.setLayout(final_layout)

        return tab_advance_setting

    def setup_game_window_viz_tab(self):
        tab_game_window_viz = QWidget()
        layout = QVBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)  # Remove margins
        tab_game_window_viz.setLayout(layout)

        # Create a large QLabel as a canvas
        self.debug_canvas = QLabel()
        self.debug_canvas.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        clear_debug_canvas(self.debug_canvas)
        self.debug_canvas.setStyleSheet("background-color: black; color: white;")
        layout.addWidget(self.debug_canvas)

        return tab_game_window_viz

    def setup_route_map_viz_tab(self):
        tab_route_map_viz_tab = QWidget()
        layout = QVBoxLayout()
        tab_route_map_viz_tab.setLayout(layout)

        # Create a large QLabel as a canvas
        self.route_map_canvas = QLabel()
        clear_debug_canvas(self.route_map_canvas)
        self.route_map_canvas.setStyleSheet("background-color: black; color: white;")
        layout.addWidget(self.route_map_canvas)

        return tab_route_map_viz_tab

    def save_ui_state(self):
        path = os.path.join(os.path.expanduser("~"), ".maplebot_ui_state.json")
        state = {
            "last_config_path": self.path_cfg_custom
        }
        with open(path, 'w') as f:
            json.dump(state, f)
        logger.info(f"[UI] Save UI state to {path}")

    def load_ui_state(self):
        path = os.path.join(os.path.expanduser("~"), ".maplebot_ui_state.json")
        if os.path.exists(path):
            with open(path, 'r') as f:
                state = json.load(f)
                # Load config
                self.load_config(create_error_label(),
                                 state.get("last_config_path"))
        logger.info(f"[UI] Load UI state from {path}")


    def create_attack_gbox(self):
        '''
        Create attack group box using two-column QFormLayouts
        '''
        gbox = QGroupBox("⚔️ 攻击设置")

        # Left column
        form_left = QFormLayout()
        self.attack_mode = QComboBox()
        self.attack_mode.addItems(["基础攻击", "AOE技能"])
        self.attack_mode.setItemData(0, "directional")
        self.attack_mode.setItemData(1, "aoe_skill")
        self.attack_mode.setFixedWidth(100)

        # Connect dropdown change to handler
        self.attack_mode.currentIndexChanged.connect(
            self.update_atk_config_trigger_by_drop_list
        )

        # Set default value
        form_left.addRow("Attack Mode:", self.attack_mode)

        self.attack_range_x = QLineEdit()
        self.attack_range_x.setFixedWidth(60)
        form_left.addRow("水平范围 X:", self.attack_range_x)

        # Right column
        form_right = QFormLayout()
        self.attack_cooldown = QLineEdit()
        self.attack_cooldown.setFixedWidth(60)
        form_right.addRow("Cooldown (s):", self.attack_cooldown)

        self.attack_range_y = QLineEdit()
        self.attack_range_y.setFixedWidth(60)
        form_right.addRow("垂直范围 Y:", self.attack_range_y)

        # Combine left and right forms
        columns = QHBoxLayout()
        columns.addLayout(form_left)
        columns.addSpacing(20)
        columns.addLayout(form_right)

        # Field validation
        error_label = create_error_label()
        self.attack_range_x.editingFinished.connect(
            lambda: validate_numerical_input(self.attack_range_x.text(), error_label, 0, 9999))
        self.attack_range_y.editingFinished.connect(
            lambda: validate_numerical_input(self.attack_range_y.text(), error_label, 0, 9999))
        self.attack_cooldown.editingFinished.connect(
            lambda: validate_numerical_input(self.attack_cooldown.text(), error_label, 0, 9999))

        # Final layout
        layout = QVBoxLayout()
        layout.addWidget(error_label)
        layout.addLayout(columns)
        gbox.setLayout(layout)
        return gbox

    def create_key_binding_gbox(self):
        gbox = QGroupBox("🎮 按键绑定")
        hbox = QHBoxLayout()

        # Left Column
        form_left = QFormLayout()
        self.basic_attack_key = SingleKeyEdit()
        self.basic_attack_key.setFixedWidth(100)
        form_left.addRow("Basic Attack:", self.basic_attack_key)

        self.teleport_key = SingleKeyEdit()
        self.teleport_key.setFixedWidth(100)
        form_left.addRow("Teleport:", self.teleport_key)

        self.party_key = SingleKeyEdit()
        self.party_key.setFixedWidth(100)
        form_left.addRow("Party:", self.party_key)

        # Right Column
        form_right = QFormLayout()
        self.aoe_skill_key = SingleKeyEdit()
        self.aoe_skill_key.setFixedWidth(100)
        form_right.addRow("AOE Skill:", self.aoe_skill_key)

        self.jump_key = SingleKeyEdit()
        self.jump_key.setFixedWidth(100)
        form_right.addRow("Jump:", self.jump_key)

        self.return_home_key = SingleKeyEdit()
        self.return_home_key.setFixedWidth(100)
        form_right.addRow("Home:", self.return_home_key)

        # Combine left and right column form
        hbox.addLayout(form_left)
        hbox.addSpacing(20)  # space between columns
        hbox.addLayout(form_right)
        gbox.setLayout(hbox)
        return gbox

    def create_buff_skill_section(self):
        '''
        Create buff skill section with toggle checkbox and dynamic rows
        '''
        container = QWidget()
        layout = QHBoxLayout()
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(4)
        layout.setAlignment(Qt.AlignLeft)
        container.setLayout(layout)

        # Auto Buff checkbox
        self.checkbox_enable_buff = QCheckBox("自动Buff")
        self.checkbox_enable_buff.stateChanged.connect(self.toggle_auto_buff)
        layout.addWidget(self.checkbox_enable_buff, alignment=Qt.AlignLeft)

        # Buff section (initially hidden)
        self.buff_section_container = QWidget()
        self.buff_section_container.setVisible(False)
        buff_section_layout = QVBoxLayout()
        buff_section_layout.setContentsMargins(0, 0, 0, 0)
        buff_section_layout.setSpacing(2)
        buff_section_layout.setAlignment(Qt.AlignLeft)
        self.buff_section_container.setLayout(buff_section_layout)

        # Buff rows layout
        self.buff_layout = QVBoxLayout()
        self.buff_layout.setSpacing(2)
        self.buff_layout.setAlignment(Qt.AlignLeft)
        self.buff_inputs = []

        # Initial buff row
        self.add_buff_row()

        # Add dynamic row layout + button
        buff_section_layout.addLayout(self.buff_layout)

        self.button_add_buff = QPushButton("+ 添加Buff按键")
        self.button_add_buff.setFixedWidth(100)
        self.button_add_buff.clicked.connect(self.add_buff_row)
        buff_section_layout.addWidget(self.button_add_buff, alignment=Qt.AlignLeft)

        layout.addWidget(self.buff_section_container)

        return container

    def create_pet_skill_gbox(self):
        gbox = QGroupBox("❤️ 宠物技能")
        layout_form = QFormLayout()

        # Auto Add HP checkbox
        hp_row = QHBoxLayout()
        self.checkbox_auto_add_hp = QCheckBox("自动加HP")
        self.checkbox_auto_add_hp.stateChanged.connect(self.toggle_auto_add_hp)
        hp_row.addWidget(self.checkbox_auto_add_hp)
        # Auto Add HP settings
        self.hp_input_widget, self.add_hp_percent, self.add_hp_key = self.create_hp_mp_widget("HP")
        self.hp_input_widget.setVisible(False) # Hide setting on default
        hp_row.addWidget(self.hp_input_widget)
        # Validation HP percent
        error_label_hp = create_error_label()
        self.add_hp_percent.editingFinished.connect(
            lambda: validate_numerical_input(self.add_hp_percent.text(), error_label_hp, 0, 100))
        # Add to layout
        layout_form.addWidget(error_label_hp)
        layout_form.addRow(hp_row)

        # Auto add MP checkbox
        mp_row = QHBoxLayout()
        self.checkbox_auto_add_mp = QCheckBox("自动加MP")
        self.checkbox_auto_add_mp.stateChanged.connect(self.toggle_auto_add_mp)
        mp_row.addWidget(self.checkbox_auto_add_mp)
        # Auto Add MPHP settings
        self.mp_input_widget, self.add_mp_percent, self.add_mp_key = self.create_hp_mp_widget("MP")
        self.mp_input_widget.setVisible(False)
        mp_row.addWidget(self.mp_input_widget)
        # Validation MP percent
        error_label_mp = create_error_label()
        self.add_mp_percent.editingFinished.connect(
            lambda: validate_numerical_input(self.add_mp_percent.text(), error_label_mp, 0, 100))
        # Add to layout
        layout_form.addWidget(error_label_mp)
        layout_form.addRow(mp_row)

        # Buff skill section
        layout_form.addRow(self.create_buff_skill_section())

        gbox.setLayout(layout_form)
        return gbox

    def create_map_selection_gbox(self):
        '''
        Creates a group box containing the scroll list for map selection
        '''
        gbox = QGroupBox("🗺️ 地图")

        # Load map list from directory
        self.list_widget_maps = QListWidget()
        self.list_widget_maps.itemClicked.connect(self.on_map_selected)
        minimap_dir = "minimaps"
        for name in os.listdir(minimap_dir):
            if name.startswith("."):
                continue  # Skip hidden/system files

            if name in self.data["eng_to_cn"]:
                name_cn = self.data["eng_to_cn"][name]
                full_path = os.path.join(minimap_dir, name)
                if os.path.isdir(full_path):
                    # self.list_widget_maps.addItem(f"{name} ({name_cn})")
                    display_text = f"{name} ({name_cn})"
                    item = QListWidgetItem(display_text)
                    item.setData(Qt.UserRole, name)
                    self.list_widget_maps.addItem(item)

        layout = QVBoxLayout()
        self.label_map_info = QLabel("请选择地图:")
        layout.addWidget(self.label_map_info)
        layout.addWidget(self.list_widget_maps)
        gbox.setLayout(layout)
        return gbox

    def create_log_gbox(self):
        gbox = QGroupBox("📜 日志")
        layout = QVBoxLayout()

        self.log_output = QPlainTextEdit()
        self.log_output.setReadOnly(True)
        self.log_output.setMaximumHeight(150)

        layout.addWidget(self.log_output)
        gbox.setLayout(layout)

        # Create Qt logger handler
        self.qt_log_handler = QtLogHandler()
        self.qt_log_handler.log_signal.connect(self.append_log)
        self.qt_log_handler.setFormatter(
            logging.Formatter('[%(asctime)s] %(levelname)s: %(message)s', '%H:%M:%S'))

        # Add it to your logger
        logger.addHandler(self.qt_log_handler)

        return gbox

    def create_control_gbox(self):
        '''
        Creates a group box with hotkey instructions and a dropdown to select mode
        '''
        gbox = QGroupBox("🕹️ 脚本控制")
        layout = QVBoxLayout()
        layout.setSpacing(6)

        # Load Config Section
        self.load_config_error_label = create_error_label()
        layout.addWidget(self.load_config_error_label)  # Add above the button

        load_config_layout = QHBoxLayout()
        load_config_layout.setSpacing(8)
        load_config_layout.setAlignment(Qt.AlignLeft)

        self.button_load_config = QPushButton("📂 加载配置")
        self.button_load_config.clicked.connect(
            lambda: self.load_config(self.load_config_error_label)
        )
        self.label_config_path = QLabel("(未加载配置)")

        load_config_layout.addWidget(self.button_load_config)
        load_config_layout.addWidget(self.label_config_path)

        # --- Control Buttons ---
        button_layout = QHBoxLayout()
        button_layout.setSpacing(8)
        button_layout.setAlignment(Qt.AlignLeft)

        # Start / Pause Button
        self.button_start_pause = QPushButton("▶ 开始 (F1)")
        self.button_start_pause.setCheckable(True)
        self.button_start_pause.clicked.connect(self.toggle_start_ui)

        # Screenshot Button
        self.button_screenshot = QPushButton("📸 截图 (F2)")
        self.button_screenshot.clicked.connect(self.toggle_screenshot_ui)

        # Record Button
        self.button_record = QPushButton("⏺ 录制 (F3)")
        self.button_record.setCheckable(True)
        self.button_record.clicked.connect(self.toggle_record_ui)

        # Bot Mode Dropdown
        layout_bot_mode = QHBoxLayout()
        layout_bot_mode.setSpacing(8)
        self.bot_mode = QComboBox()
        self.bot_mode.addItems(["普通模式", "辅助模式", "巡逻模式"])
        self.bot_mode.setItemData(0, "normal")
        self.bot_mode.setItemData(1, "aux")
        self.bot_mode.setItemData(2, "patrol")

        layout_bot_mode.addWidget(QLabel("脚本模式:"))
        layout_bot_mode.addWidget(self.bot_mode)
        layout_bot_mode.setAlignment(Qt.AlignLeft)

        button_layout.addWidget(self.button_start_pause)
        button_layout.addWidget(self.button_screenshot)
        button_layout.addWidget(self.button_record)
        button_layout.addLayout(layout_bot_mode)

        layout.addLayout(button_layout)
        layout.addLayout(load_config_layout)

        gbox.setLayout(layout)
        return gbox
        logger.info(f"[UI] Map selected: {map_name}")

    def create_attack_widget(self):
        '''
        Create a wedge widget: "Press key ➜ [KEY] for Mode A/B"
        '''
        layout_main = QHBoxLayout()

        layout_main.addWidget(QLabel("攻击按键:"))
        key_input = SingleKeyEdit()
        key_input.setFixedWidth(100)
        layout_main.addWidget(key_input)

        # Horizontal Range
        layout_main.addWidget(QLabel("水平范围 X:"))
        range_x = QLineEdit()
        range_x.setPlaceholderText("50")
        range_x.setFixedWidth(60)
        layout_main.addWidget(range_x)

        # Vertical Range
        layout_main.addWidget(QLabel("垂直范围 Y:"))
        range_y = QLineEdit()
        range_y.setPlaceholderText("50")
        range_y.setFixedWidth(60)
        layout_main.addWidget(range_y)

        # CoolDown
        layout_main.addWidget(QLabel("冷却时间 (秒):"))
        cooldown = QLineEdit()
        cooldown.setPlaceholderText("0.1")
        cooldown.setFixedWidth(60)
        layout_main.addWidget(cooldown)

        container = QWidget()
        container.setLayout(layout_main)

        return container, key_input, range_x, range_y, cooldown

    def create_hp_mp_widget(self, title):
        '''
        Creates a widget for Auto HP/MP usage with tight label-field alignment
        '''
        container = QWidget()
        layout_main = QVBoxLayout()
        layout_main.setContentsMargins(0, 0, 0, 0)
        layout_main.setSpacing(2)

        # Input line
        input_layout = QHBoxLayout()
        input_layout.setContentsMargins(0, 0, 0, 0)
        input_layout.setSpacing(2)
        input_layout.setAlignment(Qt.AlignLeft)

        label_1 = QLabel(f"当 {title} 低于:")
        label_1.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)

        percent = QLineEdit()
        percent.setPlaceholderText("50")
        percent.setFixedWidth(60)

        label_2 = QLabel("% 时，按 ")
        label_2.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)

        input_key = SingleKeyEdit()
        input_key.setFixedWidth(100)

        label_3 = QLabel("keys")
        label_3.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)

        # Add to layout
        input_layout.addWidget(label_1)
        input_layout.addWidget(percent)
        input_layout.addWidget(label_2)
        input_layout.addWidget(input_key)
        input_layout.addWidget(label_3)

        layout_main.addLayout(input_layout)
        container.setLayout(layout_main)

        return container, percent, input_key

    def load_config(self, error_label, path=None):
        '''
        Load config_custom.yaml from file and apply settings to UI
        '''
        if path is None:
            path, _ = QFileDialog.getOpenFileName(
                self, "Select Config File", "", "YAML Files (*.yaml);;All Files (*)"
            )
            if not path:
                return  # User canceled

        # Validation
        if not path.endswith(".yaml"):
            error_label.setText("仅支持 .yaml 格式文件")
            error_label.setVisible(True)
            return

        # Validate the file name
        if "config_default.yaml" in path or "config_data.yaml" in path or \
           "config_macOS.yaml" in path:
            error_label.setText(f"{path} cannot be loaded as customized yaml")
            error_label.setVisible(True)
            return

        error_label.setVisible(False)
        self.label_config_path.setText(path)
        self.label_config_path.setStyleSheet("color: green")

        # Load customized yaml
        try:
            self.cfg = override_cfg(self.cfg, load_yaml(path))
        except FileNotFoundError:
            logger.warning(f"[UI] Unable to find config file: {path}")
        else:
            self.path_cfg_custom = path

        # Re-apply config to UI
        self.apply_config_to_ui()

    def update_atk_config_trigger_by_drop_list(self):
        '''
        Update attack config fields based on selected attack mode from drop-down.
        '''
        index = self.attack_mode.currentIndex()  # Get selected index
        if index == 0:
            atk_cfg = self.cfg["directional_attack"]
        elif index == 1:
            atk_cfg = self.cfg["aoe_skill"]
        else:
            atk_cfg = None

        if atk_cfg:
            self.attack_range_x.setText(str(atk_cfg["range_x"]))
            self.attack_cooldown.setText(str(atk_cfg["cooldown"]))
            self.attack_range_y.setText(str(atk_cfg["range_y"]))

    def apply_config_to_ui(self):
        # === Attack Section ===
        atk_cfg = None
        if self.cfg["bot"]["attack"] == "directional":
            self.attack_mode.setCurrentIndex(0)
            atk_cfg = self.cfg["directional_attack"]
        elif self.cfg["bot"]["attack"] == "aoe_skill":
            self.attack_mode.setCurrentIndex(1)
            atk_cfg = self.cfg["aoe_skill"]
        self.attack_range_x.setText(str(atk_cfg["range_x"]))
        self.attack_cooldown.setText(str(atk_cfg["cooldown"]))
        self.attack_range_y.setText(str(atk_cfg["range_y"]))

        # === Key Bindings ===
        key_cfg = self.cfg["key"]
        self.basic_attack_key.set_key(key_cfg["directional_attack"])
        self.teleport_key.set_key(key_cfg["teleport"])
        self.party_key.set_key(key_cfg["party"])
        self.aoe_skill_key.set_key(key_cfg["aoe_skill"])
        self.jump_key.set_key(key_cfg["jump"])
        self.return_home_key.set_key(key_cfg["return_home"])

        # === HP/MP Section ===
        hm_cfg = self.cfg["health_monitor"]
        self.checkbox_auto_add_hp.setChecked(hm_cfg["add_hp_percent"] > 0)
        self.add_hp_percent.setText(str(hm_cfg["add_hp_percent"]))
        self.add_hp_key.set_key(self.cfg["key"]["add_hp"])
        self.checkbox_auto_add_mp.setChecked(hm_cfg["add_mp_percent"] > 0)
        self.add_mp_percent.setText(str(hm_cfg["add_mp_percent"]))
        self.add_mp_key.set_key(self.cfg["key"]["add_mp"])

        # === Buff SKills ===
        # Set MP settings default value
        buff_cfg = self.cfg["buff_skill"]
        self.checkbox_enable_buff.setChecked(len(buff_cfg["keys"]))
        # Clear old UI rows
        for i in reversed(range(self.buff_layout.count())):
            widget = self.buff_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        self.buff_inputs.clear()
        # Add new rows based on config
        for key, cd in zip(buff_cfg["keys"], buff_cfg["cooldown"]):
            self.add_buff_row(key=key, cooldown=str(cd))  # <- new version below

        # === Bot Mode ===
        index = 0
        if self.cfg["bot"]["mode"] == "aux":
            index = 1
        elif self.cfg["bot"]["mode"] == "patrol":
            index = 2
        self.bot_mode.setCurrentIndex(index)

        # Map Selection
        for i in range(self.list_widget_maps.count()):
            item = self.list_widget_maps.item(i)
            if item.data(Qt.UserRole) == self.cfg["bot"]["map"]:
                self.list_widget_maps.setCurrentItem(item)
                self.on_map_selected(item)  # Reuse existing logic
                break

        # Advance settings
        self.update_advance_setting_ui_from_cfg()

    def set_gbox_enabled(self, enabled: bool):
        gray_style = "color: lightgray;" if not enabled else ""
        gboxs = [
            self.attack_gbox,
            self.key_binding_gbox,
            self.pet_skill_gbox,
            self.map_selection_gbox,
        ]
        gboxs += list(self.advance_settings_gboxes.values())
        # Apply disable + style
        for gbox in gboxs:
            gbox.setEnabled(enabled)
            if hasattr(gbox, "setStyleSheet"):
                gbox.setStyleSheet(gray_style)

    def on_tab_changed(self, index):
        tab_name = self.tabs.tabText(index)
        if tab_name == "游戏画面":
            self.controller.enable_bot_viz()

        elif tab_name == "路线地图":
            self.controller.enable_bot_viz()

        elif tab_name == "主界面":
            self.controller.disable_bot_viz()
            self.apply_config_to_ui()

        elif tab_name == "高级设置":
            self.controller.disable_bot_viz()
            self.update_cfg_from_main_ui()
            self.apply_config_to_ui()

        else:
            logger.error(f"[UI] Unexpected tab name: {tab_name}")
            self.controller.disable_bot_viz()

        if tab_name in TAB_WINDOW_SIZE:
            self.resize(TAB_WINDOW_SIZE[tab_name][0],
                        TAB_WINDOW_SIZE[tab_name][1])

        logger.info(f"[UI] user change tab to {tab_name}")

    def on_map_selected(self, item):
        # Parse English name from item text
        map_name = item.text().split(" (")[0]
        self.selected_map = map_name

        map_path = os.path.join("minimaps", map_name)
        self.label_map_info.setText(f"已选择地图: {map_path}")

    def on_mode_checkbox_toggle(self, toggled_checkbox):
        '''
        Mutural exclusive checkbox
        '''
        if not toggled_checkbox.isChecked():
            # Prevent unchecking — always keep one mode selected
            toggled_checkbox.setChecked(True)
            return

        if toggled_checkbox == self.checkbox_attack:
            self.checkbox_aoe_skill.blockSignals(True)
            self.checkbox_aoe_skill.setChecked(False)
            self.checkbox_aoe_skill.blockSignals(False)

        elif toggled_checkbox == self.checkbox_aoe_skill:
            self.checkbox_attack.blockSignals(True)
            self.checkbox_attack.setChecked(False)
            self.checkbox_attack.blockSignals(False)

    def toggle_auto_add_hp(self, state):
        '''
        Callback function for auto add hp checkbox
        '''
        enabled = Qt.CheckState(state) == Qt.Checked
        self.hp_input_widget.setVisible(enabled)
        logger.debug("[toggle_auto_add_hp] Checkbox toggled: "
                    f"{'Enabled' if enabled else 'Disabled'}")

    def toggle_auto_add_mp(self, state):
        '''
        Callback function for auto add mp checkbox
        '''
        enabled = Qt.CheckState(state) == Qt.Checked
        self.mp_input_widget.setVisible(enabled)
        logger.debug("[toggle_auto_add_mp] Checkbox toggled: "
                    f"{'Enabled' if enabled else 'Disabled'}")

    def toggle_auto_buff(self, state):
        '''
        Callback function for auto buff
        '''
        enabled = Qt.CheckState(state) == Qt.Checked
        self.buff_section_container.setVisible(enabled)
        logger.debug("[toggle_auto_buff] Buff section :"
                     f"{'Enabled' if enabled else 'Disabled'}")

    def toggle_start_ui(self):
        if self.button_start_pause.isChecked(): # When start autobot
            self.update_cfg_from_main_ui()

            # Save UI config to tmp file
            cfg_path = "config/.config_tmp.yaml"
            save_yaml(self.cfg, cfg_path)

            # Start AutoBot
            ret = self.controller.start_bot(cfg_path)

            if ret == 0: # Start success
                self.button_start_pause.setText("⏸ 暂停 (F1)")
                self.button_start_pause.setStyleSheet("background-color: lightgreen;")
                self.set_gbox_enabled(False)
            else:
                # Start failed
                self.button_start_pause.setChecked(False)

        else: # When pause autobot
            self.button_start_pause.setText("▶ 开始 (F1)")
            self.button_start_pause.setStyleSheet("")
            self.controller.pause_bot()
            self.set_gbox_enabled(True)
            clear_debug_canvas(self.debug_canvas) # Set debug viz to null
            clear_debug_canvas(self.route_map_canvas) # Set debug viz to null

    def toggle_screenshot_ui(self):
        self.controller.take_screenshot()

    def toggle_record_ui(self):
        if self.button_record.isChecked():
            self.button_record.setText("⏹ 停止 (F3)")
            self.button_record.setStyleSheet("background-color: orange;")
            self.controller.start_recording()
        else:
            self.button_record.setText("⏺ 录制 (F3)")
            self.button_record.setStyleSheet("")
            self.controller.stop_recording()

    def update_cfg_from_main_ui(self):
        '''
        Collect setting from UI framework
        '''
        # Bot control gbox
        self.cfg["bot"]["mode"] = self.bot_mode.currentData()
        # Attack setting gbox
        if self.attack_mode.currentText() == "基础攻击":
            self.cfg["bot"]["attack"] = "directional"
            self.cfg["key"]["directional_attack"] = self.basic_attack_key.get_key()
            self.cfg["directional_attack"]["range_x"] = int(self.attack_range_x.text())
            self.cfg["directional_attack"]["range_y"] = int(self.attack_range_y.text())
            self.cfg["directional_attack"]["cooldown"] = float(self.attack_cooldown.text())
        elif self.attack_mode.currentText() == "AOE技能":
            self.cfg["bot"]["attack"] = "aoe_skill"
            self.cfg["key"]["aoe_skill"] = self.basic_attack_key.get_key()
            self.cfg["aoe_skill"]["range_x"] = int(self.attack_range_x.text())
            self.cfg["aoe_skill"]["range_y"] = int(self.attack_range_y.text())
            self.cfg["aoe_skill"]["cooldown"] = float(self.attack_cooldown.text())
        else:
            logger.error(f"[update_cfg_from_main_ui] Unsupported attack mode: {self.cfg['bot']['attack']}")
        # Key binding gbox
        self.cfg["key"]["teleport"] = self.teleport_key.get_key()
        self.cfg["key"]["party"] = self.party_key.get_key()
        self.cfg["key"]["aoe_skill"] = self.aoe_skill_key.get_key()
        self.cfg["key"]["jump"] = self.jump_key.get_key()
        self.cfg["key"]["return_home"] = self.return_home_key.get_key()
        # Auto Add HP
        if self.checkbox_auto_add_hp.isChecked():
            self.cfg["health_monitor"]["add_hp_percent"] = int(self.add_hp_percent.text())
            self.cfg["key"]["add_hp"] = self.add_hp_key.get_key()
        else:
            self.cfg["health_monitor"]["add_hp_percent"] = 0
        # Auto Add MP
        if self.checkbox_auto_add_mp.isChecked():
            self.cfg["health_monitor"]["add_mp_percent"] = int(self.add_mp_percent.text())
            self.cfg["key"]["add_mp"] = self.add_mp_key.get_key()
        else:
            self.cfg["health_monitor"]["add_mp_percent"] = 0
        # Buff skills
        if not self.checkbox_enable_buff.isChecked():
            self.cfg["buff_skill"]["keys"] = []
            self.cfg["buff_skill"]["cooldown"] = []
        else:
            keys = []
            cooldowns = []
            for key_input, cd_input in self.buff_inputs:
                key = key_input.get_key().strip()
                try:
                    cd = int(cd_input.text())
                except ValueError:
                    cd = 0  # or skip this entry / log warning
                if key:
                    keys.append(key)
                    cooldowns.append(cd)
            self.cfg["buff_skill"]["keys"] = keys
            self.cfg["buff_skill"]["cooldown"] = cooldowns

        # Map selection
        self.cfg["bot"]["map"] = self.selected_map

    def update_debug_canvas(self, img):
        if img is None:
            return

        height, width, _ = img.shape
        logger.debug(f"[update_debug_canvas] Image size: {width}x{height}, Canvas size: {self.debug_canvas.width()}x{self.debug_canvas.height()}")
        
        qimg = QImage(img.data, width, height, QImage.Format_BGR888)
        pixmap = QPixmap.fromImage(qimg)

        # Scale the image to fit canvas while maintaining aspect ratio
        scaled_pixmap = pixmap.scaled(
                            self.debug_canvas.width(),
                            self.debug_canvas.height(),
                            Qt.IgnoreAspectRatio,
                            Qt.SmoothTransformation)

        self.debug_canvas.setPixmap(scaled_pixmap)

    def update_route_map_canvas(self, img):
        if img is None:
            return

        height, width, _ = img.shape
        qimg = QImage(img.data, width, height, QImage.Format_BGR888)
        pixmap = QPixmap.fromImage(qimg)

        scaled_pixmap = pixmap.scaled(
                            self.route_map_canvas.width(),
                            self.route_map_canvas.height(),
                            Qt.IgnoreAspectRatio,
                            Qt.SmoothTransformation)

        self.route_map_canvas.setPixmap(scaled_pixmap)

    def update_advance_setting_ui_from_cfg(self):
        '''
        Updates UI fields in an existing gbox to reflect the latest cfg[title].
        '''
        for title in self.cfg:
            if title in ADV_SETTINGS_HIDE: # skip hide settings
                continue
            refs = getattr(self.advance_settings_gboxes[title], "_field_refs", {})
            for key, value in self.cfg[title].items():
                widget = refs.get(key)
                if widget is None:
                    continue  # unknown field, skip

                # Checkbox
                if isinstance(value, bool) and isinstance(widget, QCheckBox):
                    widget.setChecked(value)

                # List of QLineEdits
                elif isinstance(value, (list, tuple)) and isinstance(widget, list):
                    for line, v in zip(widget, value):
                        line.setText(str(v))

                # Single numeric value
                elif isinstance(value, (int, float)) and isinstance(widget, QLineEdit):
                    widget.setText(str(value))

                # Droplist
                elif isinstance(value, str) and isinstance(widget, QComboBox):
                    index = widget.findText(value)
                    if index != -1:
                        widget.setCurrentIndex(index)

                # String
                elif isinstance(value, str) and isinstance(widget, QLineEdit):
                    widget.setText(value)

    def add_buff_row(self, key="", cooldown=""):
        row_widget = QWidget()
        row_layout = QHBoxLayout()
        row_layout.setContentsMargins(0, 0, 0, 0)
        row_layout.setSpacing(4)  # Tight spacing

        # Buff Key
        label_1 = QLabel("按 ")
        label_1.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)

        key_edit = SingleKeyEdit()
        key_edit.setFixedWidth(100)
        if key:
            key_edit.set_key(key)
        key_edit.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)

        row_layout.addWidget(label_1)
        row_layout.addWidget(key_edit)

        # Cooldown
        label_cd = QLabel(" 键，每隔 ")
        label_cd.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)

        cooldown_edit = QLineEdit()
        cooldown_edit.setPlaceholderText("0")
        cooldown_edit.setText(cooldown)
        cooldown_edit.setFixedWidth(60)
        cooldown_edit.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Preferred)

        label_second = QLabel(" 秒。")
        label_second.setSizePolicy(QSizePolicy.Maximum, QSizePolicy.Preferred)

        row_layout.addWidget(label_cd)
        row_layout.addWidget(cooldown_edit)
        row_layout.addWidget(label_second)

        # Error label (optional)
        error_label = QLabel()
        error_label.setStyleSheet("color: red;")
        error_label.setVisible(False)

        # Validation
        cooldown_edit.editingFinished.connect(
            lambda: validate_numerical_input(cooldown_edit.text(), error_label, 0, 9999))

        # Delete button
        button_delete = QPushButton("-")
        button_delete.setFixedWidth(20)
        button_delete.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        button_delete.clicked.connect(lambda: self.remove_buff_row(row_widget, error_label))
        row_layout.addWidget(button_delete)

        # Align to left and fix widget height
        row_layout.setAlignment(Qt.AlignLeft)
        row_widget.setLayout(row_layout)
        row_widget.setFixedHeight(28)  # Optional: reduce vertical height

        self.buff_layout.addWidget(error_label)
        self.buff_layout.addWidget(row_widget)
        self.buff_inputs.append((key_edit, cooldown_edit))

    def remove_buff_row(self, row_widget: QWidget, error_label: QLabel):
        # Remove from layout_main
        self.buff_layout.removeWidget(row_widget)
        self.buff_layout.removeWidget(error_label)
        row_widget.setParent(None)
        error_label.setParent(None)

        # Remove from tracking list
        self.buff_inputs = [
            entry for entry in self.buff_inputs if entry[0] != row_widget
        ]

    def append_log(self, message: str, level: int):
        color = QColor("white")
        if level >= logging.ERROR:
            color = QColor("red")
        elif level >= logging.WARNING:
            color = QColor("orange")

        fmt = QTextCharFormat()
        fmt.setForeground(color)

        cursor = self.log_output.textCursor()
        cursor.movePosition(QTextCursor.End)
        cursor.insertText(message + "\n", fmt)
        self.log_output.setTextCursor(cursor)
        self.log_output.ensureCursorVisible()

    def closeEvent(self, event):
        '''
        Call when user close the UI window
        '''
        # Collect current UI setting and update to self.cfg
        self.update_cfg_from_main_ui()
        # Save current UI config to config_XXXX.yaml
        if "config_default.yaml" not in self.path_cfg_custom:
            cfg_diff = get_cfg_diff(self.cfg_base, self.cfg)
            save_yaml(cfg_diff, self.path_cfg_custom)

        # Save your UI state (e.g., last loaded config path)
        self.save_ui_state()

        # Terminate all bot threads
        self.controller.terminate_bot()

        event.accept()  # Continue with the close

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())
