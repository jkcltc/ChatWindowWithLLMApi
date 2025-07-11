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
                item['info']={'id':request_id}
                request_id+=1
        if (not 'name' in chathistory[0]['info']) and names:
            chathistory[0]['info']['name']=names
        if (not 'avatar' in chathistory[0]['info']) and avatar:
            chathistory[0]['info']['avatar']=avatar
        chathistory[0]['info']['id']=999999#system prompt它就应该
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

class ChatHistoryTextView(QDialog):
    """A dialog window for displaying full chat history."""
    
    def __init__(self, parent, chat_history, user_name, ai_name):
        """
        Initialize the chat history window.
        
        Args:
            parent: The parent widget
            chat_history: List of chat messages
            user_name: Name to display for user messages
            ai_name: Name to display for AI messages
        """
        super().__init__(parent)
        self.chat_history = chat_history
        self.user_name = user_name
        self.ai_name = ai_name
        
        self.setWindowTitle("Chat History")
        self.setMinimumSize(650, 500)
        
        self._init_ui()
        self._load_chat_history()
        
    def _init_ui(self):
        """Initialize the UI components."""
        self.text_browser = QTextBrowser()
        self.text_browser.setOpenExternalLinks(True)
        
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 8)
        layout.addWidget(self.text_browser)
    
    def _load_chat_history(self):
        """Load and format the chat history into the text browser."""
        buffer = []
        append = buffer.append  # Local variable for faster access
        
        for index, msg in enumerate(self.chat_history):
            name = self._get_sender_name(msg['role'])
            append(f'\n\n### {name}\n')  # 标题格式突出显示
            if 'reasoning_content' in msg and msg['reasoning_content']:
                append(f"\n> Think: {msg['reasoning_content']}\n")

            if 'content' in msg and msg['content']:
                append(f"{msg['content']}\n")

            # 添加分隔线（非最后一条消息）
            if index < len(self.chat_history) - 1:
                append('\n---')

        self.text_browser.setMarkdown('\n'.join(buffer))
    
    def _get_sender_name(self, role):
        """Get the display name for the given message role.
        
        Args:
            role: The role of the message sender ('system', 'user', or 'assistant')
            
        Returns:
            str: The display name for the sender
        """
        if role == 'system':
            return 'system'
        elif role == 'user':
            return self.user_name
        elif role == 'assistant':
            return self.ai_name
        elif role == 'tool':
            return self.ai_name+' called tool:'
        return role  # fallback for unknown roles

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
        dialog.setFixedSize(300, 150)
        
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