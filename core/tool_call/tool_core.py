import concurrent.futures
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union
import json, inspect, concurrent.futures, importlib, pkgutil, time, logging, asyncio, threading
from jsonschema import Draft202012Validator, ValidationError
import os, sys, webbrowser,subprocess, re, time, json
import typing as _t
from pathlib import Path
from PyQt6 import QtCore, QtWidgets



logger = logging.getLogger("tools")
executor = concurrent.futures.ThreadPoolExecutor(max_workers=4)

@dataclass
class Tool:
    name: str
    description: str
    parameters: Dict[str, Any]
    handler: Callable[..., Any]
    tags: List[str] = field(default_factory=list)
    timeout: float = 30.0
    permissions: List[str] = field(default_factory=list)
    is_async: bool = False

class ToolRegistry:
    def __init__(self):
        self._tools: Dict[str, Tool] = {}
        # 后台事件循环线程（仅用于运行协程工具）
        self._bg_loop: Optional[asyncio.AbstractEventLoop] = None
        self._bg_thread: Optional[threading.Thread] = None
        self._start_bg_loop()

    def _start_bg_loop(self):
        # 启动一个独立线程与事件循环，避免与GUI主线程冲突
        loop = asyncio.new_event_loop()

        def runner():
            asyncio.set_event_loop(loop)
            loop.run_forever()

        t = threading.Thread(target=runner, name="tool-registry-bg-loop", daemon=True)
        t.start()
        self._bg_loop = loop
        self._bg_thread = t

    def shutdown(self, *, wait_executor=True):
        # 关闭后台事件循环线程
        if self._bg_loop and self._bg_loop.is_running():
            try:
                self._bg_loop.call_soon_threadsafe(self._bg_loop.stop)
            except Exception:
                pass
        if self._bg_thread:
            try:
                self._bg_thread.join(timeout=2.0)
            except Exception:
                pass
        # 可选关闭线程池
        if wait_executor:
            try:
                executor.shutdown(wait=False, cancel_futures=True)
            except Exception:
                pass

    def register(self, tool: Tool):
        if tool.name in self._tools:
            raise ValueError(f"Tool '{tool.name}' already exists")
        # 预编译校验器
        tool._validator = Draft202012Validator(tool.parameters or {"type": "object"})
        self._tools[tool.name] = tool

    def tool(self, name=None, description=None, parameters=None, **meta):
        def decorator(fn: Callable):
            t = Tool(
                name=name or fn.__name__,
                description=description or (fn.__doc__ or "").strip(),
                parameters=parameters or {"type": "object", "properties": {}},
                handler=fn,
                is_async=inspect.iscoroutinefunction(fn),
                **meta
            )
            self.register(t)
            return fn
        return decorator

    def remove(self, name: str):
        self._tools.pop(name, None)

    def update(self, name: str, **patch):
        t = self._tools.get(name)
        if not t: raise KeyError(name)
        for k, v in patch.items():
            setattr(t, k, v)
        if "parameters" in patch:
            t._validator = Draft202012Validator(t.parameters)

    def get(self, name: str) -> Optional[Tool]:
        return self._tools.get(name)

    def list(self, *,  tags: Optional[List[str]]=None):
        tools = list(self._tools.values())
        if tags:
            tools = [t for t in tools if set(tags) & set(t.tags)]
        return tools

    def openai_tools(self, tool_names: Optional[List[str]] = None):
        tools = self.list()
        if tool_names is not None:
            tools = [t for t in tools if t.name in tool_names]
        
        return [
            {
                "type": "function",
                "function": {
                    "name": t.name,
                    "description": t.description,
                    "parameters": t.parameters or {"type": "object"}
                }
            }
            for t in tools
        ]

    def _coerce_arguments(self, args: Union[str, Dict[str, Any]]):
        if isinstance(args, dict):
            return args
        if isinstance(args, str):
            try:
                return json.loads(args)
            except json.JSONDecodeError as e:
                raise ValueError(f"Invalid JSON arguments: {e}")
        raise TypeError(f"Arguments must be dict or JSON str, got {type(args)}")

    def _validate(self, tool: Tool, arguments: Dict[str, Any]):
        try:
            tool._validator.validate(arguments)
        except ValidationError as e:
            raise ValueError(f"Schema validation failed: {e.message}")

    def _submit(self, tool: Tool, arguments: Dict[str, Any]) -> concurrent.futures.Future:
        # 将任务提交到合适的执行环境（协程 -> 后台事件循环；同步 -> 线程池）
        if tool.is_async:
            if not self._bg_loop:
                raise RuntimeError("Background asyncio loop not initialized")
            coro = tool.handler(**arguments)
            if not asyncio.iscoroutine(coro):
                raise TypeError(f"Async tool '{tool.name}' handler did not return a coroutine")
            fut = asyncio.run_coroutine_threadsafe(coro, self._bg_loop)
        else:
            fut = executor.submit(lambda: tool.handler(**arguments))
        return fut

    def _run(self, tool: Tool, arguments: Dict[str, Any]):
        fut = self._submit(tool, arguments)
        try:
            return fut.result(timeout=tool.timeout)
        except concurrent.futures.TimeoutError as e:
            # 尝试取消协程任务；线程池任务一般不可取消
            try:
                fut.cancel()
            except Exception:
                pass
            raise TimeoutError(f"Tool '{tool.name}' timed out after {tool.timeout}s") from e

    def call(self, name: str, arguments: Union[str, Dict[str, Any]]):
        tool = self.get(name)
        if not tool:
            raise ValueError(f"Tool '{name}' not found or disabled")

        args = self._coerce_arguments(arguments)
        self._validate(tool, args)

        start = time.time()
        try:
            result = self._run(tool, args)
            return {
                "ok": True,
                "tool": name,
                "duration_ms": int((time.time() - start) * 1000),
                "result": result
            }
        except Exception as e:
            logger.exception("Tool run error: %s", name)
            return {
                "ok": False,
                "tool": name,
                "error_type": e.__class__.__name__,
                "message": str(e)
            }

    def call_async(self, name: str, arguments: Union[str, Dict[str, Any]]) -> concurrent.futures.Future:
        """
        非阻塞入口：返回一个 concurrent.futures.Future。
        注意：返回值为 call(...) 的字典结果，而非工具原始返回值。
        """
        tool = self.get(name)
        if not tool:
            f = concurrent.futures.Future()
            f.set_result({
                "ok": False,
                "tool": name,
                "error_type": "ValueError",
                "message": f"Tool '{name}' not found or disabled"
            })
            return f

        # 这里预处理参数与校验
        try:
            args = self._coerce_arguments(arguments)
            self._validate(tool, args)
        except Exception as e:
            f = concurrent.futures.Future()
            f.set_result({
                "ok": False,
                "tool": name,
                "error_type": e.__class__.__name__,
                "message": str(e)
            })
            return f

        def runner():
            start = time.time()
            try:
                result = self._run(tool, args)
                return {
                    "ok": True,
                    "tool": name,
                    "duration_ms": int((time.time() - start) * 1000),
                    "result": result
                }
            except Exception as e:
                logger.exception("Tool run error: %s", name)
                return {
                    "ok": False,
                    "tool": name,
                    "error_type": e.__class__.__name__,
                    "message": str(e)
                }

        # 将整体包装为线程池任务，返回字典结果
        return executor.submit(runner)

    def call_from_openai(self, function_call_dict: Dict[str, Any]):
        # 兼容OpenAI/Kimi等格式
        fn = function_call_dict.get("function", {})
        name = fn.get("name")
        args = fn.get("arguments", {})
        return self.call(name, args)

    def load_plugins(self, package_or_path: str):
        # 支持包名或目录
        try:
            pkg = importlib.import_module(package_or_path)
            for _, modname, _ in pkgutil.iter_modules(pkg.__path__):
                importlib.import_module(f"{package_or_path}.{modname}")
        except ModuleNotFoundError:
            # 目录扫描
            import sys, os, glob
            sys.path.append(package_or_path)
            for py in glob.glob(os.path.join(package_or_path, "*.py")):
                modname = os.path.splitext(os.path.basename(py))[0]
                importlib.import_module(modname)


