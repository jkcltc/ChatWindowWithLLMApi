import concurrent.futures
import json
import os
import threading
import time
import uuid
from typing import Any, Dict, List, Optional, Tuple
from pathlib import Path
import heapq

from PyQt5.QtCore import *
from PyQt5.QtGui import *
from PyQt5.QtWidgets import *

from utils.tools.one_shot_api_request import APIRequestHandler

class ChatHistoryTools:
    @staticmethod
    def locate_chat_index(chathistory, request_id):
        for i, msg in enumerate(chathistory):
            info = msg.get('info', {})
            if str(info.get('id')) == str(request_id):
                return i
        return None
    
    @staticmethod
    def patch_history_0_25_1(chathistory,names=None,avatar=None,title='New Chat'):
        request_id=100001
        for item in chathistory:
            if not "info" in item:
                item['info']={'id':'patch_'+str(request_id)}
                request_id+=1
        if (not 'name' in chathistory[0]['info']) and names:
            chathistory[0]['info']['name']=names
        if (not 'avatar' in chathistory[0]['info']) and avatar:
            chathistory[0]['info']['avatar']=avatar
        if chathistory[0]['role']=='system' or chathistory[0]['role']==['developer']:
            chathistory[0]['info']['id']='system_prompt'
        if not 'chat_id' in chathistory[0]['info']:
            chathistory[0]['info']['chat_id']=str(uuid.uuid4())
        if not 'title' in chathistory[0]['info']:
            chathistory[0]['info']['title']=title
        return chathistory
    
    @staticmethod
    def clean_history(chathistory,unnecessary_items=['info']):
        exclude = set(unnecessary_items)
        return [
            {key: value for key, value in item.items() if key not in exclude}
            for item in chathistory
        ]
    
    @staticmethod
    def to_readable_str(chathistory,
                        names={}
                        ):
        lines = []
        names=names
        default={'user':'user','assistant':'assistant','tool':'tool'}
        for key in default.keys():
            if not key in names:
                names[key]=default[key]
        for message in chathistory:
            if message['role']=='system':
                continue
            lines.append(f"\n{names[message['role']]}:")
            lines.append(f"{message['content']}")
        return '\n'.join(lines)

