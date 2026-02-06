import json
import uuid
import copy
from typing import Any, Dict, List, Optional, Tuple

from PyQt6.QtCore import *
from PyQt6.QtGui import *
from PyQt6.QtWidgets import *

from core.session.chat_history_manager import TitleGenerator

class ChatHistoryEditor(QWidget):
    # 定义编辑完成的信号，传递新的聊天历史
    editCompleted = pyqtSignal(list)

    def __init__(self, title_generator: TitleGenerator, chathistory: List[Dict[str, Any]], parent: Optional[QWidget] = None):
        super().__init__(parent)
        self.setWindowTitle("聊天历史编辑器")
        self._title_generator: TitleGenerator = title_generator
        self._original_history: List[Dict[str, Any]] = copy.deepcopy(chathistory or [])
        self._history: List[Dict[str, Any]] = copy.deepcopy(chathistory or [])
        self._syncing: bool = False
        self._current_task_id: Optional[str] = None
        self._gen_running: bool = False

        self._build_ui()
        self._connect_signals()
        self._get_or_create_system_item()  # 确保结构完整
        self._load_history_to_form()
        self._update_json_editor_from_history()

        self._last_applied_json_text: str = self.json_edit.toPlainText()
        self._json_debounce_timer = QTimer(self)
        self._json_debounce_timer.setSingleShot(True)
        self._json_debounce_timer.setInterval(50)
        self._json_debounce_timer.timeout.connect(self._apply_json_editor_to_form_auto)

    # ---------- UI ----------
    def _build_ui(self) -> None:
        screen_geometry = QApplication.primaryScreen().availableGeometry()
        
        width = int(screen_geometry.width() * 0.6)
        height = int(screen_geometry.height() * 0.6)
        
        left = (screen_geometry.width() - width) // 2
        top = (screen_geometry.height() - height) // 2
        
        self.setGeometry(left, top, width, height)

        main_layout = QVBoxLayout(self)
        
        self.tabs = QTabWidget(self)

        # 表单编辑页
        form_page = QWidget(self)
        form_layout = QVBoxLayout(form_page)

        sys_group = QGroupBox("系统提示（system.content）", self)
        sys_layout = QVBoxLayout(sys_group)
        self.sys_content_edit = QTextEdit(self)
        self.sys_content_edit.setPlaceholderText("例如：你是{{char}}。你正在和{{user}}聊天。")
        sys_layout.addWidget(self.sys_content_edit)
        form_layout.addWidget(sys_group)

        name_group = QGroupBox("角色名称（info.name）", self)
        name_form = QFormLayout(name_group)
        self.user_name_edit = QLineEdit(self)
        self.assistant_name_edit = QLineEdit(self)
        name_form.addRow("User 名称：", self.user_name_edit)
        name_form.addRow("Assistant 名称：", self.assistant_name_edit)
        form_layout.addWidget(name_group)

        avatar_group = QGroupBox("头像路径（info.avatar）", self)
        avatar_form = QFormLayout(avatar_group)
        # user avatar
        self.user_avatar_edit = QLineEdit(self)
        self.user_avatar_btn = QPushButton("选择...", self)
        urow = QHBoxLayout()
        urow.addWidget(self.user_avatar_edit, 1)
        urow.addWidget(self.user_avatar_btn)
        # assistant avatar
        self.assistant_avatar_edit = QLineEdit(self)
        self.assistant_avatar_btn = QPushButton("选择...", self)
        arow = QHBoxLayout()
        arow.addWidget(self.assistant_avatar_edit, 1)
        arow.addWidget(self.assistant_avatar_btn)
        # add rows
        avatar_form.addRow("User 头像路径：", self._wrap_row(urow))
        avatar_form.addRow("Assistant 头像路径：", self._wrap_row(arow))
        form_layout.addWidget(avatar_group)

        # 标题编辑与生成
        title_group = QGroupBox("会话标题（info.title）", self)
        title_layout = QVBoxLayout(title_group)
        title_row = QHBoxLayout()
        self.title_edit = QLineEdit(self)
        self.title_edit.setPlaceholderText("会话标题...")
        self.btn_gen_title_api = QPushButton("AI生成(调用API)", self)
        self.btn_gen_title_local = QPushButton("本地生成", self)
        title_row.addWidget(self.title_edit, 1)
        title_row.addWidget(self.btn_gen_title_api)
        title_row.addWidget(self.btn_gen_title_local)
        title_layout.addLayout(title_row)

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

        # 日志
        self.log_view = QPlainTextEdit(self)
        self.log_view.setReadOnly(True)
        self.log_view.setPlaceholderText("生成日志输出...")
        self.log_view.setMaximumHeight(120)
        title_layout.addWidget(self.log_view)

        form_layout.addWidget(title_group)

        self.tabs.addTab(form_page, "表单编辑")

        # JSON 编辑页
        json_page = QWidget(self)
        json_layout = QVBoxLayout(json_page)
        self.json_edit = QPlainTextEdit(self)
        self.json_edit.setPlaceholderText("在此直接编辑 chathistory 的 JSON ...")
        json_layout.addWidget(self.json_edit)

        json_btn_row = QHBoxLayout()
        self.btn_json_apply_to_form = QPushButton("载入JSON到表单", self)
        self.btn_json_format = QPushButton("整理格式", self)
        self.btn_json_refresh_from_form = QPushButton("从表单刷新更改", self)
        json_btn_row.addWidget(self.btn_json_apply_to_form)
        json_btn_row.addWidget(self.btn_json_format)
        json_btn_row.addWidget(self.btn_json_refresh_from_form)
        json_btn_row.addStretch(1)
        json_layout.addLayout(json_btn_row)

        status_row = QHBoxLayout()
        self.json_status_label = QLabel("就绪", self)
        self.json_status_label.setStyleSheet("color: #888;")
        status_row.addWidget(self.json_status_label)
        status_row.addStretch(1)
        json_layout.addLayout(status_row)

        self.tabs.addTab(json_page, "JSON编辑")
        main_layout.addWidget(self.tabs)

        # 操作
        action_row = QHBoxLayout()
        self.btn_save = QPushButton("保存并关闭", self)
        self.btn_reset = QPushButton("放弃修改并恢复", self)
        action_row.addStretch(1)
        action_row.addWidget(self.btn_reset)
        action_row.addWidget(self.btn_save)
        main_layout.addLayout(action_row)

    def _wrap_row(self, layout: QHBoxLayout) -> QWidget:
        w = QWidget(self)
        w.setLayout(layout)
        return w

    # ---------- 信号连接 ----------
    def _connect_signals(self) -> None:
        # 表单 -> 数据
        self.sys_content_edit.textChanged.connect(self._on_sys_content_changed)
        self.user_name_edit.textChanged.connect(self._on_user_name_changed)
        self.assistant_name_edit.textChanged.connect(self._on_assistant_name_changed)
        self.user_avatar_edit.textChanged.connect(self._on_user_avatar_changed)
        self.assistant_avatar_edit.textChanged.connect(self._on_assistant_avatar_changed)
        self.title_edit.textChanged.connect(self._on_title_changed)
        self.user_avatar_btn.clicked.connect(lambda: self._pick_avatar(self.user_avatar_edit))
        self.assistant_avatar_btn.clicked.connect(lambda: self._pick_avatar(self.assistant_avatar_edit))

        # 标题生成
        self.btn_gen_title_api.clicked.connect(self._on_generate_title_api)
        self.btn_gen_title_local.clicked.connect(self._on_generate_title_local)

        # 操作
        self.btn_save.clicked.connect(self._on_save_clicked)
        self.btn_reset.clicked.connect(self._on_reset_clicked)

        # JSON 编辑
        self.btn_json_apply_to_form.clicked.connect(self._on_json_apply_to_form)
        self.btn_json_format.clicked.connect(self._on_json_format)
        self.btn_json_refresh_from_form.clicked.connect(self._update_json_editor_from_history)
        self.json_edit.textChanged.connect(self._on_json_text_changed)

        # TitleGenerator 日志/结果
        # 注意：title_generated 的参数顺序为 (task_id, title)
        self._title_generator.title_generated.connect(self._on_title_generated)
        self._title_generator.log_signal.connect(self._on_log_signal)
        self._title_generator.warning_signal.connect(lambda s: self._append_log(s, "warn"))
        self._title_generator.error_signal.connect(self._on_error_signal)

    # ---------- 数据与UI同步 ----------
    def _get_or_create_system_item(self) -> Tuple[int, Dict[str, Any]]:
        idx = -1
        sys_item = None
        for i, item in enumerate(self._history):
            if isinstance(item, dict) and item.get("role") == "system":
                idx = i
                sys_item = item
                break
        # system消息必定存在，原来的重组系统消息逻辑现在已经剔除
        return idx, sys_item

    def _load_history_to_form(self) -> None:
        self._syncing = True
        _, sys_item = self._get_or_create_system_item()
        info:dict    = sys_item.get("info", {})
        name:dict    = info.get("name", {})
        avatar:dict  = info.get("avatar", {})

        self.sys_content_edit.setPlainText(sys_item.get("content", "") or "")
        self.user_name_edit.setText(name.get("user", "") or "")
        self.assistant_name_edit.setText(name.get("assistant", "") or "")
        self.user_avatar_edit.setText(avatar.get("user", "") or "")
        self.assistant_avatar_edit.setText(avatar.get("assistant", "") or "")
        self.title_edit.setText(info.get("title", "") or "")
        self._syncing = False

    def _update_json_editor_from_history(self) -> None:
        if self._syncing:
            return
        self._syncing = True
        try:
            text = json.dumps(self._history, ensure_ascii=False, indent=2)
            self.json_edit.setPlainText(text)
            self.json_status_label.setText("JSON 已更新")
            self.json_status_label.setStyleSheet("color: #888;")
            self._last_applied_json_text = text
        finally:
            self._syncing = False

    def _apply_form_to_history(self) -> None:
        self._update_json_editor_from_history()

    # ---------- 表单事件 ----------
    def _on_sys_content_changed(self) -> None:
        if self._syncing:
            return
        _, sys_item = self._get_or_create_system_item()
        sys_item["content"] = self.sys_content_edit.toPlainText()
        self._update_json_editor_from_history()

    def _on_user_name_changed(self, text: str) -> None:
        if self._syncing:
            return
        _, sys_item = self._get_or_create_system_item()
        sys_item["info"]["name"]["user"] = text
        self._update_json_editor_from_history()

    def _on_assistant_name_changed(self, text: str) -> None:
        if self._syncing:
            return
        _, sys_item = self._get_or_create_system_item()
        sys_item["info"]["name"]["assistant"] = text
        self._update_json_editor_from_history()

    def _on_user_avatar_changed(self, text: str) -> None:
        if self._syncing:
            return
        _, sys_item = self._get_or_create_system_item()
        sys_item["info"]["avatar"]["user"] = text
        self._update_json_editor_from_history()

    def _on_assistant_avatar_changed(self, text: str) -> None:
        if self._syncing:
            return
        _, sys_item = self._get_or_create_system_item()
        sys_item["info"]["avatar"]["assistant"] = text
        self._update_json_editor_from_history()

    def _on_title_changed(self, text: str) -> None:
        if self._syncing:
            return
        _, sys_item = self._get_or_create_system_item()
        sys_item["info"]["title"] = text
        self._update_json_editor_from_history()

    def _pick_avatar(self, target_edit: QLineEdit) -> None:
        path, _ = QFileDialog.getOpenFileName(self, "选择头像图片", "", "图像文件 (*.png *.jpg *.jpeg *.bmp *.gif);;所有文件 (*.*)")
        if path:
            target_edit.setText(path)

    # ---------- 标题生成 ----------
    def _on_generate_title_api(self) -> None:
        self._set_generating(True)
        self._current_task_id = str(uuid.uuid4())
        self._title_generator.create_chat_title(
            chathistory=copy.deepcopy(self._history),
            task_id=self._current_task_id,
            use_local=False,
            max_length=int(self.maxlen_spin.value()),
            include_system_prompt=self.include_system_chk.isChecked()
        )

    def _on_generate_title_local(self) -> None:
        title = self._title_generator.generate_title_from_history_local(
            chathistory=copy.deepcopy(self._history),
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
        # 注意参数顺序：(task_id, title)
        if self._current_task_id and task_id != self._current_task_id:
            return
        text = (title or "").strip()
        self._syncing = True
        self.title_edit.setText(text)
        self._syncing = False
        self._on_title_changed(text)
        self._set_generating(False)
        self._current_task_id = None

    def _set_generating(self, generating: bool) -> None:
        self._gen_running = generating
        self.btn_gen_title_api.setEnabled(not generating)
        self.btn_gen_title_local.setEnabled(not generating)
        self._append_log("正在生成标题..." if generating else "标题生成完成。", "log")

    # ---------- JSON 编辑 ----------
    def _on_json_apply_to_form(self) -> None:
        self._apply_json_editor_to_form_auto()

    def _on_json_format(self) -> None:
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
        if self._syncing:
            return
        text = self.json_edit.toPlainText().strip()
        if not text:
            self.json_status_label.setText("JSON 为空")
            self.json_status_label.setStyleSheet("color: #d9534f;")
            # 仍然启用定时器（若用户继续输入会重启），也可以选择直接 return
            self._json_debounce_timer.start()
            return

        # 不立即解析，启动/重启防抖定时器
        self.json_status_label.setText("正在编辑 JSON ...")
        self.json_status_label.setStyleSheet("color: #888;")
        self._json_debounce_timer.start()

    def _apply_json_editor_to_form_auto(self) -> None:
        if self._syncing:
            return
        text = self.json_edit.toPlainText().strip()
        if not text:
            self.json_status_label.setText("JSON 为空")
            self.json_status_label.setStyleSheet("color: #d9534f;")
            return

        # 避免重复对相同文本应用
        if text == self._last_applied_json_text:
            # 仍可在此更新“格式良好”状态（上次已成功）
            self.json_status_label.setText("JSON 格式良好")
            self.json_status_label.setStyleSheet("color: #5cb85c;")
            return

        try:
            data = json.loads(text)
            if not isinstance(data, list):
                raise ValueError("JSON 根应为列表(list)。")
        except Exception as e:
            self.json_status_label.setText(f"JSON 非法：{e}")
            self.json_status_label.setStyleSheet("color: #d9534f;")
            return

        # 应用到模型
        self._history = data
        self._get_or_create_system_item()

        # 回填表单（_load_history_to_form 内部已设置 _syncing 防止回流）
        self._load_history_to_form()

        # 状态
        self.json_status_label.setText("JSON 已应用到表单")
        self.json_status_label.setStyleSheet("color: #5cb85c;")

        # 记录已应用文本，用于去重
        self._last_applied_json_text = text
    # ---------- 保存/重置 ----------
    def _on_save_clicked(self) -> None:
        self._apply_form_to_history()
        self.editCompleted.emit(copy.deepcopy(self._history))
        self._append_log("已保存并通过 editCompleted 发出。", "log")
        self.close()
        self.deleteLater()

    def _on_reset_clicked(self) -> None:
        self._history = copy.deepcopy(self._original_history)
        self._load_history_to_form()
        self._update_json_editor_from_history()
        self._append_log("已恢复到初始内容。", "warn")

    # ---------- 日志 ----------
    def _append_log(self, text: str, level: str = "log") -> None:
        prefix = {"log": "", "warn": "[警告] ", "error": "[错误] "}.get(level, "")
        self.log_view.appendPlainText(prefix + text)

    def _on_log_signal(self, s: str) -> None:
        self._append_log(s, "log")
        if "Title generation error" in s or "error" in s.lower():
            if self._gen_running:
                self._append_log("检测到 API 错误，已停止等待。", "warn")
                self._set_generating(False)
                self._current_task_id = None

    def _on_error_signal(self, s: str) -> None:
        self._append_log(s, "error")
        if self._gen_running:
            self._set_generating(False)
            self._current_task_id = None