registry = ToolRegistry()

@registry.tool(
    name="open_file",
    description="Open a URL or local file/folder with system default app",
    parameters={
        "type": "object",
        "properties": {"url": {"type": "string", "minLength": 1}},
        "required": ["url"]
    },
    tags=["system", "io",'builtin'],
    timeout=5.0
)
def open_file(url: str):
    # 简单判断是否URL
    if re.match(r"^[a-zA-Z][a-zA-Z0-9+.-]*://", url):
        webbrowser.open(url)
        return f"Opened URL: {url}"
    p = os.path.abspath(os.path.expanduser(url))
    if not os.path.exists(p):
        raise FileNotFoundError(p)
    if sys.platform.startswith("win"):
        os.startfile(p)  # type: ignore
    elif sys.platform == "darwin":
        subprocess.check_call(["open", p])
    else:
        subprocess.check_call(["xdg-open", p])
    return f"Opened path: {p}"

@registry.tool(
    name="sys_time",
    description="Get current date/time",
    parameters={
        "type": "object",
        "properties": {"type": {"type": "string", "enum": ["date", "time", "datetime"]}},
        "required": ["type"]
    },
    tags=["utility",'builtin'],
    timeout=2.0
)
def sys_time(type: str):
    import datetime
    now = datetime.datetime.now()
    if type == "date": return now.strftime("%Y-%m-%d")
    if type == "time": return now.strftime("%H:%M:%S")
    return now.strftime("%Y-%m-%d %H:%M:%S")