class ChatHistoryTextView(QWidget):
    """A dialog window for displaying full chat history with right-aligned controls."""
    
    def __init__(self, chat_history, user_name, ai_name):
        super().__init__()
        self.chat_history = chat_history
        self.user_name = user_name
        self.ai_name = ai_name

        if chat_history and isinstance(chat_history[0], dict):
            first_msg = chat_history[0]
            info = first_msg.get('info', {})
            name_data = info.get('name', {}) if isinstance(info, dict) else {}
            
            if isinstance(name_data, dict):
                if name_data.get('user'):
                    self.user_name = name_data['user']
                if name_data.get('assistant'):
                    self.ai_name = name_data['assistant']
        
        self.setWindowTitle("聊天历史-文本")
        self.setMinimumSize(1280, 720)  # 增加最小宽度以适应右侧面板
        
        # 显示选项默认值
        self.show_reasoning = False
        self.show_tools = True
        self.show_metadata = False
        self.use_markdown = True
        
        self._init_ui()
        self._load_chat_history()
    
    def _init_ui(self):
        """初始化UI组件，控制面板在右侧"""
        main_layout = QHBoxLayout()  # 使用水平布局
        
        # 创建文本浏览区域（左侧）
        self.text_browser = QTextBrowser()
        self.text_browser.setOpenExternalLinks(True)
        main_layout.addWidget(self.text_browser, 3)  # 文本区域占3/4宽度
        
        # 创建右侧面板布局
        controls_layout = QVBoxLayout()
        controls_layout.setAlignment(Qt.AlignTop)
        
        # 添加"显示选项"分组框（右侧）
        options_group = QGroupBox("显示选项")
        options_layout = QVBoxLayout()
        
        # 添加思考链选项
        reasoning_group = QGroupBox("思考链")
        reasoning_layout = QVBoxLayout()
        self.reasoning_cb = QCheckBox("显示思考链")
        self.reasoning_cb.stateChanged.connect(self._toggle_reasoning)
        reasoning_layout.addWidget(self.reasoning_cb)
        reasoning_group.setLayout(reasoning_layout)
        options_layout.addWidget(reasoning_group)
        
        # 添加工具调用选项
        tools_group = QGroupBox("工具调用")
        tools_layout = QVBoxLayout()
        self.tools_cb = QCheckBox("显示工具调用")
        self.tools_cb.setChecked(True)
        self.tools_cb.stateChanged.connect(self._toggle_tools)
        tools_layout.addWidget(self.tools_cb)
        tools_group.setLayout(tools_layout)
        options_layout.addWidget(tools_group)
        
        # 添加元数据显示选项
        metadata_group = QGroupBox("元数据")
        metadata_layout = QVBoxLayout()
        self.metadata_cb = QCheckBox("显示消息元数据")
        self.metadata_cb.stateChanged.connect(self._toggle_metadata)
        metadata_layout.addWidget(self.metadata_cb)
        metadata_group.setLayout(metadata_layout)
        options_layout.addWidget(metadata_group)
        
        # 添加格式选项（右下角）
        format_group = QGroupBox("显示格式")
        format_layout = QVBoxLayout()
        
        self.markdown_rb = QRadioButton("Markdown格式")
        self.markdown_rb.setChecked(True)
        self.markdown_rb.toggled.connect(self._toggle_format)
        
        self.plaintext_rb = QRadioButton("纯文本格式")
        self.plaintext_rb.toggled.connect(self._toggle_format)
        
        format_layout.addWidget(self.markdown_rb)
        format_layout.addWidget(self.plaintext_rb)
        format_group.setLayout(format_layout)
        options_layout.addWidget(format_group)
        
        # 添加重载按钮
        reload_btn = QPushButton("刷新视图")
        reload_btn.clicked.connect(self._load_chat_history)
        options_layout.addWidget(reload_btn)
        
        # 添加间距
        options_layout.addSpacing(20)

        options_group.setLayout(options_layout)
        controls_layout.addWidget(options_group)
        
        # 创建右侧容器
        controls_container = QWidget()
        controls_container.setLayout(controls_layout)
        
        main_layout.addWidget(controls_container, 1)  # 右侧面板占1/4宽度
        
        self.setLayout(main_layout)
    
    def _toggle_reasoning(self, state):
        self.show_reasoning = (state == Qt.Checked)
        self._load_chat_history()
    
    def _toggle_tools(self, state):
        self.show_tools = (state == Qt.Checked)
        self._load_chat_history()
    
    def _toggle_metadata(self, state):
        self.show_metadata = (state == Qt.Checked)
        self._load_chat_history()
    
    def _toggle_format(self):
        self.use_markdown = self.markdown_rb.isChecked()
        self._load_chat_history()
    
    def _load_chat_history(self):
        """根据选项加载和格式化聊天历史"""
        buffer = []
        
        for index, msg in enumerate(self.chat_history):
            # 获取发送者名称
            role = msg.get('role', '')
            name = self._get_sender_name(role)
            
            # 过滤工具调用消息（如果不显示）
            if role == 'tool' and not self.show_tools:
                continue
                
            # 添加消息头部标识
            if self.use_markdown:
                buffer.append(f"\n\n**{name}**")
            else:
                buffer.append(f"\n\n{name}")
            
            # 添加思考链（如果存在且需要显示）
            if self.show_reasoning and 'reasoning_content' in msg:
                reasoning_content = msg['reasoning_content'].replace('### AI 思考链\n---', '').strip()
                if reasoning_content:
                    if self.use_markdown:
                        buffer.append(f"\n```  \n Think: {reasoning_content}  \n  ```  \n---  \n  ")
                    else:
                        buffer.append(f"\n```  \n Think: {reasoning_content}  \n  ```  \n---  \n  ")
            
            # 添加消息内容
            content = msg.get('content', '')
            if content:
                buffer.append(f"\n\n{content}")
            
            # 添加元数据（如果存在且需要显示）
            if self.show_metadata and 'info' in msg:
                info = msg['info']
                if info:
                    if self.use_markdown:
                        buffer.append("\n\n<small>")
                        buffer.append("\n \n ")
                        if msg['role'] == 'system':
                            buffer.append("系统提示设置")
                        else:
                            parts = []
                            if info.get('model'):
                                parts.append(f"模型: {info['model']}")
                            if info.get('time'):
                                parts.append(f"时间: {info['time']}")
                            if info.get('id'):
                                parts.append(f"ID: {info['id']}")
                            buffer.append(" | ".join(parts))
                        buffer.append("</small>")
                    else:
                        buffer.append("\n[元数据]")
                        if msg['role'] == 'system':
                            buffer.append("系统提示设置")
                        else:
                            if info.get('model'):
                                buffer.append(f"  模型: {info['model']}")
                            if info.get('time'):
                                buffer.append(f"  时间: {info['time']}")
                            if info.get('id'):
                                buffer.append(f"  消息ID: {info['id']}")
            
            # 添加消息分隔线（不是最后一条消息）
            if index < len(self.chat_history) - 1:
                buffer.append("\n" + ("---" if self.use_markdown else "─"*10))
        
        # 根据格式设置文本
        full_text = '\n'.join(buffer).strip()
        if self.use_markdown:
            self.text_browser.setMarkdown(full_text)
        else:
            self.text_browser.setPlainText(full_text)
    
    def _get_sender_name(self, role):
        if role == 'system':
            return '系统提示'
        elif role == 'user':
            return self.user_name
        elif role == 'assistant':
            return self.ai_name
        elif role == 'tool':
            return f"{self.ai_name} called tool"
        return role

