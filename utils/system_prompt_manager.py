import os
from PyQt5 import QtCore, QtWidgets,QtGui
from dataclasses import dataclass, field
from typing import List, Dict, Any
import json
from typing import List, Tuple, Optional
import hashlib
from utils.tool_core import FunctionsSelectorWidget

@dataclass
class SystemPromptPreset:
    name: str = ""
    content: str = ""
    post_history: str = ""
    tools: List[str] = field(default_factory=list)
    info: Dict[str, Any] = field(default_factory=dict)
    avatars: Dict[str, str] = field(default_factory=dict)

    @classmethod
    def from_json(cls, data: Dict[str, Any]):
        info = data.get("info", {}) or {}
        # 兼容多处字段
        tools = info.get("tools", [])
        avatars = info.get("avatar") or data.get("avatar") or {}
        return cls(
            name=data.get("name", ""),
            content=data.get("content", ""),
            post_history=data.get("post_history", ""),
            tools=tools or [],
            info=info,
            avatars={"user": avatars.get("user", ""), "assistant": avatars.get("assistant", "")},
        )

    def to_json(self) -> Dict[str, Any]:
        info = dict(self.info or {})
        info.setdefault("id", "system_prompt")
        # 确保默认中文名
        names = info.get("name") or {}
        info["name"] = {
            "user": names.get("user", ""),
            "assistant": names.get("assistant", "")
        }
        # 工具与头像
        info["tools"] = list(self.tools or [])
        info["avatar"] = {
            "user": (self.avatars or {}).get("user", ""),
            "assistant": (self.avatars or {}).get("assistant", "")
        }
        return {
            "name": self.name,
            "content": self.content,
            "post_history": self.post_history,
            "info": info
        }

class SystemPromptStore:
    def __init__(self, folder_path: str = "utils/system_prompt_presets"):
        self.folder_path = folder_path
        os.makedirs(self.folder_path, exist_ok=True)

    def _full_path(self, file_name: str) -> str:
        if not file_name.endswith(".json"):
            file_name += ".json"
        return os.path.join(self.folder_path, file_name)

    def list_files(self) -> List[str]:
        try:
            with os.scandir(self.folder_path) as it:
                return [e.path for e in it if e.is_file() and e.name.endswith(".json")]
        except FileNotFoundError:
            os.makedirs(self.folder_path, exist_ok=True)
            return []

    def list_presets(self) -> List[Tuple[str, SystemPromptPreset]]:
        out = []
        for path in self.list_files():
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                preset = SystemPromptPreset.from_json(data)
                out.append((path, preset))
            except Exception:
                # 跳过损坏文件
                continue
        return out

    def read(self, file_path: str) -> Optional[SystemPromptPreset]:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                return SystemPromptPreset.from_json(json.load(f))
        except Exception:
            return None

    def save(self, file_path: str, preset: SystemPromptPreset) -> bool:
        try:
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(preset.to_json(), f, indent=2, ensure_ascii=False)
            return True
        except Exception:
            return False

    def create(self, file_name: str, preset: SystemPromptPreset) -> Optional[str]:
        path = self._full_path(file_name)
        ok = self.save(path, preset)
        return path if ok else None

    def delete(self, file_path: str) -> bool:
        try:
            os.remove(file_path)
            return True
        except Exception:
            return False

    def current_dialog_path(self, base_name: str = "当前对话") -> str:
        return self._full_path(base_name)