@registry.tool(
    name="python_cmd",
    description="A Python interpreter that will run the code you provide.Only print() output is returned. Ensure the code is safe.",
    parameters={
        "type": "object",
        "properties": {
            "code": {"type": "string", "minLength": 1},
            "timeout_sec": {"type": "number", "minimum": 0, "default": 6000}
        },
        "required": ["code"]
    },
    tags=["dangerous", "dev",'builtin'],
    timeout=6000,
    permissions=["sandbox"]
)

def python_cmd(code: str, timeout_sec: float = 6000):
    """Python命令执行函数，捕获print输出"""
    import contextlib
    from io import StringIO
    code = code.replace('```python', '').replace('```', '').replace('`', '')
    print(f"Executing code: {code}")
    output_buffer = StringIO()
    try:
        with contextlib.redirect_stdout(output_buffer):
            exec(code, {})  # 在独立环境中执行代码
        captured_output = output_buffer.getvalue().strip()
        if len(captured_output)>10000:
            return '执行完成，响应过长。'+captured_output[0:10000]+"\nWARNING:\ntoo many output!\nthe first 10000 words are kept and the rest is abandoned."
        if len(captured_output) == 0:
            return '执行完成，无打印内容'
        return f"执行完成，打印内容：\n{captured_output}"
    except Exception as e:
        return f"执行失败：{str(e)}"


@registry.tool(
    name="web_search",
    description="A simple web search based on web crawlers.",
    parameters={
        "type": "object",
        "properties": {
            "keywords": {"type": "string", "minLength": 1},
            'engine':{'type':'string',"enum":['bing','baidu'], "default":'bing'},
            "timeout_sec": {"type": "number", "minimum": 0, "default": 40},
            'result_num':{'type':'integer',"default":10,'maximum':10}
        },
        "required": ["keywords"]
    },
    tags=["search", "web"],
    timeout=40
)

def web_search(keywords: str,engine='bing',timeout_sec: float = 40,result_num=10):
    """联网搜索"""
   
    # 根据引擎创建搜索器
    if engine == "baidu":
        from utils.online_rag import baidu_search
        searcher = baidu_search()
        searcher.TOTAL_SEARCH_RESULTS = result_num
    elif engine == "bing":
        from utils.online_rag import bing_search
        searcher = bing_search()
    try:
        result = searcher.get_search_results(query=keywords)
        return result[:result_num]
    except Exception as e:
        return f'web_search failed: Interal - {e} '


# -----------------------
# 全局单例访问器
# -----------------------
_REGISTRY_SINGLETON: ToolRegistry = registry

def get_tool_registry() -> ToolRegistry:
    global _REGISTRY_SINGLETON
    if _REGISTRY_SINGLETON is None:
        _REGISTRY_SINGLETON = ToolRegistry()
    return _REGISTRY_SINGLETON


