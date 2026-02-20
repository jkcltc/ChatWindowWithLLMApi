import concurrent.futures
from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Optional, Union
import json, inspect, concurrent.futures, importlib, pkgutil, time, logging, asyncio, threading
from jsonschema import Draft202012Validator, ValidationError
import os, sys, webbrowser,subprocess, re, time, json
import typing as _t
from pathlib import Path
from PyQt6 import QtCore



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

    def list(self, *,  tags: Optional[List[str]]=None) ->list:
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
        from service.web_search.online_rag import baidu_search
        searcher = baidu_search()
        searcher.TOTAL_SEARCH_RESULTS = result_num
    elif engine == "bing":
        from service.web_search.online_rag import bing_search
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
            if mod.startswith("core.tool_call.function_lib"):
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
    负责 core.tool_call.function_lib 的脚手架、文件监控、加载/重载与冲突处理。
    - 每个模块（.py 文件）导入时，记录其注册的工具名集合，便于卸载/重载。
    - 监控文件变化，防抖后自动重载。
    - 发出事件总线信号，驱动 UI 刷新。
    """

    DEFAULT_PACKAGE = "core.tool_call.function_lib"

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
        解析 core.tool_call.function_lib 目录实际路径；若未安装包，默认使用 CWD 下 core/tool_call/function_lib。
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
        创建 core/tool_call/function_lib 目录及 __init__.py、functions_api.py（如不存在）。
        functions_api.py 提供 user_tool 装饰器，桥接到 get_tool_registry().tool
        """
        self._dir.mkdir(parents=True, exist_ok=True)
        init_file = self._dir / "__init__.py"
        if not init_file.exists():
            init_file.write_text("# core.tool_call.function_lib package\n", encoding="utf-8")

        # functions_api 提供 user_tool 简化导入
        api_file = self._dir.parent / "functions_api.py"  # core/tool_call/function_lib/functions_api.py
        if not api_file.exists():
            api_code = (
                "from core.tool_call.function_lib import get_tool_registry\n"
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

        # 先确保 core.tool_call.function_lib 是包
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
        生成一个工具文件（模板），放在 core/tool_call/function_lib 下。
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
from core.tool_call.function_lib.functions_api import user_tool

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