class SystemPromptManager(QtWidgets.QWidget):
    update_system_prompt = QtCore.pyqtSignal(str)
    update_tool_selection = QtCore.pyqtSignal(list)
    update_preset = QtCore.pyqtSignal(dict)

    def __init__(self, store=None, parent=None):
        super().__init__(parent)
        self.setObjectName("systemPromptEditor")
        self.setWindowTitle("system prompt")
        screen_geometry = QtWidgets.QApplication.primaryScreen().availableGeometry()
        
        width = int(screen_geometry.width() * 0.8)
        height = int(screen_geometry.height() * 0.8)
        
        left = (screen_geometry.width() - width) // 2
        top = (screen_geometry.height() - height) // 2
        
        self.setGeometry(left, top, width, height)

        # 外部依赖（需由外部提供）
        if store is None:
            store = SystemPromptStore()
        self.store = store

        # 内部状态
        self._ignore_selection = False
        self.current_file: Optional[str] = None
        self.is_modified = False
        self.ignore_changes = False
        self.default_current_filename = "当前对话"

        # 默认名
        self.name_user = ""
        self.name_ai = ""

        # 头像路径（隐藏，不再显示路径输入框）
        self.avatar_user_path: str = ""
        self.avatar_ai_path: str = ""

        # ===== UI =====
        main_grid = QtWidgets.QGridLayout(self)
        self.splitter = QtWidgets.QSplitter(self)
        self.splitter.setChildrenCollapsible(False)
        main_grid.addWidget(self.splitter, 0, 0, 1, 1)

        # 左侧：预设列表 + 搜索 + 底部新建/删除
        left_widget = QtWidgets.QWidget()
        left_grid = QtWidgets.QGridLayout(left_widget)
        
        # 预设列表标签
        left_grid.addWidget(QtWidgets.QLabel("预设列表"), 0, 0, 1, 1)

        # 搜索框
        self.search_edit = QtWidgets.QLineEdit()
        self.search_edit.setPlaceholderText("搜索预设…")
        self.search_edit.textChanged.connect(self._filter_list)
        left_grid.addWidget(self.search_edit, 1, 0, 1, 1)

        # 列表控件
        self.list_widget = QtWidgets.QListWidget()
        self.list_widget.setAlternatingRowColors(True)
        self.list_widget.setUniformItemSizes(True)
        self.list_widget.setSelectionMode(QtWidgets.QAbstractItemView.SingleSelection)
        self.list_widget.setMinimumWidth(220)
        self.list_widget.itemSelectionChanged.connect(self._on_file_selected)
        left_grid.addWidget(self.list_widget, 2, 0, 1, 1)

        # 左侧底部：新建 / 删除
        self.btn_new = QtWidgets.QPushButton("新建配置")
        self.btn_new.clicked.connect(self._create_new_config)
        left_grid.addWidget(self.btn_new, 3, 0, 1, 1)

        self.btn_delete = QtWidgets.QPushButton("删除配置")
        self.btn_delete.clicked.connect(self._delete_current_config)
        left_grid.addWidget(self.btn_delete, 4, 0, 1, 1)

        # 设置左侧布局的拉伸因子
        left_grid.setRowStretch(2, 1)  # 列表控件可拉伸

        # 右侧：名称 + 中部分栏（左：内容；右：头像/工具/代称）+ 底部保存/覆盖
        right_widget = QtWidgets.QWidget()
        right_grid = QtWidgets.QGridLayout(right_widget)

        # 顶部：配置名称
        right_grid.addWidget(QtWidgets.QLabel("配置名称:"), 0, 0, 1, 1)
        self.name_edit = QtWidgets.QLineEdit()
        self.name_edit.setPlaceholderText("命名预设")
        self.name_edit.textChanged.connect(self._on_content_changed)
        right_grid.addWidget(self.name_edit, 0, 1, 1, 1)

        # 中部
        self.center_widget = QtWidgets.QWidget()
        self.center_layout = QtWidgets.QGridLayout(self.center_widget)

        # 左：配置内容
        content_wrap = QtWidgets.QWidget()
        content_grid = QtWidgets.QGridLayout(content_wrap)
        content_grid.addWidget(QtWidgets.QLabel("配置内容:"), 0, 0, 1, 1)

        self.content_edit = QtWidgets.QTextEdit()
        self.content_edit.setPlaceholderText(r"在此编写系统提示。{{user}} 表示用户，{{char}} 表示助手")
        self.content_edit.textChanged.connect(self._on_content_changed)
        try:
            fixed = QtGui.QFontDatabase.systemFont(QtGui.QFontDatabase.FixedFont)
            self.content_edit.setFont(fixed)
        except Exception:
            pass

        content_grid.addWidget(self.content_edit, 1, 0, 1, 1)
        content_grid.setRowStretch(1, 1)  # 内容编辑框可拉伸
        self.center_layout.addWidget(content_wrap, 0, 0, 1, 1)

        # 右：侧栏（头像选择在顶部 -> 工具选择 -> 代称），整体放进滚动区
        side_panel = QtWidgets.QWidget()
        side_grid = QtWidgets.QGridLayout(side_panel)
        side_grid.setContentsMargins(0, 0, 0, 0)

        # 顶部：头像选择（不显示路径，仅按钮与预览）
        avatars_group = QtWidgets.QGroupBox("头像选择")
        avatars_grid = QtWidgets.QGridLayout(avatars_group)
        
        # 用户头像
        self.avatar_user_preview = QtWidgets.QLabel()
        self.avatar_user_preview.setFixedSize(40, 40)
        self.avatar_user_preview.setFrameShape(QtWidgets.QFrame.StyledPanel)
        avatars_grid.addWidget(self.avatar_user_preview, 0, 0, 1, 1)
        
        self.avatar_user_btn = QtWidgets.QPushButton("选择用户头像")
        self.avatar_user_btn.clicked.connect(lambda: self._pick_avatar("user"))
        avatars_grid.addWidget(self.avatar_user_btn, 0, 1, 1, 1)
        
        # 助手头像
        self.avatar_ai_preview = QtWidgets.QLabel()
        self.avatar_ai_preview.setFixedSize(40, 40)
        self.avatar_ai_preview.setFrameShape(QtWidgets.QFrame.StyledPanel)
        avatars_grid.addWidget(self.avatar_ai_preview, 1, 0, 1, 1)
        
        self.avatar_ai_btn = QtWidgets.QPushButton("选择AI头像")
        self.avatar_ai_btn.clicked.connect(lambda: self._pick_avatar("assistant"))
        avatars_grid.addWidget(self.avatar_ai_btn, 1, 1, 1, 1)
        
        side_grid.addWidget(avatars_group, 0, 0, 1, 1)

        # 工具选择
        tools_group = QtWidgets.QGroupBox("工具选择")
        tools_grid = QtWidgets.QGridLayout(tools_group)
        self.tools_widget = FunctionsSelectorWidget(self)
        self.tools_widget.selectionChanged.connect(lambda _: self._on_content_changed())
        tools_grid.addWidget(self.tools_widget, 0, 0, 1, 1)
        side_grid.addWidget(tools_group, 2, 0, 1, 1)

        # 工具选择下方：代称
        alias_group = QtWidgets.QGroupBox("代称")
        alias_grid = QtWidgets.QGridLayout(alias_group)
        alias_grid.addWidget(QtWidgets.QLabel(r"用户代称 {{user}} ="), 0, 0, 1, 1)
        self.name_user_edit = QtWidgets.QLineEdit()
        self.name_user_edit.setText(self.name_user)
        self.name_user_edit.textChanged.connect(self._on_user_name_changed)
        alias_grid.addWidget(self.name_user_edit, 1, 0, 1, 1)

        alias_grid.addWidget(QtWidgets.QLabel(r"AI 代称 {{char}} ="), 2, 0, 1, 1)
        self.name_ai_edit = QtWidgets.QLineEdit()
        self.name_ai_edit.setText(self.name_ai)
        self.name_ai_edit.textChanged.connect(self._on_ai_name_changed)
        alias_grid.addWidget(self.name_ai_edit, 3, 0, 1, 1)
        side_grid.addWidget(alias_group, 1, 0, 1, 1)

        # 设置侧边栏的拉伸因子
        side_grid.setRowStretch(2, 1)  # 工具选择可拉伸

        self.center_layout.addWidget(side_panel, 0, 1, 1, 1)

        self.center_layout.setColumnStretch(0, 3)
        self.center_layout.setColumnStretch(1, 0)
        right_grid.addWidget(self.center_widget, 1, 0, 1, 2)

        # 底部：保存/覆盖系统提示（右下角）
        bottom_widget = QtWidgets.QWidget()
        bottom_grid = QtWidgets.QGridLayout(bottom_widget)
        spacer=QtWidgets.QWidget()
        spacer.setSizePolicy(QtWidgets.QSizePolicy.Expanding,QtWidgets.QSizePolicy.Preferred)
        bottom_grid.addWidget(spacer, 2, 0, 1, 1)
        self.btn_save = QtWidgets.QPushButton("保存更改")
        self.btn_save.clicked.connect(self._save_current_config)
        self.btn_save.setEnabled(False)
        bottom_grid.addWidget(self.btn_save, 2, 1, 1, 1)

        self.btn_send = QtWidgets.QPushButton("覆盖系统提示")
        self.btn_send.clicked.connect(self._send_current)
        bottom_grid.addWidget(self.btn_send, 2, 2, 1, 1)

        right_grid.addWidget(bottom_widget, 2, 1, 1, 1)

        # 设置右侧布局的拉伸因子
        right_grid.setRowStretch(1, 1)  # 中间分割器可拉伸
        right_grid.setColumnStretch(1, 1)  # 名称编辑框可拉伸

        # 装入主分割器
        self.splitter.addWidget(left_widget)
        self.splitter.addWidget(right_widget)
        self.splitter.setStretchFactor(0, 0)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([260, 840])

        # Tab 顺序（名称 -> 内容 -> 工具 -> 用户代称 -> AI 代称）
        self.setTabOrder(self.name_edit, self.content_edit)
        try:
            self.setTabOrder(self.content_edit, self.tools_widget)
        except Exception:
            pass
        self.setTabOrder(self.name_user_edit, self.name_ai_edit)

        # 初始化列表
        self._reload_list()

    # ---------- 外部接口 ----------
    def load_income_prompt(self, system_message: dict):
        """兼容老接口：加载传入的系统消息"""
        # 提取系统提示内容
        system_prompt = system_message.get('content', '')
        
        # 提取info字段
        info = system_message.get('info', {})
        
        # 检查是否有未保存的更改
        if self.is_modified and system_prompt != self.content_edit.toPlainText():
            self._save_current_config()

        #更新标题
        self.name_edit.setText('当前对话')

        # 更新代称
        name_info = info.get('name', {})
        if name_info:
            self.name_user = name_info.get('user', self.name_user)
            self.name_ai = name_info.get('assistant', self.name_ai)
            self.name_user_edit.setText(self.name_user)
            self.name_ai_edit.setText(self.name_ai)
        
        # 更新头像路径
        avatar_info = info.get('avatar', {})
        if avatar_info:
            self.avatar_user_path = avatar_info.get('user', self.avatar_user_path)
            self.avatar_ai_path = avatar_info.get('assistant', self.avatar_ai_path)
            self._update_avatar_preview("user")
            self._update_avatar_preview("assistant")
        
        # 更新工具选择
        tools = info.get('tools', [])
        if tools:
            self.tools_widget.set_initial_selection(tools)
        
        # 查找或创建"当前对话"配置
        filename = f"{self.default_current_filename}.json"
        current_path = self.store.current_dialog_path(self.default_current_filename)
        
        # 检查是否已存在
        existing_preset = None
        if os.path.exists(current_path):
            existing_preset = self.store.read(current_path)
        
        # 创建新的预设对象
        preset = SystemPromptPreset(
            name=self.default_current_filename,
            content=system_prompt,
            post_history="",
            tools=tools,
            info={
                "id": "system_prompt",
                "name": {"user": self.name_user, "assistant": self.name_ai},
                "title": "Current Chat",
                "tools": tools,
                "avatar": {
                    "user": self.avatar_user_path,
                    "assistant": self.avatar_ai_path,
                },
            },
            avatars={
                "user": self.avatar_user_path,
                "assistant": self.avatar_ai_path,
            }
        )
        
        # 保存到当前对话文件
        if not self.store.save(current_path, preset):
            QtWidgets.QMessageBox.warning(self, "保存失败", f"无法保存到：{filename}")
            return
        
        # 刷新列表并选中当前对话
        self._ignore_selection=True
        self._reload_list()
        items = self.list_widget.findItems(filename, QtCore.Qt.MatchExactly)
        if items:
            self.list_widget.setCurrentItem(items[0])
        self._ignore_selection=False
        
        # 直接更新UI显示（不触发修改标志）
        self.ignore_changes = True
        try:
            self.content_edit.setText(system_prompt)
            self.is_modified = False
            self.btn_save.setEnabled(False)
        finally:
            self.ignore_changes = False
    
    # ---------- 内部工具 ----------
    def _reload_list(self, select_path: Optional[str] = None):
        blocker = QtCore.QSignalBlocker(self.list_widget)
        self.list_widget.clear()
        for path, preset in self.store.list_presets():
            item = QtWidgets.QListWidgetItem(os.path.basename(path))
            item.setData(QtCore.Qt.UserRole, path)
            self.list_widget.addItem(item)
            if select_path and path == select_path:
                self.list_widget.setCurrentItem(item)
        if hasattr(self, "search_edit"):
            self._filter_list(self.search_edit.text())

    def _filter_list(self, text: str):
        text = (text or "").strip().lower()
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            item.setHidden(text not in item.text().lower())

    def _select_item_by_path(self, path: Optional[str]):
        if not path:
            return
        base = os.path.basename(path)
        matches = self.list_widget.findItems(base, QtCore.Qt.MatchExactly)
        if matches:
            self.list_widget.setCurrentItem(matches[0])

    def _on_user_name_changed(self, text: str):
        self.name_user = text or ""
        self._on_content_changed()

    def _on_ai_name_changed(self, text: str):
        self.name_ai = text or ""
        self._on_content_changed()

    def _on_content_changed(self):
        if self.ignore_changes:
            return
        self.is_modified = True
        self.btn_save.setEnabled(True)

    def _current_preset_from_ui(self) -> "SystemPromptPreset":
        return SystemPromptPreset(
            name=self.name_edit.text().strip(),
            content=self.content_edit.toPlainText(),
            post_history="",
            tools=self.tools_widget.get_selected_functions(),
            info={
                "id": "system_prompt",
                "name": {"user": self.name_user, "assistant": self.name_ai},
                "title": "New Chat",
                "tools": self.tools_widget.get_selected_functions(),
                "avatar": {
                    "user": self.avatar_user_path.strip(),
                    "assistant": self.avatar_ai_path.strip(),
                },
            },
            avatars={
                "user": self.avatar_user_path.strip(),
                "assistant": self.avatar_ai_path.strip(),
            }
        )

    def _apply_preset_to_ui(self, preset: "SystemPromptPreset"):
        self.ignore_changes = True
        try:
            # 名称与内容
            self.name_edit.setText(preset.name or "")
            self.content_edit.setText(preset.content or "")
            # 代称
            info_names = (preset.info or {}).get("name", {})
            self.name_user = info_names.get("user", self.name_user or "")
            self.name_ai = info_names.get("assistant", self.name_ai or "")
            self.name_user_edit.setText(self.name_user)
            self.name_ai_edit.setText(self.name_ai)
            # 工具
            self.tools_widget.set_initial_selection(preset.tools or [])
            # 头像
            av = (preset.info or {}).get("avatar") or preset.avatars or {}
            self.avatar_user_path = av.get("user", "") or ""
            self.avatar_ai_path = av.get("assistant", "") or ""
            self._update_avatar_preview("user")
            self._update_avatar_preview("assistant")
            # 状态
            self.is_modified = False
            self.btn_save.setEnabled(False)
        finally:
            self.ignore_changes = False

    # ---------- 列表交互 ----------
    def _on_file_selected(self):
        if getattr(self, "_ignore_selection", False):
            return

        items = self.list_widget.selectedItems()
        if not items:
            return

        target_path = items[0].data(QtCore.Qt.UserRole)

        if self.is_modified:
            self._ignore_selection = True
            ok = self._save_current_config()
            self._ignore_selection = False
            if not ok:
                blocker = QtCore.QSignalBlocker(self.list_widget)
                self._select_item_by_path(self.current_file)
                return

        preset = self.store.read(target_path)
        if not preset:
            QtWidgets.QMessageBox.warning(self, "读取失败", f"无法读取：{os.path.basename(target_path)}")
            return

        self.current_file = target_path
        self._apply_preset_to_ui(preset)

        blocker = QtCore.QSignalBlocker(self.list_widget)
        self._select_item_by_path(target_path)

    # ---------- CRUD ----------
    def _create_new_config(self):
        name, ok = QtWidgets.QInputDialog.getText(self, "新建配置", "请输入配置名称：")
        if not ok or not name.strip():
            return
        preset = SystemPromptPreset(
            name=name.strip(),
            content="",
            post_history="",
            tools=[],
            info={
                "id": "system_prompt",
                "name": {"user": self.name_user, "assistant": self.name_ai},
                "title": "New Chat",
                "tools": []
            }
        )
        path = self.store.create(name.strip(), preset)
        if not path:
            QtWidgets.QMessageBox.critical(self, "创建失败", "无法创建新配置文件")
            return
        self._reload_list()
        items = self.list_widget.findItems(os.path.basename(path), QtCore.Qt.MatchExactly)
        if items:
            self.list_widget.setCurrentItem(items[0])

    def _delete_current_config(self):
        items = self.list_widget.selectedItems()
        if not items:
            return
        file_name = items[0].text()
        if QtWidgets.QMessageBox.question(
            self, "确认删除", f"确定删除 '{file_name}' ？",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
        ) != QtWidgets.QMessageBox.Yes:
            return
        path = items[0].data(QtCore.Qt.UserRole)
        if not self.store.delete(path):
            QtWidgets.QMessageBox.critical(self, "删除失败", "无法删除配置文件")
            return
        self.current_file = None
        self._reload_list()
        # 清空右侧
        self.name_edit.clear()
        self.content_edit.clear()
        self.tools_widget.set_initial_selection([])
        self.avatar_user_path = ""
        self.avatar_ai_path = ""
        self._update_avatar_preview("user")
        self._update_avatar_preview("assistant")
        self.is_modified = False
        self.btn_save.setEnabled(False)

    def _save_current_config(self) -> bool:
        if not self.is_modified:
            return True
        preset = self._current_preset_from_ui()
        if not preset.name:
            QtWidgets.QMessageBox.warning(self, "无效名称", "配置名称不能为空")
            return False

        new_file_name = f"{preset.name}.json"
        target_path = os.path.join(self.store.folder_path, new_file_name)

        if not self.store.save(target_path, preset):
            QtWidgets.QMessageBox.critical(self, "保存失败", "无法保存配置文件")
            return False

        ## 如发生重命名，删除旧文件
        #if self.current_file and os.path.abspath(self.current_file) != os.path.abspath(target_path):
        #    if os.path.exists(self.current_file):
        #        self.store.delete(self.current_file)

        self.current_file = target_path
        self.is_modified = False
        self.btn_save.setEnabled(False)

        # 刷新列表并恢复选中
        cur_name = os.path.basename(self.current_file)
        blocker = QtCore.QSignalBlocker(self.list_widget)
        self._reload_list()
        matches = self.list_widget.findItems(cur_name, QtCore.Qt.MatchExactly)
        if matches:
            self.list_widget.setCurrentItem(matches[0])

        return True

    # ---------- 覆盖当前会话 ----------
    def _send_current(self):
        preset = self._current_preset_from_ui()
        current_path = self.store.current_dialog_path(self.default_current_filename)
        if not self.store.save(current_path, preset):
            QtWidgets.QMessageBox.critical(self, "失败", "无法写入当前对话")
            return
        self.update_system_prompt.emit(preset.content)
        self.update_tool_selection.emit(preset.tools)
        self.update_preset.emit(preset.to_json())  # 内含 info.avatar
        QtWidgets.QMessageBox.information(self, "已覆盖", "已覆盖到当前对话")

    def _pick_avatar(self, who: str):
        path, _ = QtWidgets.QFileDialog.getOpenFileName(
            self, "选择头像", "", "Images (*.png *.jpg *.jpeg *.bmp *.gif);;All Files (*)"
        )
        if not path:
            return
        if who == "user":
            self.avatar_user_path = path
            self._update_avatar_preview("user")
        else:
            self.avatar_ai_path = path
            self._update_avatar_preview("assistant")
        self._on_content_changed()

    def _update_avatar_preview(self, who: str):
        label = self.avatar_user_preview if who == "user" else self.avatar_ai_preview
        path = self.avatar_user_path if who == "user" else self.avatar_ai_path
        if path and os.path.exists(path):
            pix = QtGui.QPixmap(path)
            if not pix.isNull():
                pix = pix.scaled(label.size(), QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)
                label.setPixmap(pix)
                return
        label.setPixmap(QtGui.QPixmap())  # 清空