# -----------------------
# 数据模型：ToolsListModel
# -----------------------
class ToolsListModel(QtCore.QAbstractListModel):
    """
    列出所有工具并支持复选激活。
    角色：
      - name、description、tags、timeout、is_async、permissions、parameters、source、checked
    """

    NameRole = QtCore.Qt.ItemDataRole.UserRole + 1
    DescriptionRole = QtCore.Qt.ItemDataRole.UserRole + 2
    TagsRole = QtCore.Qt.ItemDataRole.UserRole + 3
    TimeoutRole = QtCore.Qt.ItemDataRole.UserRole + 4
    IsAsyncRole = QtCore.Qt.ItemDataRole.UserRole + 5
    PermissionsRole = QtCore.Qt.ItemDataRole.UserRole + 6
    ParametersRole = QtCore.Qt.ItemDataRole.UserRole + 7
    SourceRole = QtCore.Qt.ItemDataRole.UserRole + 8
    CheckedRole = QtCore.Qt.ItemDataRole.UserRole + 9

    selectionChanged = QtCore.pyqtSignal(list)  # 发出当前选中（激活）的工具名列表

    def __init__(self, parent=None):
        super().__init__(parent)
        self._registry = get_tool_registry()
        self._items: _t.List[dict] = []
        self._active_set: _t.Set[str] = set()

    def roleNames(self):
        return {
            QtCore.Qt.ItemDataRole.DisplayRole: b"display",
            QtCore.Qt.ItemDataRole.ToolTipRole: b"tooltip",
            self.NameRole: b"name",
            self.DescriptionRole: b"description",
            self.TagsRole: b"tags",
            self.TimeoutRole: b"timeout",
            self.IsAsyncRole: b"is_async",
            self.PermissionsRole: b"permissions",
            self.ParametersRole: b"parameters",
            self.SourceRole: b"source",
            self.CheckedRole: b"checked",
        }

    def rowCount(self, parent=QtCore.QModelIndex()):
        if parent.isValid():
            return 0
        return len(self._items)

    def data(self, index, role=QtCore.Qt.ItemDataRole.DisplayRole):
        if not index.isValid():
            return None
        item = self._items[index.row()]
        if role == QtCore.Qt.ItemDataRole.DisplayRole:
            return item["name"]
        if role == QtCore.Qt.ItemDataRole.ToolTipRole:
            return item.get("description", "") or item["name"]
        if role == self.NameRole:
            return item["name"]
        if role == self.DescriptionRole:
            return item.get("description", "")
        if role == self.TagsRole:
            return item.get("tags", [])
        if role == self.TimeoutRole:
            return item.get("timeout", 30.0)
        if role == self.IsAsyncRole:
            return item.get("is_async", False)
        if role == self.PermissionsRole:
            return item.get("permissions", [])
        if role == self.ParametersRole:
            return item.get("parameters", {})
        if role == self.SourceRole:
            return item.get("source", "")
        if role == self.CheckedRole:
            return item.get("checked", False)
        if role == QtCore.Qt.ItemDataRole.CheckStateRole:
            return QtCore.Qt.CheckState.Checked if item.get("checked", False) else QtCore.Qt.CheckState.Unchecked
        return None

    def flags(self, index):
        if not index.isValid():
            return QtCore.Qt.NoItemFlags
        base = QtCore.Qt.ItemFlag.ItemIsEnabled | QtCore.Qt.ItemFlag.ItemIsSelectable | QtCore.Qt.ItemFlag.ItemIsUserCheckable
        return base

    def setData(self, index, value, role=QtCore.Qt.ItemDataRole.EditRole):
        if not index.isValid():
            return False
        if role in (QtCore.Qt.ItemDataRole.CheckStateRole, self.CheckedRole):
            checked = bool(value == QtCore.Qt.CheckState.Checked or value is True)
            name = self._items[index.row()]["name"]
            self._items[index.row()]["checked"] = checked
            if checked:
                self._active_set.add(name)
            else:
                self._active_set.discard(name)
            self.dataChanged.emit(index, index, [QtCore.Qt.ItemDataRole.CheckStateRole, self.CheckedRole])
            self.selectionChanged.emit(self.get_selected_functions())
            return True
        return False

    def refresh_from_registry(self, available_names: _t.Optional[_t.List[str]] = None):
        """
        从全局 registry 重新加载工具列表。
        available_names: 可选，只显示指定工具名集合（否则显示全部）。
        """
        tools = self._registry.list()
        if available_names is not None:
            allow = set(available_names)
            tools = [t for t in tools if t.name in allow]

        items = []
        for t in tools:
            # 识别来源（内置/用户）
            mod = getattr(t.handler, "__module__", "") or ""
            if mod.startswith("utils.functions"):
                source = "user"
            else:
                source = mod or "builtin"
            name = t.name
            items.append({
                "name": name,
                "description": t.description or "",
                "tags": list(getattr(t, "tags", []) or []),
                "timeout": getattr(t, "timeout", 30.0),
                "is_async": getattr(t, "is_async", False),
                "permissions": list(getattr(t, "permissions", []) or []),
                "parameters": getattr(t, "parameters", {}) or {},
                "source": source,
                "checked": name in self._active_set,
            })

        self.beginResetModel()
        self._items = items
        self.endResetModel()
        # 刷新后同步一次选择变更
        self.selectionChanged.emit(self.get_selected_functions())

    def set_active_tools(self, names: _t.List[str]):
        """
        设置初始激活集合。调用后请执行 refresh_from_registry() 以应用到视图。
        """
        self._active_set = set(names or [])
        # 更新现有 items 的 checked 状态（若已加载）
        if self._items:
            for i, it in enumerate(self._items):
                new_checked = it["name"] in self._active_set
                if it.get("checked") != new_checked:
                    it["checked"] = new_checked
                    idx = self.index(i)
                    self.dataChanged.emit(idx, idx, [QtCore.Qt.ItemDataRole.CheckStateRole, self.CheckedRole])
            self.selectionChanged.emit(self.get_selected_functions())

    def get_selected_functions(self) -> _t.List[str]:
        """
        返回当前激活（勾选）的工具名列表。
        """
        # 以 _active_set 为准，同时确保存在于当前模型
        names = {it["name"] for it in self._items}
        return sorted([n for n in self._active_set if n in names])


