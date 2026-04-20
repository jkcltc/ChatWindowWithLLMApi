import json
import uuid
import copy
from typing import Any, Dict, Optional,TYPE_CHECKING
from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QHBoxLayout, QTabWidget, QGroupBox, 
    QTextEdit, QFormLayout, QLineEdit, QPushButton, QLabel,
    QCheckBox, QSpinBox, QPlainTextEdit, QFileDialog, QApplication
)
from PyQt6.QtCore import pyqtSignal, QTimer

if TYPE_CHECKING:
    from core.session.title_generate import TitleGenerator
    from core.session.session_model import ChatSession


class ChatHistoryEditor(QWidget):
    """
    聊天历史编辑器 - 仅支持 ChatSession 数据结构
    JSON 编辑页仅编辑 history 列表，不包含 Session 的顶层元数据
    相对于主对话独立，需要持有单独的标题生成器
    """
    editCompleted = pyqtSignal(object) 

    def __init__(self, title_generator: 'TitleGenerator', session: 'ChatSession', 
                 parent: Optional[QWidget] = None) -> None:
        super().__init__(parent)
        
        self.setWindowTitle("聊天历史编辑器")
        self._title_generator = title_generator
        
        # 深拷贝 Session，确保编辑器内修改不影响外部
        self._session: 'ChatSession' = copy.deepcopy(session)
        self._original_session: 'ChatSession' = copy.deepcopy(session)
        
        # 状态标记
        self._syncing: bool = False
        self._current_task_id: Optional[str] = None
        self._gen_running: bool = False

        # 构建 UI
        self._build_ui()
        self._connect_signals()
        
        # 初始化数据
        self._ensure_system_message()
        self._load_history_to_form()
        self._update_json_editor_from_history()

        # JSON 防抖定时器
        self._last_applied_json_text: str = self.json_edit.toPlainText()
        self._json_debounce_timer = QTimer(self)
        self._json_debounce_timer.setSingleShot(True)
        self._json_debounce_timer.setInterval(300)  # 300ms 防抖
        self._json_debounce_timer.timeout.connect(self._apply_json_editor_to_form_auto)

    # ---------- UI 构建 ----------
    def _build_ui(self) -> None:
        # 窗口尺寸设置
        screen_geometry = QApplication.primaryScreen().availableGeometry()
        width = int(screen_geometry.width() * 0.6)
        height = int(screen_geometry.height() * 0.6)
        left = (screen_geometry.width() - width) // 2
        top = (screen_geometry.height() - height) // 2
        self.setGeometry(left, top, width, height)

        main_layout = QVBoxLayout(self)
        self.tabs = QTabWidget(self)

        # ===== 表单编辑页 =====
        form_page = QWidget(self)
        form_layout = QVBoxLayout(form_page)

        # System 提示编辑
        sys_group = QGroupBox("系统提示（System Content）", self)
        sys_layout = QVBoxLayout(sys_group)
        self.sys_content_edit = QTextEdit(self)
        self.sys_content_edit.setPlaceholderText("例如：你是{{char}}。你正在和{{user}}聊天。")
        sys_layout.addWidget(self.sys_content_edit)
        form_layout.addWidget(sys_group)

        # 角色名称编辑
        name_group = QGroupBox("角色名称（Name）", self)
        name_form = QFormLayout(name_group)
        self.user_name_edit = QLineEdit(self)
        self.assistant_name_edit = QLineEdit(self)
        name_form.addRow("User 名称：", self.user_name_edit)
        name_form.addRow("Assistant 名称：", self.assistant_name_edit)
        form_layout.addWidget(name_group)

        # 头像路径编辑
        avatar_group = QGroupBox("头像路径（Avatars）", self)
        avatar_form = QFormLayout(avatar_group)
        
        # User 头像
        self.user_avatar_edit = QLineEdit(self)
        self.user_avatar_btn = QPushButton("选择...", self)
        urow = QHBoxLayout()
        urow.addWidget(self.user_avatar_edit, 1)
        urow.addWidget(self.user_avatar_btn)
        avatar_form.addRow("User 头像路径：", self._wrap_layout(urow))
        
        # Assistant 头像
        self.assistant_avatar_edit = QLineEdit(self)
        self.assistant_avatar_btn = QPushButton("选择...", self)
        arow = QHBoxLayout()
        arow.addWidget(self.assistant_avatar_edit, 1)
        arow.addWidget(self.assistant_avatar_btn)
        avatar_form.addRow("Assistant 头像路径：", self._wrap_layout(arow))
        
        form_layout.addWidget(avatar_group)

        # 标题编辑与生成
        title_group = QGroupBox("会话标题（Title）", self)
        title_layout = QVBoxLayout(title_group)
        
        # 标题输入行
        title_row = QHBoxLayout()
        self.title_edit = QLineEdit(self)
        self.title_edit.setPlaceholderText("会话标题...")
        self.btn_gen_title_api = QPushButton("AI生成(调用API)", self)
        self.btn_gen_title_local = QPushButton("本地生成", self)
        title_row.addWidget(self.title_edit, 1)
        title_row.addWidget(self.btn_gen_title_api)
        title_row.addWidget(self.btn_gen_title_local)
        title_layout.addLayout(title_row)

        # 生成选项
        opt_row = QHBoxLayout()
        self.include_system_chk = QCheckBox("包含系统提示参与生成", self)
        self.maxlen_spin = QSpinBox(self)
        self.maxlen_spin.setRange(4, 100)
        self.maxlen_spin.setValue(20)
        opt_row.addWidget(self.include_system_chk)
        opt_row.addWidget(QLabel("最大长度：", self))
        opt_row.addWidget(self.maxlen_spin)
        opt_row.addStretch(1)
        title_layout.addLayout(opt_row)

        # 日志输出
        self.log_view = QPlainTextEdit(self)
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText("生成日志输出...")
        self.log_view.setMaximumHeight(120)
        title_layout.addWidget(self.log_view)

        form_layout.addWidget(title_group)
        form_layout.addStretch(1)  # 表单内容靠上
        
        self.tabs.addTab(form_page, "表单编辑")

        # ===== JSON 编辑页（仅编辑 history） =====
        json_page = QWidget(self)
        json_layout = QVBoxLayout(json_page)
        
        self.json_edit = QPlainTextEdit(self)
        self.json_edit.setPlaceholderText("在此直接编辑 chat history 的 JSON（仅消息列表，不包含 Session 元数据）...")
        json_layout.addWidget(self.json_edit)

        # JSON 操作按钮
        json_btn_row = QHBoxLayout()
        self.btn_json_apply_to_form = QPushButton("载入JSON到表单", self)
        self.btn_json_format = QPushButton("整理格式", self)
        self.btn_json_refresh_from_form = QPushButton("从表单刷新", self)
        json_btn_row.addWidget(self.btn_json_apply_to_form)
        json_btn_row.addWidget(self.btn_json_format)
        json_btn_row.addWidget(self.btn_json_refresh_from_form)
        json_btn_row.addStretch(1)
        json_layout.addLayout(json_btn_row)

        # JSON 状态标签
        status_row = QHBoxLayout()
        self.json_status_label = QLabel("就绪", self)
        self.json_status_label.setStyleSheet("color: #888;")
        status_row.addWidget(self.json_status_label)
        status_row.addStretch(1)
        json_layout.addLayout(status_row)

        self.tabs.addTab(json_page, "JSON编辑（History）")
        main_layout.addWidget(self.tabs)

        # ===== 底部操作按钮 =====
        action_row = QHBoxLayout()
        self.btn_save = QPushButton("保存并关闭", self)
        self.btn_reset = QPushButton("放弃修改并恢复", self)
        action_row.addStretch(1)
        action_row.addWidget(self.btn_reset)
        action_row.addWidget(self.btn_save)
        main_layout.addLayout(action_row)

    def _wrap_layout(self, layout: QHBoxLayout) -> QWidget:
        """辅助方法：将布局包装成 QWidget"""
        w = QWidget(self)
        w.setLayout(layout)
        return w

    # ---------- 信号连接 ----------
    def _connect_signals(self) -> None:
        # 表单字段变更 -> 更新 Session -> 更新 JSON 编辑器
        self.sys_content_edit.textChanged.connect(self._on_sys_content_changed)
        self.user_name_edit.textChanged.connect(self._on_user_name_changed)
        self.assistant_name_edit.textChanged.connect(self._on_assistant_name_changed)
        self.user_avatar_edit.textChanged.connect(self._on_user_avatar_changed)
        self.assistant_avatar_edit.textChanged.connect(self._on_assistant_avatar_changed)
        self.title_edit.textChanged.connect(self._on_title_changed)
        
        # 头像选择按钮
        self.user_avatar_btn.clicked.connect(lambda: self._pick_avatar(self.user_avatar_edit))
        self.assistant_avatar_btn.clicked.connect(lambda: self._pick_avatar(self.assistant_avatar_edit))

        # 标题生成
        self.btn_gen_title_api.clicked.connect(self._on_generate_title_api)
        self.btn_gen_title_local.clicked.connect(self._on_generate_title_local)

        # 保存/重置
        self.btn_save.clicked.connect(self._on_save_clicked)
        self.btn_reset.clicked.connect(self._on_reset_clicked)

        # JSON 编辑器
        self.btn_json_apply_to_form.clicked.connect(self._on_json_apply_to_form)
        self.btn_json_format.clicked.connect(self._on_json_format)
        self.btn_json_refresh_from_form.clicked.connect(self._update_json_editor_from_history)
        self.json_edit.textChanged.connect(self._on_json_text_changed)

        # TitleGenerator 信号
        self._title_generator.title_generated.connect(self._on_title_generated)
        self._title_generator.log.connect(self._on_log_signal)
        self._title_generator.warning.connect(lambda s: self._append_log(s, "warn"))
        self._title_generator.error.connect(self._on_error_signal)

    # ---------- 数据访问辅助 ----------
    def _ensure_system_message(self) -> None:
        """确保 history 第一条是 system 消息"""
        if not self._session.history:
            self._session.history = [{
                "role": "system",
                "content": "",
                "info": {"id": "system_prompt"}
            }]
        elif self._session.history[0].get("role") != "system":
            # 在开头插入 system 消息
            self._session.history.insert(0, {
                "role": "system",
                "content": "",
                "info": {"id": "system_prompt"}
            })

    def _get_system_message(self) -> Dict[str, Any]:
        """获取第一条 system 消息，如果不存在则创建"""
        self._ensure_system_message()
        return self._session.history[0]

    # ---------- 表单与数据同步 ----------
    def _load_history_to_form(self) -> None:
        """从 Session 加载数据到表单"""
        self._syncing = True
        
        # System content 从 history[0] 读取
        sys_msg = self._get_system_message()
        self.sys_content_edit.setPlainText(sys_msg.get("content", ""))
        
        # 元数据从 Session 顶层属性读取
        self.user_name_edit.setText(self._session.name.get("user", ""))
        self.assistant_name_edit.setText(self._session.name.get("assistant", ""))
        self.user_avatar_edit.setText(self._session.avatars.get("user", ""))
        self.assistant_avatar_edit.setText(self._session.avatars.get("assistant", ""))
        self.title_edit.setText(self._session.title)
        
        self._syncing = False

    def _update_json_editor_from_history(self) -> None:
        """将 history 列表同步到 JSON 编辑器"""
        if self._syncing:
            return
            
        self._syncing = True
        try:
            # 仅序列化 history 列表
            text = json.dumps(self._session.history, ensure_ascii=False, indent=2)
            self.json_edit.setPlainText(text)
            self.json_status_label.setText("JSON 已更新")
            self.json_status_label.setStyleSheet("color: #888;")
            self._last_applied_json_text = text
        finally:
            self._syncing = False

    def _apply_form_to_history(self) -> None:
        """将表单数据应用到 Session 并更新 JSON 编辑器"""
        # 此方法在旧代码中用于手动同步，现在实时同步已处理
        # 但保留用于确保最终一致性
        self._update_json_editor_from_history()

    # ---------- 表单事件处理 ----------
    def _on_sys_content_changed(self) -> None:
        """System content 变更"""
        if self._syncing:
            return
        sys_msg = self._get_system_message()
        sys_msg["content"] = self.sys_content_edit.toPlainText()
        self._update_json_editor_from_history()

    def _on_user_name_changed(self, text: str) -> None:
        """User 名称变更"""
        if self._syncing:
            return
        self._session.name["user"] = text
        # 不触发 JSON 更新，因为 name 不在 history 中

    def _on_assistant_name_changed(self, text: str) -> None:
        """Assistant 名称变更"""
        if self._syncing:
            return
        self._session.name["assistant"] = text

    def _on_user_avatar_changed(self, text: str) -> None:
        """User 头像变更"""
        if self._syncing:
            return
        self._session.avatars["user"] = text

    def _on_assistant_avatar_changed(self, text: str) -> None:
        """Assistant 头像变更"""
        if self._syncing:
            return
        self._session.avatars["assistant"] = text

    def _on_title_changed(self, text: str) -> None:
        """标题变更"""
        if self._syncing:
            return
        self._session.title = text

    def _pick_avatar(self, target_edit: QLineEdit) -> None:
        """选择头像文件"""
        path, _ = QFileDialog.getOpenFileName(
            self, 
            "选择头像图片", 
            "", 
            "图像文件 (*.png *.jpg *.jpeg *.bmp *.gif);;所有文件 (*.*)"
        )
        if path:
            target_edit.setText(path)

    # ---------- 标题生成 ----------
    def _on_generate_title_api(self) -> None:
        """调用 API 生成标题"""
        self._set_generating(True)
        self._current_task_id = str(uuid.uuid4())
        
        # 使用 shallow_history（list 的浅拷贝）或深拷贝取决于 TitleGenerator 是否会修改数据
        self._title_generator.create_chat_title(
            chathistory=copy.deepcopy(self._session.history),  # 防止生成过程中修改当前编辑内容
            task_id=self._current_task_id,
            use_local=False,
            max_length=int(self.maxlen_spin.value()),
            include_system_prompt=self.include_system_chk.isChecked()
        )

    def _on_generate_title_local(self) -> None:
        """本地生成标题"""
        title = self._title_generator.generate_title_from_history_local(
            chathistory=copy.deepcopy(self._session.history),
            max_length=int(self.maxlen_spin.value())
        )
        if not isinstance(title, str) or not title.strip():
            self._append_log("[本地] 生成标题失败：未找到合适的消息。", "warn")
            return
        
        self._append_log(f"[本地] 生成标题：{title}", "log")
        self._syncing = True
        self.title_edit.setText(title)
        self._syncing = False
        self._on_title_changed(title)

    def _on_title_generated(self, task_id: str, title: str) -> None:
        """标题生成完成的回调"""
        if self._current_task_id and task_id != self._current_task_id:
            return
            
        text = (title or "").strip()
        self._syncing = True
        self.title_edit.setText(text)
        self._syncing = False
        self._on_title_changed(text)  # 更新 session.title
        self._set_generating(False)
        self._current_task_id = None

    def _set_generating(self, generating: bool) -> None:
        """设置生成状态"""
        self._gen_running = generating
        self.btn_gen_title_api.setEnabled(not generating)
        self.btn_gen_title_local.setEnabled(not generating)
        self._append_log("正在生成标题..." if generating else "标题生成完成。", "log")

    # ---------- JSON 编辑 ----------
    def _on_json_apply_to_form(self) -> None:
        """手动触发 JSON 应用到表单"""
        self._apply_json_editor_to_form_auto()

    def _on_json_format(self) -> None:
        """格式化 JSON"""
        try:
            text = self.json_edit.toPlainText()
            data = json.loads(text)
            self._syncing = True
            self.json_edit.setPlainText(json.dumps(data, ensure_ascii=False, indent=2))
            self._syncing = False
            self.json_status_label.setText("JSON 已格式化")
            self.json_status_label.setStyleSheet("color: #5cb85c;")
        except Exception as e:
            self.json_status_label.setText(f"格式化失败：{e}")
            self.json_status_label.setStyleSheet("color: #d9534f;")

    def _on_json_text_changed(self) -> None:
        """JSON 文本变更，启动防抖定时器"""
        if self._syncing:
            return
            
        text = self.json_edit.toPlainText().strip()
        if not text:
            self.json_status_label.setText("JSON 为空")
            self.json_status_label.setStyleSheet("color: #d9534f;")
            self._json_debounce_timer.start()
            return

        self.json_status_label.setText("正在编辑 JSON ...")
        self.json_status_label.setStyleSheet("color: #888;")
        self._json_debounce_timer.start()

    def _apply_json_editor_to_form_auto(self) -> None:
        """防抖后自动应用 JSON 到表单"""
        if self._syncing:
            return
            
        text = self.json_edit.toPlainText().strip()
        if not text:
            self.json_status_label.setText("JSON 为空")
            self.json_status_label.setStyleSheet("color: #d9534f;")
            return

        # 避免重复应用相同内容
        if text == self._last_applied_json_text:
            self.json_status_label.setText("JSON 格式良好")
            self.json_status_label.setStyleSheet("color: #5cb85c;")
            return

        try:
            data = json.loads(text)
            if not isinstance(data, list):
                raise ValueError("JSON 根应为列表(list)")
                
            # 验证基本结构（可选：检查每个 item 是否有 role）
            
        except Exception as e:
            self.json_status_label.setText(f"JSON 非法：{e}")
            self.json_status_label.setStyleSheet("color: #d9534f;")
            return

        # 应用到 Session
        self._session.history = data
        self._ensure_system_message()  # 确保 system 消息存在
        
        # 回填表单（这会更新 system content，但不会覆盖 name/avatar/title）
        self._load_history_to_form()
        
        self.json_status_label.setText("JSON 已应用到表单")
        self.json_status_label.setStyleSheet("color: #5cb85c;")
        self._last_applied_json_text = text

    # ---------- 保存与重置 ----------
    def _on_save_clicked(self) -> None:
        """保存并关闭"""
        # 确保当前 JSON 编辑器内容已应用（如果正在编辑 JSON）
        if self.tabs.currentIndex() == 1:  # JSON 编辑页是第 2 个 tab（索引 1）
            self._apply_json_editor_to_form_auto()
        
        self._apply_form_to_history()
        self.editCompleted.emit(copy.deepcopy(self._session))
        self._append_log("已保存并通过 editCompleted 发出。", "log")
        self.close()
        self.deleteLater()

    def _on_reset_clicked(self) -> None:
        """重置到初始状态"""
        self._session = copy.deepcopy(self._original_session)
        self._load_history_to_form()
        self._update_json_editor_from_history()
        self._append_log("已恢复到初始内容。", "warn")

    # ---------- 日志 ----------
    def _append_log(self, text: str, level: str = "log") -> None:
        """追加日志"""
        prefix = {"log": "", "warn": "[警告] ", "error": "[错误] "}.get(level, "")
        self.log_view.appendPlainText(prefix + text)

    def _on_log_signal(self, s: str) -> None:
        """TitleGenerator 日志信号"""
        self._append_log(s, "log")
        if "Title generation error" in s or "error" in s.lower():
            if self._gen_running:
                self._append_log("检测到 API 错误，已停止等待。", "warn")
                self._set_generating(False)
                self._current_task_id = None

    def _on_error_signal(self, s: str) -> None:
        """TitleGenerator 错误信号"""
        self._append_log(s, "error")
        if self._gen_running:
            self._set_generating(False)
            self._current_task_id = None