class ChatHistoryEditor(QDialog):
    # 定义编辑完成的信号，传递新的聊天历史
    editCompleted = pyqtSignal(list)

    def __init__(self, chathistory: list, parent=None):
        super().__init__(parent)
        self.chathistory = chathistory
        self.init_ui()

    def init_ui(self):
        self.setWindowTitle("编辑聊天记录")
        if self.parent():
            self.resize(int(self.parent().width() * 0.8), int(self.parent().height() * 0.8))

        # 主布局（带外边距）
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)  # 增加容器内边距
        main_layout.setSpacing(15)  # 增加控件间距

        # 提示标签（居中+自动换行）
        note_label = QLabel("在文本框中修改内容，AI的回复也可以修改")
        note_label.setAlignment(Qt.AlignCenter)  # 文字居中
        note_label.setWordWrap(True)  # 自动换行
        note_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Maximum)  # 高度自适应
        main_layout.addWidget(note_label)

        # 文本编辑区（添加弹性空间）
        text_container = QWidget()
        text_layout = QVBoxLayout(text_container)
        text_layout.setContentsMargins(0, 0, 0, 0)
        
        self.text_edit = QTextEdit()
        self.text_edit.setText(json.dumps(self.chathistory, ensure_ascii=False, indent=4))
        text_layout.addWidget(self.text_edit)
        
        main_layout.addWidget(text_container, 1)  # 添加伸缩因子使文本框优先扩展

        # 按钮组（水平排列+间距）
        button_group = QGroupBox("编辑")
        button_layout = QHBoxLayout(button_group)  # 改用水平布局
        button_layout.setSpacing(10)  # 按钮间距
        button_layout.setContentsMargins(15, 15, 15, 15)  # 组内边距

        # 按钮创建
        delete_btn = QPushButton("删除上一条")
        replace_btn = QPushButton("替换文本")
        complete_btn = QPushButton("完成编辑")
        
        # 添加到布局（添加拉伸因子）
        button_layout.addWidget(delete_btn)
        button_layout.addWidget(replace_btn)
        button_layout.addStretch(1)  # 添加弹性空间使按钮靠左
        button_layout.addWidget(complete_btn)

        main_layout.addWidget(button_group)

        # 连接信号槽
        delete_btn.clicked.connect(self.delete_last_message)
        replace_btn.clicked.connect(self.show_replace_dialog)
        complete_btn.clicked.connect(self.on_complete)
    def validate_history_format(self, data) -> bool:
        """验证聊天历史格式是否正确"""
        return isinstance(data, list) and all(
            isinstance(item, dict) and "role" in item and "content" in item
            for item in data
        )

    def delete_last_message(self):
        """删除最后一条非系统消息"""
        current_text = self.text_edit.toPlainText().strip()
        try:
            history = json.loads(current_text)
            if history and history[-1].get("role") != "system":
                history.pop()
                self.text_edit.setText(json.dumps(history, ensure_ascii=False, indent=4))
        except json.JSONDecodeError:
            QMessageBox.critical(self, "格式错误", "当前内容不是有效的JSON格式")

    def show_replace_dialog(self):
        """显示替换内容对话框"""
        dialog = QDialog(self)
        dialog.setWindowTitle("替换内容")
        
        layout = QVBoxLayout(dialog)
        
        old_label = QLabel("查找内容:")
        old_edit = QLineEdit()
        new_label = QLabel("替换为:")
        new_edit = QLineEdit()
        replace_btn = QPushButton('执行替换')
        
        layout.addWidget(old_label)
        layout.addWidget(old_edit)
        layout.addWidget(new_label)
        layout.addWidget(new_edit)
        layout.addWidget(replace_btn)
        
        def execute_replace():
            old_text = old_edit.text()
            new_text = new_edit.text()
            
            if not old_text:
                QMessageBox.warning(dialog, "警告", "替换内容不能为空")
                return
                
            current_text = self.text_edit.toPlainText().strip()
            try:
                updated_text = current_text.replace(old_text, new_text)
                self.text_edit.setText(updated_text)
                dialog.close()
            except Exception as e:
                QMessageBox.critical(dialog, "错误", f"替换失败: {str(e)}")
        
        replace_btn.clicked.connect(execute_replace)
        dialog.exec_()

    def on_complete(self):
        """完成编辑的槽函数"""
        edited_json = self.text_edit.toPlainText().strip()
        try:
            new_chathistory = json.loads(edited_json)
            if self.validate_history_format(new_chathistory):
                self.editCompleted.emit(new_chathistory)
                self.accept()
            else:
                QMessageBox.critical(self, "格式错误", "聊天记录必须包含字典列表，且每个字典有role和content字段")
        except json.JSONDecodeError as e:
            QMessageBox.critical(self, "格式错误", f"JSON解析失败: {e}")

