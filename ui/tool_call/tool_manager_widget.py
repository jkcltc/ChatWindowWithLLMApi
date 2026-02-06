
from typing import Any, Dict, List
import typing as _t
import json
import re
import logging
from pathlib import Path
from PyQt6 import QtWidgets,QtCore

from core.tool_call.tool_core import (
    FunctionsPluginManager,get_tools_event_bus,get_tool_registry,
    ToolsListModel,ToolsFilterProxyModel
)

logger = logging.getLogger("tools")

    # 公开单例
_PLUGIN_MANAGER_SINGLETON: FunctionsPluginManager = None

def get_functions_plugin_manager() -> FunctionsPluginManager:
    global _PLUGIN_MANAGER_SINGLETON
    if _PLUGIN_MANAGER_SINGLETON is None:
        _PLUGIN_MANAGER_SINGLETON = FunctionsPluginManager()
    return _PLUGIN_MANAGER_SINGLETON

class FunctionEditorDialog(QtWidgets.QDialog):
    """
    用户工具编辑器：
      - 左侧表单（名称/描述/标签/权限/超时/参数Schema）
      - 右侧代码（可编辑；表单可一键生成模板覆盖）
      - 保存到 core.tool_call.function_lib 下并触发热重载
    """
    def __init__(self, parent=None, existing_file: Path | None = None):
        super().__init__(parent)
        self.setWindowTitle("函数工具编辑器")
        self.resize(960, 640)
        self._pm = get_functions_plugin_manager()
        self._bus = get_tools_event_bus()

        # UI 组件
        self.nameEdit = QtWidgets.QLineEdit()
        self.descEdit = QtWidgets.QPlainTextEdit()
        self.tagsEdit = QtWidgets.QLineEdit()
        self.permsEdit = QtWidgets.QLineEdit()
        self.timeoutSpin = QtWidgets.QDoubleSpinBox()
        self.timeoutSpin.setDecimals(1)
        self.timeoutSpin.setRange(0.1, 600.0)
        self.timeoutSpin.setSingleStep(0.5)
        self.timeoutSpin.setValue(30.0)

        self.schemaEdit = QtWidgets.QPlainTextEdit()
        self.schemaEdit.setPlaceholderText('{"type": "object", "properties": {}}')

        self.codeEdit = QtWidgets.QPlainTextEdit()
        font = self.codeEdit.font()
        font.setFamily("Consolas")
        font.setPointSize(font.pointSize() + 1)
        self.codeEdit.setFont(font)

        self.btnGen = QtWidgets.QPushButton("从表单生成代码")
        self.btnValidate = QtWidgets.QPushButton("校验语法")
        self.btnSave = QtWidgets.QPushButton("保存并重载")
        self.btnCancel = QtWidgets.QPushButton("取消")

        # 布局
        form = QtWidgets.QFormLayout()
        form.addRow("名称（唯一）:", self.nameEdit)
        form.addRow("描述:", self.descEdit)
        form.addRow("标签（逗号分隔）:", self.tagsEdit)
        form.addRow("权限（逗号分隔）:", self.permsEdit)
        form.addRow("超时（秒）:", self.timeoutSpin)
        form.addRow("参数 Schema（JSON）:", self.schemaEdit)

        left = QtWidgets.QWidget()
        left.setLayout(form)

        right = QtWidgets.QWidget()
        v = QtWidgets.QVBoxLayout(right)
        v.setContentsMargins(0, 0, 0, 0)
        v.addWidget(self.codeEdit)

        btns = QtWidgets.QHBoxLayout()
        btns.addStretch(1)
        btns.addWidget(self.btnGen)
        btns.addWidget(self.btnValidate)
        btns.addWidget(self.btnSave)
        btns.addWidget(self.btnCancel)

        root = QtWidgets.QGridLayout(self)
        root.addWidget(left, 0, 0)
        root.addWidget(right, 0, 1)
        root.addLayout(btns, 1, 0, 1, 2)
        root.setColumnStretch(0, 0)
        root.setColumnStretch(1, 1)

        # 事件
        self.btnCancel.clicked.connect(self.reject)
        self.btnGen.clicked.connect(self._generate_code_from_form)
        self.btnValidate.clicked.connect(self._validate_code)
        self.btnSave.clicked.connect(self._save_and_reload)

        self._existing_file = existing_file
        if existing_file:
            self._load_existing(existing_file)

    # 行为

    def _parse_comma_list(self, s: str) -> list[str]:
        return [x.strip() for x in (s or "").split(",") if x.strip()]

    def _default_schema(self) -> dict:
        return {"type": "object", "properties": {}}

    def _generate_code_from_form(self):
        name = self.nameEdit.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(self, "提示", "请填写名称")
            return
        try:
            schema = json.loads(self.schemaEdit.toPlainText().strip() or "{}")
            if not isinstance(schema, dict):
                raise ValueError("Schema 必须为 JSON 对象")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Schema 错误", str(e))
            return
        desc = self.descEdit.toPlainText().strip()
        tags = self._parse_comma_list(self.tagsEdit.text())
        perms = self._parse_comma_list(self.permsEdit.text())
        timeout = float(self.timeoutSpin.value())

        try:
            code_path = self._pm.create_tool_file_from_template(
                name=name,
                description=desc,
                parameters=schema or self._default_schema(),
                tags=tags,
                permissions=perms,
                timeout=timeout,
                code_body=None,  # 用默认体
                filename=f"{name}.py",
                overwrite=True,  # 生成到临时代码框，不落盘；但这里借用模板生成文本
            )
            # 读取模板内容到编辑器（我们不真正覆盖磁盘，因为 overwrite=True 已写入；但用户可能希望再改）
            code_text = code_path.read_text(encoding="utf-8")
            # 生成后立即删除临时写入，避免误保存
            try:
                code_path.unlink(missing_ok=True)
            except Exception:
                pass
            self.codeEdit.setPlainText(code_text)
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "生成失败", str(e))

    def _validate_code(self):
        code = self.codeEdit.toPlainText()
        if not code.strip():
            QtWidgets.QMessageBox.information(self, "提示", "代码为空")
            return
        try:
            compile(code, "<tool_preview>", "exec")
            QtWidgets.QMessageBox.information(self, "通过", "语法检查通过")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "语法错误", str(e))

    def _save_and_reload(self):
        # 基于名称决定文件名
        name = self.nameEdit.text().strip()
        if not name:
            QtWidgets.QMessageBox.warning(self, "提示", "请填写名称（用于文件名与唯一标识）")
            return
        code = self.codeEdit.toPlainText()
        if not code.strip():
            QtWidgets.QMessageBox.warning(self, "提示", "代码为空，无法保存")
            return

        # 写入文件
        try:
            target = self._pm._dir / f"{name}.py"
            target.write_text(code, encoding="utf-8")
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "保存失败", str(e))
            return

        # 重载
        summary = self._pm.reload_all()
        errs = summary.get("errors") if isinstance(summary, dict) else []
        if errs:
            QtWidgets.QMessageBox.warning(self, "重载完成（有错误）", "\n".join(errs)[:2000])
        else:
            QtWidgets.QMessageBox.information(self, "成功", "已保存并重载")
        self.accept()

    def _load_existing(self, path: Path):
        try:
            code = path.read_text(encoding="utf-8")
            self.codeEdit.setPlainText(code)
            # 尝试从代码中提取 name/desc/schema（弱解析）
            m_name = re.search(r'name\s*=\s*["\'](.+?)["\']', code)
            if m_name:
                self.nameEdit.setText(m_name.group(1))
            m_desc = re.search(r'description\s*=\s*["\']([\s\S]*?)["\']\s*,', code)
            if m_desc:
                self.descEdit.setPlainText(m_desc.group(1))
            m_params = re.search(r'parameters\s*=\s*(\{[\s\S]*?\})\s*,', code)
            if m_params:
                try:
                    self.schemaEdit.setPlainText(json.dumps(json.loads(m_params.group(1)), ensure_ascii=False, indent=2))
                except Exception:
                    self.schemaEdit.setPlainText(m_params.group(1))
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "读取失败", str(e))


