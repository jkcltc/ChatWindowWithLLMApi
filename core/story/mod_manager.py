import sys
from PyQt6.QtWidgets import QTabWidget, QWidget, QGridLayout, QLabel, QPushButton, QCheckBox, QApplication
from mods.status_monitor import StatusMonitorWindow, StatusMonitorInstruction
from mods.story_creator import MainStoryCreaterInstruction
from utils.custom_widget import GradientLabel

#mod管理器
class ModConfiger(QTabWidget):
    """
    A tab-based configuration widget for managing various mods in the application.
    This widget provides a centralized interface for configuring and managing
    different mods including status monitoring, TTS server, and story creation
    functionality. It automatically handles mod availability and provides
    appropriate UI elements for each enabled mod.
    Attributes:
        status_monitor_manager (QWidget): Widget container for status monitor mod
        status_monitor (StatusMonitorWindow): Instance of status monitor window
        status_monitor_enable_box (QCheckBox): Checkbox to enable/disable status monitor
        story_creator_manager (QWidget): Widget container for story creator mod
        tts_server (QWidget): Widget container for TTS server mod
    Methods:
        init_ui(): Initialize the user interface and window properties
        addtabs(): Add all mod configuration tabs
        add_status_monitor(): Add status monitor mod configuration tab
        add_story_creator(): Add story creator mod configuration tab
        add_tts_server(): Add TTS server mod configuration tab
        handle_new_message(message, chathistory): Process new messages for mods
        status_monitor_handle_new_message(message): Handle messages for status monitor
        finish_story_creator_init(): Complete story creator initialization
        run_close_event(): Perform cleanup operations when closing
    """
    def __init__(self):
        self.init_ui()
    
    def init_ui(self):
        super().__init__()
        self.setWindowTitle("Mod Configer")

        screen_geometry = QApplication.primaryScreen().availableGeometry()
        
        width = int(screen_geometry.width() * 0.6)
        height = int(screen_geometry.height() * 0.6)
        
        left = (screen_geometry.width() - width) //4
        top = (screen_geometry.height() - height) // 4
        
        self.setGeometry(left, top, width, height)
        # Create tabs
        self.addtabs()

    def addtabs(self):
        self.add_status_monitor()
        self.add_tts_server()
        self.add_story_creator()

    def handle_new_message(self,message,chathistory):
        self.status_monitor_handle_new_message(message)

    def add_status_monitor(self):
        self.status_monitor_manager = QWidget()
        status_monitor_layout = QGridLayout()
        self.status_monitor_manager.setLayout(status_monitor_layout)
        self.addTab(self.status_monitor_manager, "角色扮演状态栏")

        self.status_monitor_enable_box=QCheckBox("启用挂载")
        status_monitor_layout.addWidget(self.status_monitor_enable_box, 2, 0, 1, 1)
        self.status_monitor_enable_box.setToolTip("模块可以使用")
        if not "mods.status_monitor" in sys.modules:
            self.status_monitor_enable_box.setText('未安装')
            self.status_monitor_enable_box.setEnabled(False)
            self.status_monitor_enable_box.setToolTip("模块未安装")
            return
        
        self.status_monitor = StatusMonitorWindow()

        self.status_label = QLabel("角色扮演状态栏")
        status_monitor_layout.addWidget(self.status_label, 0, 0, 1, 1)
        self.status_label_info = QLabel("AI状态栏是一个mod，用于给AI提供状态信息，可以引导AI的行为。\n需要模型有较强的理解能力。\n预计启用后token使用量增加≈30-50")
        status_monitor_layout.addWidget(self.status_label_info, 1, 0, 1, 2)
        self.status_label_info.setWordWrap(True)
        self.start_status_monitor_button = QPushButton("启动状态栏")
        self.start_status_monitor_button.clicked.connect(lambda : self.status_monitor.show())
        status_monitor_layout.addWidget(self.start_status_monitor_button, 2, 1, 1, 1)
        #挂载MOD设置
        status_monitor_layout.addWidget(StatusMonitorInstruction.mod_configer())

        status_monitor_layout.setRowStretch(0,0)
        status_monitor_layout.setRowStretch(1,0)
        status_monitor_layout.setRowStretch(2,0)
        status_monitor_layout.setRowStretch(3,1)

    def add_story_creator(self):
        self.story_creator_manager=QWidget()
        self.creator_manager_layout=QGridLayout()
        self.story_creator_manager.setLayout(self.creator_manager_layout)
        self.addTab(self.story_creator_manager, "主线创建器")
        if not "mods.story_creator" in sys.modules:
            self.creator_manager_layout.addWidget(QLabel("主线生成器模块未挂载"),0,0,1,1)
            return
        self.enable_story_insert=QCheckBox("启用主线剧情挂载")
        self.creator_manager_layout.addWidget(self.enable_story_insert,0,0,1,1)
        self.main_story_creator_placeholder=GradientLabel('正在等待模型库更新...')
        self.creator_manager_layout.addWidget(self.main_story_creator_placeholder,1,0,1,1)
        
    def finish_story_creator_init(self):
        self.main_story_creator_placeholder.hide()
        self.story_creator=MainStoryCreaterInstruction.mod_configer()
        self.creator_manager_layout.addWidget(self.story_creator,1,0,1,1)

    def status_monitor_handle_new_message(self,message):
        if type(message)==dict:
            message=message[-1]["content"]
        if not "mods.status_monitor" in sys.modules:
            return
        if self.status_monitor.get_ai_variables()!={}:
            self.status_monitor.update_ai_variables(message)
        self.status_monitor.perform_cycle_step()
            
    def add_tts_server(self):
        if not "mods.chatapi_tts" in sys.modules:
            return
        self.tts_server = QWidget()
        self.addTab(self.tts_server,'语音识别')
        return

    def run_close_event(self):
        if "mods.story_creator" in sys.modules and hasattr(self,"story_creator"):
            self.story_creator.save_settings('utils')

