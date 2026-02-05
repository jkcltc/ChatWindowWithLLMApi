import time
start_time_stamp=time.time()
print(f'CWLA init timer start, time cost:{time.time()-start_time_stamp:.2f}s')
import configparser
import copy
import ctypes
import json
import os
import re
import sys
import threading
import difflib
import warnings
import uuid
warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore", message="libpng warning: iCCP: known incorrect sRGB profile")

#基础类初始化
from utils.tools.init_functions import DEFAULT_APIS,api_init,install_packages

print(f'CWLA iner import finished, time cost:{time.time()-start_time_stamp:.2f}s')

install_packages()

#第三方类初始化
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from PyQt6.QtSvg import *
import openai

print(f'CWLA 3rd party lib import finished, time cost:{time.time()-start_time_stamp:.2f}s')

#自定义类初始化

from utils.info_module import InfoManager,LOGMANAGER
LOGGER=LOGMANAGER

from utils.custom_widget import *
from utils.system_prompt_manager import SystemPromptManager,SystemPromptComboBox
from utils.setting import APP_SETTINGS,MainSettingWindow,APP_RUNTIME,ConfigManager

from utils.model_map_manager import APIConfigWidget,RandomModelSelecter
from utils.theme_manager import ThemeSelector
from utils.tool_core import FunctionManager,get_functions_events
from utils.concurrentor import ConvergenceDialogueOptiProcessor
from utils.preset_data import *
from utils.usage_analysis import TokenAnalysisWidget
from utils.chat_history_manager import ChatHistoryEditor,ChathistoryFileManager,TitleGenerator,ChatHistoryTools,ChatHistoryTextView,HistoryListWidget
from utils.message.preprocessor import MessagePreprocessor,PreprocessorPatch
from utils.avatar import AvatarCreatorWindow
from utils.background_generate import BackgroundAgent
from utils.tools.one_shot_api_request import FullFunctionRequestHandler,APIRequestHandler
from utils.status_analysis import StatusAnalyzer
from utils.tools.str_tools import StrTools

LOGGER.log(f'CWLA custom lib import finished, time cost:{time.time()-start_time_stamp:.2f}s')

#TTS初始化
from mods.chatapi_tts import TTSAgent

#小功能初始化
from mods.mod_manager import ModConfiger

LOGGER.log(f'CWLA mod lib import finished, time cost:{time.time()-start_time_stamp:.2f}s')

#路径初始化
if getattr(sys, 'frozen', False):
    # 打包后的程序
    application_path = os.path.dirname(sys.executable)
    temp_path = sys._MEIPASS
else:
    # 普通 Python 脚本
    application_path = os.path.dirname(os.path.abspath(__file__))

#缩进图片
if not os.path.exists('background.jpg'):
    with open('background.jpg', 'wb') as f:
        f.write(think_img)

# 全局设置库初始化
ConfigManager.load_settings(APP_SETTINGS)


#强制降重
class RepeatProcessor:
    def __init__(self, main_class):
        self.main = main_class  # 持有主类的引用

    def find_last_repeats(self):
        """处理重复内容的核心方法"""
        # 还原之前的修改
        if self.main.difflib_modified_flag:
            self._restore_original_settings()
            self.main.difflib_modified_flag = False

        # 处理重复内容逻辑
        assistants = self._get_assistant_messages()
        clean_output = []
        
        if len(assistants) >= 4:
            last_four = assistants[-4:]
            has_high_similarity = self._check_similarity(last_four)
            
            if has_high_similarity:
                self._apply_similarity_settings()

            repeats = self._find_repeated_substrings(last_four)
            clean_output = self._clean_repeats(repeats)

        return clean_output

    def _restore_original_settings(self):
        """恢复原始配置"""
        APP_SETTINGS.generation.max_message_rounds  = self.main.original_max_message_rounds
        APP_SETTINGS.lci.placement                  = self.main.original_long_chat_placement
        APP_SETTINGS.lci.enabled                    = self.main.original_long_chat_improve_var
        self.main.original_max_message_rounds = None
        self.main.original_long_chat_placement = None
        self.main.original_long_chat_improve_var = None

    def _get_assistant_messages(self):
        """获取助手消息"""
        return [msg['content'] for msg in self.main.chathistory if msg['role'] == 'assistant']

    def _check_similarity(self, last_four):
        """检查消息相似度"""
        similarity_threshold = 0.4
        has_high_similarity = False
        
        for i in range(len(last_four)):
            for j in range(i+1, len(last_four)):
                ratio = difflib.SequenceMatcher(None, last_four[i], last_four[j]).ratio()
                LOGGER.info(f'当前相似度 {ratio}')
                if ratio >= similarity_threshold:
                    LOGGER.warning('过高相似度，激进降重触发')
                    return True
        return False

    def _apply_similarity_settings(self):
        """应用相似度过高时的配置"""
        if not self.main.difflib_modified_flag:
            self.main.original_max_message_rounds =     APP_SETTINGS.generation.max_message_rounds  
            self.main.original_long_chat_placement =    APP_SETTINGS.lci.placement                  
            self.main.original_long_chat_improve_var=   APP_SETTINGS.lci.enabled                    
            APP_SETTINGS.generation.max_message_rounds = 3
            APP_SETTINGS.lci.placement = "对话第一位"
            self.main.difflib_modified_flag = True

    def _find_repeated_substrings(self, last_four):
        """查找重复子串"""
        repeats = set()
        for i in range(len(last_four)):
            for j in range(i + 1, len(last_four)):
                s_prev = last_four[i]
                s_current = last_four[j]
                self._add_repeats(s_prev, s_current, repeats)
        return sorted(repeats, key=lambda x: (-len(x), x))

    def _add_repeats(self, s1, s2, repeats):
        """添加发现的重复项"""
        len_s1 = len(s1)
        for idx in range(len_s1):
            max_len = len_s1 - idx
            for l in range(max_len, 0, -1):
                substr = s1[idx:idx+l]
                if substr in s2:
                    repeats.add(substr)
                    break

    def _clean_repeats(self, repeats):
        """清洗重复项结果"""
        symbol_to_remove = [',','.','"',"'",'，','。','！','？','...','——','：','~']
        clean_output = []
        repeats.reverse()
        
        for item1 in repeats:
            if self._is_unique_substring(item1, repeats) and len(item1) > 3:
                cleaned = self._remove_symbols(item1, symbol_to_remove)
                clean_output.append(cleaned)
        return clean_output

    def _is_unique_substring(self, item, repeats):
        """检查是否唯一子串"""
        return not any(item in item2 and item != item2 for item2 in repeats)

    def _remove_symbols(self, text, symbols):
        """移除指定符号"""
        for symbol in symbols:
            text = text.replace(symbol, '')
        return text

