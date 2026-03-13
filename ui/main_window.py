import time
start_time_stamp=time.time()

_ts_1=f'CWLA init timer start, time stamp:{time.time()-start_time_stamp:.2f}s'

# 并发导入重类
import threading
def _ir():
    import requests
def _ioai():
    import openai
def _ids():
    from config import APP_SETTINGS,ConfigManager
    ConfigManager.load_settings(APP_SETTINGS)


threading.Thread(
    target=_ir,
).start()
threading.Thread(
    target=_ioai,
).start()
threading.Thread(
    target=_ids,
).start()

import os
import sys
from typing import TYPE_CHECKING,TypedDict, Optional, Literal

#基础类初始化
from common.init_functions import install_packages

_ts_2=f'CWLA iner import finished, time stamp:{time.time()-start_time_stamp:.2f}s'

install_packages()

#第三方类初始化
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from PyQt6.QtSvg import *
app = QApplication(sys.argv)

_ts_3=f'CWLA 3rd party lib import finished, time stamp:{time.time()-start_time_stamp:.2f}s'

from ui.splash_window import SplashScreen
sp = SplashScreen()
sp.show()
st_ct = 1
def start_log(ts):
    global st_ct
    st_ct += 1
    LOGGER.log(ts)
    sp.progress(int(100*st_ct/12), ts)

#自定义类初始化

from common.info_module import InfoManager,LOGMANAGER

LOGGER=LOGMANAGER
LOGGER.log(_ts_1)
LOGGER.log(_ts_2)
LOGGER.log(_ts_3)

start_log(f'CWLA Log init finished, time stamp:{time.time()-start_time_stamp:.2f}s')

from config import APP_SETTINGS,APP_RUNTIME,ConfigManager
from config.settings import LLMUsagePack # 不行我看不得这个

# 就地初始化
# ConfigManager.load_settings(APP_SETTINGS)

start_log(f'CWLA config recover finished, time stamp:{time.time()-start_time_stamp:.2f}s')

from service.chat_completion.llm_requester import APIRequestHandler
from service.tts.chatapi_tts import TTSAgent

start_log(f'CWLA service import finished, time stamp:{time.time()-start_time_stamp:.2f}s')

from core.session.title_generate import TitleGenerator
start_log(f'CWLA core title import finished, time stamp:{time.time()-start_time_stamp:.2f}s')

from core.multimodal_coordination.background_generate import BackgroundAgent

start_log(f'CWLA core multimodal_coordination import finished, time stamp:{time.time()-start_time_stamp:.2f}s')

from core.app_core import CWLACore

start_log(f'CWLA core import finished, time stamp:{time.time()-start_time_stamp:.2f}s')

from ui.custom_widget import *
from ui.setting.system_prompt_widget import SystemPromptManager,SystemPromptComboBox
from ui.setting.main_setting_window import MainSettingWindow
from ui.setting.api_config_widget import APIConfigWidget
from ui.setting.model_poll_setting_widget import RandomModelSelecter
from ui.setting.theme_manager import ThemeSelector
from ui.avatar import AvatarCreatorWindow
from ui.chat.user_input import MultiModalTextEdit
from ui.chat.chathistory_view_widget import ChatapiTextBrowser,ChatHistoryWidget,ChatHistoryTextView,HistoryListWidget
from ui.chat.chathistory_manage_widget import ChatHistoryEditor
from ui.tool_call.tool_manager_widget import FunctionManager

from ui.bridge import UiMainSignalBridge

start_log(f'CWLA UI import finished, time stamp:{time.time()-start_time_stamp:.2f}s')

from utils.preset_data import *
from utils.usage_analysis import TokenAnalysisWidget
from utils.chat_buffer import ChatBuffer

start_log(f'CWLA utils import finished, time stamp:{time.time()-start_time_stamp:.2f}s')

start_log(f'CWLA import finished, time stamp:{time.time()-start_time_stamp:.2f}s')

if TYPE_CHECKING:
    from core.session.session_model import ChatSession