# -----------------------
# 过滤/搜索代理：ToolsFilterProxyModel
# -----------------------
class ToolsFilterProxyModel(QtCore.QSortFilterProxyModel):
    """
    支持：
      - 文本搜索（名称、描述、标签）
      - 允许集合 allowed_names
      - 包含标签 include_tags（交集）
      - 排除标签 exclude_tags（不相交）
    """
    def __init__(self, parent=None):
        super().__init__(parent)
        self._search = ""
        self._allowed_names: _t.Optional[_t.Set[str]] = None
        self._include_tags: _t.Optional[_t.Set[str]] = None
        self._exclude_tags: _t.Optional[_t.Set[str]] = None
        self.setFilterCaseSensitivity(QtCore.Qt.CaseSensitivity.CaseInsensitive)

    # 配置接口
    def set_search_text(self, text: str):
        self._search = (text or "").strip().lower()
        self.invalidateFilter()

    def set_allowed_names(self, names: _t.Optional[_t.List[str]]):
        self._allowed_names = set(names) if names else None
        self.invalidateFilter()

    def set_include_tags(self, tags: _t.Optional[_t.List[str]]):
        self._include_tags = set(t.strip() for t in (tags or []) if t.strip())
        if not self._include_tags:
            self._include_tags = None
        self.invalidateFilter()

    def set_exclude_tags(self, tags: _t.Optional[_t.List[str]]):
        self._exclude_tags = set(t.strip() for t in (tags or []) if t.strip())
        if not self._exclude_tags:
            self._exclude_tags = None
        self.invalidateFilter()

    def filterAcceptsRow(self, source_row, source_parent):
        src = self.sourceModel()
        idx = src.index(source_row, 0, source_parent)
        name = src.data(idx, ToolsListModel.NameRole) or ""
        desc = src.data(idx, ToolsListModel.DescriptionRole) or ""
        tags = src.data(idx, ToolsListModel.TagsRole) or []

        # 允许集合过滤
        if self._allowed_names is not None and name not in self._allowed_names:
            return False

        # 标签包含过滤（至少有一个匹配）
        if self._include_tags is not None:
            if not set(tags) & self._include_tags:
                return False

        # 标签排除过滤（任一命中即排除）
        if self._exclude_tags is not None:
            if set(tags) & self._exclude_tags:
                return False

        # 文本搜索
        if self._search:
            haystack = " ".join([name, desc, " ".join(tags)]).lower()
            if self._search not in haystack:
                return False

        return True


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