class SystemPromptComboBox(QtWidgets.QWidget):
    update_system_prompt = QtCore.pyqtSignal(str)
    update_tool_selection = QtCore.pyqtSignal(list)  # 新增
    update_preset = QtCore.pyqtSignal(dict)          # 新增
    request_open_editor = QtCore.pyqtSignal()

    class _Entry:
        __slots__ = ("display_name", "mtime_ns", "size", "content_hash", "tools_hash")
        def __init__(self, display_name="", mtime_ns=0, size=0, content_hash=None, tools_hash=None):
            self.display_name = display_name
            self.mtime_ns = mtime_ns
            self.size = size
            self.content_hash = content_hash
            self.tools_hash = tools_hash

    def __init__(self, folder_path='system_prompt_presets', parent=None,
                 include_placeholder=True, current_filename_base='当前对话',
                 auto_emit_on_external_change=False):
        super().__init__(parent)
        self.store = SystemPromptStore(folder_path)
        self.include_placeholder = include_placeholder
        self.current_filename_base = current_filename_base
        self.auto_emit_on_external_change = auto_emit_on_external_change
        self.special_current_display = "临时修改的系统提示"
        self.setContentsMargins(0, 0, 0, 0)

        # UI
        self.combo = QtWidgets.QComboBox()
        self.combo.currentIndexChanged.connect(self._on_index_changed)
        self.combo.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

        self.open_btn = QtWidgets.QToolButton()
        self.open_btn.setText("+")
        self.open_btn.setToolTip("打开完整编辑器")
        self.open_btn.clicked.connect(lambda: self.request_open_editor.emit())
        self.open_btn.setSizePolicy(QtWidgets.QSizePolicy.Expanding, QtWidgets.QSizePolicy.Expanding)

        lay = QtWidgets.QHBoxLayout(self)
        lay.addWidget(self.combo, 1)
        lay.addWidget(self.open_btn, 0)
        lay.setSpacing(0)
        lay.setContentsMargins(0,0,0,0)

        # 状态
        self.ignore_combo_signals = False
        self._reload_timer = QtCore.QTimer(self)
        self._reload_timer.setSingleShot(True)
        self._reload_timer.setInterval(200)
        self._reload_timer.timeout.connect(self._do_reload)

        self.watcher = QtCore.QFileSystemWatcher(self)
        self.watcher.directoryChanged.connect(lambda _: self.schedule_reload())
        self.watcher.fileChanged.connect(self._on_file_changed)
        self._watched_dir = None
        self._watched_file = None

        self._cache = {}  # path -> _Entry
        self._items_snapshot = []
        self._last_target_data = None

        self.reload_presets(keep_current=False)

    def set_folder_path(self, folder_path: str):
        if self.store.folder_path == folder_path:
            return
        self.store = SystemPromptStore(folder_path)
        self.reload_presets(keep_current=False)

    def schedule_reload(self, delay_ms=200):
        self._reload_timer.start(delay_ms)

    def _on_file_changed(self, path):
        if self.auto_emit_on_external_change and path and path == self.combo.currentData():
            self._emit_current_from_path(path)
        self.schedule_reload()

    def _do_reload(self):
        self.reload_presets(keep_current=True)

    def _current_json_path(self):
        return self.store.current_dialog_path(self.current_filename_base)

    def _hash_text(self, text: str):
        return hashlib.blake2b(text.encode("utf-8"), digest_size=16).hexdigest()

    def _stat(self, path):
        try:
            st = os.stat(path)
            return st.st_mtime_ns, st.st_size
        except Exception:
            return 0, 0

    def _read_min(self, path):
        # 返回 (display_name, preset, ok)
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
            preset = SystemPromptPreset.from_json(data)
            display_name = preset.name or os.path.splitext(os.path.basename(path))[0]
            return display_name, preset, True
        except Exception:
            return os.path.splitext(os.path.basename(path))[0], SystemPromptPreset(), False

    def reload_presets(self, keep_current=True):
        prev_data = self.combo.currentData() if keep_current else None
        folder = self.store.folder_path
        os.makedirs(folder, exist_ok=True)

        cur_path = self._current_json_path()
        all_paths = self.store.list_files()

        # 读取当前对话内容 hash 用于匹配来源
        current_hash = None
        if os.path.isfile(cur_path):
            _, preset, ok = self._read_min(cur_path)
            if ok:
                current_hash = self._hash_text(preset.content)

        # 更新缓存
        for p in all_paths:
            mtime_ns, size = self._stat(p)
            ent = self._cache.get(p)
            if ent and ent.mtime_ns == mtime_ns and ent.size == size:
                continue
            display_name, preset, ok = self._read_min(p)
            ch = self._hash_text(preset.content) if ok else None
            th = self._hash_text(",".join(sorted(preset.tools or []))) if ok else None
            self._cache[p] = self._Entry(display_name, mtime_ns, size, ch, th)

        # 清理
        live = set(all_paths)
        for k in list(self._cache.keys()):
            if k not in live:
                self._cache.pop(k, None)

        # 列表（排除当前对话.json）
        items = []
        for p in all_paths:
            if cur_path and os.path.abspath(p) == os.path.abspath(cur_path):
                continue
            ent = self._cache.get(p)
            disp = ent.display_name if ent else os.path.splitext(os.path.basename(p))[0]
            items.append((disp, p))
        items.sort(key=lambda x: x[0].casefold())

        # 匹配来源
        matched = None
        if current_hash is not None:
            for _, p in items:
                ent = self._cache.get(p)
                if ent and ent.content_hash == current_hash:
                    matched = p; break

        # 生成最终列表
        final_items = []
        if self.include_placeholder:
            final_items.append(("选择系统提示…", None))
        added_special = False
        if cur_path and os.path.isfile(cur_path) and matched is None:
            final_items.append((self.special_current_display, cur_path))
            added_special = True
        final_items.extend(items)

        # 目标选择
        target_data = None
        if matched: target_data = matched
        elif added_special: target_data = cur_path
        elif keep_current and prev_data: target_data = prev_data

        same_list = (self._items_snapshot == final_items)
        same_target = (self._last_target_data == target_data)

        if not same_list:
            self.ignore_combo_signals = True
            self.combo.blockSignals(True)
            self.combo.clear()
            for dn, p in final_items:
                self.combo.addItem(dn, p)
            if target_data is not None:
                idx = self.combo.findData(target_data)
                self.combo.setCurrentIndex(idx if idx >= 0 else (0 if self.include_placeholder else (0 if self.combo.count() > 0 else -1)))
            else:
                self.combo.setCurrentIndex(0 if self.include_placeholder else (0 if self.combo.count() > 0 else -1))
            self.combo.blockSignals(False)
            self.ignore_combo_signals = False
            self._items_snapshot = list(final_items)
        else:
            if target_data is not None and not same_target:
                idx = self.combo.findData(target_data)
                if idx >= 0 and idx != self.combo.currentIndex():
                    self.ignore_combo_signals = True
                    self.combo.blockSignals(True)
                    self.combo.setCurrentIndex(idx)
                    self.combo.blockSignals(False)
                    self.ignore_combo_signals = False

        self._last_target_data = target_data
        self._update_watchers(self.combo.currentData())

        if self.auto_emit_on_external_change:
            self._emit_current_from_path(self.combo.currentData())

    def _update_watchers(self, current_selected):
        # 目录监听
        if self._watched_dir != self.store.folder_path:
            try:
                if self._watched_dir:
                    self.watcher.removePath(self._watched_dir)
            except Exception:
                pass
            try:
                self.watcher.addPath(self.store.folder_path)
                self._watched_dir = self.store.folder_path
            except Exception:
                self._watched_dir = None
        # 文件监听
        if self._watched_file and self._watched_file != current_selected:
            try:
                self.watcher.removePath(self._watched_file)
            except Exception:
                pass
            self._watched_file = None
        if current_selected and os.path.exists(current_selected) and self._watched_file != current_selected:
            try:
                self.watcher.addPath(current_selected)
                self._watched_file = current_selected
            except Exception:
                self._watched_file = None

    def _emit_current_from_path(self, path):
        if not path or not os.path.exists(path):
            return
        _, preset, ok = self._read_min(path)
        if not ok:
            return
        self.update_system_prompt.emit(preset.content or "")
        self.update_tool_selection.emit(preset.tools or [])
        self.update_preset.emit(preset.to_json())

    def _on_index_changed(self, idx):
        if self.ignore_combo_signals:
            return
        path = self.combo.itemData(idx)
        if not path:
            return
        self._update_watchers(path)
        self._emit_current_from_path(path)

    # 可选帮助
    def select_by_name(self, display_name: str):
        i = self.combo.findText(display_name, QtCore.Qt.MatchFixedString)
        if i >= 0:
            self.combo.setCurrentIndex(i)

    def select_by_filename(self, filename: str):
        p = os.path.join(self.store.folder_path, filename)
        i = self.combo.findData(p)
        if i >= 0:
            self.combo.setCurrentIndex(i)