class TitleGenerator(QObject):
    log_signal = pyqtSignal(str)
    warning_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)
    title_generated = pyqtSignal(str,str)

    def __init__(self, api_handler: APIRequestHandler = None):
        super().__init__()
        self.api_handler = api_handler
        if self.api_handler:
            self.api_handler.request_completed.connect(self._handle_title_response)
            self.api_handler.error_occurred.connect(lambda msg: self.log_signal.emit(f"Title generation error: {msg}"))

    def bind_api_handler(self, api_handler: APIRequestHandler):
        self.api_handler = api_handler
        if self.api_handler:
            self.api_handler.request_completed.connect(self._handle_title_response)
            self.api_handler.error_occurred.connect(lambda msg: self.log_signal.emit(f"Title generation error: {msg}"))
    
    def set_provider(self, provider, model, api_config=None):
        """
        设置API提供商和配置信息
        :param provider: 提供商名称
        :param model: 模型名称
        :param api_config: API配置信息
        """
        if self.api_handler:
            self.api_handler.set_provider(provider, model, api_config)
        else:
            self.error_signal.emit("API handler not bound, cannot set provider")
            
    def generate_title_from_history_local(self, chathistory,max_length=20):
        title = False
        for chat in chathistory:
            if chat["role"] == "user":  
                title = chat["content"]     
                unsupported_chars = ["\n", '<', '>', ':', '"', '/', '\\', '|', '?', '*', '{', '}', ',', '.', '，', '。', ' ', '!', '！']
                for char in unsupported_chars:
                    title = title.replace(char, '')
                title = title.rstrip(' .')
                if len(title) > max_length:
                    title = title[:max_length]
                break
        if title:
            title = time.strftime("[%Y-%m-%d]", time.localtime()) + title
        return title

    def create_chat_title(
            self,
            chathistory,
            task_id=None,
            use_local=False,
            max_length=20,
            include_system_prompt=False
        ):
        self.task_id = task_id
        system_msg = next((msg for msg in chathistory if msg.get('role') == 'system'), None)
        first_user_msg = next((msg for msg in chathistory if msg.get('role') == 'user'), None)
        if not first_user_msg:
            self.warning_signal.emit("No user message found to generate title.")
            self.title_generated.emit(self.task_id, "New Chat")
            return
        user_content = first_user_msg.get('content', '')
        if not user_content.strip():
            self.warning_signal.emit("User message is empty, cannot generate title.")
            self.title_generated.emit(self.task_id, "New Chat")
            return
        if (not self.api_handler) or use_local:
            self.log_signal.emit("API handler not available, generating title locally.")
            title = self.generate_title_from_history_local(chathistory,max_length=max_length)
            self.title_generated.emit(self.task_id, title)
            return
        # 使用API生成标题
        self.log_signal.emit("Requesting title generation from API.")
        if include_system_prompt and system_msg:
            system_content = system_msg.get('content', '')
            prompt_parts = [
                f"请结合以下'AI角色'和'用户输入'，生成一个不超过{max_length}字的简短标题。标题应体现AI对用户输入的处理意图。直接输出标题，不要包含任何解释或标点符号。标题语言应与用户输入一致。",
                f"Combine the following 'AI Role' and 'User Input' to generate a short title within {max_length} characters. The title should reflect the AI's processing intent for the user input. Output the title directly without any explanation or punctuation. The title's language should match the user's input.",
                f"AI角色/AI Role:\n{system_content}",
                f"用户输入/User Input:\n{user_content}",
                "标题/Title:"
            ]
        else:
            # --- 情况二：不存在系统提示 ---
            # 保持原有逻辑，只基于用户消息生成标题
            prompt_parts = [
                f"为以下用户输入生成一个不超过{max_length}字的简短标题。请直接输出标题，不要包含任何解释或标点符号。标题语言应与用户输入一致。",
                f"Generate a short title for the following user input within {max_length} characters. Output the title directly without any explanation or punctuation. The title's language should match the user's input.",
                f"用户输入/User Input:\n{user_content}",
                "标题/Title:"
            ]

        message = [{"role": "user", "content": '\n\n'.join(prompt_parts)}]
        print(message)
        self.api_handler.send_request(message)

    def _handle_title_response(self, response):
        if len(response) > 100:  # 控件也显示不了这么多
            response = response[:100]
        if response and isinstance(response, str):
            title = time.strftime("[%Y-%m-%d]", time.localtime()) + response.strip().strip('"').strip("'")
            self.title_generated.emit(self.task_id, title)
            return title
        else:
            self.title_generated.emit(self.task_id, "生成失败")
            return "生成失败"