# 会话选择持久化（内存简单存储，可按需替换为 JSON 落盘）
class _SelectionStore:
    def __init__(self):
        self._store: dict[str, list[str]] = {}

    def set(self, conversation_id: str, names: list[str]):
        self._store[conversation_id] = list(names or [])

    def get(self, conversation_id: str) -> list[str]:
        return list(self._store.get(conversation_id, []))


_SELECTION_STORE = _SelectionStore()


class FunctionManager(QtWidgets.QWidget):
    """
    主设置界面：
      - 针对某个对话进行工具携带管理（勾选）
      - 显示工具详情
      - 测试运行工具（异步），查看结果
      - 新建/编辑/删除用户工具，热重载
      - 导出本次对话要携带的 openai tools 负载片段
    使用方法：
      - 调用 start(conversation_id, initial_active_names, available_names=None)
      - 监听 activatedToolsChanged(list[str]) 信号或调用 get_selected_functions()
    """

    activatedToolsChanged = QtCore.pyqtSignal(list)
    testRunFinished = QtCore.pyqtSignal(dict)

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Tools Manager")
        
        screen_geometry = QtWidgets.QApplication.primaryScreen().availableGeometry()
        
        width = int(screen_geometry.width() * 0.6)
        height = int(screen_geometry.height() * 0.6)
        
        left = (screen_geometry.width() - width) // 2
        top = (screen_geometry.height() - height) // 2
        
        self.setGeometry(left, top, width, height)

        self._registry = get_tool_registry() if get_tool_registry else None
        self._pm = get_functions_plugin_manager()
        self._bus = get_tools_event_bus()

        self._conversation_id: str | None = None
        self._available_names: list[str] | None = None

        # 左侧：搜索 + 列表（复选）
        self._model = ToolsListModel(self)
        self._proxy = ToolsFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)

        self.searchEdit = QtWidgets.QLineEdit(self)
        self.searchEdit.setPlaceholderText("搜索（名称/描述/标签）")
        self.listView = QtWidgets.QListView(self)
        self.listView.setModel(self._proxy)
        self.listView.setUniformItemSizes(True)
        self.listView.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self.listView.clicked.connect(self._toggle_checked_on_click)
        self.listView.doubleClicked.connect(self._toggle_checked_on_click)

        leftBox = QtWidgets.QVBoxLayout()
        leftBox.addWidget(self.searchEdit)
        leftBox.addWidget(self.listView)

        # 右侧：TabWidget 包含详情和测试
        self.tabWidget = QtWidgets.QTabWidget(self)
        
        # 详情 Tab
        self.detailWidget = QtWidgets.QWidget()
        detailLayout = QtWidgets.QVBoxLayout(self.detailWidget)
        
        # 详情区域
        self.lblName = QtWidgets.QLabel("-")
        self.lblSource = QtWidgets.QLabel("-")
        self.lblAsync = QtWidgets.QLabel("-")
        self.lblTimeout = QtWidgets.QLabel("-")
        self.lblTags = QtWidgets.QLabel("-")
        self.lblPerms = QtWidgets.QLabel("-")
        self.descEdit = QtWidgets.QPlainTextEdit()
        self.descEdit.setReadOnly(True)
        self.schemaEdit = QtWidgets.QPlainTextEdit()
        self.schemaEdit.setReadOnly(True)

        form = QtWidgets.QFormLayout()
        form.addRow("名称:", self.lblName)
        form.addRow("来源:", self.lblSource)
        form.addRow("异步:", self.lblAsync)
        form.addRow("超时:", self.lblTimeout)
        form.addRow("标签:", self.lblTags)
        form.addRow("权限:", self.lblPerms)

        grpInfo = QtWidgets.QGroupBox("工具详情")
        infoLay = QtWidgets.QVBoxLayout()
        infoLay.addLayout(form)

        infoLay.addWidget(QtWidgets.QLabel("描述:"))
        infoLay.addWidget(self.descEdit, 1)

        infoLay.addWidget(QtWidgets.QLabel("参数 Schema:"))
        infoLay.addWidget(self.schemaEdit, 2)

        # 详情下方按钮：编辑/新建/删除/重载/复制OpenAI tools JSON
        self.btnNew = QtWidgets.QPushButton("新建工具")
        self.btnEdit = QtWidgets.QPushButton("编辑工具")
        self.btnDelete = QtWidgets.QPushButton("删除工具")
        self.btnReload = QtWidgets.QPushButton("重载工具")
        self.btnCopyToolsJSON = QtWidgets.QPushButton("复制 Tools JSON")

        btnRow1 = QtWidgets.QHBoxLayout()
        btnRow1.addWidget(self.btnNew)
        btnRow1.addWidget(self.btnEdit)
        btnRow1.addWidget(self.btnDelete)
        btnRow1.addStretch(1)
        btnRow1.addWidget(self.btnReload)
        btnRow1.addWidget(self.btnCopyToolsJSON)

        infoLay.addLayout(btnRow1)
        grpInfo.setLayout(infoLay)
        
        detailLayout.addWidget(grpInfo)
        self.tabWidget.addTab(self.detailWidget, "工具详情")

        # 测试运行 Tab
        self.testWidget = QtWidgets.QWidget()
        testLayout = QtWidgets.QVBoxLayout(self.testWidget)
        
        # 测试运行区域
        self.argsEdit = QtWidgets.QPlainTextEdit()
        self.argsEdit.setPlaceholderText('输入 JSON 参数，例如：{"text": "hello"}')
        self.btnRun = QtWidgets.QPushButton("测试运行")
        self.runStatus = QtWidgets.QLabel("")
        self.outputEdit = QtWidgets.QPlainTextEdit()
        self.outputEdit.setReadOnly(True)

        runRow = QtWidgets.QHBoxLayout()
        runRow.addWidget(self.btnRun)
        runRow.addWidget(self.runStatus, 1)

        grpTest = QtWidgets.QGroupBox("测试运行")
        testLay = QtWidgets.QVBoxLayout()
        testLay.addWidget(QtWidgets.QLabel("调用参数（JSON）:"))
        testLay.addWidget(self.argsEdit, 1)
        testLay.addLayout(runRow)
        testLay.addWidget(QtWidgets.QLabel("返回结果:"))
        testLay.addWidget(self.outputEdit, 2)
        grpTest.setLayout(testLay)
        
        testLayout.addWidget(grpTest)
        self.tabWidget.addTab(self.testWidget, "测试运行")

        right = QtWidgets.QVBoxLayout()
        right.addWidget(self.tabWidget, 1)

        root = QtWidgets.QGridLayout(self)
        leftWidget = QtWidgets.QWidget(self)
        leftWidget.setLayout(leftBox)
        root.addWidget(leftWidget, 0, 0)
        rightWidget = QtWidgets.QWidget(self)
        rightWidget.setLayout(right)
        root.addWidget(rightWidget, 0, 1)
        root.setColumnStretch(0, 1)
        root.setColumnStretch(1, 2)
        root.setRowStretch(0, 1)

        # 信号连接
        self.searchEdit.textChanged.connect(self._proxy.set_search_text)
        self.listView.selectionModel().currentChanged.connect(self._on_current_changed)
        self._model.selectionChanged.connect(self._on_selection_changed)
        #self.btnApply.clicked.connect(self._on_apply)
        self.btnRun.clicked.connect(self._on_run_clicked)
        self.testRunFinished.connect(self._on_test_finished)

        self.btnNew.clicked.connect(self._on_new_tool)
        self.btnEdit.clicked.connect(self._on_edit_tool)
        self.btnDelete.clicked.connect(self._on_delete_tool)
        self.btnReload.clicked.connect(self._on_reload)
        self.btnCopyToolsJSON.clicked.connect(self._on_copy_tools_json)

        # 监听插件事件，自动刷新列表
        self._bus.toolsChanged.connect(self._refresh_list_only)

        # 初始刷新
        self.refresh()

    # 对外 API

    def start(self, conversation_id: str, initial_active_names: _t.List[str], available_names: _t.Optional[_t.List[str]] = None):
        """绑定当前对话，设置初始激活集合并刷新视图"""
        self._conversation_id = conversation_id
        self._available_names = list(available_names) if available_names else None
        
        # 新增：确保用户工具已加载
        if not self._pm._module_records:  # 检查是否已加载
            self._pm.initial_load()  # 加载用户自定义工具
        
        # 先设定激活，再刷新
        self._model.set_active_tools(initial_active_names or [])
        self._model.refresh_from_registry(available_names=self._available_names)
        self._ensure_first_selection()
        self._update_details_from_index(self.listView.currentIndex())

    def set_active_tools(self, names: _t.List[str]):
        """
        设置当前激活的工具名列表（覆盖）。
        """
        self._model.set_active_tools(names or [])
        self._ensure_first_selection()

    def refresh(self):
        """
        重新加载工具列表（从 registry）。
        """
        self._model.refresh_from_registry(available_names=self._available_names)
        self._ensure_first_selection()

    def get_selected_function_names(self) -> _t.List[str]:
        """
        返回当前勾选的工具名列表（兼容旧接口）。
        """
        return self._model.get_selected_functions()

    def get_selected_functions(self) -> List[Dict[str, Any]]:
        """
        返回当前勾选工具的 OpenAI 格式工具清单
        """
        selected_names = self.get_selected_function_names()
        if not self._registry:
            logger.warning("ToolRegistry not available")
            return []
        
        # 直接使用 registry 的 openai_tools 方法
        return self._registry.openai_tools(tool_names=selected_names)
    # 内部行为

    def _ensure_first_selection(self):
        if self._proxy.rowCount() > 0:
            cur = self.listView.currentIndex()
            if not cur.isValid():
                self.listView.setCurrentIndex(self._proxy.index(0, 0))

    def _toggle_checked_on_click(self, proxy_index: QtCore.QModelIndex):
        if not proxy_index.isValid():
            return
        src_index = self._proxy.mapToSource(proxy_index)
        checked = self._model.data(src_index, QtCore.Qt.ItemDataRole.CheckStateRole) == QtCore.Qt.CheckState.Checked
        self._model.setData(src_index, QtCore.Qt.CheckState.Unchecked if checked else QtCore.Qt.CheckState.Checked, QtCore.Qt.ItemDataRole.CheckStateRole)
        self._on_apply()

    def _on_current_changed(self, current: QtCore.QModelIndex, previous: QtCore.QModelIndex):
        self._update_details_from_index(current)

    def _on_selection_changed(self, names: list[str]):
        # 选择勾选变化时，可更新 Tools JSON 预览状态等（这里仅更新状态条）
        self.runStatus.setText(f"已选择 {len(names)} 个工具")

    def _update_details_from_index(self, proxy_index: QtCore.QModelIndex):
        if not proxy_index.isValid():
            self._clear_details()
            return
        src = self._proxy.mapToSource(proxy_index)
        name = self._model.data(src, ToolsListModel.NameRole) or "-"
        desc = self._model.data(src, ToolsListModel.DescriptionRole) or "-"
        tags = self._model.data(src, ToolsListModel.TagsRole) or []
        timeout = self._model.data(src, ToolsListModel.TimeoutRole)
        is_async = self._model.data(src, ToolsListModel.IsAsyncRole)
        perms = self._model.data(src, ToolsListModel.PermissionsRole) or []
        params = self._model.data(src, ToolsListModel.ParametersRole) or {}
        source = self._model.data(src, ToolsListModel.SourceRole) or "-"

        self.lblName.setText(name)
        self.lblSource.setText(source)
        self.lblAsync.setText("是" if is_async else "否")
        self.lblTimeout.setText(f"{timeout}s")
        self.lblTags.setText(", ".join(tags) if tags else "-")
        self.lblPerms.setText(", ".join(perms) if perms else "-")
        self.descEdit.setPlainText(desc)
        try:
            self.schemaEdit.setPlainText(json.dumps(params, ensure_ascii=False, indent=2))
        except Exception:
            self.schemaEdit.setPlainText(str(params))

    def _clear_details(self):
        self.lblName.setText("-")
        self.lblSource.setText("-")
        self.lblAsync.setText("-")
        self.lblTimeout.setText("-")
        self.lblTags.setText("-")
        self.lblPerms.setText("-")
        self.descEdit.clear()
        self.schemaEdit.clear()

    def _on_apply(self):
        names = self.get_selected_function_names()
        # 保存当前会话的选择
        if self._conversation_id:
            _SELECTION_STORE.set(self._conversation_id, names)
        self.activatedToolsChanged.emit(names)

    def _on_run_clicked(self):
        if not self._registry:
            QtWidgets.QMessageBox.warning(self, "错误", "找不到 ToolRegistry 单例（get_tool_registry 未就绪）")
            return
        idx = self.listView.currentIndex()
        if not idx.isValid():
            QtWidgets.QMessageBox.information(self, "提示", "请先选择一个工具")
            return
        src = self._proxy.mapToSource(idx)
        name = self._model.data(src, ToolsListModel.NameRole)
        try:
            args_text = self.argsEdit.toPlainText().strip() or "{}"
            args = json.loads(args_text)
            if not isinstance(args, dict):
                raise ValueError("参数 JSON 必须是对象类型")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "参数错误", str(e))
            return

        self.btnRun.setEnabled(False)
        self.runStatus.setText(f"运行中：{name} ...")
        self.outputEdit.clear()

        fut = self._registry.call_async(name, args)

        def _done(f):
            try:
                res = f.result()
            except Exception as ex:
                res = {"ok": False, "tool": name, "error_type": ex.__class__.__name__, "message": str(ex)}
            # 跨线程发回 UI
            self.testRunFinished.emit(res)

        fut.add_done_callback(_done)

    @QtCore.pyqtSlot(dict)
    def _on_test_finished(self, result: dict):
        self.btnRun.setEnabled(True)
        self.runStatus.setText("完成")
        try:
            self.outputEdit.setPlainText(json.dumps(result, ensure_ascii=False, indent=2))
        except Exception:
            self.outputEdit.setPlainText(str(result))

    def _on_new_tool(self):
        dlg = FunctionEditorDialog(self)
        if dlg.exec():
            # 插件管理器会在保存时触发 reload；此处保守再刷新一次 UI
            self._refresh_list_only()

    def _on_edit_tool(self):
        idx = self.listView.currentIndex()
        if not idx.isValid():
            QtWidgets.QMessageBox.information(self, "提示", "请先选择要编辑的工具")
            return
        src = self._proxy.mapToSource(idx)
        name = self._model.data(src, ToolsListModel.NameRole)
        fp = self._pm.find_tool_file(name)
        if not fp:
            QtWidgets.QMessageBox.information(self, "提示", "只能编辑用户工具（core.tool_call.function_lib 下的工具）")
            return
        dlg = FunctionEditorDialog(self, existing_file=fp)
        if dlg.exec():
            self._refresh_list_only()

    def _on_delete_tool(self):
        idx = self.listView.currentIndex()
        if not idx.isValid():
            QtWidgets.QMessageBox.information(self, "提示", "请先选择要删除的工具")
            return
        src = self._proxy.mapToSource(idx)
        name = self._model.data(src, ToolsListModel.NameRole)
        fp = self._pm.find_tool_file(name)
        if not fp:
            QtWidgets.QMessageBox.information(self, "提示", "只能删除用户工具（core.tool_call.function_lib 下的工具）")
            return

        ret = QtWidgets.QMessageBox.question(self, "确认删除", f"确定删除用户工具文件：\n{fp} ？",
                                             QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No)
        if ret != QtWidgets.QMessageBox.StandardButton.Yes:
            return

        try:
            fp.unlink()
        except Exception as e:
            QtWidgets.QMessageBox.critical(self, "删除失败", str(e))
            return

        # 重载并刷新
        self._pm.reload_all()
        self._refresh_list_only()

    def _on_reload(self):
        self._pm.reload_all()
        self._refresh_list_only()

    def _on_copy_tools_json(self):
        names = self.get_selected_functions()
        if not self._registry:
            QtWidgets.QMessageBox.warning(self, "错误", "ToolRegistry 未就绪")
            return
        tools_payload = self._registry.openai_tools(tool_names=names)
        txt = json.dumps(tools_payload, ensure_ascii=False, indent=2)
        cb = QtWidgets.QApplication.clipboard()
        cb.setText(txt)
        QtWidgets.QMessageBox.information(self, "已复制", "OpenAI Tools JSON 已复制到剪贴板")

    def _refresh_list_only(self):
        self._model.refresh_from_registry(available_names=self._available_names)
        self._ensure_first_selection()
        self._update_details_from_index(self.listView.currentIndex())