#主类
class MainWindow(QMainWindow):
    ai_response_signal= pyqtSignal(str,str)
    think_response_signal= pyqtSignal(str,str)
    back_animation_finished = pyqtSignal()
    update_background_signal= pyqtSignal(str)

    def setupUi(self):
        print(APP_SETTINGS.ui.theme)
        self.theme_selector = ThemeSelector()
        self.theme_selector.apply_saved_theme()


    def __init__(self):
        super().__init__()
        self.setupUi()
        self.setWindowTitle("CWLA - Chat Window with LLM Api")
        self.setWindowIcon(self.render_svg_to_icon(MAIN_ICON))
        self.message_status=StatusAnalyzer()
        self.repeat_processor=RepeatProcessor(self)

        screen_geometry = QApplication.primaryScreen().availableGeometry()
        
        width = int(screen_geometry.width() * 0.8)
        height = int(screen_geometry.height() * 0.8)
        
        left = (screen_geometry.width() - width) // 2
        top = (screen_geometry.height() - height) // 2
        
        self.setGeometry(left, top, width, height)

        # 初始化参数
        self.init_self_params()

        #初始化响应管理器
        self.init_response_manager()

        # 请求发送器
        self.init_requester()

        # 提示窗口
        self.init_info_manager()

        #function call
        self.init_function_call()

        self.init_concurrenter()

        self.init_chathistory_components()

        self.init_title_creator()
        self.init_system_prompt_window()
        
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
        self.cancel_trigger_background_update.clicked.connect(
            lambda: (setattr(
                self, 'new_background_rounds', 0), 
                self.update_opti_bar())
                )

        self.cancel_trigger_chat_opti=QPushButton("×")
        self.cancel_trigger_chat_opti.clicked.connect(
            lambda: (
                setattr(self, 'new_chat_rounds', 0), 
                self.update_opti_bar())
                )

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
        self.init_mod_configer_page()



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
        self.pause_button.clicked.connect(self.requester.pause)


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

        self.sysrule=self.init_sysrule()
        self.creat_new_chathistory()
        self.ai_response_signal.connect(self.update_ai_response_text)
        self.update_background_signal.connect(self.update_background)#可以弃用了
        self.think_response_signal.connect(self.update_think_response_text)
        self.thread_event = threading.Event()
        self.installEventFilter(self)
        self.bind_hot_key()
        self.update_opti_bar()

        #UI状态恢复
        self.recover_ui_status()
        #UI创建后
        self.init_post_ui_creation()
        self.info_manager.log(f'CWLA init finished, time cost:{time.time()-start_time_stamp:.2f}s',level='debug')

    def init_self_params(self):
        self.chathistory=[]
        self.setting_img = setting_img
        self.temp_style=''

        # 状态控制标志
        self.hotkey_sysrule_var = True
        self.difflib_modified_flag = False

        # 聊天会话管理
        self.new_chat_rounds = 0
        self.last_summary = ''
        self.full_response = ''

        # 背景处理相关
        self.new_background_rounds = 0
        """自从上次背景更新后的新对话轮数"""

        #对话储存点
        self.think_response=''
        self.full_response=''
        self.tool_response=''
        self.finish_reason_raw     =''
        self.finish_reason_readable=''

    
    def init_system_prompt_window(self):
        self.system_prompt_override_window = SystemPromptManager()#folder_path='utils/system_prompt_presets'
        self.system_prompt_override_window.update_tool_selection.connect(self.function_manager.set_active_tools)
        self.system_prompt_override_window.update_preset.connect(self.update_system_preset)


    def init_response_manager(self):
        # AI响应更新控制
        self.ai_last_update_time = 0
        self.ai_update_timer = QTimer()
        self.ai_update_timer.setSingleShot(True)

        # 思考过程更新控制
        self.think_last_update_time = 0
        self.think_update_timer = QTimer()
        self.think_update_timer.setSingleShot(True)

        # 工具调用响应更新控制
        self.tool_last_update_time = 0
        self.tool_update_timer = QTimer()
        self.tool_update_timer.setSingleShot(True)

        self.last_chat_info={}

    def init_mod_configer_page(self):
        self.mod_configer=ModConfiger()

    def init_requester(self):
        self.requester=FullFunctionRequestHandler()

        # AI 响应，完整内容
        self.requester.ai_response_signal.connect(
            lambda id,content:
            setattr(self,'request_id',id) 
            or 
            setattr(self,'full_response',content)
        )
        self.requester.ai_response_signal.connect(self.update_ai_response_text)

        # 思维链，完整内容
        self.requester.think_response_signal.connect(
            lambda id,content:
            setattr(self,'request_id',id) 
            or 
            setattr(self,'think_response',content)
        )
        self.requester.think_response_signal.connect(self.update_think_response_text)

        self.requester.tool_response_signal.connect(
            lambda id,content:
            setattr(self,'request_id',id) 
            or 
            setattr(self,'tool_response',content)
        )
        self.requester.tool_response_signal.connect(self.update_tool_response_text)

        # 对话生成失败
        self.requester.completion_failed.connect(
            self._requester_completion_failed
            )

        self.requester.request_finished.connect(self._receive_message)

        self.requester.ask_repeat_request.connect(self.resend_message_by_tool)

        self.requester.report_finish_reason.connect(
            lambda request_id, finish_reason_raw, finish_reason_readable:
            (
                setattr(self,'finish_reason_raw'        ,finish_reason_raw      ),
                setattr(self,'finish_reason_readable'   ,finish_reason_readable)
            )
        )

        self.requester.log_signal.connect(lambda message: self.info_manager.log(str(message)))
        self.requester.warning_signal.connect(lambda message: self.info_manager.notify(str(message), level='warning'))

    def _requester_completion_failed(self, id_, content,message):
        print('_requester_completion_failed',self.chathistory)
        self.request_id = id_
        self.full_response = content
        self.info_manager.notify(content, level='error')
        self._receive_message(message)

    def init_info_manager(self):
        self.info_manager=InfoManager(
            anchor_widget=self,
            log_manager=LOGGER,
        )

    def init_function_call(self):
        self.function_manager = FunctionManager()
        get_functions_events().errorOccurred.connect(
            lambda message: self.info_manager.notify(message, level='error')
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
            folder_path='utils/system_prompt_presets',
            parent=None,
            include_placeholder=False,
            current_filename_base='当前对话',
        )
        # 切换选择时覆盖系统提示
        self.quick_system_prompt_changer.update_preset.connect(
            lambda preset:(
                self.update_system_preset(preset),
                self.system_prompt_override_window.load_income_prompt(preset),
                )
        )
        self.quick_system_prompt_changer.update_tool_selection.connect(self.function_manager.set_active_tools)
        self.quick_system_prompt_changer.request_open_editor.connect(
            self.open_system_prompt
        )

        #0.25.1 更新
        #聊天历史气泡
        self.bubble_background=QTextBrowser()
        self.main_layout.addWidget(self.bubble_background, 3, 2, 4, 3)
        self.chat_history_bubbles = ChatHistoryWidget()
        self.main_layout.addWidget(self.chat_history_bubbles, 3, 2, 4, 3)
        self.main_layout.addWidget(self.display_full_chat_history, 2, 4, 1, 1)
        self.main_layout.addWidget(self.chat_history_label, 2, 2, 1, 1)
        self.main_layout.addWidget(self.quick_system_prompt_changer, 2, 3, 1, 1)

        #气泡信号绑定
        self.chat_history_bubbles.regenerateRequested.connect(self.resend_message)
        self.chat_history_bubbles.editFinished.connect(self.edit_chathistory_by_index)
        self.chat_history_bubbles.RequestAvatarChange.connect(self.show_avatar_window)
        
    def init_concurrenter(self):
        self.concurrent_model=ConvergenceDialogueOptiProcessor()
        self.concurrent_model.concurrentor_content.connect(self.concurrentor_content_receive)
        self.concurrent_model.concurrentor_reasoning.connect(self.concurrentor_reasoning_receive)
        self.concurrent_model.concurrentor_finish.connect(self.concurrentor_finish_receive)

    def init_sysrule(self):
        # 定义文件路径
        file_path = os.path.join(APP_RUNTIME.paths.application_path,'utils','system_prompt_presets','当前对话.json')
        
        # 检查文件是否存在
        if os.path.exists(file_path):
            # 读取JSON文件内容
            with open(file_path, 'r', encoding='utf-8') as f:
                config_data = json.load(f)
            
            # 获取content字段的值
            self.sysrule = config_data["content"]
            
        else:
            # 创建目录（如果不存在）
            os.makedirs(os.path.dirname(file_path), exist_ok=True)
            name_user=APP_SETTINGS.names.user
            name_ai=APP_SETTINGS.names.ai
            
            # 创建默认配置数据
            default_content = "你是一个有用的AI助手"
            new_config = {
                "name": "当前对话",
                "content": default_content,
                "post_history": "",
                'info':{
                    'id':'system_prompt',
                    'name':{'user':name_user,'assistant':name_ai},
                    'title':'New Chat',
                    'tools':[]
                }
            }
            
            # 写入新文件
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(new_config, f, ensure_ascii=False, indent=2)
            
            # 设置系统规则
            self.sysrule = default_content
        
        # 返回当前系统规则
        return self.sysrule

    def init_chathistory_components(self):
        self.chathistory_file_manager=ChathistoryFileManager(APP_RUNTIME.paths.history_path)
        self.chathistory_file_manager.log_signal.connect(self.info_manager.log)
        self.chathistory_file_manager.warning_signal.connect(self.info_manager.warning)
        self.chathistory_file_manager.error_signal.connect(self.info_manager.error)
    
    def init_title_creator(self):
        api_requester=APIRequestHandler(api_config=APP_SETTINGS.api.providers)
        self.title_generator=TitleGenerator(api_handler=api_requester)
        self.title_generator.set_provider(
            provider=APP_SETTINGS.title.provider,
            model=APP_SETTINGS.title.model,
            api_config=APP_SETTINGS.api.providers
        )
        self.title_generator.log_signal.connect(self.info_manager.log)
        self.title_generator.error_signal.connect(self.info_manager.error)
        self.title_generator.warning_signal.connect(self.info_manager.warning)
        self.title_generator.title_generated.connect(self.update_chat_title)

    def init_web_searcher(self):
        """懒导入，不常用模块，加速启动"""
        if not hasattr(self, 'web_searcher'):
            from utils.online_rag import WebSearchSettingWindows
            self.web_searcher = WebSearchSettingWindows()
    
    def create_one_time_use_title_creator(self):
        api_requester=APIRequestHandler(api_config=APP_SETTINGS.api.providers)
        title_generator=TitleGenerator(api_handler=api_requester)
        title_generator.set_provider(
            provider=APP_SETTINGS.title.provider,
            model=APP_SETTINGS.title.model,
            api_config=APP_SETTINGS.api.providers
        )
        title_generator.log_signal.connect(self.info_manager.log)
        title_generator.error_signal.connect(self.info_manager.error)
        title_generator.warning_signal.connect(self.info_manager.warning)
        return title_generator
        
    def add_tts_page(self):
        if not "mods.chatapi_tts" in sys.modules:
            return
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
        # 数据结构
        data = [
            {"上级名称": "系统", "提示语": "API/模型库设置", "执行函数": "self.open_api_window"},
            {"上级名称": "系统", "提示语": "System Prompt 设定 Ctrl+E", "执行函数": "self.open_system_prompt"},
            {"上级名称": "系统", "提示语": "MOD管理器", "执行函数": "self.show_mod_configer"},
            {"上级名称": "记录", "提示语": "保存记录", "执行函数": "self.save_chathistory"},
            {"上级名称": "记录", "提示语": "导入记录", "执行函数": "self.load_chathistory"},
            {"上级名称": "记录", "提示语": "修改原始记录", "执行函数": "self.edit_chathistory"},
            {"上级名称": "记录", "提示语": "对话分析", "执行函数": "self.show_analysis_window"},
            {"上级名称": "对话", "提示语": "强制触发长对话优化", "执行函数": "self.long_chat_improve"},
            {"上级名称": "对话", "提示语": "函数调用", "执行函数": "self.show_function_call_window"},
            {"上级名称": "背景", "提示语": "背景设置", "执行函数": "self.background_settings_window"},
            {"上级名称": "背景", "提示语": "触发背景更新（跟随聊天）", "执行函数": "self.call_background_update"},
            {"上级名称": "背景", "提示语": "生成自定义背景（正在重构）", "执行函数": "self.show_pic_creater"},
            {"上级名称": "设置", "提示语": "对话设置", "执行函数": "self.open_max_send_lenth_window"},
            {"上级名称": "设置", "提示语": "主题", "执行函数": "self.show_theme_settings"},
            {"上级名称": "设置", "提示语": "快捷键", "执行函数": "self.open_settings_window"},
            {"上级名称": "设置", "提示语": "联网搜索", "执行函数": "self.open_web_search_setting_window"},
           
        ]

        # 创建根节点
        parent_nodes = {}
        for item in data:
            parent_name = item["上级名称"]
            if parent_name not in parent_nodes:
                parent_item = QTreeWidgetItem([parent_name])
                self.tree_view.addTopLevelItem(parent_item)
                parent_nodes[parent_name] = parent_item

        # 创建子节点
        for item in data:
            parent_name = item["上级名称"]
            parent_item = parent_nodes[parent_name]
            child_item = QTreeWidgetItem([item["提示语"]])
            child_item.setData(0, Qt.ItemDataRole.UserRole, item["执行函数"])  # 将执行函数存储在用户数据中
            parent_item.addChild(child_item)
        self.tree_view.expandAll()

    #设置界面：响应点击
    def on_tree_item_clicked(self, item, column):
        # 获取用户数据（执行函数名）
        function_name = item.data(column, Qt.ItemDataRole.UserRole)
        if function_name:
            # 动态调用对应的函数
            func = getattr(self, function_name.split('.')[-1])
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
        self.history_text_view = ChatHistoryTextView(self.chathistory)
        
        self.history_text_view.show()
        self.history_text_view.raise_()

    #流式处理的末端方法
    def update_chat_history(self, clear=True, new_msg=None,msg_id=''):
        name_ai=self.chathistory[0]['info']['name']['assistant']
        name_user=self.chathistory[0]['info']['name']['user']
        if not new_msg:
            self.chat_history_bubbles.streaming_scroll(False)
            self.chat_history_bubbles.set_role_nickname('assistant',name_ai)
            self.chat_history_bubbles.set_role_nickname('user', name_user)
            self.chat_history_bubbles.set_chat_history(self.chathistory)
            try:
                self.tts_handler.send_tts_request(
                    name_ai,
                    self.full_response,
                    force_remain=True
                )
            except Exception as e:
                self.info_manager.notify(f'tts_handler.send_tts_request{e}','warning')

        else:
            self.chat_history_bubbles.streaming_scroll(True)
            self.chat_history_bubbles.update_bubble(
                msg_id=msg_id,
                content=self.full_response,
                streaming='streaming',
                model=self.message_status.model #发送时绑定的模型参数就剩它了
            )

        # 条件保存（仅在内容变化时）
        if clear :
            if not new_msg:
                self.chathistory_file_manager.autosave_save_chathistory(self.chathistory)
                self.update_opti_bar()
                

    #更新AI回复
    def update_ai_response_text(self,request_id,content):
        self._handle_update(
            response_length=len(self.full_response),
            timer=self.ai_update_timer,
            update_method=self.perform_ai_actual_update,
            last_update_attr='ai_last_update_time',
            delay_threshold=5000,
            delays=(300, 600),
            request_id=request_id
        )

    #更新AI思考链
    def update_think_response_text(self,request_id,content):
        self._handle_update(
            response_length=len(self.think_response),
            timer=self.think_update_timer,
            update_method=self.perform_think_actual_update,
            last_update_attr='think_last_update_time',
            delay_threshold=5000,
            delays=(300, 600),
            request_id=request_id
        )

    def update_tool_response_text(self,request_id,content):
        self._handle_update(
            response_length=len(self.tool_response),
            timer=self.tool_update_timer,
            update_method=self.perform_tool_actual_update,
            last_update_attr='tool_last_update_time',
            delay_threshold=5000,
            delays=(300, 600),
            request_id=request_id
        )


    #更新AI辅助函数
    def _handle_update(self, response_length, timer: QTimer, update_method, last_update_attr, delay_threshold, delays,request_id):
        current_time = QDateTime.currentDateTime().toMSecsSinceEpoch()
        fast_delay, slow_delay = delays
        delay = slow_delay if response_length > delay_threshold else fast_delay
        
        # 获取对应的最后更新时间
        last_update_time = getattr(self, last_update_attr)
        elapsed = current_time - last_update_time

        if elapsed >= delay:
            # 立即执行更新
            update_method(request_id)
        else:
            # 设置延迟更新
            remaining = delay - elapsed
            if timer.isActive():
                timer.stop()
            timer.start(remaining)

    #实施更新
    def perform_ai_actual_update(self,request_id):
        # 更新界面和滚动条
        self.ai_response_text.setMarkdown(
            self.get_status_str()
        )
        actual_response = StrTools.combined_remove_var_vast_replace(
            self.full_response,
            setting=APP_SETTINGS.replace,
            mod_enabled=self.mod_configer.status_monitor_enable_box.isChecked()
        )
        self.update_chat_history(new_msg=actual_response,msg_id=request_id)
        name_ai=self.chathistory[0]['info']['name']['assistant']

        #0.25.1 气泡
        try:
            self.tts_handler.send_tts_request(
                name_ai,
                self.full_response
            )
        except Exception as e:
            self.info_manager.notify(f'tts_handler.send_tts_request{e}','error')

        # 更新时间戳
        self.ai_last_update_time = QDateTime.currentDateTime().toMSecsSinceEpoch()
        self.message_status.process_input(self.think_response+self.full_response+self.tool_response)

    def perform_think_actual_update(self,request_id):
        #0.25.1 气泡思考栏
        self.chat_history_bubbles.streaming_scroll(True)
        self.chat_history_bubbles.update_bubble(msg_id=request_id,reasoning_content=self.think_response,streaming='streaming',model=self.message_status.model)
        
        # 更新时间戳
        self.think_last_update_time = QDateTime.currentDateTime().toMSecsSinceEpoch()
        self.message_status.process_input(self.think_response+self.full_response+self.tool_response)
        self.ai_response_text.setMarkdown(
            self.get_status_str()
        )

    def perform_tool_actual_update(self,request_id):
        #0.25.1 气泡工具栏
        self.chat_history_bubbles.streaming_scroll(True)
        self.chat_history_bubbles.update_bubble(msg_id=request_id,reasoning_content=self.tool_response,streaming='streaming',model=self.message_status.model,role='tool')
        
        # 更新时间戳
        self.tool_last_update_time = QDateTime.currentDateTime().toMSecsSinceEpoch()
        self.message_status.process_input(self.think_response+self.full_response+self.tool_response)
        self.ai_response_text.setMarkdown(
            self.get_status_str()
        )


    #打包一个从返回信息中做re替换的方法
    def _replace_for_receive_message(self,message):
        for item in message:
            content=item['content']
            content = re.sub(r'<think>.*?</think>', '', content, flags=re.DOTALL)
            if content.startswith("\n\n"):
                content = content[2:]
            content = content.replace('</think>', '')
            content = StrTools.combined_remove_var_vast_replace(
                content=content,
                setting=APP_SETTINGS.replace,
                mod_enabled=self.mod_configer.status_monitor_enable_box.isChecked()
            )
            item['content']=content
        return message


    #接受信息，信息后处理
    def _receive_message(self,message):
        try:
            message=self._replace_for_receive_message(message)
            self.chathistory.extend(message)
            # AI响应状态栏更新
            self.ai_response_text.setMarkdown(self.get_status_str(message_finished=True))

            # mod后处理
            self.mod_configer.handle_new_message(self.full_response,self.chathistory)
        except Exception as e:
            self.info_manager.notify(level='error',text='receive fail '+str(e))
        finally:
            self.control_frame_to_state('finished')
            self.update_chat_history()

    ###发送请求主函数 0.25.3 api基础重构
    def send_request(self,create_thread=True):
        self.full_response=''
        self.think_response=''
        self.tool_response=''
        def target():
            pack = PreprocessorPatch(self).prepare_patch()  # 创建预处理器实例
            message, params = MessagePreprocessor().prepare_message(pack=pack)
            if APP_SETTINGS.concurrent.enabled:
                self.concurrent_model.start_workflow(params)
                return
            self.requester.set_provider(
            provider=self.api_var.currentText(),
            api_config=APP_SETTINGS.api.providers
            )
            self.requester.send_request(params)
        try:
            if create_thread:
                thread1 = threading.Thread(target=target)
                thread1.start()
            else:
                target()
            self.main_message_process_timer_end=time.time()*1000
            LOGGER.info(f'消息前处理耗时:{(self.main_message_process_timer_end-self.main_message_process_timer_start):.2f}ms')
            self.message_status.start_record(
                model=self.model_combobox.currentText(),
                provider=self.api_var.currentText(),
                request_send_time=self.main_message_process_timer_end/1000
            )
        except Exception as e:
            self.info_manager.notify(f"Error in sending request: {e}",level='error')
        

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


    #发送消息前的预处理，防止报错,触发长文本优化,触发联网搜索
    def sending_rule(self):   
        user_input = self.user_input_text.toPlainText()
        if self.chathistory[-1]['role'] == "user":
            # 创建一个自定义的 QMessageBox
            msg_box = QMessageBox(self)
            msg_box.setWindowTitle('确认操作')
            msg_box.setText('确定连发两条吗？')
            
            # 添加自定义按钮
            btn_yes = msg_box.addButton('确定', QMessageBox.ButtonRole.YesRole)
            btn_no = msg_box.addButton('取消', QMessageBox.ButtonRole.NoRole)
            btn_edit = msg_box.addButton('编辑聊天记录', QMessageBox.ButtonRole.ActionRole)
            
            # 显示消息框并获取用户的选择
            msg_box.exec()
            
            # 根据用户点击的按钮执行操作
            if msg_box.clickedButton() == btn_yes:
                # 正常继续
                pass
            elif msg_box.clickedButton() == btn_no:
                # 如果否定：return False
                return False
            elif msg_box.clickedButton() == btn_edit:
                # 如果“编辑聊天记录”：跳转self.edit_chathistory()
                self.edit_chathistory()
                return False
        elif user_input == '':
            # 弹出窗口：确定发送空消息？
            reply = QMessageBox.question(self, '确认操作', '确定发送空消息？',
                                        QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No,
                                        QMessageBox.StandardButton.No)
            if reply == QMessageBox.StandardButton.Yes:
                self.user_input_text.setText('_')
                # 正常继续
            elif reply == QMessageBox.StandardButton.No:
                # 如果否定：return False
                return False
        if APP_SETTINGS.lci.enabled:
            try:
                self.new_chat_rounds+=2

                full_chat_lenth=StrTools.get_chat_content_length(self.chathistory)

                message_lenth_bool=(len(self.chathistory)>APP_SETTINGS.generation.max_message_rounds \
                                    or full_chat_lenth>APP_SETTINGS.lci.max_total_length)
                
                newchat_rounds_bool=self.new_chat_rounds>APP_SETTINGS.generation.max_message_rounds

                newchat_lenth_bool=StrTools.get_chat_content_length(self.chathistory[-self.new_chat_rounds:])>APP_SETTINGS.lci.max_segment_length

                long_chat_improve_bool=message_lenth_bool and newchat_rounds_bool or newchat_lenth_bool

                self.info_manager.log(
                    ''.join(
                        [
                            '长对话优化日志：',
                            '\n当前对话次数:', str(len(self.chathistory)-1),
                            '\n当前对话长度（包含system prompt）:', str(full_chat_lenth),
                            '\n当前新对话轮次:', str(self.new_chat_rounds), '/', str(APP_SETTINGS.generation.max_message_rounds),
                            '\n新对话长度:', str(len(str(self.chathistory[-self.new_chat_rounds:]))),
                            '\n触发条件:',
                            '\n总对话轮数达标:'
                            '\n对话长度达达到', str(APP_SETTINGS.generation.max_message_rounds), ":", str(message_lenth_bool),
                            '\n新对话轮次超过限制:', str(newchat_rounds_bool),
                            '\n新对话长度超过限制:', str(newchat_lenth_bool),
                            '\n触发长对话优化:', str(long_chat_improve_bool)
                        ]
                    ),
                    level='info'
                )
                if long_chat_improve_bool:
                    self.new_chat_rounds=0
                    self.info_manager.notify('条件达到,长文本优化已触发','info')
                    self.long_chat_improve()
            except Exception as e:
                self.info_manager.notify(f"long chat improvement failed, Error code:{e}",'error')
        if APP_SETTINGS.background.enabled:
            try:
                self.new_background_rounds+=2
                full_chat_lenth=StrTools.get_chat_content_length(self.chathistory)
                message_lenth_bool=(len(self.chathistory)>APP_SETTINGS.background.max_rounds \
                                    or full_chat_lenth>APP_SETTINGS.background.max_length)
                newchat_rounds_bool=self.new_background_rounds>APP_SETTINGS.background.max_rounds

                long_chat_improve_bool=message_lenth_bool and newchat_rounds_bool

                self.info_manager.log(f"""背景更新日志：
当前对话次数: {len(self.chathistory)-1}
当前对话长度（包含system prompt）: {full_chat_lenth}
当前新对话轮次: {self.new_background_rounds}/{APP_SETTINGS.background.max_rounds}
新对话长度: {StrTools.get_chat_content_length(self.chathistory[-self.new_background_rounds:])-StrTools.get_chat_content_length([self.chathistory[0]])}
触发条件:
总对话轮数达标:
对话长度达到 {APP_SETTINGS.background.max_length}: {message_lenth_bool}
新对话轮次超过限制{APP_SETTINGS.background.max_rounds}: {newchat_rounds_bool}
触发背景更新: {long_chat_improve_bool}""",
                    level='info')
                if long_chat_improve_bool:
                    self.new_background_rounds=0
                    
                    self.info_manager.notify('条件达到,背景更新已触发')
                    self.call_background_update()
                
            except Exception as e:
                LOGGER.error(f"Background update failed, Error code:{e}")
        if APP_SETTINGS.force_repeat.enabled:

            APP_RUNTIME.force_repeat.text=''
            repeat_list=self.repeat_processor.find_last_repeats()
            if len(repeat_list)>0:
                for i in repeat_list:
                    APP_RUNTIME.force_repeat.text+=i+'"或"'
                APP_RUNTIME.force_repeat.text='避免回复词汇"'+APP_RUNTIME.force_repeat.text[:-2]
        else:
            APP_RUNTIME.force_repeat.text=''
        return True

    #“发送”按钮触发，开始消息预处理和UI更新
    def send_message(self):
        self.main_message_process_timer_start=time.time()*1000
        if self.send_button.isEnabled() and self.sending_rule():
            if APP_SETTINGS.model_poll.enabled:
                s=self.ordered_model.get_next_model()
                provider=s.provider
                modelname=s.model
                if provider and modelname:
                    self.api_var.setCurrentText(provider)
                    self.model_combobox.setCurrentText(modelname)
            # 此时确认消息可以发送
            self.send_message_toapi()

    #预处理用户输入，并创建发送信息的线程
    def send_message_toapi(self):
        '''
        提取用户输入，
        创建用户消息，
        更新聊天记录，
        发送请求，
        清空输入框，
        '''
        self.control_frame_to_state('sending')
        self.ai_response_text.setText("已发送，等待回复...")
        user_input = self.user_input_text.toPlainText()
        multimodal_input=self.user_input_text.get_multimodal_content()

        new_message={
                'role': 'user', 
                'content': user_input,
                'info':{
                    "id":str(int(time.time())),
                    'time':time.strftime("%Y-%m-%d %H:%M:%S")
                    }
            }
        
        if multimodal_input:
            new_message['info']['multimodal']=multimodal_input
        self.chathistory.append(new_message)
        self.user_input_text.clear()
        self.create_chat_title_when_empty(self.chathistory)
        self.update_chat_history()
        self.send_request(create_thread= not APP_SETTINGS.concurrent.enabled)

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
        self.chathistory_file_manager.autosave_save_chathistory(self.chathistory)
        self.creat_new_chathistory()
        self.chat_history_bubbles.clear()
        self.ai_response_text.clear()
        self.new_chat_rounds=0
        self.new_background_rounds=0
        self.last_summary=''
        self.update_chat_history()

    # 系统提示预设更新
    def update_system_preset(self,preset):
        # 只需要content，剩下post_history和name没必要
        self.chathistory[0]['content']=preset['content']
        info=preset["info"]
        for key,value in info.items():
            if key == 'title':
                continue
            self.chathistory[0]['info'][key]=value
        self._update_preset_to_ui_by_system_message()

    # 打开系统提示设置窗口
    def open_system_prompt(self, show_at_call=True):
        if show_at_call:
            self.system_prompt_override_window.show()
        if self.system_prompt_override_window.isVisible():
            self.system_prompt_override_window.raise_()
            self.system_prompt_override_window.activateWindow()
        self.system_prompt_override_window.load_income_prompt(self.chathistory[0])


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
        QShortcut(QKeySequence("Ctrl+S"), self).activated.connect(lambda: self.chathistory_file_manager.save_chathistory(self.chathistory))
        QShortcut(QKeySequence("Ctrl+M"), self).activated.connect(self.show_mod_configer)
        QShortcut(QKeySequence("Ctrl+T"), self).activated.connect(self.show_theme_settings)
        QShortcut(QKeySequence("Ctrl+D"), self).activated.connect(self.open_max_send_lenth_window)
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

    #Enter发送信息
    def autosend_message(self, event):
        """自定义按键事件处理"""
        if event.key() == Qt.Key_Return or event.key() == Qt.Key_Enter:
            self.send_message()
        else:
            # 调用原始的 keyPressEvent 处理其他按键
            QTextEdit.keyPressEvent(self.user_input_text, event)

    #获取ai说的最后一句
    def get_last_assistant_content(self):
        # 从后向前遍历聊天历史
        for chat in reversed(self.chathistory):
            if chat.get('role') == 'assistant':  # 检查 role 是否为 'assistant'
                return chat.get('content')  # 返回对应的 content 值
        return None  # 如果没有找到 role 为 'assistant' 的记录，返回 None

    #打开模式设置
    def open_module_window(self):
        pass

    #载入记录
    def load_chathistory(self,file_path=None):
        load_start_time=time.perf_counter()
        chathistory=self.chathistory_file_manager.load_chathistory(file_path)
        if chathistory:
            self.chathistory=chathistory
            self.new_chat_rounds=min(APP_SETTINGS.generation.max_message_rounds,len(self.chathistory))
            self.new_background_rounds=min(APP_SETTINGS.background.max_rounds,len(self.chathistory))
            self.last_summary=''
            
            self._update_preset_to_ui_by_system_message()
            self.update_chat_history()  # 更新聊天历史显示
            tool_list=chathistory[0].get('info',{}).get('tools',[])
            self.function_manager.set_active_tools(tool_list)
            self.info_manager.notify(
                f'''聊天记录已导入，当前聊天记录：{file_path}
对话长度 {len(self.chathistory)},
识别长度 {len(self.chathistory[-1]['content'])}
处理时间 {(time.perf_counter()-load_start_time)*1000:.2f}ms''')

    #保存记录
    def save_chathistory(self):
        self.chathistory_file_manager.save_chathistory(self.chathistory)

    #编辑记录
    def edit_chathistory(self, file_path=''):
        # 确定要使用的聊天记录和标题生成器
        if file_path:
            chathistory = self.chathistory_file_manager.load_chathistory(file_path)
            if self.chathistory == chathistory or self.chathistory_file_manager.is_equal(self.chathistory, chathistory):
                # 使用当前聊天记录
                target_history = self.chathistory
                title_generator = self.title_generator
                connect_current = True
            else:
                # 使用加载的聊天记录
                target_history = chathistory
                title_generator = self.create_one_time_use_title_creator()
                connect_current = False
        else:
            # 使用当前聊天记录
            target_history = self.chathistory
            title_generator = self.title_generator
            connect_current = True
        
        # 创建编辑器实例
        self.history_editor = ChatHistoryEditor(
            title_generator=title_generator, 
            chathistory=target_history
        )
        
        # 连接信号
        if connect_current:
            # 连接到当前聊天记录的更新
            self.history_editor.editCompleted.connect(lambda new_history: setattr(self, 'chathistory', new_history))
            self.history_editor.editCompleted.connect(self.update_chat_history)
        else:
            # 连接到文件保存
            self.history_editor.editCompleted.connect(self.chathistory_file_manager.autosave_save_chathistory)
            self.history_editor.editCompleted.connect(self.grab_past_chats)
        
        self.history_editor.show()

    def edit_chathistory_by_index(self,id,text):
        index=ChatHistoryTools.locate_chat_index(self.chathistory,id)
        self.chathistory[index]['content']=text

    #修改问题
    def edit_user_last_question(self):
        # 从后往前遍历聊天历史
        self.handel_call_back_to_lci_bgu()
        if self.chathistory[-1]["role"]=="user":
            self.user_input_text.setText(self.chathistory[-1]["content"])
            self.user_input_text.setAttachments(self.chathistory[-1].get('info',{}).get('multimodal',[]))
            self.chathistory.pop()
        elif self.chathistory[-1]["role"]=="assistant" or self.chathistory[-1]["role"]=="tool":#处理工具调用时被用户截断
            while self.chathistory[-1]["role"]!="user":
                self.chathistory.pop()
            self.user_input_text.setText(self.chathistory[-1]["content"])
            self.user_input_text.setAttachments(self.chathistory[-1].get('info',{}).get('multimodal',[]))
            self.chathistory.pop()
        else:
            QMessageBox.warning(self,'重传无效','至少需要发送过一次消息')
        self.update_chat_history(clear= False)

    #重生成消息，直接创建最后一条
    def resend_message_last(self):
        self.resend_message()
    
    def resend_message(self,request_id=''):
        self.main_message_process_timer_start=time.time()*1000
        if not self.send_button.isEnabled():
            return

        self.handel_call_back_to_lci_bgu()
        if request_id:
            index=ChatHistoryTools.locate_chat_index(self.chathistory,request_id)
            chathistory=self.chathistory[:index+1]
        else:
            chathistory=self.chathistory.copy()

        if chathistory[-1]["role"]=="assistant" or chathistory[-1]["role"]=="tool":
            while len(chathistory)>1 and chathistory[-1]["role"]!="user":
                chathistory.pop()

        if len(chathistory)==1 or chathistory[-1]["role"]!="user":
            QMessageBox.warning(self,'重传无效','至少需要发送过一次消息')
            return
        
        self.chathistory=chathistory
        self.control_frame_to_state('sending')
        self.ai_response_text.setText("正在重传，等待回复...")
        self.update_chat_history()
        self.send_request(create_thread= not APP_SETTINGS.concurrent.enabled)

    #重写关闭事件，添加自动保存聊天记录和设置
    def closeEvent(self, event):
        """窗口关闭事件"""
        try:
            self.chathistory_file_manager.autosave_save_chathistory(self.chathistory)  # 调用自动保存聊天历史的方法
        except Exception as e:
            LOGGER.error(f"autosave_save_chathistory fail: {e}")
        try:
            self.save_hotkey_config()
        except Exception as e:
            LOGGER.error(f"save_hotkey_config fail: {e}")
        #try:
        #    ConfigManagerOld.config_save(self)
        #except Exception as e:
        #    LOGGER.error(f"config_save fail: {e}")
        #ModelMapManager().save_model_map(MODEL_MAP)
        ConfigManager.save_settings(APP_SETTINGS)
        self.mod_configer.run_close_event()
        # 确保执行父类关闭操作
        super().closeEvent(event)
        event.accept()  # 确保窗口可以正常关闭

    #保存快捷键设置
    def save_hotkey_config(self):
        # 创建配置文件对象
        config = configparser.ConfigParser()
        # 添加一个section
        config.add_section('HotkeyConfig')
        # 设置变量值
        config.set('HotkeyConfig', 'send_message_var', str(self.send_message_var))
        config.set('HotkeyConfig', 'autoslide_var', str(self.autoslide_var))
        config.set('HotkeyConfig', 'hotkey_sysrule_var', str(self.hotkey_sysrule_var))
        # 写入文件
        with open('hot_key.ini', 'w', encoding='utf-8') as configfile:
            config.write(configfile)

    #读取快捷键ini
    def read_hotkey_config(self):
        # 创建配置文件对象
        config = configparser.ConfigParser()
        # 读取文件
        config.read('hot_key.ini')
        # 读取变量值
        try:
            if 'HotkeyConfig' in config:
                self.send_message_var = config.getboolean('HotkeyConfig', 'send_message_var')
                self.autoslide_var = config.getboolean('HotkeyConfig', 'autoslide_var')
                self.hotkey_sysrule_var=config.getboolean('HotkeyConfig', 'hotkey_sysrule_var')
            else:
                self.info_manager.warning("配置文件中没有找到 HotkeyConfig 部分。")
        except Exception as e:
            print(e)

    #获取历史记录
    def grab_past_chats(self):
        # 获取当前文件夹下所有.json文件
        past_chats = self.chathistory_file_manager.load_past_chats(APP_RUNTIME.paths.history_path)

        # 将文件名添加到QComboBox中
        self.past_chat_list.populate_history(past_chats)

    #从历史记录载入聊天
    def load_from_past(self, index):
        self.chathistory_file_manager.autosave_save_chathistory(self.chathistory)
        
        # 基础安全校验
        if not self.past_chat_list.currentItem():
            self.info_manager.warning("No item selected")
            return

        # 获取当前选中的列表项
        selected_item_path = self.past_chat_list.get_selected_file_path()
        
        # 直接读取存储的完整路径
        if os.path.exists(selected_item_path):
            self.load_chathistory(file_path=selected_item_path)
        else:
            self.info_manager.error(f"数据读取失败: {str(selected_item_path)}")

    #长文本优化：启动线程
    def long_chat_improve(self):
        self.new_chat_rounds=0
        self.update_opti_bar()
        try:
            self.info_manager.info("长文本优化：线程启动")
            threading.Thread(target=self.long_chat_improve_thread).start()
        except Exception as e:
            print(e)

    #长文本优化：总结进程
    def long_chat_improve_thread(self):
        self.last_summary=''
        self.lci_cleaned_system_prompt=''
        summary_prompt=LongChatImprovePersetVars.summary_prompt
        user_summary=LongChatImprovePersetVars.user_summary
        if APP_SETTINGS.lci.hint!='':
            user_summary+=LongChatImprovePersetVars.long_chat_hint_prefix+str(APP_SETTINGS.lci.hint)
        if self.chathistory[0]["role"]=="system":
            try:
                self.last_summary=(self.chathistory[0]["content"].split(LongChatImprovePersetVars.before_last_summary))[1]
                self.lci_cleaned_system_prompt=(self.chathistory[0]["content"].split(LongChatImprovePersetVars.before_last_summary))[0]
            except Exception as e:
                self.last_summary=''
            last_full_story=LongChatImprovePersetVars.before_last_summary+\
                            self.last_summary+\
                            LongChatImprovePersetVars.after_last_summary+\
                            ChatHistoryTools.to_readable_str(self.chathistory[-APP_SETTINGS.generation.max_message_rounds:])#,{'user':self.name_user,'assistant':self.name_ai,})
        else:
            last_full_story=ChatHistoryTools.to_readable_str(self.chathistory[-APP_SETTINGS.generation.max_message_rounds:])
            if self.lci_cleaned_system_prompt and APP_SETTINGS.lci.collect_system_prompt:
                last_full_story=self.lci_cleaned_system_prompt+last_full_story
                

        last_full_story=user_summary+last_full_story
        messages=[
            {"role":"system","content":summary_prompt},
            {"role":"user","content":last_full_story}
        ]
        if APP_SETTINGS.lci.api_provider:
            api_provider=APP_SETTINGS.lci.api_provider
            self.info_manager.log(f'自定义长对话优化API提供商：{api_provider}')
        else:
            api_provider = self.api_var.currentText()
            self.info_manager.log(f'默认对话优化API提供商：{api_provider}')
        if APP_SETTINGS.lci.model:
            model=APP_SETTINGS.lci.model
            self.info_manager.log(f'自定义长对话优化模型：{model}')
        else:
            model = self.model_combobox.currentText()
            self.info_manager.log(f'默认长对话优化模型：{model}')
        client = openai.Client(
            api_key=APP_SETTINGS.api.providers[api_provider].key,
            base_url=APP_SETTINGS.api.providers[api_provider].url
        )
        try:
            self.info_manager.log(f"长文本优化：迭代1发送。\n发送内容长度:{len(last_full_story)}")
            completion = client.chat.completions.create(
                model=model,
                messages=messages,
                #temperature=0
            )
            return_story = completion.choices[0].message.content
            self.info_manager.log(f"长文本优化：迭代1完成。\n返回长度:{len(return_story)}\n返回内容：{return_story}")
            if self.last_summary=='':
                self.info_manager.log("self.last_summary==''")
            if self.last_summary!='':
                last_full_story=LongChatImprovePersetVars.summary_merge_prompt+self.last_summary+LongChatImprovePersetVars.summary_merge_prompt_and+return_story
                self.info_manager.log(f"长文本优化：迭代2开始。\n发送长度:{len(last_full_story)}={len(self.last_summary)}+{len(return_story)}")
                messages=[
                {"role":"system","content":summary_prompt},
                {"role":"user","content":last_full_story}
                ]
                completion = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    #temperature=0
                )
                return_story = completion.choices[0].message.content
                self.info_manager.log(f"长文本优化：迭代2完成。\n返回长度:{len(return_story)}\n返回内容：{return_story}")
            try:
                if self.chathistory[0]["role"]=="system":
                    pervious_sysrule = self.chathistory[0]["content"].split(LongChatImprovePersetVars.before_last_summary)[0]
                else:
                    pervious_sysrule=self.sysrule.split(LongChatImprovePersetVars.before_last_summary)[0]
            except Exception as e:
                if self.chathistory[0]["role"]=="system":
                    pervious_sysrule = self.chathistory[0]["content"]
                else:
                    pervious_sysrule=self.sysrule
                self.info_manager.warning(f"pervious_sysrule failure, Error code:{e}\nCurrent 'pervious_sysrule':{pervious_sysrule}")
            # 替换系统背景
            
            self.sysrule=pervious_sysrule+'\n'+LongChatImprovePersetVars.before_last_summary+return_story
            self.chathistory[0]["content"]=self.sysrule
            self.last_summary=return_story
            self.info_manager.log(f'长对话处理一次,历史记录第一位更新为：{self.chathistory[0]["content"]}')
            self.chathistory_file_manager.autosave_save_chathistory(self.chathistory)
        except Exception as e:
            # 如果线程中发生异常，也通过信号通知主线程
            self.info_manager.warning(f'长对话优化报错，Error code:{e}')

    # === 对话设置，主设置，全局设置 ===
    def open_max_send_lenth_window(self):
        if not hasattr(self, "main_setting_window"):
            self.main_setting_window = MainSettingWindow(settings=APP_SETTINGS)
            self._connect_setting_signals()
        self.main_setting_window.populate_values()
        self.main_setting_window.show()
        self.main_setting_window.raise_()


    def _connect_setting_signals(self):
        # LCI开关 → 更新状态栏图标
        self.main_setting_window.lci_enabled_changed.connect(self.update_opti_bar)

        # 标题生成provider/model变更 → 重新设置title_generator
        self.main_setting_window.title_provider_changed.connect(
            lambda provider, model: self.title_generator.set_provider(
                provider=provider, model=model, api_config=APP_SETTINGS.api.providers
            )
        )


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
        chathistory_to_delete=self.chathistory_file_manager.load_chathistory(file_path)
        if chathistory_to_delete==self.chathistory or\
            self.chathistory_file_manager.is_equal(self.chathistory,chathistory_to_delete):
            self.clear_history()

        # 删除文件
        self.chathistory_file_manager.delete_chathistory(file_path)

        # 从界面移除项
        item = self.past_chat_list.currentItem()
        row = self.past_chat_list.row(item)
        self.past_chat_list.takeItem(row)


    #读取过去system prompt
    def load_sys_pmt_from_past_record(self):
        file_path = self.past_chat_list.get_selected_file_path()
        sys_pmt=self.chathistory_file_manager.load_sys_pmt_from_past_record(file_path=file_path)
        if sys_pmt:
            self.sysrule=sys_pmt
            self.chathistory[0]['content']=sys_pmt
            self.info_manager.success('系统提示已导入并覆盖当前对话中的系统提示')
        
    def analysis_past_chat(self):
        file_path = self.past_chat_list.get_selected_file_path()
        self.show_analysis_window(file_path)

    #背景更新：触发线程
    def call_background_update(self):
        self._setup_bsw()
        self.background_agent.generate(
            chathistory=self.chathistory,
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
        try:
            self.chat_opti_trigger_bar.setVisible(APP_SETTINGS.lci.enabled)
            self.chat_opti_trigger_bar.setValue(self.new_chat_rounds)
            self.chat_opti_trigger_bar.setMaximum(APP_SETTINGS.generation.max_message_rounds)
            self.Background_trigger_bar.setVisible(APP_SETTINGS.background.enabled)
            self.Background_trigger_bar.setValue(self.new_background_rounds)
            self.Background_trigger_bar.setMaximum(APP_SETTINGS.background.max_rounds)
            self.cancel_trigger_background_update.setVisible(APP_SETTINGS.background.enabled)
            self.cancel_trigger_chat_opti.setVisible(APP_SETTINGS.lci.enabled)
            if self.new_chat_rounds>=APP_SETTINGS.generation.max_message_rounds:
                self.chat_opti_trigger_bar.setFormat(f'对话优化: 即将触发')
            else:
                self.chat_opti_trigger_bar.setFormat(f'对话优化: {self.new_chat_rounds}/{APP_SETTINGS.generation.max_message_rounds}')
            if self.new_background_rounds>=APP_SETTINGS.generation.max_message_rounds:
                self.Background_trigger_bar.setFormat(f'背景更新: 即将触发')
            else:
                self.Background_trigger_bar.setFormat(f'背景更新: {self.new_background_rounds}/{APP_SETTINGS.background.max_rounds}')
            self.opti_frame.setVisible(APP_SETTINGS.background.enabled or APP_SETTINGS.lci.enabled)
        except Exception as e:
            self.info_manager.log(f"Setting up process bar,ignore if first set up: {e}")

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

    #长对话/背景更新启用时的消息回退
    def handel_call_back_to_lci_bgu(self):
        '''长对话/背景更新启用时的消息回退'''
        handlers = [
            (APP_SETTINGS.lci.enabled, 'new_chat_rounds'),
            (APP_SETTINGS.background.enabled, 'new_background_rounds'),
        ]
        
        for condition, attr in handlers:
            if condition:
                current = getattr(self, attr)
                setattr(self, attr, max(0, current - 2))
        self.update_opti_bar()
        
    def show_theme_settings(self):
        self.theme_selector.hide()
        self.theme_selector.show()

    def show_concurrent_model(self,show=False):
        if not getattr(self,"concurrent_model",None):
            self.concurrent_model=ConvergenceDialogueOptiProcessor()
        if show:
            self.concurrent_model.show()
        else:
            self.concurrent_model.hide()

    def show_analysis_window(self,data=None):
        if not data:
            data=self.chathistory
        if not hasattr(self,'token_analyzer'):
            self.token_analyzer=TokenAnalysisWidget()
        self.token_analyzer.show()
        self.token_analyzer.raise_()
        self.token_analyzer.activateWindow()
        self.token_analyzer.set_data(data)

    # 0.24.4 模型并发信号
    def concurrentor_content_receive(self,msg_id,content):
        self.full_response=content
        self.update_ai_response_text(str(msg_id),content)

    def concurrentor_reasoning_receive(self,msg_id,content):
        self.think_response=content
        self.thinked=True
        self.update_think_response_text(str(msg_id),content)

    def concurrentor_finish_receive(self,msg_id,content):
        self.last_chat_info = self.concurrent_model.get_concurrentor_info()
        self.full_response=content
        self._receive_message(
            {
                "role": "assistant",
                "content": content,
                "info": {
                    "id": msg_id,
                    "time":time.strftime("%Y-%m-%d %H:%M:%S")
                }
            }
        )

    # 0.25.1 avatar
    # 显示头像窗口
    def show_avatar_window(self,msg_id,name):

        # 从历史取初始值
        do_init=False
        name_user=self.chathistory[0]['info']['name']['user']
        name_ai=self.chathistory[0]['info']['name']['assistant']
        avatar_user=self.chathistory[0]['info']['avatar']['user']
        avatar_ai=self.chathistory[0]['info']['avatar']['assistant']
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
                chathistory=self.chathistory
                )
            self.avatar_creator.avatarCreated.connect(self.chat_history_bubbles.set_role_avatar)
            self.avatar_creator.avatarCreated.connect(self.update_avatar_to_system_prompt)
        
        # 更新选择
        self.avatar_creator.character_for.setCurrentText(avatar_info[name]['name'])
        self.avatar_creator.chathistory=self.chathistory

        # 显示窗口
        self.avatar_creator.show()
        self.avatar_creator.raise_()
    
    # 头像和历史记录同步更新
    def update_avatar_to_system_prompt(self,name,path):
        if not 'info' in self.chathistory[0]:
            self.chathistory[0]['info']={"id":'system_prompt'}
        if not 'avatar' in self.chathistory[0]['info']:
            self.chathistory[0]['info']['avatar']={'user':'','assistant':''}#path
        self.chathistory[0]['info']['avatar'][name]=path
    
    #头像注入气泡
    def update_avatar_to_chat_bubbles(self):
        ai_avatar_path=os.path.join(APP_RUNTIME.paths.application_path,'pics','avatar','AI_avatar.png')
        user_avatar_path=os.path.join(APP_RUNTIME.paths.application_path,'pics','avatar','USER_avatar.png')
        if 'avatar' in self.chathistory[0]['info']:
            avatar_path=self.chathistory[0]['info']['avatar']
            if not avatar_path['user'] or not os.path.exists(avatar_path['user']):
                avatar_path['user']=user_avatar_path
            if not avatar_path['assistant'] or not os.path.exists(avatar_path['assistant']):
                avatar_path['assistant']=ai_avatar_path
        else:
            self.chathistory[0]['info']['avatar']={
                'user':user_avatar_path,
                'assistant':ai_avatar_path
            }
        self.chat_history_bubbles.avatars=self.chathistory[0]['info']['avatar']
        self.chat_history_bubbles.update_all_avatars()

    #气泡名称更新
    def update_name_to_chatbubbles(self):
        name_user=self.chathistory[0]['info']['name']['user']
        name_ai=self.chathistory[0]['info']['name']['assistant']
        self.chat_history_bubbles.nicknames = {
            'user': name_user, 
            'assistant': name_ai
        }
        self.chat_history_bubbles.update_all_nicknames()

    #创建新消息
    def creat_new_chathistory(self):
        # 如果已有历史消息，更新系统提示窗口暂存的预设到本地
        if self.chathistory:
            self.system_prompt_override_window.load_income_prompt(self.chathistory[0])

        # 获取系统提示管理器洗干净的预设消息
        system_message=self.system_prompt_override_window.get_init_system_message()

        # 清空历史记录，添加系统消息
        self.chathistory = []
        self.chathistory.append(system_message)
        
        self._update_preset_to_ui_by_system_message()

    def _update_preset_to_ui_by_system_message(self):
        self.update_avatar_to_chat_bubbles()
        self.update_name_to_chatbubbles()
    
    #状态分析器
    def get_status_str(self,message_finished=False):
        # 表格头部
        header = "| 指标          | 数值                               |\n| :------------ | :--------------------------------- |"
        
        rows = []
        
        # 模型信息
        model_info = f"`{self.message_status.provider}/{self.message_status.model}`"
        rows.append(f"| **模型**        | {model_info}")

        # 思维链 (CoT) 字数
        if self.think_response:
            rows.append(f"| **思维链字数**  | `{len(self.think_response)}` 字")
        
        if self.tool_response:
            rows.append(f"| **工具调用字数**| `{len(self.tool_response)}` 字")

        # 回复 (CoN) 字数或状态
        if self.full_response:
            rows.append(f"| **回复字数**    | `{len(self.full_response)}` 字")
        else:
            rows.append("| **回复**        | 正在等待思维链结束...")

        # 性能指标
        speed = f"平均 `{self.message_status.get_current_rate():.2f}` / 峰值 `{self.message_status.get_peak_rate():.2f}`"
        latency = f"`{int(self.message_status.get_first_token()*1000)}` ms"
        duration = f"`{int(self.message_status.get_completion_time())}` s"
        
        rows.append(f"| **速度 (TPS)**  | {speed}")
        rows.append(f"| **首Token延迟** | {latency}")
        rows.append(f"| **总耗时**      | {duration}")
        
        if message_finished:
            total_rounds=self.message_status.get_chat_rounds(self.chathistory)
            total_length=self.message_status.get_chat_length(self.chathistory)
            rows.append(f"| **对话总轮数**      | {total_rounds}")
            rows.append(f"| **对话总字数**      | {total_length}")
            rows.append(f"> {self.finish_reason_readable}")

        # 将所有行数据补全表格格式并连接
        table_body = "\n".join([f"{row:<20}|" for row in rows])

        return f"""## 📊 对话状态
---
{header}
{table_body}
"""
    
    
    #0.25.3 info_manager + api request基础重构
    def resend_message_by_tool(self):
        self._receive_message([])
        self.control_frame_to_state("sending")
        self.send_request()
    
    def create_chat_title_when_empty(self,chathistory):
        if chathistory[0]['info']['title'] in [None,'','New Chat',"Untitled Chat"] and len(chathistory)==2:
            self.create_chat_title(chathistory)
        
    def create_chat_title(self,chathistory):
        include_sys_pmt =   APP_SETTINGS.title.include_sys_pmt
        use_local       =   APP_SETTINGS.title.use_local
        max_length      =   APP_SETTINGS.title.max_length
        task_id         =   chathistory[0]['info']['chat_id']

        self.title_generator.create_chat_title(
            chathistory=chathistory,
            include_system_prompt=include_sys_pmt,
            use_local=use_local,
            max_length=max_length,
            task_id= task_id
        )

    def update_chat_title(self,chat_id,title):
        if self.chathistory and 'info' in self.chathistory[0] and self.chathistory[0]['info']['chat_id']==chat_id:
            self.chathistory[0]['info']['title']=title
            self.info_manager.log(f'对话标题更新为：{title}')
            self.chathistory_file_manager.autosave_save_chathistory(self.chathistory)
            self.grab_past_chats()

LOGGER.log(f'CWLA Class import finished, time cost:{time.time()-start_time_stamp:.2f}s',level='debug')

def start():
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    LOGGER.log(f'CWLA shown on desktop, time cost:{time.time()-start_time_stamp:.2f}s',level='debug')
    sys.exit(app.exec())

if __name__=="__main__":
    start()