# -----------------------
# 事件总线（全局）
# -----------------------
class ToolsEventBus(QtCore.QObject):
    toolsChanged    = QtCore.pyqtSignal()
    reloadStarted   = QtCore.pyqtSignal()
    reloadFinished  = QtCore.pyqtSignal(dict)
    errorOccurred   = QtCore.pyqtSignal(str)

_EVENT_BUS_SINGLETON: ToolsEventBus = None

def get_tools_event_bus() -> ToolsEventBus:
    global _EVENT_BUS_SINGLETON
    if _EVENT_BUS_SINGLETON is None:
        _EVENT_BUS_SINGLETON = ToolsEventBus()
    return _EVENT_BUS_SINGLETON

# 写个别称
get_functions_events = get_tools_event_bus

# -----------------------
# 加载索引与结果摘要
# -----------------------
@dataclass
class ModuleRecord:
    module: str
    file_path: Path
    tool_names: _t.Set[str] = field(default_factory=set)

@dataclass
class ReloadSummary:
    added: _t.List[str] = field(default_factory=list)
    removed: _t.List[str] = field(default_factory=list)
    updated: _t.List[str] = field(default_factory=list)
    failed: _t.List[str] = field(default_factory=list)
    errors: _t.List[str] = field(default_factory=list)

    def to_dict(self):
        return {
            "added": self.added,
            "removed": self.removed,
            "updated": self.updated,
            "failed": self.failed,
            "errors": self.errors,
        }


# -----------------------
# FunctionsPluginManager
# -----------------------
class FunctionsPluginManager(QtCore.QObject):
    """
    负责 utils/functions 的脚手架、文件监控、加载/重载与冲突处理。
    - 每个模块（.py 文件）导入时，记录其注册的工具名集合，便于卸载/重载。
    - 监控文件变化，防抖后自动重载。
    - 发出事件总线信号，驱动 UI 刷新。
    """

    DEFAULT_PACKAGE = "utils.functions"

    def __init__(self, package: str = None, parent=None):
        super().__init__(parent)
        self.package = package or self.DEFAULT_PACKAGE
        self._registry = get_tool_registry()
        self._event_bus = get_tools_event_bus()

        self._watcher = QtCore.QFileSystemWatcher(self)
        self._debounce = QtCore.QTimer(self)
        self._debounce.setInterval(300)
        self._debounce.setSingleShot(True)
        self._debounce.timeout.connect(self._on_debounced_reload)

        self._dir: Path = self._resolve_dir()
        self._module_records: dict[str, ModuleRecord] = {}  # fqmn -> record

        # 连接监控信号
        self._watcher.directoryChanged.connect(self._on_fs_changed)
        self._watcher.fileChanged.connect(self._on_fs_changed)

        # 确保脚手架存在，并初始化监控
        self.ensure_scaffold()
        self._start_watch()