import csv
class FPSMonitor(QLabel):
    def __init__(self, parent=None, alert_threshold_ms=100):
        super().__init__(parent)
        self.setStyleSheet("""
            QLabel {
                background-color: rgba(0, 0, 0, 180);
                color: #00FF00;
                font-family: Consolas, monospace;
                font-size: 12px;
                font-weight: bold;
                padding: 4px 8px;
                border-radius: 4px;
            }
        """)
        self.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.alert_threshold_ms = alert_threshold_ms
        self.frames = 0
        self.max_dt = 0.0
        self.last_tick = time.perf_counter()

        self.perf_history = []
        self.start_timestamp = time.time()

        self.heartbeat = QTimer(self)
        self.heartbeat.timeout.connect(self._on_tick)
        self.heartbeat.start(2) 

        self.updater = QTimer(self)
        self.updater.timeout.connect(self._update_display)
        self.updater.start(500)

    def _on_tick(self):
        now = time.perf_counter()
        dt = now - self.last_tick
        self.last_tick = now

        self.frames += 1
        if dt > self.max_dt:
            self.max_dt = dt

    def _update_display(self):
        fps = int(self.frames * 2) 
        lag_ms = int(self.max_dt * 1000)

        run_time = round(time.time() - self.start_timestamp, 1)
        self.perf_history.append((run_time, fps, lag_ms))

        color = "#00FF00"
        if lag_ms > 30:  color = "#FFFF00"
        if lag_ms > 100: color = "#FF0000"

        self.setText(f"FPS: {fps:02d} | Lag: <span style='color:{color}'>{lag_ms}ms</span>")
        self.adjustSize()

        self.frames = 0
        self.max_dt = 0.0

    def export_csv(self, file_path="ui_performance.csv"):
        if not self.perf_history:
            return

        try:
            with open(file_path, mode='w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                # 写入表头
                writer.writerow(["Run_Time(s)", "FPS", "Max_Lag(ms)"])
                # 批量写入数据
                writer.writerows(self.perf_history)
            print(f"性能数据已成功导出至: {os.path.abspath(file_path)}")
        except Exception as e:
            print(f"导出性能数据失败: {e}")

class MainWindow(QMainWindow):
    pass

class MainWindow(MainWindow):
    back_animation_finished = pyqtSignal()
    update_background_signal= pyqtSignal(str)

    def setupTheme(self):
        # 从全局配置获取路径
        theme_path = APP_SETTINGS.ui.theme

        if not theme_path:
            return

        if os.path.exists(theme_path):
            try:
                with open(theme_path, "r", encoding="utf-8") as f:
                    qss = f.read()
                    QApplication.instance().setStyleSheet(qss)
            except Exception as e:
                print(f"应用保存的主题失败: {e}")
        else:
            print(f"配置的主题文件不存在: {theme_path}")


    def __init__(self):
        super().__init__()
        self.setupTheme()
        self.setWindowTitle("CWLA - Chat Window with LLM Api")
        self.setWindowIcon(self.render_svg_to_icon(MAIN_ICON))

        screen_geometry = QApplication.primaryScreen().availableGeometry()
        
        width = int(screen_geometry.width() * 0.8)
        height = int(screen_geometry.height() * 0.8)
        
        left = (screen_geometry.width() - width) // 2
        top = (screen_geometry.height() - height) // 2
        
        self.setGeometry(left, top, width, height)

        self.init_app_core()
        

        # 初始化参数
        self.init_self_params()

        # 提示窗口
        self.init_info_manager()

        self.init_concurrenter()
        self.init_function_window()

        self.init_system_prompt_window()
        self.init_chat_bubble_render_loop()

        self.init_signal_bus()
        self.connect_bus_signals()
        
        # 模型轮询器
        self.ordered_model=RandomModelSelecter(
            api_config=APP_SETTINGS.api,
            poll_settings=APP_SETTINGS.model_poll,
            logger=self.info_manager
        )

        # 创建主布局
        self.main_layout = QGridLayout()
        central_widget = QFrame()
        central_widget.setLayout(self.main_layout)
        self.setCentralWidget(central_widget)

        #背景
        self.init_back_ground_label(APP_SETTINGS.background.image_path)

        api_label = QLabel("API 提供商:")
        self.api_var = QComboBox()
        """主要对话供应商下拉框"""

        model_label = QLabel("选择模型:")
        self.model_combobox = QComboBox()
        """主要模型下拉框"""

        self.api_var.addItems(APP_SETTINGS.api.providers.keys())
        self.api_var.currentTextChanged.connect(self.update_model_combobox)

        # 手动触发一次，初始化模型列表
        if self.api_var.currentText():
            self.update_model_combobox(self.api_var.currentText())

        index = self.api_var.findText(APP_SETTINGS.ui.LLM.provider)
        if index >= 0:
            self.api_var.setCurrentIndex(index)
        
        index = self.model_combobox.findText(APP_SETTINGS.ui.LLM.model)
        if index >= 0:
            self.model_combobox.setCurrentIndex(index)

        self.api_var.currentTextChanged.connect(
            lambda s: APP_SETTINGS.ui.LLM.update({"provider":s})
        )

        self.model_combobox.currentTextChanged.connect(
            lambda text: APP_SETTINGS.ui.LLM.update({"model":text})
        )

        #轮换模型
        self.use_muti_model=QCheckBox("模型轮询")
        self.use_muti_model.setChecked(APP_SETTINGS.model_poll.enabled)
        self.use_muti_model.toggled.connect(
            lambda checked: (
                self.ordered_model.show() if checked else self.ordered_model.hide(),
                self.api_var.setEnabled(not checked),
                self.model_combobox.setEnabled(not checked)
            )
        )
        self.use_muti_model.setToolTip("用于TPM/RPM合并扩增|AI回复去重")

        #汇流优化
        self.use_concurrent_model=QCheckBox("使用汇流优化")
        self.use_concurrent_model.setChecked(APP_SETTINGS.concurrent.enabled)
        self.use_concurrent_model.setToolTip("用于提高生成质量\n注意！！极高token消耗量！！")
        self.use_concurrent_model.toggled.connect(lambda checked: self.show_concurrent_model(show=checked))

        #两模式互斥
        self.use_muti_model.toggled.connect(lambda c: self.use_concurrent_model.setChecked(False) if c else None)
        self.use_muti_model.toggled.connect(lambda c: APP_SETTINGS.model_poll.update({"enabled":c}))
        self.use_concurrent_model.toggled.connect(lambda c: self.use_muti_model.setChecked(False) if c else None)
        self.use_concurrent_model.toggled.connect(lambda c: APP_SETTINGS.concurrent.update({"enabled":c}))


        #优化功能触发进度
        self.opti_frame=QGroupBox("触发优化")
        self.opti_frame_layout = QGridLayout()
        self.opti_frame.setLayout(self.opti_frame_layout)
        self.Background_trigger_bar = QProgressBar(self)
        self.opti_frame_layout.addWidget(self.Background_trigger_bar,0,0,1,7)

        self.chat_opti_trigger_bar = QProgressBar(self)
        self.opti_frame_layout.addWidget(self.chat_opti_trigger_bar,1,0,1,7)

        self.cancel_trigger_background_update=QPushButton("×")
        self.cancel_trigger_background_update.clicked.connect(self.session_manager.current_chat.reset_background_rounds)

        self.cancel_trigger_chat_opti=QPushButton("×")
        self.cancel_trigger_chat_opti.clicked.connect(self.session_manager.current_chat.reset_chat_rounds)

        self.opti_frame_layout.addWidget(self.cancel_trigger_background_update, 0,  8,  1,  1)
        self.opti_frame_layout.addWidget(self.cancel_trigger_chat_opti,         1,  8,  1,  1)
        self.opti_frame.hide()

        self.stat_tab_widget = QTabWidget()
        self.stat_tab_widget.setSizePolicy(QSizePolicy.Policy.Preferred,QSizePolicy.Policy.Minimum)
        api_page = QWidget()
        api_page_layout = QGridLayout(api_page)

        api_page_layout.addWidget(api_label                 ,0,0,1,1)
        api_page_layout.addWidget(self.api_var              ,0,1,1,1)
        api_page_layout.addWidget(model_label               ,1,0,1,1)
        api_page_layout.addWidget(self.model_combobox       ,1,1,1,1)
        api_page_layout.addWidget(self.use_muti_model       ,2,0,1,1)
        api_page_layout.addWidget(self.use_concurrent_model ,2,1,1,1)

        opti_page = QWidget()
        opti_page_layout = QVBoxLayout(opti_page)
        opti_page_layout.addWidget(self.opti_frame)
        self.stat_tab_widget.addTab(api_page, "模型选择")
        self.stat_tab_widget.addTab(opti_page, "优化监控")

        #tts页面初始化
        self.add_tts_page()

        # 用户输入文本框
        user_input_label = QLabel("用户输入：")
        temp_style_edit = QLineEdit()
        # 临时风格
        temp_style_edit.setPlaceholderText("指定临时风格")
        temp_style_edit.textChanged.connect(lambda text: setattr(self, 'temp_style', text or ''))

        self.user_input_text = MultiModalTextEdit()
        self.main_layout.addWidget(temp_style_edit,2,1,1,1)
        self.main_layout.addWidget(user_input_label, 2, 0, 1, 1)
        self.main_layout.addWidget(self.user_input_text, 3, 0, 1, 2)

        self.init_chat_history_bubbles()

        # AI 回复文本框
        ai_response_label = QLabel("AI 状态")
        self.ai_response_text = ChatapiTextBrowser()
        self.ai_response_text.anchorClicked.connect(lambda url: os.startfile(url.toString()))
        self.ai_response_text.setOpenExternalLinks(False)

        #强制去重
        self.enforce_lower_repeat=QCheckBox("强制去重")
        self.enforce_lower_repeat.setChecked(APP_SETTINGS.force_repeat.enabled)
        self.enforce_lower_repeat.toggled.connect(
            lambda state: APP_SETTINGS.force_repeat.update({'enabled':bool(state)})
        )

        self.main_layout.addWidget(ai_response_label, 5, 0, 1, 1)
        self.main_layout.addWidget(self.enforce_lower_repeat, 5, 1, 1, 1)
        self.main_layout.addWidget(self.ai_response_text, 6, 0, 1, 2)
        
        control_frame = QGroupBox("控制")  # 直接在构造函数中设置标题
        # 发送按钮
        self.send_button = QPushButton("发送 Ctrl+Enter")
        self.send_button.clicked.connect(self.send_message)

        self.control_frame_layout = QGridLayout()
        control_frame.setLayout(self.control_frame_layout)

        self.pause_button = QPushButton("暂停")
        self.pause_button.clicked.connect(lambda: self.control_frame_to_state('finished'))
        self.pause_button.clicked.connect(lambda _:self.chat_history_bubbles.streaming_scroll(False))
        self.pause_button.clicked.connect(self.cfm.pause)


        self.clear_button = QPushButton("清空")
        self.clear_button.clicked.connect(self.clear_history)

        self.resend_button= QPushButton("重新回答")
        self.resend_button.clicked.connect(self.resend_message_last)

        self.edit_question_button=QPushButton("修改问题")
        self.edit_question_button.clicked.connect(self.edit_user_last_question)

        self.edit_message_button=QPushButton("原始记录")
        self.edit_message_button.clicked.connect(self.edit_chathistory)

        self.search_result_button=SwitchButton(texta='搜索结果 ',textb=' 搜索结果')
        self.search_result_label=QLabel("搜索结果")
        self.search_result_button.hide()
        self.search_result_button.clicked.connect(self.handle_search_result_button_toggle)
        self.main_layout.addWidget(self.search_result_button,6,1,1,1,Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignRight)

        self.web_search_button=ExpandableButton(["搜索：关闭","搜索：自动","搜索：强制",])
        self.web_search_button.toggled.connect(self.handle_web_search_button_toggled)
        self.web_search_button.indexChanged.connect(self.handle_web_search_button_index_changed)
        if APP_SETTINGS.web_search.web_search_enabled:
            self.web_search_button.setCurrentIndex(2)
        

        self.enable_thinking_button=ExpandableButton(['深度思考','思考：短','思考：中','思考：高'])
        self.enable_thinking_button.setChecked(APP_SETTINGS.generation.thinking_enabled)
        self.enable_thinking_button.setCurrentIndex(APP_SETTINGS.generation.reasoning_effort)
        self.enable_thinking_button.toggled.connect(
            lambda state:APP_SETTINGS.generation.update(
                {
                    'thinking_enabled':state
                }
            )
        )
        self.enable_thinking_button.itemSelected.connect(
            lambda text: self.enable_thinking_button.setChecked(
                not text==self.enable_thinking_button.get_items()[0]
            )
        )
        self.enable_thinking_button.itemSelected.connect(
            lambda _: APP_SETTINGS.generation.update(
                {
                    'reasoning_effort': self.enable_thinking_button.currentIndex()
                }
            )
        )

        separators = [QFrame() for _ in range(3)]
        for sep in separators:
            sep.setFrameShape(QFrame.Shape.VLine)
            sep.setFrameShadow(QFrame.Shadow.Sunken)
        self.control_frame_layout.addWidget(self.send_button,           0, 0, 1, 15)
        self.control_frame_layout.addWidget(self.pause_button,          1, 0, 1, 2)
        self.control_frame_layout.addWidget(self.clear_button,          1, 2, 1, 2)
        self.control_frame_layout.addWidget(separators[0],              1, 4, 1, 1)
        self.control_frame_layout.addWidget(self.resend_button,         1, 5, 1, 2)
        self.control_frame_layout.addWidget(separators[1],              1, 7, 1, 1)
        self.control_frame_layout.addWidget(self.edit_question_button,  1, 8, 1, 2)
        self.control_frame_layout.addWidget(self.edit_message_button,   1, 10,1, 2)
        self.control_frame_layout.addWidget(separators[2],              1, 12,1, 1)
        self.control_frame_layout.addWidget(self.enable_thinking_button,1, 13,1, 1)
        self.control_frame_layout.addWidget(self.web_search_button,     1, 14,1, 1)

        # 设置列的拉伸因子，使按钮等宽缩放，分隔符固定
        for i in [4, 7, 12]:  # 分隔符所在的列
            self.control_frame_layout.setColumnStretch(i, 0)
        for i in [0, 1, 2, 3, 5, 6, 8, 9, 10, 11]: # 占两列的按钮
            self.control_frame_layout.setColumnStretch(i, 1)
        for i in [13, 14]: # 占一列的按钮
            self.control_frame_layout.setColumnStretch(i, 2)

        self.main_layout.addWidget(control_frame, 4, 0, 1, 2)
    
        #AI回复左上角控件组
        
        sub_height=int(self.height()*0.04)
        total_height=int(sub_height*2.25)
        sub_width=int(self.height()*0.04)
        total_width=int(sub_width*1.5)
        margin=int(sub_height*0.1)

        ai_control_widget=QFrame()
        #ai_control_widget.setFixedSize(total_width,total_height)
        ai_control_layout=QGridLayout()
        ai_control_layout.setContentsMargins(margin,margin,margin,margin)
        ai_control_widget.setLayout(ai_control_layout)

        open_image_icon=QPixmap()
        open_image_icon.loadFromData(image_icon)
        self.open_image_button=QPushButton()
        self.open_image_button.setIcon(QIcon(open_image_icon))
        self.open_image_button.setFixedSize(sub_width,sub_height)
        self.open_image_button.setIconSize(open_image_icon.size()*0.12)
        self.open_image_button.setToolTip('打开背景图')
        self.open_image_button.clicked.connect(self.open_background_pic)

        ai_control_layout.addWidget(self.open_image_button,1,0,1,1)

        self.main_layout.addWidget(ai_control_widget, 6, 1, 1, 1,Qt.AlignmentFlag.AlignTop | Qt.AlignmentFlag.AlignRight)

        #历史记录 显示框
        self.past_chat_frame = QGroupBox()
        self.past_chat_frame_layout = QGridLayout()
        self.past_chat_frame.setLayout(self.past_chat_frame_layout)

        self.past_chat_list = HistoryListWidget()
        self.past_chat_list.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)  # 强制单选模式
        self.past_chat_list.itemClicked.connect(self.load_from_past)
        self.past_chat_list.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.past_chat_list.customContextMenuRequested.connect(self.past_chats_menu)
        
        self.reload_chat_list=QPushButton("🗘")
        self.reload_chat_list.clicked.connect(self.grab_past_chats)
        self.reload_chat_list.setToolTip("刷新（在打开本页面时会自动刷新)")
        self.reload_chat_list.setStyleSheet("""
    QPushButton {
        font-size: 18px;
        max-width: 20px;
        max-height: 20px;
        padding: 0px 0px;
    }
""")
        
        self.del_item_chat_list=QPushButton('🗑')
        self.del_item_chat_list.clicked.connect(self.delete_selected_history)
        self.del_item_chat_list.setToolTip("删除")
        self.del_item_chat_list.setStyleSheet("""
    QPushButton {
        font-size: 18px;
        max-width: 20px;
        max-height: 20px;
        padding: 0px 0px;
    }
""")

        self.load_stories_chat_list=QPushButton('📊')
        self.load_stories_chat_list.clicked.connect(self.analysis_past_chat)
        self.load_stories_chat_list.setToolTip("分析用量")
        self.load_stories_chat_list.setStyleSheet("""
    QPushButton {
        font-size: 18px;
        max-width: 20px;
        max-height: 20px;
        padding: 0px 0px;
    }
""")

        self.load_sys_pmt_chat_list=QPushButton('🌐')
        self.load_sys_pmt_chat_list.clicked.connect(self.load_sys_pmt_from_past_record)
        self.load_sys_pmt_chat_list.setToolTip("导入system prompt")
        self.load_sys_pmt_chat_list.setStyleSheet("""
    QPushButton {
        font-size: 18px;
        max-width: 20px;
        max-height: 20px;
        padding: 0px 0px;
    }
""")

        self.load_from_past_chat_list=QPushButton('✔')
        self.load_from_past_chat_list.clicked.connect(self.load_from_past)
        self.load_from_past_chat_list.setToolTip("载入")
        self.load_from_past_chat_list.setStyleSheet("""
    QPushButton {
        font-size: 18px;
        max-width: 20px;
        max-height: 20px;
        padding: 0px 0px;
    }
""")

        hislabel=QLabel("历史记录")
        hislabel.setMaximumHeight(20)

        self.past_chat_frame_layout.addWidget(self.stat_tab_widget,         0,0,1,5)
        self.past_chat_frame_layout.addWidget(hislabel,                     1,0,1,4)
        self.past_chat_frame_layout.addWidget(self.past_chat_list,          2,1,8,4)
        self.past_chat_frame_layout.addWidget(self.reload_chat_list,        2,0,1,1)
        self.past_chat_frame_layout.addWidget(self.load_from_past_chat_list,3,0,1,1)
        self.past_chat_frame_layout.addWidget(self.del_item_chat_list,      4,0,1,1)
        self.past_chat_frame_layout.addWidget(self.load_sys_pmt_chat_list,  5,0,1,1)
        self.past_chat_frame_layout.addWidget(self.load_stories_chat_list,  6,0,1,1)

        self.past_chat_frame.setParent(self)
        self.past_chat_frame.hide()

        # 创建 TreeView
        self.tree_view = QTreeWidget()
        self.tree_view.setHeaderHidden(True)
        self.tree_view.itemClicked.connect(self.on_tree_item_clicked)  # 点击事件
        self.tree_view.setGeometry(-int(self.width()*0.3), 0, int(self.width()*0.3), int(self.height()))
        self.tree_view.setParent(self)
        self.tree_view.hide()

        # 填充 TreeView
        self.populate_tree_view()

        # 设置行和列的权重
        self.main_layout.setRowStretch(0, 0)
        self.main_layout.setRowStretch(1, 0)
        self.main_layout.setRowStretch(3, 1)
        self.main_layout.setRowStretch(6, 1)
        self.main_layout.setRowStretch(2, 0)
        self.main_layout.setColumnStretch(0, 1)
        self.main_layout.setColumnStretch(1, 1)
        self.main_layout.setColumnStretch(2, 1)
        self.main_layout.setColumnStretch(3, 1)


        pixmap = QPixmap()
        pixmap.loadFromData(self.setting_img)
        self.toggle_tree_button = QPushButton()
        self.toggle_tree_button.clicked.connect(self.toggle_tree_view)
        self.toggle_tree_button.setGeometry(0, self.height() - int(self.height() * 0.06), int(self.height() * 0.06), int(self.height() * 0.06))
        self.toggle_tree_button.setParent(self)
        self.toggle_tree_button.raise_()  # 确保按钮在最上层
        self.toggle_tree_button.setIcon(QIcon(pixmap))
        self.toggle_tree_button.setIconSize(pixmap.size())
        self.toggle_tree_button.resizeEvent = self.on_button_resize
        self.toggle_tree_button.setStyleSheet(
            MainWindowPresetVars.toggle_tree_button_stylesheet
        )

        self.creat_new_chat()
        self.installEventFilter(self)
        self.bind_hot_key()
        self.update_opti_bar()

        #UI状态恢复
        self.recover_ui_status()
        #UI创建后
        self.init_post_ui_creation()
        self.info_manager.log(f'CWLA init finished, time stamp:{time.time()-start_time_stamp:.2f}s')

        self.fps_monitor = FPSMonitor(self)
        self.fps_monitor.show()
        # 让它飘在最上层
        self.fps_monitor.raise_()


    def init_signal_bus(self):
        self.back_end_signal_bridge=UiMainSignalBridge()

    if TYPE_CHECKING:
        from core.signals import MainBus

    @ property
    def BESB(self)->"MainBus":
        """MainWindow.back_end_signal_bridge"""
        return self.back_end_signal_bridge

    def connect_bus_signals(self):
        self.BESB
        b=self.BESB
        b.bus_connect(self.core.signals)
        b.full_content.connect(self.update_ai_response_text)
        b.full_reasoning.connect(self.update_think_response_text)
        b.full_tool_call.connect(self.update_tool_response_text)
        b.finished.connect(self.handle_main_chat_completed)
        b.history_changed.connect(
            lambda id,history: self.chat_history_bubbles.set_chat_history(history)
        )
        b.request_status.connect(self.update_status)
        b.failed.connect(self.handle_main_chat_completed)

        b.name_changed.connect(self.update_name_to_chatbubbles)
        b.avatar_changed.connect(self.update_avatar_to_chat_bubbles)
        b.history_changed.connect(self.finalize_chat_render)
        b.session_changed.connect(self.handle_session_change)

        b.notify.connect(self.info_manager.notify)
        b.warning.connect(self.info_manager.warning)
        b.error.connect(self.info_manager.error)


    def init_app_core(self):
        self.core = CWLACore()

    @property
    def session_manager(self):
        return self.core.session_manager
    
    @property
    def cfm(self):
        return self.core.cfm


    def init_self_params(self):
        self.setting_img = setting_img
        self.temp_style=''

        # 状态控制标志
        self.hotkey_sysrule_var = True

        #对话储存点
        self._cb_buffers=ChatBuffer()
        self._cb_buffers.reset()

    def init_function_window(self):
        self.function_manager = FunctionManager()
        self.function_manager.activatedToolsChanged.connect(self.session_manager.set_tools)

    def init_system_prompt_window(self):
        self.system_prompt_override_window = SystemPromptManager(
            folder_path=APP_RUNTIME.paths.system_prompt_preset_path
        )
        self.system_prompt_override_window.update_tool_selection.connect(self.session_manager.set_tools)
        self.system_prompt_override_window.update_preset.connect(self.update_system_preset)
        self.system_prompt_override_window.update_system_prompt.connect(self.session_manager.set_system_content)

    @property
    def mod_configer(self):
        if not hasattr(self,'_mod_configer'):
            from core.story.mod_manager import ModConfiger
            self._mod_configer=ModConfiger()
        return self._mod_configer

    def init_info_manager(self):
        self.info_manager=InfoManager(
            anchor_widget=self,
            log_manager=LOGGER,
        )


    def init_post_ui_creation(self):
        self.mod_configer.finish_story_creator_init()
        
    def init_chat_history_bubbles(self):
        # 当前聊天文本框
        self.chat_history_label = QLabel("当前聊天")
        self.display_full_chat_history=QPushButton("完整记录")
        self.display_full_chat_history.clicked.connect(self.display_full_chat_history_window)
        self.chat_history_text = ChatapiTextBrowser()
        self.chat_history_text.anchorClicked.connect(lambda url: os.startfile(url.toString()))
        self.chat_history_text.setOpenExternalLinks(False)

        self.quick_system_prompt_changer = SystemPromptComboBox(
            folder_path='data/system_prompt_presets',
            parent=None,
            include_placeholder=False,
            current_filename_base='当前对话',
        )
        # 切换选择时覆盖系统提示
        self.quick_system_prompt_changer.update_preset.connect(
            lambda preset:(
                self.update_system_preset(preset)
                #self.system_prompt_override_window.load_income_prompt(preset),#todo
                )
        )
        self.quick_system_prompt_changer.request_open_editor.connect(
            self.open_system_prompt
        )

        #0.25.1 更新
        #聊天历史气泡
        self.bubble_background=QTextBrowser()
        self.main_layout.addWidget(self.bubble_background, 3, 2, 4, 3)
        self.chat_history_bubbles = ChatHistoryWidget()
        self.init_chat_bubble()
        self.main_layout.addWidget(self.chat_history_bubbles, 3, 2, 4, 3)
        self.main_layout.addWidget(self.display_full_chat_history, 2, 4, 1, 1)
        self.main_layout.addWidget(self.chat_history_label, 2, 2, 1, 1)
        self.main_layout.addWidget(self.quick_system_prompt_changer, 2, 3, 1, 1)

        #气泡信号绑定
        self.chat_history_bubbles.regenerateRequested.connect(self.resend_message)
        self.chat_history_bubbles.editFinished.connect(self.session_manager.edit_by_id)
        self.chat_history_bubbles.RequestAvatarChange.connect(self.show_avatar_window)

    def init_chat_bubble(self):
        self.chat_history_bubbles.avatars

    def init_concurrenter(self):
        pass
    
    def ensure_concurrenter(self):
        if not hasattr(self, 'concurrent_model'):
            from core.session.concurrentor import ConvergenceDialogueOptiProcessor
            self.concurrent_model=ConvergenceDialogueOptiProcessor()
        #self.concurrent_model.concurrentor_content.connect(self.concurrentor_content_receive)
        #self.concurrent_model.concurrentor_reasoning.connect(self.concurrentor_reasoning_receive)
        #self.concurrent_model.concurrentor_finish.connect(self.concurrentor_finish_receive)

    def init_web_searcher(self):
        """懒导入，不常用模块，加速启动"""
        if not hasattr(self, 'web_searcher'):
            from service.web_search.online_rag import WebSearchSettingWindows
            self.web_searcher = WebSearchSettingWindows()
    
    def add_tts_page(self):
        self.tts_handler=TTSAgent(setting=APP_SETTINGS.tts,application_path=APP_RUNTIME.paths.application_path)
        self.stat_tab_widget.addTab(self.tts_handler, "语音生成")

    def show_mod_configer(self):
        self.mod_configer.show()

    def recover_ui_status(self):
        """
        恢复API提供商和模型选择的UI状态（如果有保存的值）。
        如果存在已保存的值，则设置对应下拉框的当前选项。
        同时连接下拉框的currentTextChanged信号，在用户更改选择时更新保存的值。
        """
        index = self.api_var.findText(APP_SETTINGS.ui.LLM.provider)
        if index >= 0:
            self.api_var.setCurrentIndex(index)
        
        index = self.model_combobox.findText(APP_SETTINGS.ui.LLM.model)
        if index >= 0:
            self.model_combobox.setCurrentIndex(index)


    #svg图标渲染器
    def render_svg_to_icon(self, svg_data):
        svg_byte_array = QByteArray(svg_data)
        svg_renderer = QSvgRenderer(svg_byte_array)
        
        icon = QIcon()
        # 常见图标尺寸列表
        sizes = [16, 24, 32, 48, 64, 96, 128]
        
        for size in sizes:
            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.GlobalColor.transparent)
            
            painter = QPainter(pixmap)
            svg_renderer.render(painter)
            painter.end()
            
            icon.addPixmap(pixmap)
        
        return icon

    #设置按钮：大小自适应
    def on_button_resize(self, event):
        # 获取按钮的当前大小
        super().resizeEvent(event)
        button_size = self.toggle_tree_button.size()
        # 设置图标大小为按钮大小
        self.toggle_tree_button.setIconSize(button_size*0.8)
        # 调用父类的 resizeEvent
        
        self.toggle_tree_button.setGeometry(
            0, self.height() - int(self.height() * 0.06), 
            int(self.height() * 0.06), int(self.height() * 0.06)
        )

    #设置按钮：自动贴边：重写窗口缩放
    def resizeEvent(self, event):
        super().resizeEvent(event)  # 调用父类的resizeEvent，确保正常处理窗口大小变化
        # 动态调整按钮位置和大小
        self.toggle_tree_button.setGeometry(
            0, self.height() - int(self.height() * 0.06), 
            int(self.height() * 0.06), int(self.height() * 0.06)
        )
        self.past_chat_frame.setGeometry(self.width()-self.past_chat_frame.width(), 0, int(self.width() * 0.3), int(self.height()))
        self.tree_view.setGeometry(0, 0, int(self.width() * 0.3), int(self.height()))
    def changeEvent(self, event):
        try:
            self.past_chat_frame.setGeometry(self.width()-self.past_chat_frame.width(), 0, int(self.width() * 0.3), int(self.height()))
            self.tree_view.setGeometry(0, 0, int(self.width() * 0.3), int(self.height()))
        except Exception as e:
            if not 'past_chat_frame' in str(e):
                self.info_manager.notify(f'changeEvent failed, Error code:{e}','error')
        super().changeEvent(event)

    #设置界面：函数库
    def populate_tree_view(self):
        data = [
            {"上级名称": "系统", "提示语": "API/模型库设置", "执行函数": self.open_api_window},
            {"上级名称": "系统", "提示语": "System Prompt 设定 Ctrl+E", "执行函数": self.open_system_prompt},
            {"上级名称": "系统", "提示语": "MOD管理器", "执行函数": self.show_mod_configer},
            {"上级名称": "记录", "提示语": "保存记录", "执行函数": self.save_chathistory},
            {"上级名称": "记录", "提示语": "导入记录", "执行函数": self.load_chathistory},
            {"上级名称": "记录", "提示语": "修改原始记录", "执行函数": self.edit_chathistory},
            {"上级名称": "记录", "提示语": "对话分析", "执行函数": self.show_analysis_window},
            {"上级名称": "对话", "提示语": "强制触发长对话优化", "执行函数": self.cfm.enforce_lci},
            {"上级名称": "对话", "提示语": "函数调用", "执行函数": self.show_function_call_window},
            {"上级名称": "背景", "提示语": "背景设置", "执行函数": self.background_settings_window},
            {"上级名称": "背景", "提示语": "触发背景更新（跟随聊天）", "执行函数": self.call_background_update},
            {"上级名称": "背景", "提示语": "生成自定义背景（正在重构）", "执行函数": self.show_pic_creater},
            {"上级名称": "设置", "提示语": "对话设置", "执行函数": self.open_main_setting_window},
            {"上级名称": "设置", "提示语": "快捷键", "执行函数": self.open_settings_window},
            {"上级名称": "设置", "提示语": "联网搜索", "执行函数": self.open_web_search_setting_window},
        ]

        parent_nodes = {}
        for item in data:
            parent_name = item["上级名称"]
            if parent_name not in parent_nodes:
                parent_item = QTreeWidgetItem([parent_name])
                self.tree_view.addTopLevelItem(parent_item)
                parent_nodes[parent_name] = parent_item

            parent_item = parent_nodes[parent_name]
            child_item = QTreeWidgetItem([item["提示语"]])
            # 直接存函数对象
            child_item.setData(0, Qt.ItemDataRole.UserRole, item["执行函数"])
            parent_item.addChild(child_item)
        
        self.tree_view.expandAll()

    def on_tree_item_clicked(self, item, column):
        func = item.data(column, Qt.ItemDataRole.UserRole)
        # 直接调用，省去getattr解析
        if callable(func):
            func()

    #设置界面：展开/收起 带动画绑定
    def toggle_tree_view(self):
        # 切换 TreeView 的显示状态
        if self.tree_view.isHidden() :
            self.past_chat_frame.setGeometry(self.width(), 0, int(self.width() * 0.3), int(self.height()))
            self.past_chat_frame.show()
            self.past_chat_frame_animation = QPropertyAnimation(self.past_chat_frame, b"geometry")
            self.past_chat_frame_animation.setDuration(300)
            self.past_chat_frame_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
            self.past_chat_frame_animation.setStartValue(QRect(self.width(), 0, self.past_chat_frame.width(), self.height()))
            self.past_chat_frame_animation.setEndValue(QRect(self.width()-self.past_chat_frame.width(), 0, self.past_chat_frame.width(), self.height()))
            self.past_chat_frame.raise_()

            # 显示 TreeView
            self.tree_view.show()
            self.tree_view.setGeometry(-int(self.width() * 0.3), 0, int(self.width() * 0.3), int(self.height()))
            self.tree_view.raise_()  # 确保 TreeView 在最上层

            # 创建 TreeView 的动画
            self.tree_animation = QPropertyAnimation(self.tree_view, b"geometry")
            self.tree_animation.setDuration(300)
            self.tree_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
            self.tree_animation.setStartValue(QRect(-self.tree_view.width(), 0, self.tree_view.width(), self.height()))
            self.tree_animation.setEndValue(QRect(0, 0, self.tree_view.width(), self.height()))

            # 创建 toggle_tree_button 的动画
            self.button_animation = QPropertyAnimation(self.toggle_tree_button, b"geometry")
            self.button_animation.setDuration(300)
            self.button_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
            self.button_animation.setStartValue(self.toggle_tree_button.geometry())
            self.button_animation.setEndValue(QRect(self.tree_view.width(), self.toggle_tree_button.y(), self.toggle_tree_button.width(), self.toggle_tree_button.height()))

            # 同时启动两个动画
            self.tree_animation.start()
            self.button_animation.start()
            self.past_chat_frame_animation.start()
            self.grab_past_chats()
        else:
            self.past_chat_frame_animation = QPropertyAnimation(self.past_chat_frame, b"geometry")
            self.past_chat_frame_animation.setDuration(300)
            self.past_chat_frame_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
            self.past_chat_frame_animation.setStartValue(QRect(self.width()-self.past_chat_frame.width(), 0, self.past_chat_frame.width(), self.height()))
            self.past_chat_frame_animation.setEndValue(QRect(self.width(), 0, self.past_chat_frame.width(), self.height()))
            self.past_chat_frame_animation.finished.connect(self.past_chat_frame.hide)

            # 隐藏 TreeView
            self.tree_animation = QPropertyAnimation(self.tree_view, b"geometry")
            self.tree_animation.setDuration(300)
            self.tree_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
            self.tree_animation.setStartValue(QRect(0, 0, self.tree_view.width(), self.height()))
            self.tree_animation.setEndValue(QRect(-self.tree_view.width(), 0, self.tree_view.width(), self.height()))
            self.tree_animation.finished.connect(self.tree_view.hide)

            # 创建 toggle_tree_button 的动画
            self.button_animation = QPropertyAnimation(self.toggle_tree_button, b"geometry")
            self.button_animation.setDuration(300)
            self.button_animation.setEasingCurve(QEasingCurve.Type.InOutQuad)
            self.button_animation.setStartValue(self.toggle_tree_button.geometry())
            self.button_animation.setEndValue(QRect(0, self.toggle_tree_button.y(), self.toggle_tree_button.width(), self.toggle_tree_button.height()))

            # 同时启动两个动画
            self.tree_animation.start()
            self.button_animation.start()
            self.past_chat_frame_animation.start()

    #设置界面：点击外部收起
    def eventFilter(self, obj, event):
      if event.type() == QEvent.Type.MouseButtonPress:
          if self.tree_view.isVisible():
              # 将全局坐标转换为树视图的局部坐标
              local_pos = self.tree_view.mapFromGlobal(event.globalPosition().toPoint())
              if not self.tree_view.rect().contains(local_pos):
                  self.toggle_tree_view()
      return super().eventFilter(obj, event)

    def show_function_call_window(self):
        self.function_manager.set_active_tools(self.session_manager.tools)
        self.function_manager.show()
        self.function_manager.raise_()

    #api来源：更改提供商
    def update_model_combobox(self, selected_api):
        """更改提供商时更新模型下拉框"""
        self.model_combobox.clear()

        available_models = APP_SETTINGS.api.model_map.get(selected_api, [])

        if available_models:
            self.model_combobox.addItems(available_models)
            self.model_combobox.setCurrentIndex(0)
        else:
            self.model_combobox.addItem("无可用模型")

    #超长文本显示优化
    def display_full_chat_history_window(self):
        self.history_text_view = ChatHistoryTextView(
            self.session_manager.history
        )
        
        self.history_text_view.show()
        self.history_text_view.raise_()
    
    def init_chat_bubble_render_loop(self):
        self.cb_render_timer = QTimer(self)
        self.cb_render_timer.setInterval(300)
        self.cb_render_timer.timeout.connect(self._flush_chat_buffer)
    
    def update_ai_response_text(self, request_id, full_content):
        self._update_buffer(request_id, 'content', full_content)

    def update_think_response_text(self, request_id, full_reasoning):
        self._update_buffer(request_id, 'reasoning', full_reasoning)

    def update_tool_response_text(self, request_id, full_tool):
        self._update_buffer(request_id, 'tool', full_tool)
    
    def update_status(self,status:dict):
        self._cb_buffers.status=status
        if not self.cb_render_timer.isActive():
            def _u():
                self.update_request_status(status)
            QTimer.singleShot(10,_u)

    def _update_buffer(self, req_id, key, text):
        if req_id!=self._cb_buffers.id:
            self._cb_buffers.clean()

        self._cb_buffers.id = req_id

        setattr(self._cb_buffers, key, text)

        self._cb_buffers.renewed = True
        self._cb_buffers.role = 'assistant' if key in ['content', 'reasoning'] else 'tool'

        if not self.cb_render_timer.isActive():
            self.cb_render_timer.start()

    def _flush_chat_buffer(self):
        if not self._cb_buffers.renewed:
            return

        self.chat_history_bubbles.streaming_scroll(True)
        self.chat_history_bubbles.update_bubble(
            msg_id=self._cb_buffers.id,
            content=self._cb_buffers.content,
            reasoning_content=self._cb_buffers.reasoning,
            tool_content=self._cb_buffers.tool,
            streaming='streaming',
            role=self._cb_buffers.role,
            model=self._cb_buffers.model
        )

        self.update_request_status(self._cb_buffers.status)
    
    def finalize_chat_render(self, req_id, msg):
        self._flush_chat_buffer()
        self.cb_render_timer.stop()
        self.chat_history_bubbles.streaming_scroll(False)

    def control_frame_to_state(self,state:bool | str):
        if not isinstance(state,bool):
            state_map={
                'sending':False,
                'finished':True
            }
            state=state_map[state]
        self.send_button.setEnabled(state)
        self.clear_button.setEnabled(state)
        self.resend_button.setEnabled(state)
        self.edit_question_button.setEnabled(state)
        self.past_chat_list.setEnabled(state)

    def _get_current_llm_usage(self) -> LLMUsagePack:
        """：处理模型轮询，并组装当前 UI 选择的模型参数"""
        if APP_SETTINGS.model_poll.enabled:
            s = self.ordered_model.get_next_model()
            if s.provider and s.model:
                self.api_var.setCurrentText(s.provider)
                self.model_combobox.setCurrentText(s.model)

        return LLMUsagePack(
            provider=self.api_var.currentText(),
            model=self.model_combobox.currentText()
        )

    def _prepare_ui_for_sending(self, model_name: str, status_text: str):
        """抽取公共逻辑：请求成功后的 UI 初始化动作"""
        self._cb_buffers.model = model_name
        self.control_frame_to_state('sending')
        self.ai_response_text.setText(status_text)
    
    #重生成消息，直接创建最后一条
    def resend_message_last(self):
        self.resend_message()

    def resend_message(self, request_id=''):
        # 防呆
        if not self.send_button.isEnabled():
            return
        self._cb_buffers.reset()

        # 1. 拿参数
        llm_usage = self._get_current_llm_usage()

        # 2. 进 CFM
        success = self.cfm.resend_message(
            msg_id=request_id,
            LLM_usage=llm_usage,
            temp_style=self.temp_style
        )

        # 3. 走 UI 流程
        if success:
            self._prepare_ui_for_sending(llm_usage.model, "正在重传，等待回复...")


    def send_message(self):
        if not self.send_button.isEnabled():
            return
        self._cb_buffers.reset()

        user_input = self.user_input_text.toPlainText()
        multimodal_input = self.user_input_text.get_multimodal_content()

        # 1. UI 防呆拦截
        if self.session_manager.get_last_message().get("role", '') == "user":
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle('确认操作')
            msg_box.setText('确定连发两条吗？\n(这会导致上一条未回复的消息成为历史)')
            btn_yes = msg_box.addButton('确定发送', QMessageBox.ButtonRole.YesRole)
            btn_no = msg_box.addButton('取消', QMessageBox.ButtonRole.NoRole)
            btn_edit = msg_box.addButton('编辑聊天记录', QMessageBox.ButtonRole.ActionRole)

            msg_box.exec()

            if msg_box.clickedButton() == btn_no:
                return # 放弃发送
            elif msg_box.clickedButton() == btn_edit:
                self.edit_chathistory() 
                return 

        elif not user_input.strip():

            reply = QMessageBox.question(
                self, '确认操作', '确定发送空消息？',
                QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                QMessageBox.StandardButton.No
            )
            if reply == QMessageBox.StandardButton.No: return
            user_input = "_" # 占位符


        # 2. 拿参数
        llm_usage = self._get_current_llm_usage()

        # 3. 进 CFM
        success = self.cfm.send_new_message(
            prompt_pack=(user_input, multimodal_input),
            LLM_usage=llm_usage,
            temp_style=self.temp_style
        )

        # 4. 走 UI 流程
        if success:
            self.user_input_text.clear() # 独有逻辑：清空输入框
            self._prepare_ui_for_sending(llm_usage.model, "已发送，等待回复...")

    #api导入窗口
    def open_api_window(self):
        if not hasattr(self,'api_window'):
            self.api_window = APIConfigWidget()
            self.api_window.configUpdated.connect(self._handle_api_update)
            self.api_window.notificationRequested.connect(self.info_manager.notify)
        self.api_window.show()
        self.api_window.raise_()

    def _handle_api_update(self) -> None:
        """处理API配置更新信号"""
        model_map = APP_SETTINGS.api.model_map

        # 保存当前选择
        previous_api = self.api_var.currentText()
        previous_model = self.model_combobox.currentText()

        # 刷新供应商下拉框
        self.api_var.clear() 
        self.api_var.addItems(model_map.keys())

        # 恢复之前选的供应商
        if previous_api in model_map:
            self.api_var.setCurrentText(previous_api)

        # 刷新模型下拉框
        current_api = self.api_var.currentText()
        self.model_combobox.clear() 
        if current_api in model_map:
            self.model_combobox.addItems(model_map[current_api])
            if previous_model in model_map[current_api]:
                self.model_combobox.setCurrentText(previous_model)

    #清除聊天记录
    def clear_history(self):
        self.chat_history_bubbles.clear()
        self.ai_response_text.clear()
        self._cb_buffers.reset()
        self.creat_new_chat()

    # 系统提示预设更新
    def update_system_preset(self, preset):
        self.session_manager.update_preset(preset)

    # 打开系统提示设置窗口
    def open_system_prompt(self, show_at_call=True):
        if show_at_call:
            self.system_prompt_override_window.show()
        if self.system_prompt_override_window.isVisible():
            self.system_prompt_override_window.raise_()
            self.system_prompt_override_window.activateWindow()
        self.system_prompt_override_window.load_income_prompt(self.session_manager.current_chat)

    #打开设置，快捷键
    def open_settings_window(self):
        self.settings_window = QDialog(self)
        self.settings_window.setWindowTitle("设置")
        self.settings_window.resize(300, 80)  # 设置子窗口大小

        layout = QVBoxLayout()
        self.settings_window.setLayout(layout)

        send_message_bu = QCheckBox("Ctrl+Enter键发送消息")
        send_message_bu.setChecked(self.send_message_var)  # 默认选中

        autoslide_bu = QCheckBox("Tab/Ctrl+Q推出设置")
        autoslide_bu.setChecked(self.autoslide_var)  # 默认选中

        hotkey_sysrule_bu = QCheckBox("Ctrl+E打开system prompt")
        hotkey_sysrule_bu.setChecked(self.hotkey_sysrule_var)  # 默认选中

        layout.addWidget(send_message_bu)
        layout.addWidget(autoslide_bu)
        layout.addWidget(hotkey_sysrule_bu)

        confirm_bu=QPushButton("确认")
        layout.addWidget(confirm_bu)

        def confirm_settings():
            self.send_message_var = send_message_bu.isChecked()
            self.autoslide_var=autoslide_bu.isChecked()
            self.hotkey_sysrule_var=hotkey_sysrule_bu.isChecked()
            #self.bind_hot_key()
            self.settings_window.close()

        confirm_bu.clicked.connect(confirm_settings)
        self.settings_window.exec()

    #绑定快捷键
    def bind_hot_key(self):
        """
        根据当前设置动态绑定或解绑所有快捷键。
        功能说明
        ----------
        1. 固定快捷键（始终生效）
            - F11            : 切换全屏 / 正常窗口
            - Ctrl+N         : 清空聊天记录
            - Ctrl+O         : 加载聊天记录
            - Ctrl+S         : 保存聊天记录
            - Ctrl+M         : 打开mod配置窗口
            - Ctrl+T         : 打开主题设置窗口
            - Ctrl+D         : 打开对话设置窗口
            - Ctrl+B         : 打开背景设置窗口
        2. 可选快捷键（根据布尔变量动态启用 / 禁用）
            - Ctrl+Enter     : 发送消息（由 send_message_var 控制）
            - Tab            : 切换树形视图（由 autoslide_var 控制）
            - Ctrl+Q         : 同上，切换树形视图
            - Ctrl+E         : 打开系统提示窗口（由 hotkey_sysrule_var 控制）
        实现细节
        ----------
        - 当对应布尔变量为 True 时，为相应功能创建并绑定 QShortcut。
        - 当对应布尔变量为 False 且快捷键对象已存在时，将其键序列设为空，
          从而临时禁用该快捷键，但保留对象以便后续重新绑定。
        """
        self.send_message_var = True
        self.autoslide_var = True
        self.send_message_var=True
        self.send_message_shortcut= QShortcut(QKeySequence(), self)
        self.shortcut1 = QShortcut(QKeySequence(), self)
        self.shortcut2 = QShortcut(QKeySequence(), self)
        self.hotkey_sysrule= QShortcut(QKeySequence(), self)
        self.shortcut1.activated.connect(self.toggle_tree_view)
        self.shortcut2.activated.connect(self.toggle_tree_view)
        self.send_message_shortcut.activated.connect(self.send_message)
        QShortcut(QKeySequence("F11"), self).activated.connect(
            lambda: self.showFullScreen() if not self.isFullScreen() else self.showNormal()
        )

        QShortcut(QKeySequence("Ctrl+N"), self).activated.connect(self.clear_history)
        QShortcut(QKeySequence("Ctrl+O"), self).activated.connect(self.load_chathistory)
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(lambda: self.save_chathistory())#self.session_manager.save_chathistory())
        QShortcut(QKeySequence("Ctrl+M"), self).activated.connect(self.show_mod_configer)
        QShortcut(QKeySequence("Ctrl+D"), self).activated.connect(self.open_main_setting_window)
        QShortcut(QKeySequence("Ctrl+B"), self).activated.connect(self.background_settings_window)
        QShortcut(QKeySequence("Ctrl+F"), self).activated.connect(self.show_function_call_window)

        if self.send_message_var:
            self.send_message_shortcut = QShortcut(QKeySequence(), self)
            self.send_message_shortcut.setKey(QKeySequence("Ctrl+Return"))
            self.send_message_shortcut.activated.connect(self.send_message)
            self.send_message_var = True
        elif self.send_message_shortcut:
            self.send_message_shortcut.setKey(QKeySequence())
            
        if self.autoslide_var:
            self.shortcut1 = QShortcut(QKeySequence(), self)
            self.shortcut1.setKey(QKeySequence(Qt.Key.Key_Tab))  # 修复
            self.shortcut1.activated.connect(self.toggle_tree_view)
            self.shortcut2 = QShortcut(QKeySequence(), self)
            self.shortcut2.setKey(QKeySequence("Ctrl+Q"))  # 使用字符串格式
            self.shortcut2.activated.connect(self.toggle_tree_view)
            self.autoslide_var=True
        elif self.shortcut1:
            self.shortcut1.setKey(QKeySequence())
            self.shortcut2.setKey(QKeySequence())

        if self.hotkey_sysrule_var:
            self.hotkey_sysrule = QShortcut(QKeySequence(), self)
            self.hotkey_sysrule.setKey(QKeySequence("Ctrl+E"))  # 使用字符串格式
            self.hotkey_sysrule.activated.connect(self.open_system_prompt)
            self.hotkey_sysrule_var=True
        elif self.hotkey_sysrule:
            self.hotkey_sysrule.setKey(QKeySequence())

    #载入记录
    def load_chathistory(self,file_path=None):
        if not file_path:
            file_path, _ = QFileDialog.getOpenFileName(
                self,
                "选择聊天记录文件",
                "",
                "JSON Files (*.json);;All Files (*)"
            )
            if not file_path:
                self.BESB.warning.emit("未选择文件")
                return
        
        if self.session_manager.change_session_by_path(file_path):
            self.info_manager.notify(
f'''聊天记录已导入，当前聊天：{self.session_manager.title}
对话轮数 {self.session_manager.chat_rounds},
对话标识 {self.session_manager.chat_id}'''
)

    #编辑记录
    def edit_chathistory(self, file_path=''):
        connect_current = False
        if file_path:
            if self.session_manager.is_saved_current_history(file_path):
                session = self.session_manager.current_chat
                connect_current = True
            else:
                session = self.session_manager.load_chathistory(file_path)
                connect_current = False
        else:
            session = self.session_manager.current_chat
            connect_current = True

        editor = ChatHistoryEditor(
            title_generator=TitleGenerator(
                api_handler= APIRequestHandler(),
                settings=APP_SETTINGS.title
            ),
            session= session
        )

        # 连接信号
        if connect_current:
            # 连接到当前聊天记录的更新
            editor.editCompleted.connect(self.session_manager.set_session)
        else:
            # 连接到文件保存
            editor.editCompleted.connect(
                lambda ch: self.session_manager.save_chathistory(chat_session=ch)
            )
            editor.editCompleted.connect(self.grab_past_chats)
        
        editor.show()
    
    def save_chathistory(self):
        """打开文件选择窗口并保存当前聊天记录"""

        if self.session_manager.current_chat.chat_rounds <= 1:
            QMessageBox.warning(self, "保存失败", "当前没有足够的聊天记录可以保存。")
            return

        default_file_name = "chat_history.json"
        file_path, _ = QFileDialog.getSaveFileName(
            self,
            "保存聊天记录",
            default_file_name,
            "JSON 文件 (*.json);;文本文件 (*.txt);;所有文件 (*)"
        )

        if not file_path:
            return

        success = self.session_manager.save_chathistory(
            file_path=file_path,
            chat_session=self.session_manager.current_chat
        )

    #修改问题
    def edit_user_last_question(self):
        if self.session_manager.chat_rounds <= 1:
            self.info_manager.warning("当前没有可编辑的问题")
            return
        text,muti = self.session_manager.fallback_history_for_edit()
        
        self.user_input_text.setText(text)
        self.user_input_text.setAttachments(muti)
        


    #重写关闭事件，添加自动保存聊天记录和设置
    def closeEvent(self, event):
        """窗口关闭事件"""
        self.session_manager.autosave()
        ConfigManager.save_settings(APP_SETTINGS)
        self.mod_configer.run_close_event()
        if hasattr(self, 'fps_monitor'):
            self.fps_monitor.export_csv("cwla_ui_performance.csv")
        # 确保执行父类关闭操作
        super().closeEvent(event)
        event.accept()  # 确保窗口可以正常关闭


    #获取历史记录
    def grab_past_chats(self):
        self.past_chat_list.populate_history(
            self.session_manager.past_session_list
        )

    #从历史记录载入聊天
    def load_from_past(self, index):
        if not self.past_chat_list.currentItem():
            self.info_manager.warning("No item selected")
            return
        self.load_chathistory(
            file_path=self.past_chat_list.get_selected_file_path()
        )

    # === 对话设置，主设置，全局设置 ===
    def open_main_setting_window(self):
        if not hasattr(self, "main_setting_window"):
            self.main_setting_window = MainSettingWindow(settings=APP_SETTINGS)
            self._connect_setting_signals()
        self.main_setting_window.populate_values()
        self.main_setting_window.show()
        self.main_setting_window.raise_()


    def _connect_setting_signals(self):
        # LCI开关 → 更新状态栏图标
        self.main_setting_window.lci_enabled_changed.connect(self.update_opti_bar)
        self.main_setting_window.name_changed.connect(self.session_manager.set_role_name)

        ## 标题生成provider/model变更 → 重新设置title_generator
        #self.main_setting_window.title_provider_changed.connect(
        #    lambda provider, model: self.title_generator.set_provider(
        #        provider=provider, model=model, api_config=APP_SETTINGS.api.providers
        #    )
        #)


    #历史对话
    def past_chats_menu(self, position):
        target_item = self.past_chat_list.itemAt(position)
        if not target_item:
            return

        context_menu = QMenu(self.past_chat_list)

        load_history = context_menu.addAction("载入")
        load_history.triggered.connect(
            lambda: self.load_chathistory(
                file_path=self.past_chat_list.get_selected_file_path()
            )
        )

        edit_action=context_menu.addAction("修改")
        edit_action.setToolTip('修改存档对话的内容和标题')
        edit_action.triggered.connect(
            lambda: self.edit_chathistory(
                file_path=self.past_chat_list.get_selected_file_path()
            )
        )

        delete_action = context_menu.addAction("删除")
        delete_action.triggered.connect(
            lambda: self.delete_selected_history()
        )

        import_action = context_menu.addAction("导入system prompt")
        import_action.setToolTip('从过去的中获取系统提示文本并覆盖掉\n当前对话中的系统提示。')
        import_action.triggered.connect(
            lambda: self.load_sys_pmt_from_past_record()
        )

        world_view_action = context_menu.addAction("分析")
        world_view_action.setToolTip('打开分析窗口')
        world_view_action.triggered.connect(
            lambda: self.analysis_past_chat()
        )

        context_menu.exec(self.past_chat_list.viewport().mapToGlobal(position))

    #删除记录
    def delete_selected_history(self):
        """删除选中的历史记录及其对应文件"""
        # 获取当前选中的列表项
        file_path = self.past_chat_list.get_selected_file_path()
        if not file_path:
            self.info_manager.warning("No item selected")
            return
        if self.session_manager.is_saved_current_history(file_path):
            self.clear_history()

        # 删除文件
        self.session_manager.delete_chathistory(file_path)

        # 从界面移除项
        item = self.past_chat_list.currentItem()
        row = self.past_chat_list.row(item)
        self.past_chat_list.takeItem(row)


    #读取过去system prompt
    def load_sys_pmt_from_past_record(self):
        file_path = self.past_chat_list.get_selected_file_path()
        sys_pmt=self.session_manager.load_sys_pmt_from_past_record(file_path=file_path)
        if sys_pmt:
            self.session_manager.set_system_content()
            self.info_manager.success('系统提示已导入并覆盖当前对话中的系统提示')
        
    def analysis_past_chat(self):
        file_path = self.past_chat_list.get_selected_file_path()
        self.show_analysis_window(file_path)

    #背景更新：触发线程
    def call_background_update(self):
        self._setup_bsw()
        self.background_agent.generate(
            chathistory=self.session_manager.history,
        )

    #背景更新：触发UI更新
    def update_background(self,file_path):
        fp = os.path.join(APP_RUNTIME.paths.application_path,file_path)
        self.info_manager.log(f'update_background: {file_path}')
        if not file_path\
        or not os.path.isfile(fp):
            QMessageBox.critical(
                None,
                '背景更新',
                '获取的图像路径无效',
                QMessageBox.StandardButton.Ok
            )
            return
        self.switchImage(fp)

    def _setup_bsw(self):
        if not hasattr(self,'background_agent'):
            self.background_agent=BackgroundAgent()
            self.bind_background_signals()

    #背景更新：设置窗口
    def background_settings_window(self):
        """创建并显示设置子窗口，用于更新配置变量"""
        self._setup_bsw()
        self.background_agent.show()
        self.background_agent.raise_()
        
    
    def bind_background_signals(self):
        # 断开所有已存在的信号连接
        if hasattr(self, '_bg_signal_connections'):
            for disconnect_func in self._bg_signal_connections:
                disconnect_func()
            self._bg_signal_connections.clear()
        else:
            self._bg_signal_connections = []

        # 重新连接所有信号并保存断开方法
        def add_connection(signal, slot):
            connection = signal.connect(slot)
            self._bg_signal_connections.append(lambda: signal.disconnect(connection))

        add_connection(
            self.background_agent.setting_window.updateSettingChanged,
            self.update_opti_bar
        )

        add_connection(
            self.background_agent.poll_success,
            lambda path: [
                self.update_background(path) or self.info_manager.log(f'背景生成返回了路径，返回了{path}')] if path else [
                    self.update_background('background.jpg'), self.info_manager.log(f'背景生成没返回路径，返回了{path}')
                    ]
        )
   
    #背景生成器
    def show_pic_creater(self):
        pass

        #打开背景图片    
    def open_background_pic(self):
        os.startfile(
            os.path.join(
                APP_RUNTIME.paths.application_path,
                APP_SETTINGS.background.image_path
            )
        )

    #背景控件初始化
    def init_back_ground_label(self,path):
        # 先加载原始图片
        self.original_pixmap = QPixmap(path)

        # 实例化标签并传递原始图片
        self.target_label = AspectLabel(self.original_pixmap, self)

        # 视觉效果配置
        self.opacity_effect = QGraphicsOpacityEffect()
        self.opacity_effect.setOpacity(0.5)
        self.target_label.setGraphicsEffect(self.opacity_effect)
        
        # 布局配置
        self.main_layout.addWidget(self.target_label, 0, 0, 10, 10)


 
    #图片更换动画
    def _start_animation(self, new_pixmap):
        self.anim_out = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.anim_out.setDuration(300)
        self.anim_out.setStartValue(0.5)
        self.anim_out.setEndValue(0.0)
        self.anim_out.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.anim_out.finished.connect(lambda: self._apply_image(new_pixmap))
        self.anim_out.start()
    def _apply_image(self, pixmap):
        self.target_label.update_icon(pixmap)
        self.anim_in = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.anim_in.setDuration(300)
        self.anim_in.setStartValue(0.0)
        self.anim_in.setEndValue(0.5)
        self.anim_in.setEasingCurve(QEasingCurve.Type.InOutQuad)
        self.anim_in.finished.connect(self.back_animation_finished.emit)
        self.anim_in.start()
 
    #更换图片
    def switchImage(self, new_image_path):
        new_pixmap = QPixmap(new_image_path)
        self._start_animation(new_pixmap)


    #更新触发进度条
    def update_opti_bar(self,_=None):
        ncr=self.session_manager.current_chat.new_chat_rounds
        nbr=self.session_manager.current_chat.new_background_rounds
        self.chat_opti_trigger_bar.setVisible(APP_SETTINGS.lci.enabled)
        self.chat_opti_trigger_bar.setValue(ncr)
        self.chat_opti_trigger_bar.setMaximum(APP_SETTINGS.lci.max_segment_rounds)
        self.Background_trigger_bar.setVisible(APP_SETTINGS.background.enabled)
        self.Background_trigger_bar.setValue(nbr)
        self.Background_trigger_bar.setMaximum(APP_SETTINGS.background.max_rounds)
        self.cancel_trigger_background_update.setVisible(APP_SETTINGS.background.enabled)
        self.cancel_trigger_chat_opti.setVisible(APP_SETTINGS.lci.enabled)
        if ncr>=APP_SETTINGS.lci.max_segment_rounds:
            self.chat_opti_trigger_bar.setFormat(f'对话优化: 即将触发')
        else:
            self.chat_opti_trigger_bar.setFormat(f'对话优化: {ncr}/{APP_SETTINGS.generation.max_message_rounds}')
        if nbr>=APP_SETTINGS.generation.max_message_rounds:
            self.Background_trigger_bar.setFormat(f'背景更新: 即将触发')
        else:
            self.Background_trigger_bar.setFormat(f'背景更新: {nbr}/{APP_SETTINGS.background.max_rounds}')
        self.opti_frame.setVisible(APP_SETTINGS.background.enabled or APP_SETTINGS.lci.enabled)

    #联网搜索结果窗口
    def handle_search_result_button_toggle(self):
        self.init_web_searcher()
        if self.search_result_button.isChecked():
            self.web_searcher.search_results_widget.show()
            self.search_result_label.show()
            self.main_layout.addWidget(self.display_full_chat_history, 2, 4, 1, 1)
            self.main_layout.addWidget(self.chat_history_label, 2, 3, 1, 1)
            self.main_layout.addWidget(self.chat_history_bubbles, 3, 3, 4, 3)
            self.main_layout.addWidget(self.search_result_label, 2, 2, 1, 1)
            self.main_layout.addWidget(self.web_searcher.search_results_widget,3, 2, 4, 1)
            self.main_layout.setColumnStretch(0, 1)

        else:
            self.web_searcher.search_results_widget.hide()
            self.search_result_label.hide()
            self.main_layout.addWidget(self.display_full_chat_history, 2, 4, 1, 1)
            self.main_layout.addWidget(self.chat_history_label, 2, 2, 1, 1)
            self.main_layout.addWidget(self.chat_history_bubbles, 3, 2, 4, 3)

    def handle_web_search_button_index_changed(self,index):
        # 关闭搜索模块
        if index==0:
            self.web_search_button.setChecked(False)
            self.search_result_button.setChecked(False)
            self.handle_search_result_button_toggle()
            self.search_result_button.hide()
            self.web_searcher.search_results_widget.hide()
            self.search_result_label.hide()
        # 启用搜索工具
        if index == 1:
            self.web_search_button.setChecked(True)
            selected_functions = self.function_manager.get_selected_function_names()
            selected_functions = list(set(selected_functions) | {'web_search'})
        if index ==2 :
            self.init_web_searcher()
            self.web_search_button.setChecked(True)
            APP_SETTINGS.web_search.web_search_enabled = True
            self.search_result_button.show()
        else:
            APP_SETTINGS.web_search.web_search_enabled = False
            self.search_result_button.hide()
            self.search_result_label.hide()

        if index in [0,2]:
            selected_functions = self.function_manager.get_selected_function_names()
            selected_functions = [func for func in selected_functions if func != 'web_search']
        self.function_manager.set_active_tools(selected_functions)
        
        # 强制搜索，老接口
        APP_SETTINGS.web_search.web_search_enabled = index == 2
            

    def handle_web_search_button_toggled(self,checked):
        if not checked and self.web_search_button.currentIndex()!=0:
            self.web_search_button.setCurrentIndex(0)
        if  checked and self.web_search_button.currentIndex()==0:
            self.web_search_button.setCurrentIndex(1)

    def open_web_search_setting_window(self):
        self.init_web_searcher()
        self.web_searcher.search_settings_widget.show()

    def show_concurrent_model(self,show=False):
        self.ensure_concurrenter()
        if show:
            self.concurrent_model.show()
        else:
            self.concurrent_model.hide()

    def show_analysis_window(self,data=None):
        if not data:
            data=self.session_manager.history
        if not hasattr(self,'token_analyzer'):
            self.token_analyzer=TokenAnalysisWidget()
        self.token_analyzer.show()
        self.token_analyzer.raise_()
        self.token_analyzer.activateWindow()
        self.token_analyzer.set_data(data)

    # 0.24.4 模型并发信号
    def concurrentor_content_receive(self,msg_id,content):pass
        #self.full_response=content
        #self.update_ai_response_text(str(msg_id),content)

    def concurrentor_reasoning_receive(self,msg_id,content):pass
        #self.think_response=content
        #self.thinked=True
        #self.update_think_response_text(str(msg_id),content)

    def concurrentor_finish_receive(self,msg_id,content):pass
    #    self.last_chat_info = self.concurrent_model.get_concurrentor_info()
    #    self.full_response=content
    #    self._receive_message(
    #        {
    #            "role": "assistant",
    #            "content": content,
    #            "info": {
    #                "id": msg_id,
    #                "time":time.strftime("%Y-%m-%d %H:%M:%S")
    #            }
    #        }
    #    )

    # 0.25.1 avatar
    # 显示头像窗口
    def show_avatar_window(self,msg_id,name):

        # 从历史取初始值
        do_init=False
        names= self.session_manager.current_chat.name
        name_user = names['user']
        name_ai   = names['assistant']

        avatar    = self.session_manager.current_chat.avatars
        avatar_user= avatar['user']
        avatar_ai= avatar['assistant']

        avatar_info={
            'user':{
                'name':name_user,
                'image':avatar_user
            },
            'assistant':{
                'name':name_ai,
                'image':avatar_ai
            },
        }

        # 检查初始化
        if (not hasattr(self,'avatar_creator')):
            do_init=True   
        
        elif self.avatar_creator.avatar_info['user']!=name_user or\
        self.avatar_creator.avatar_info['assistant'] != name_ai:
            do_init=True
        if do_init:
            self.avatar_creator=AvatarCreatorWindow(
                avatar_info=avatar_info,
                application_path=APP_RUNTIME.paths.application_path,
                init_character={'lock':not msg_id,'character':name},
                model_map=APP_SETTINGS.api.model_map,
                default_apis=APP_SETTINGS.api.providers,
                msg_id=msg_id,
                chathistory=self.session_manager.history
                )
            self.avatar_creator.avatarCreated.connect(self.session_manager.set_role_avatar)
        
        # 更新选择
        self.avatar_creator.character_for.setCurrentText(avatar_info[name]['name'])
        self.avatar_creator.chathistory=self.session_manager.history

        # 显示窗口
        self.avatar_creator.show()
        self.avatar_creator.raise_()

    #创建新消息
    def creat_new_chat(self):
        # todo: 兼容chatsession
        self.system_prompt_override_window.load_income_prompt(
            self.session_manager.current_chat
        )

        # 获取系统提示管理器洗干净的预设消息
        preset=self.system_prompt_override_window.get_init_preset()

        print('self.session_manager.create_new_session(preset)',preset,type(preset.info['name']))

        self.session_manager.create_new_session(preset)

    def update_avatar_to_chat_bubbles(self,id='',avatars = {}):
        if not avatars:
            avatars=self.session_manager.avatars
        self.chat_history_bubbles.avatars = avatars
        self.chat_history_bubbles.update_all_avatars()

    def update_name_to_chatbubbles(self,id='',names=None):
        if not names:
            names = self.core.session_manager.current_chat.name

        self.chat_history_bubbles.nicknames = {
            'user': names.get('user', 'User'), 
            'assistant': names.get('assistant', 'AI')
        }

        self.chat_history_bubbles.update_all_nicknames()


    def update_request_status(self, status: dict):
        if self._cb_buffers.status:
            markdown_str = self._render_status_markdown(status)
            self.ai_response_text.setMarkdown(markdown_str)

    def _render_status_markdown(self, stats: dict) -> str:
        #状态分析器    def _render_status_markdown(self, stats: dict) -> str:
        header = "| 指标          | 数值                               |\n| :------------ | :--------------------------------- |"
        rows = []

        # 1. 基础信息
        rows.append(f"| **模型**        | `{stats['provider']}/{stats['model']}`")

        # 2. 过程字数
        if stats['reasoning_chars'] > 0:
            rows.append(f"| **思维链字数**  | `{stats['reasoning_chars']}` 字")
        if stats['tool_chars'] > 0:
            rows.append(f"| **工具调用字数**| `{stats['tool_chars']}` 字")

        # 3. 回复状态
        if stats['content_chars'] > 0:
            rows.append(f"| **回复字数**    | `{stats['content_chars']}` 字")
        elif stats['reasoning_chars'] > 0:
            rows.append("| **回复**        | 正在等待思维链结束...")
        else:
            rows.append("| **回复**        | 正在生成...")

        # 4. 性能指标
        speed = f"平均 `{stats['tps']}` / 峰值 `{stats['peak_tps']}`"
        rows.append(f"| **速度 (TPS)**  | {speed}")
        rows.append(f"| **首Token延迟** | `{stats['ttft_ms']}` ms")
        rows.append(f"| **总耗时**      | `{stats['duration_s']}` s")

        # 5. 收尾指标
        if 'total_rounds' in stats:
            rows.append(f"| **对话总轮数**  | `{stats['total_rounds']}`")
            rows.append(f"| **对话总字数**  | `{stats['total_length']}`")
            rows.append(f"> {stats['finish_reason']}")

        table_body = "\n".join([f"{row:<20}|" for row in rows])

        return f"## 📊 对话状态\n---\n{header}\n{table_body}\n"

    def handle_session_change(self,session:'ChatSession'):
        self.chat_history_bubbles.set_chat_history(session.history)
        self.update_avatar_to_chat_bubbles()
        self.update_name_to_chatbubbles()
    
    def handle_main_chat_completed(self,id,message):
        self.control_frame_to_state('finished')
        self.chat_history_bubbles.streaming_scroll(run=False)

start_log(f'CWLA Class import finished, time stamp:{time.time()-start_time_stamp:.2f}s')

def start():
    window = MainWindow()
    window.show()
    start_log(f'CWLA shown on desktop, time stamp:{time.time()-start_time_stamp:.2f}s')
    sp.close()
    sys.exit(app.exec())

if __name__=="__main__":
    start()