class ChathistoryFileManager(QObject):
    log_signal = pyqtSignal(str)
    warning_signal = pyqtSignal(str)
    error_signal = pyqtSignal(str)

    def __init__(self, history_path='history', title_generator=TitleGenerator()):
        super().__init__()
        self.history_path = history_path
        self.title_generator = title_generator
        self.history_map = {}  # 记录历史文件的id和路径对应关系

    def bind_title_generator(self, title_generator: TitleGenerator):
        self.title_generator = title_generator

    # 载入记录
    def load_chathistory(self, file_path=None):
        # 弹出文件选择窗口
        chathistory = []
        if not file_path:
            file_path, _ = QFileDialog.getOpenFileName(
                None, "导入聊天记录", "", "JSON files (*.json);;All files (*)"
            )
        if file_path and os.path.exists(file_path):
            with open(file_path, "r", encoding="utf-8") as file:
                chathistory = json.load(file)
        else:
            self.warning_signal.emit(f'failed loading chathistory from {file_path}')
            return []
        return chathistory

    # 保存聊天记录
    def save_chathistory(self, chathistory, file_path=None):
        if not file_path:
            # 弹出文件保存窗口
            file_path, _ = QFileDialog.getSaveFileName(
                None, "保存聊天记录", "", "JSON files (*.json);;All files (*)"
            )
            # 更新历史的UUID，防止重复，用户自定义的名字保留
            chathistory[0]['info']['chat_id'] = str(uuid.uuid4())
        self._write_chathistory_to_file(chathistory, file_path)

    def delete_chathistory(self, file_path: str):
        # 输入验证
        if not file_path or not isinstance(file_path, str):
            self.warning_signal.emit(f"Invalid file path provided: {file_path}")
            return
        
        # 路径规范化检查
        try:
            # 转换为绝对路径并解析符号链接
            normalized_path = os.path.realpath(os.path.abspath(file_path))
        except Exception as e:
            self.error_signal.emit(f"Invalid path format: {e}")
            return
        
        
        # 文件扩展名检查
        allowed_extensions = {'.json'}  # 根据实际需求调整
        file_extension = Path(normalized_path).suffix.lower()
        if allowed_extensions and file_extension not in allowed_extensions:
            self.error_signal.emit(f"File type not allowed: {file_extension}")
            return
        
        # 执行删除操作
        if os.path.exists(normalized_path):
            try:
                # 额外检查：确保是文件而不是目录
                if not os.path.isfile(normalized_path):
                    self.error_signal.emit("Cannot delete directories")
                    return
                    
                os.remove(normalized_path)
                self.log_signal.emit(f"Deleted chat history file: {normalized_path}")
            except Exception as e:
                self.error_signal.emit(f"Failed to delete file {normalized_path}: {e}")
        else:
            self.warning_signal.emit(f"File not found for deletion: {normalized_path}")

    # 写入聊天记录到本地
    def _write_chathistory_to_file(self, chathistory: list, file_path: str):
        # 分离路径和文件名，只清洗文件名部分
        dir_path = os.path.dirname(file_path)
        file_name = os.path.basename(file_path)
        
        # 清洗文件名（不包括扩展名）
        unsupported_chars = ["\n", '<', '>', ':', '"', '/', '\\', '|', '?', '*', '{', '}', ',', '，', '。', ' ', '!', '！']
        name_without_ext, ext = os.path.splitext(file_name)
        
        for char in unsupported_chars:
            name_without_ext = name_without_ext.replace(char, '')
        
        # 重新组合路径
        cleaned_file_name = name_without_ext + (ext if ext else '.json')
        if not cleaned_file_name.endswith('.json'):
            cleaned_file_name += '.json'
        
        file_path = os.path.join(dir_path, cleaned_file_name) if dir_path else cleaned_file_name

        if file_path and file_name:  # 检查 file_path 是否有效, file_name 不为空
            self.log_signal.emit(f'saving chathistory to {file_path}')
            try:
                # 确保目录存在
                if dir_path and not os.path.exists(dir_path):
                    os.makedirs(dir_path, exist_ok=True)
                    
                with open(file_path, "w", encoding="utf-8") as file:
                    json.dump(chathistory, file, ensure_ascii=False, indent=4)
            except Exception as e:
                self.error_signal.emit(f'failed saving chathistory {chathistory}')
                QMessageBox.critical(None, "保存失败", f"保存聊天记录时发生错误：{e}")
        else:
            QMessageBox.warning(None, "取消保存", "未选择保存路径，聊天记录未保存。")

    # 自动保存
    def autosave_save_chathistory(self, chathistory):
        '''
        自动保存聊天记录到默认路径
        文件名称如果没有保存在info里，就用本地生成的标题
        仅在自动保存时，chat_id同时作为文件名和对话ID
        '''
        file_path = chathistory[0]['info']['chat_id']
        file_path = os.path.join(self.history_path, file_path)
        if file_path and len(chathistory) > 1:
            self.save_chathistory(chathistory, file_path=file_path)

    # 读取过去system prompt
    def load_sys_pmt_from_past_record(self, chathistory=[], file_path=None):
        """
        从当前或过去的聊天记录中加载系统提示
        Args:
            chathistory (list): 当前聊天记录
            file_path (str): 过去聊天记录的完整路径

        """
        if chathistory:
            return chathistory[0]["content"]
        elif file_path:
            past_chathistory = self.load_chathistory(file_path)
            if past_chathistory and isinstance(past_chathistory, list) and len(past_chathistory) > 0 and past_chathistory[0]["role"] == "system":
                return past_chathistory[0]["content"]
            else:
                self.error_signal.emit(f'failed loading chathistory from {file_path}')
                return ''
        else:
            self.error_signal.emit(f"didn't get any valid input to load sys pmt")
            return ''


    def load_past_chats(self, application_path: str = '', file_count: int = 50) -> List[Dict[str, Any]]:
        """
        并行获取并验证历史聊天记录（优化版：减少 IO、避免重复计算）
        """
        # 路径准备
        if not application_path:
            application_path = self.history_path
        os.makedirs(application_path, exist_ok=True)

        def load_json_from_file(path: str):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)

        # 读取/初始化元数据缓存（减少重复解析）
        cache_path = os.path.join(application_path, ".chat_index.json")
        try:
            with open(cache_path, "r", encoding="utf-8") as cf:
                meta_cache: Dict[str, Dict[str, Any]] = json.load(cf)
        except Exception:
            meta_cache = {}

        def select_latest_jsons(base: str, n: int) -> List[Tuple[str, str, float]]:
            """高效获取按修改时间降序的前 n 个 JSON 文件 (path, name, mtime)"""
            entries = []
            with os.scandir(base) as it:
                for e in it:
                    try:
                        if not e.is_file():
                            continue
                        name = e.name
                        # 跳过缓存与隐藏文件
                        if not name.endswith(".json") or name.startswith("."):
                            continue
                        st = e.stat()
                        entries.append((st.st_mtime, e.path, name))
                    except FileNotFoundError:
                        continue

            if len(entries) <= n:
                entries.sort(key=lambda t: t[0], reverse=True)
                return [(p, name, mtime) for mtime, p, name in entries]

            top = heapq.nlargest(n, entries, key=lambda t: t[0])
            top.sort(key=lambda t: t[0], reverse=True)  # 保持降序输出
            return [(p, name, mtime) for mtime, p, name in top]

        def extract_chat_title(chat_data: List[Dict[str, Any]]) -> str:
            """从聊天数据中提取标题"""
            for message in chat_data:
                if message.get("role") == "system":
                    info = message.get("info") or {}
                    title = info.get("title")
                    if title:
                        return title
            return "Untitled Chat"

        def validate_json_structure(data) -> bool:
            """验证JSON数据结构，支持工具调用格式"""
            if not isinstance(data, list):
                return False

            role_set = {"user", "system", "assistant", "tool"}

            for item in data:
                if not isinstance(item, dict):
                    return False

                role = item.get("role")
                if role not in role_set:
                    return False

                if role in ("user", "system"):
                    content = item.get("content")
                    if not isinstance(content, str):
                        return False

                elif role == "assistant":
                    has_content = "content" in item
                    has_tool_calls = "tool_calls" in item
                    if not (has_content or has_tool_calls):
                        return False
                    if has_content and not isinstance(item["content"], (str, type(None))):
                        return False
                    if has_tool_calls and not isinstance(item["tool_calls"], list):
                        return False

                else:  # role == "tool"
                    if "tool_call_id" not in item or "content" not in item:
                        return False
                    if not isinstance(item["content"], str):
                        return False

            return True

        def parse_one(path: str, name: str, mtime: float) -> Tuple[bool, str, str, float, str, str]:
            """返回: ok, name, path, mtime, err_msg, title"""
            try:
                data = load_json_from_file(path)
                if not validate_json_structure(data):
                    return False, name, path, mtime, "Invalid data structure", ""
                title = extract_chat_title(data)
                return True, name, path, mtime, "", title
            except json.JSONDecodeError:
                return False, name, path, mtime, "Invalid JSON format", ""
            except FileNotFoundError:
                return False, name, path, mtime, "File not found", ""
            except Exception as e:
                return False, name, path, mtime, str(e), ""

        # 1) 仅挑选最新 file_count 个
        selected = select_latest_jsons(application_path, file_count)

        # 2) 命中缓存的直接使用，未命中的再并发解析
        past_chats: List[Dict[str, Any]] = []
        to_parse: List[Tuple[str, str, float]] = []

        def cache_valid(rec: Dict[str, Any], m: float) -> bool:
            # mtime 精度可能不同，给一点容差
            return isinstance(rec, dict) and abs(rec.get("mtime", -1) - m) < 1e-6 and "title" in rec

        for path, name, mtime in selected:
            rec = meta_cache.get(name)
            if rec and cache_valid(rec, mtime):
                past_chats.append({
                    "file_path": path,
                    "title": rec["title"],
                    "modification_time": mtime,
                })
            else:
                to_parse.append((path, name, mtime))

        # 3) 并发解析未命中的文件（IO 为主，线程池足够；数量小就不用开太多线程）
        if to_parse:
            max_workers = min(32, max(1, len(to_parse)))
            with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                futures = [executor.submit(parse_one, p, n, m) for p, n, m in to_parse]

                for future in concurrent.futures.as_completed(futures):
                    ok, name, path, mtime, msg, title = future.result()
                    if ok:
                        past_chats.append({
                            "file_path": path,
                            "title": title,
                            "modification_time": mtime,
                        })
                        # 更新缓存
                        meta_cache[name] = {"mtime": mtime, "title": title}
                    else:
                        self.warning_signal.emit(f"Skipped {name}: {msg}")

        # 4) 写回缓存（失败不影响主流程）
        try:
            with open(cache_path, "w", encoding="utf-8") as cf:
                json.dump(meta_cache, cf, ensure_ascii=False)
        except Exception as e:
            self.warning_signal.emit(f"Failed to update cache: {e}")

        # 5) 最终按时间排序输出
        past_chats.sort(key=lambda x: x["modification_time"], reverse=True)
        return past_chats

class HistoryListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # 性能与体验优化（可选）
        self.setUniformItemSizes(True)  # 每项统一高度，加速布局计算
        self.setAlternatingRowColors(True)
        self._history_signature = None  # 用于跳过重复刷新

    def populate_history(self, history_data):
        """
        高效填充历史记录：
        - 增量更新：只改动变化的项
        - 暂停重绘/信号，减少 UI 开销
        - 保留当前选中项
        """
        # 若数据完全一致，则跳过
        sig = tuple(
            (item.get('file_path'), item.get('modification_time'), item.get('title'))
            for item in history_data or []
        )
        if sig == self._history_signature:
            return
        self._history_signature = sig

        # 记录当前选中项（按 file_path）
        selected_fp = None
        cur = self.currentItem()
        if cur:
            data = cur.data(Qt.UserRole)
            if isinstance(data, dict):
                selected_fp = data.get('file_path')

        # 暂停信号与重绘
        self.blockSignals(True)
        self.setUpdatesEnabled(False)
        sorting_prev = self.isSortingEnabled()
        self.setSortingEnabled(False)  # 防止排序影响插入顺序

        try:
            # 新数据的顺序与精简映射
            new_order = []
            new_map = {}
            for d in (history_data or []):
                fp = d.get('file_path')
                if not fp:
                    continue  # 跳过无效数据
                lean = {
                    'file_path': fp,
                    'title': d.get('title', 'Untitled Chat'),
                    'modification_time': d.get('modification_time', 0),
                }
                new_order.append(fp)
                new_map[fp] = lean

            # 旧项映射：file_path -> QListWidgetItem
            old_map = {}
            for row in range(self.count()):
                item = self.item(row)
                data = item.data(Qt.UserRole)
                fp = data.get('file_path') if isinstance(data, dict) else None
                if fp:
                    old_map[fp] = item

            # 删除不再存在的项（从底部开始避免重排成本）
            to_remove_rows = sorted(
                (self.row(item) for fp, item in old_map.items() if fp not in new_map),
                reverse=True
            )
            for row in to_remove_rows:
                it = self.takeItem(row)
                del it  # 提示 GC 回收

            # 按新顺序逐个处理：更新/移动/新增
            for target_row, fp in enumerate(new_order):
                data = new_map[fp]
                if fp in old_map:
                    item = old_map[fp]
                    # 文本变化才更新，减少不必要的刷新
                    if item.text() != data['title']:
                        item.setText(data['title'])
                    # 更新存储数据
                    item.setData(Qt.UserRole, data)
                    # 若位置不对，移动到目标位置
                    cur_row = self.row(item)
                    if cur_row != target_row:
                        self.takeItem(cur_row)
                        self.insertItem(target_row, item)
                else:
                    # 新增项
                    item = QListWidgetItem(data['title'])
                    item.setData(Qt.UserRole, data)
                    self.insertItem(target_row, item)

            # 恢复选中项（若仍存在）
            if selected_fp and selected_fp in new_map:
                for row in range(self.count()):
                    item = self.item(row)
                    data = item.data(Qt.UserRole)
                    if isinstance(data, dict) and data.get('file_path') == selected_fp:
                        self.setCurrentRow(row)
                        break
            else:
                # 无选中项则选择第一项（可按需调整）
                if self.count() and self.currentRow() < 0:
                    self.setCurrentRow(0)

        finally:
            self.setSortingEnabled(sorting_prev)
            self.setUpdatesEnabled(True)
            self.blockSignals(False)
    
    def get_selected_file_path(self):
        """获取当前选中项的文件路径"""
        current_item = self.currentItem()
        if current_item:
            item_data = current_item.data(Qt.UserRole)
            return item_data.get('file_path')
        return None

    def get_selected_item_data(self):
        """获取当前选中项的完整数据"""
        current_item = self.currentItem()
        if current_item:
            return current_item.data(Qt.UserRole)
        return None