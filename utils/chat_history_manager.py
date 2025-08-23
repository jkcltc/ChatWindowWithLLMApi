from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import json

class ChatHistoryTools:
    @staticmethod
    def locate_chat_index(chathistory, request_id):
        for i, msg in enumerate(chathistory):
            info = msg.get('info', {})
            if str(info.get('id')) == str(request_id):
                return i
        return None
    
    @staticmethod
    def patch_history_0_25_1(chathistory,names=None,avatar=None):
        request_id=100001
        for item in chathistory:
            if not "info" in item:
                item['info']={'id':str(request_id)}
                request_id+=1
        if (not 'name' in chathistory[0]['info']) and names:
            chathistory[0]['info']['name']=names
        if (not 'avatar' in chathistory[0]['info']) and avatar:
            chathistory[0]['info']['avatar']=avatar
        if chathistory[0]['role']=='system' or chathistory[0]['role']==['developer']:
            chathistory[0]['info']['id']='system_prompt'
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
    
    # 其他方法保持不变（以下方法与前一个版本相同）...
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