from PyQt6 import QtWidgets,QtCore

# -----------------------
# 通用视图：FunctionsSelectorWidget
# -----------------------
class FunctionsSelectorWidget(QtWidgets.QWidget):
    """
    迷你选择器（通用视图）：
      - 展示工具库（名称 + 复选）
      - 搜索框
      - 外部可设定过滤条件
      - 提供 get_selected_functions()
      - 发出 selectionChanged(list[str]) 信号
    """
    selectionChanged = QtCore.pyqtSignal(list)

    def __init__(self, parent=None):
        super().__init__(parent)
        self._model = ToolsListModel(self)
        self._proxy = ToolsFilterProxyModel(self)
        self._proxy.setSourceModel(self._model)

        # UI
        self._search = QtWidgets.QLineEdit(self)
        self._search.setPlaceholderText("搜索工具（名称/描述/标签）")
        self._list = QtWidgets.QListView(self)
        self._list.setModel(self._proxy)
        self._list.setSelectionMode(QtWidgets.QAbstractItemView.SelectionMode.SingleSelection)
        self._list.setEditTriggers(QtWidgets.QAbstractItemView.EditTrigger.NoEditTriggers)
        self._list.setUniformItemSizes(True)

        layout = QtWidgets.QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._search)
        layout.addWidget(self._list)

        # 事件
        self._search.textChanged.connect(self._proxy.set_search_text)
        # 勾选变化透传
        self._model.selectionChanged.connect(self.selectionChanged)

        # 单击项切换勾选
        self._list.clicked.connect(self._toggle_checked_on_index)

        # 初次加载
        self.refresh()

    # 公共 API
    def refresh(self, available_names: _t.Optional[_t.List[str]] = None):
        """
        重新从 registry 加载工具。
        available_names: 限制显示集合（可选）。
        """
        self._model.refresh_from_registry(available_names=available_names)

    def set_initial_selection(self, names: _t.List[str]):
        """
        设置初始激活集合后刷新。
        """
        self._model.set_active_tools(names)
        # 刷新以更新视图勾选状态
        self._model.refresh_from_registry()

    def set_allowed_names(self, names: _t.Optional[_t.List[str]]):
        """
        限制仅显示指定工具集合（代理层过滤，不影响模型数据）。
        """
        self._proxy.set_allowed_names(names)

    def set_include_tags(self, tags: _t.Optional[_t.List[str]]):
        self._proxy.set_include_tags(tags)

    def set_exclude_tags(self, tags: _t.Optional[_t.List[str]]):
        self._proxy.set_exclude_tags(tags)

    def get_selected_functions(self) -> _t.List[str]:
        """
        返回当前激活工具名列表（模型层维护）。
        """
        return self._model.get_selected_functions()

    # 内部事件：单击切换勾选
    def _toggle_checked_on_index(self, proxy_index: QtCore.QModelIndex):
        if not proxy_index.isValid():
            return
        src_index = self._proxy.mapToSource(proxy_index)
        if not src_index.isValid():
            return
        checked = self._model.data(src_index, QtCore.Qt.ItemDataRole.CheckStateRole) == QtCore.Qt.CheckState.Checked
        self._model.setData(src_index, QtCore.Qt.CheckState.Unchecked if checked else QtCore.Qt.CheckState.Checked, QtCore.Qt.ItemDataRole.CheckStateRole)