# 将类定义放在单例函数之后，避免名称覆盖
class FunctionsPluginManager(FunctionsPluginManager):  # 继续类定义
    # 工具

    def _resolve_dir(self) -> Path:
        """
        解析 utils/functions 目录实际路径；若未安装包，默认使用 CWD 下 utils/functions。
        """
        try:
            pkg = importlib.import_module(self.package)
            # 包已存在
            dir_path = Path(next(iter(pkg.__path__)))
            return dir_path
        except ModuleNotFoundError:
            # 使用本地路径
            return Path.cwd() / self.package.replace(".", os.sep)

    def ensure_scaffold(self):
        """
        创建 utils/functions 目录及 __init__.py、functions_api.py（如不存在）。
        functions_api.py 提供 user_tool 装饰器，桥接到 get_tool_registry().tool
        """
        self._dir.mkdir(parents=True, exist_ok=True)
        init_file = self._dir / "__init__.py"
        if not init_file.exists():
            init_file.write_text("# utils.functions package\n", encoding="utf-8")

        # functions_api 提供 user_tool 简化导入
        api_file = self._dir.parent / "functions_api.py"  # utils/functions_api.py
        if not api_file.exists():
            api_code = (
                "from utils.tool_core import get_tool_registry\n"
                "def user_tool(name=None, description=None, parameters=None, **meta):\n"
                "    \"\"\"装饰器：桥接到全局 ToolRegistry 单例。\"\"\"\n"
                "    return get_tool_registry().tool(name=name, description=description, parameters=parameters, **meta)\n"
            )
            api_file.write_text(api_code, encoding="utf-8")

    def _iter_module_files(self) -> list[Path]:
        files = []
        for p in self._dir.glob("*.py"):
            if p.name == "__init__.py":
                continue
            files.append(p)
        return files

    def _start_watch(self):
        # 先清空旧监控
        try:
            for d in self._watcher.directories():
                self._watcher.removePath(d)
            for f in self._watcher.files():
                self._watcher.removePath(f)
        except Exception:
            pass
        # 添加新监控
        self._watcher.addPath(str(self._dir))
        for f in self._iter_module_files():
            self._watcher.addPath(str(f))

    def _on_fs_changed(self, path: str):
        # 文件系统变化后防抖再重载
        self._debounce.start()

    def _on_debounced_reload(self):
        self.reload_all()

    def _get_registry_tool_names(self) -> set[str]:
        try:
            return {t.name for t in self._registry.list()}
        except Exception:
            # 容错：list 失败则尝试内部属性（不建议）
            return set()

    def _remove_tools_for_module(self, fqmn: str, summary: ReloadSummary):
        rec = self._module_records.get(fqmn)
        if not rec:
            return
        for name in list(rec.tool_names):
            try:
                self._registry.remove(name)
                summary.removed.append(name)
            except Exception as e:
                summary.errors.append(f"remove {name} failed: {e}")
        rec.tool_names.clear()

    def _import_module_collect(self, fqmn: str, file_path: Path, summary: ReloadSummary):
        """
        导入模块并收集本模块新注册的工具名。
        使用前后 diff 来判断新增注册的工具名集合。
        """
        before = self._get_registry_tool_names()
        try:
            if fqmn in sys.modules:
                # reload 前先卸载，避免旧符号残留
                sys.modules.pop(fqmn, None)
            importlib.invalidate_caches()
            mod = importlib.import_module(fqmn)
        except Exception as e:
            summary.failed.append(fqmn)
            summary.errors.append(f"import {fqmn} failed: {e}")
            return

        after = self._get_registry_tool_names()
        new_tools = after - before
        rec = self._module_records.get(fqmn)
        if not rec:
            rec = ModuleRecord(module=fqmn, file_path=file_path, tool_names=set())
            self._module_records[fqmn] = rec
        rec.tool_names = set(new_tools)
        for n in new_tools:
            if n in before:
                # 理论上不会发生（差集已排除），保守处理
                summary.updated.append(n)
            else:
                summary.added.append(n)

    # 公开 API

    def initial_load(self) -> dict:
        """
        初次加载（不触发 remove），适合应用启动阶段调用。
        """
        self._event_bus.reloadStarted.emit()
        summary = ReloadSummary()
        self.ensure_scaffold()
        importlib.invalidate_caches()

        # 先确保 utils/functions 是包
        try:
            importlib.import_module(self.package)
        except ModuleNotFoundError:
            # 若不存在，创建后再导入（ensure_scaffold 已创建 __init__.py）
            try:
                importlib.import_module(self.package)
            except Exception as e:
                summary.errors.append(f"import package {self.package} failed: {e}")
                self._event_bus.reloadFinished.emit(summary.to_dict())
                return summary.to_dict()

        for f in self._iter_module_files():
            fqmn = f"{self.package}.{f.stem}"
            self._import_module_collect(fqmn, f, summary)

        # 更新监控
        self._start_watch()

        self._event_bus.reloadFinished.emit(summary.to_dict())
        if summary.added or summary.removed or summary.updated:
            self._event_bus.toolsChanged.emit()
        return summary.to_dict()

    def reload_all(self) -> dict:
        """
        热重载：检测现有模块，卸载每个模块对应的工具后再导入。
        如文件已删除，则清理记录并从注册表中移除对应工具。
        """
        self._event_bus.reloadStarted.emit()
        summary = ReloadSummary()
        self.ensure_scaffold()
        importlib.invalidate_caches()

        existing_files = {f.stem: f for f in self._iter_module_files()}
        known_modules = set(self._module_records.keys())

        # 处理删除的模块
        for fqmn in list(known_modules):
            modname = fqmn.split(".")[-1]
            if modname not in existing_files:
                # 文件被删除，移除其工具并删记录
                self._remove_tools_for_module(fqmn, summary)
                self._module_records.pop(fqmn, None)

        # 对现有文件逐个 reload
        for modname, fp in existing_files.items():
            fqmn = f"{self.package}.{modname}"
            # 先移除旧工具
            self._remove_tools_for_module(fqmn, summary)
            # 再导入并收集新增工具
            self._import_module_collect(fqmn, fp, summary)

        # 监控更新
        self._start_watch()

        self._event_bus.reloadFinished.emit(summary.to_dict())
        self._event_bus.toolsChanged.emit()
        return summary.to_dict()

    def create_tool_file_from_template(
        self,
        name: str,
        description: str = "",
        parameters: dict | None = None,
        *,
        tags: list[str] | None = None,
        permissions: list[str] | None = None,
        timeout: float | None = None,
        code_body: str | None = None,
        filename: str | None = None,
        overwrite: bool = False,
    ) -> Path:
        """
        生成一个工具文件（模板），放在 utils/functions 下。
        返回文件路径。不会自动重载，需调用 reload_all。
        """
        assert name, "Tool name required"
        parameters = parameters or {"type": "object", "properties": {}}
        tags = tags or []
        permissions = permissions or []
        timeout = 30.0 if timeout is None else timeout
        filename = filename or f"{name}.py"

        file_path = self._dir / filename
        if file_path.exists() and not overwrite:
            raise FileExistsError(f"File exists: {file_path}")

        # 模板代码
        params_json = json.dumps(parameters, ensure_ascii=False, indent=2)
        tags_list = ", ".join([json.dumps(t, ensure_ascii=False) for t in tags])
        perms_list = ", ".join([json.dumps(p, ensure_ascii=False) for p in permissions])
        code_body = code_body or (
            "    # TODO: 实现你的工具逻辑\n"
            "    # 输入参数在 kwargs 中，或按照 parameters 的属性名定义显式参数\n"
            "    return {\"echo\": kwargs}\n"
        )

        tpl = f'''# -*- coding: utf-8 -*-
"""
Auto-generated tool: {name}
"""
from utils.functions_api import user_tool

@user_tool(
    name={json.dumps(name, ensure_ascii=False)},
    description={json.dumps(description or "", ensure_ascii=False)},
    parameters={params_json},
    tags=[{tags_list}],
    timeout={timeout},
    permissions=[{perms_list}],
)
def {self._sanitize_func_name(name)}(**kwargs):
    """
    {description}
    """
{code_body}
'''
        file_path.write_text(tpl, encoding="utf-8")
        return file_path

    def _sanitize_func_name(self, name: str) -> str:
        safe = re.sub(r"[^0-9a-zA-Z_]", "_", name.strip())
        if not re.match(r"[a-zA-Z_]", safe):
            safe = f"f_{safe}"
        return safe

    def find_tool_file(self, tool_name: str) -> Path | None:
        """
        根据工具名猜测文件名（同名.py），不保证一定存在。
        """
        candidate = self._dir / f"{tool_name}.py"
        if candidate.exists():
            return candidate
        # 退化遍历：查找包含该装饰器的文件
        pattern = re.compile(rf'name\s*=\s*["\']{re.escape(tool_name)}["\']')
        for f in self._iter_module_files():
            try:
                if pattern.search(f.read_text(encoding="utf-8")):
                    return f
            except Exception:
                pass
        return None


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
      - 保存到 utils/functions 下并触发热重载
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
            QtWidgets.QMessageBox.information(self, "提示", "只能编辑用户工具（utils/functions 下的工具）")
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
            QtWidgets.QMessageBox.information(self, "提示", "只能删除用户工具（utils/functions 下的工具）")
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


