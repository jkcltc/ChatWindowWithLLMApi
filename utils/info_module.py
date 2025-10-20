# Created by GPT-5 & Gemini 2.5 Pro, Doc by Kimi k2
# Introduced in 0.25.3
from __future__ import annotations
from PyQt5 import QtCore, QtGui, QtWidgets
import logging
import logging.handlers
from logging import Logger
from typing import Optional, Dict, Any, Iterable
from pathlib import Path
import queue as _queue

from typing import Any, Dict, Optional, Set, Mapping, Union
class ToastBubble(QtWidgets.QWidget):
    '''
    ===========
    一个轻量级、非阻塞的 PyQt5 Toast 风格通知组件。
    功能特性
    --------
    - 无边框、半透明圆角矩形，可自定义颜色与圆角半径。
    - 可选投影，支持自定义模糊半径与偏移。
    - 平滑淡入/淡出并伴随上滑动画。
    - 可配置自动关闭时长（默认 3 秒）。
    - 可选点击关闭。
    - 支持带动画的重新定位。
    - 关闭时发射 `closed` 信号，便于后续清理。
    构造参数
    --------
    parent : QWidget, 可选
        父控件；通常留 None，使 Toast 成为顶层窗口。
    width : int, 默认 320
        Toast 窗口的固定宽度（像素）。
    bg_color : QColor, 默认 QColor(34, 34, 34, 230)
        背景颜色。
    text_color : QColor, 默认 QColor(255, 255, 255, 230)
        文字颜色。
    radius : int, 默认 10
        圆角半径（像素）。
    padding : tuple[int, int, int, int], 默认 (12, 10, 12, 10)
        内边距，顺序同 CSS：左、上、右、下。
    shadow : bool, 默认 True
        是否绘制投影。
    duration_ms : int, 默认 3000
        自动关闭时长（毫秒）。
    enable_click_to_close : bool, 默认 False
        若为 True，点击 Toast 立即触发淡出。
    shadow_blur : int, 默认 30
        投影模糊半径。
    shadow_offset : QPoint, 默认 QPoint(0, 6)
        投影偏移（像素）。
    公开方法
    --------
    setText(text: str)
        修改显示文本并重新计算尺寸（稳定的按宽算高）。
    setFixedWidth(w: int)
        覆盖固定宽度，并将约束同步到内部控件（稳定的按宽算高）。
    popup(end_pos: QPoint, duration_ms: int | None = None)
        在指定位置 `end_pos` 显示 Toast，带淡入动画与自动关闭计时器。
    shift_to(end_pos: QPoint, animate=True, duration=160)
        将 Toast 移动到 `end_pos`，可选滑动动画。
    fade_out()
        手动触发淡出并伴随上滑动画。
    setColors(bg_color: QColor, text_color: QColor)
        动态更新背景与文字颜色。
    信号
    ----
    closed(object)
        Toast 完成淡出动画即将隐藏并删除时发射，携带 `self` 作为参数。
    注意事项
    --------
    - 实际绘制发生在内部面板 `_panel`，顶层窗口保持透明，避免闪烁。
    - 所有动画均通过 `DeleteWhenStopped` 自动清理。
    - 为避免 Windows 下多行文本触发 setGeometry 日志，内部采用“按宽算高”的稳定几何计算，
      并在 show 前用 resize 设置最终尺寸，而非 adjustSize。
    '''
    closed = QtCore.pyqtSignal(object)

    def __init__(
        self,
        parent=None,
        width=320,
        bg_color=QtGui.QColor(34, 34, 34, 230),
        text_color=QtGui.QColor(255, 255, 255, 230),
        radius=10,
        padding=(12, 10, 12, 10),
        shadow=True,
        duration_ms=3000,
        enable_click_to_close=False,
        shadow_blur=30,
        shadow_offset=QtCore.QPoint(0, 6),
    ):
        super().__init__(parent, flags=QtCore.Qt.Tool | QtCore.Qt.FramelessWindowHint)
        self.setAttribute(QtCore.Qt.WA_ShowWithoutActivating, True)
        self.setAttribute(QtCore.Qt.WA_TranslucentBackground, True)
        self.setFocusPolicy(QtCore.Qt.NoFocus)

        self._bg = QtGui.QColor(bg_color)
        self._text = QtGui.QColor(text_color)
        self._radius = radius
        self._padding = padding
        self._default_duration = duration_ms
        self._closing = False

        self._move_anim = None
        self._in_anim = None
        self._out_anim = None

        # 计算阴影在四周需要的安全边距
        self._shadow_blur = shadow_blur
        self._shadow_offset = QtCore.QPoint(shadow_offset)
        sx, sy = self._shadow_offset.x(), self._shadow_offset.y()
        lpad = self._shadow_blur
        rpad = self._shadow_blur
        tpad = max(0, self._shadow_blur - max(0, sy))
        bpad = self._shadow_blur + max(0, sy)
        self._shadow_margins = (lpad, tpad, rpad, bpad)

        # 外层布局：仅用于留出阴影空间
        outer = QtWidgets.QVBoxLayout(self)
        outer.setContentsMargins(*self._shadow_margins)
        outer.setSpacing(0)

        # 内层内容面板：在这里画背景和圆角、并挂阴影
        self._panel = QtWidgets.QWidget(self)
        self._panel.setObjectName("toast_panel")
        outer.addWidget(self._panel)

        # 阴影挂到 panel
        if shadow:
            eff = QtWidgets.QGraphicsDropShadowEffect(self._panel)
            eff.setBlurRadius(self._shadow_blur)
            eff.setOffset(self._shadow_offset)
            eff.setColor(QtGui.QColor(0, 0, 0, 120))
            self._panel.setGraphicsEffect(eff)

        # panel 的布局：放 label
        self._box = QtWidgets.QVBoxLayout(self._panel)
        self._box.setContentsMargins(*self._padding)
        self._box.setSpacing(6)

        self._label = QtWidgets.QLabel(self._panel)
        self._label.setWordWrap(True)
        self._label.setTextInteractionFlags(QtCore.Qt.NoTextInteraction)
        self._label.setStyleSheet(
            "color: rgba(%d,%d,%d,%d);" % (self._text.red(), self._text.green(), self._text.blue(), self._text.alpha())
        )
        self._box.addWidget(self._label)

        # 在 panel 上用样式表绘制圆角背景
        self._apply_panel_style()

        # 宽度设置：外层窗口固定宽度，panel 宽度 = 外层 - 阴影左右边距
        self.setFixedWidth(width)

        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents, not enable_click_to_close)
        if enable_click_to_close:
            self.mousePressEvent = lambda e: self.fade_out()

    # ---------------- 尺寸计算（按宽算高，稳定几何） ----------------

    def _apply_panel_style(self):
        self._panel.setStyleSheet(
            """
            #toast_panel {
                background-color: rgba(%d,%d,%d,%d);
                border-radius: %dpx;
            }
            """
            % (self._bg.red(), self._bg.green(), self._bg.blue(), self._bg.alpha(), self._radius)
        )

    def _label_width_for_outer(self, outer_w: int) -> int:
        sl, st, sr, sb = self._shadow_margins
        inner_w = max(60, outer_w - sl - sr)
        l, t, r, b = self._padding
        return max(1, inner_w - l - r)

    def _height_for_width(self, outer_w: int) -> int:
        # 计算给定总宽度下的总高度（包含 padding 与 shadow）
        lw = self._label_width_for_outer(outer_w)
        lh = self._label.heightForWidth(lw)
        if lh < 0:
            fm = self._label.fontMetrics()
            br = fm.boundingRect(0, 0, lw, 10_000, QtCore.Qt.TextWordWrap, self._label.text() or "")
            lh = br.height()

        l, t, r, b = self._padding
        sl, st, sr, sb = self._shadow_margins
        panel_h = t + lh + b
        return st + panel_h + sb

    def _sync_size(self, outer_w: int | None = None):
        if outer_w is None:
            outer_w = max(self.width(), self.minimumWidth(), 60)
        h = self._height_for_width(outer_w)
        # 用 resize，而不是 adjustSize，避免隐藏时对几何“拍板”
        self.resize(outer_w, h)

    def sizeHint(self):
        w = max(self.width(), self.minimumWidth(), 60)
        return QtCore.QSize(w, self._height_for_width(w))

    # ---------------- 公共 API ----------------

    def setText(self, text: str):
        self._label.setText(text)
        # 文本变更后按当前宽度同步几何
        self._sync_size()

    def setFixedWidth(self, w: int):
        # 外层窗口固定宽度
        super().setFixedWidth(w)

        # panel 和 label 实际可用宽度
        sl, st, sr, sb = self._shadow_margins
        inner_w = max(60, w - sl - sr)
        self._panel.setFixedWidth(inner_w)

        self._label.setFixedWidth(self._label_width_for_outer(w))

        # 同步整体尺寸，避免 show 时几何被平台“修正”
        self._sync_size(w)

    # 顶层不再绘制任何内容，避免 layered 更新问题
    def paintEvent(self, e: QtGui.QPaintEvent):
        return

    def popup(self, end_pos: QtCore.QPoint, duration_ms=None):
        if duration_ms is None:
            duration_ms = self._default_duration

        # 确保尺寸已是最终值（基于 width 和文本），避免 show 时几何被平台“修正”
        self._sync_size()

        self.move(end_pos)
        self.setWindowOpacity(0.0)
        self.show()

        anim_op = QtCore.QPropertyAnimation(self, b"windowOpacity", self)
        anim_op.setDuration(220)
        anim_op.setStartValue(0.0)
        anim_op.setEndValue(1.0)
        anim_op.setEasingCurve(QtCore.QEasingCurve.OutCubic)

        self._in_anim = anim_op
        anim_op.start(QtCore.QAbstractAnimation.DeleteWhenStopped)

        QtCore.QTimer.singleShot(int(duration_ms), self.fade_out)

    def shift_to(self, end_pos: QtCore.QPoint, animate=True, duration=160):
        if not self.isVisible() or self._closing:
            return

        if not animate:
            self.move(end_pos)
            return

        if not self._move_anim:
            self._move_anim = QtCore.QPropertyAnimation(self, b"pos", self)
            self._move_anim.setEasingCurve(QtCore.QEasingCurve.OutCubic)

        self._move_anim.stop()
        self._move_anim.setDuration(duration)
        self._move_anim.setStartValue(self.pos())
        self._move_anim.setEndValue(end_pos)
        self._move_anim.start()

    def fade_out(self):
        if self._closing:
            return
        self._closing = True

        anim_op = QtCore.QPropertyAnimation(self, b"windowOpacity", self)
        anim_op.setDuration(260)
        anim_op.setStartValue(self.windowOpacity())
        anim_op.setEndValue(0.0)

        anim_pos = QtCore.QPropertyAnimation(self, b"pos", self)
        anim_pos.setDuration(260)
        anim_pos.setStartValue(self.pos())
        anim_pos.setEndValue(self.pos() - QtCore.QPoint(0, 10))
        anim_pos.setEasingCurve(QtCore.QEasingCurve.OutCubic)

        group = QtCore.QParallelAnimationGroup(self)
        group.addAnimation(anim_op)
        group.addAnimation(anim_pos)
        self._out_anim = group
        group.finished.connect(self._on_closed)
        group.start(QtCore.QAbstractAnimation.DeleteWhenStopped)

    def _on_closed(self):
        try:
            self.hide()
        except Exception:
            pass
        self.closed.emit(self)
        self.deleteLater()

    def setColors(self, bg_color: QtGui.QColor, text_color: QtGui.QColor):
        self._bg = QtGui.QColor(bg_color)
        self._text = QtGui.QColor(text_color)
        self._label.setStyleSheet(
            "color: rgba(%d,%d,%d,%d);" % (self._text.red(), self._text.green(), self._text.blue(), self._text.alpha())
        )
        self._apply_panel_style()
        self.update()


# --------- 子类示例：成功、警告、错误提示 ----------
class SuccessToast(ToastBubble):
    def __init__(self, parent=None, width=320, duration_ms=2600):
        super().__init__(
            parent=parent,
            width=width,
            bg_color=QtGui.QColor(28, 120, 83, 235),
            text_color=QtGui.QColor(255, 255, 255, 240),
            radius=10,
            duration_ms=duration_ms,
            shadow=True,
        )


class WarningToast(ToastBubble):
    def __init__(self, parent=None, width=320, duration_ms=3500):
        super().__init__(
            parent=parent,
            width=width,
            bg_color=QtGui.QColor(216, 144, 0, 235),  # Amber color
            text_color=QtGui.QColor(255, 255, 255, 240),
            radius=10,
            duration_ms=duration_ms,
            shadow=True,
        )


class ErrorToast(ToastBubble):
    def __init__(self, parent=None, width=320, duration_ms=5000):
        super().__init__(
            parent=parent,
            width=width,
            bg_color=QtGui.QColor(180, 40, 40, 235),  # Dark red color
            text_color=QtGui.QColor(255, 255, 255, 240),
            radius=10,
            duration_ms=duration_ms,
            shadow=True,
        )


# --------- 管理器：从右下角堆叠/顶起 ----------
class ToastManager(QtCore.QObject):
    """
    ToastManager
    ============
    基于 Qt 的通知管理器，可将非模态的 Toast 气泡固定在任意 QWidget 的右下角。
    气泡自下而上垂直堆叠，当锚点窗口移动、调整大小、显示或窗口状态变化时自动重排。

    功能特性
    --------
    - 级别感知：通过字符串级别（“info”、“success”、“warning”、“error”）映射到具体的
      `ToastBubble` 子类。
    - 运行时注册：通过 `registerBubbleClass()` 动态添加或覆盖级别与类的映射。
    - 自动溢出处理：仅保留最新的 `max_visible` 个气泡，旧气泡自动淡出。
    - 可配置几何：宽度、边距、间距、最大可见数量均可通过 `setOptions()` 实时调整。
    - 流畅动画：气泡滑入定位，淡出优雅。

    用法示例
    --------
    >>> manager = ToastManager(my_widget)
    >>> manager.show("文件已保存", level="success")
    >>> manager.show("磁盘空间不足", level="warning", duration_ms=5000)

    公开 API
    --------
    show(text, level="info", duration_ms=None)
        创建并显示一条指定消息与级别的 Toast 气泡，返回创建的气泡实例。
    registerBubbleClass(level, cls)
        为新的或已有级别字符串注册自定义 `ToastBubble` 子类。
    setOptions(width=None, margin=None, spacing=None, max_visible=None)
        更新布局参数并重新排列可见气泡。

    注意事项
    --------
    - 管理器会在锚点控件上安装事件过滤器，以响应几何变化。
    - 气泡以锚点控件为父对象，确保正确的层级与生命周期管理。
    """

    def __init__(
        self,
        anchor_widget: QtWidgets.QWidget,
        width=320,
        margin=12,
        spacing=8,
        max_visible=6,
    ):
        super().__init__(anchor_widget)
        self._anchor = anchor_widget
        self._width = width
        self._margin = margin
        self._spacing = spacing
        self._max_visible = max_visible
        self._bubble_classes = {
            "info": ToastBubble,
            "success": SuccessToast,
            "warning": WarningToast,
            "error": ErrorToast,
        }

        self._toasts = []
        self._anchor.installEventFilter(self)

    def registerBubbleClass(self, level: str, cls: type):
        """为给定 level 注册自定义 ToastBubble 子类。"""
        if issubclass(cls, ToastBubble):
            self._bubble_classes[level.lower()] = cls
        else:
            raise TypeError("The provided class must be a subclass of ToastBubble.")

    def show(self, text: str, level: str = "info", duration_ms: int = None):
        """
        创建并显示一条 Toast。
        Args:
            text: 显示文本。
            level: 'info'|'success'|'warning'|'error'。
            duration_ms: 覆盖时长；None 则用对应类的默认。
        """
        level = level.lower()
        bubble_cls = self._bubble_classes.get(level, self._bubble_classes["info"])

        # 不在此处传入 duration；popup() 会用传入的或类默认值。
        bubble = bubble_cls(parent=self._anchor, width=self._width)
        bubble.setText(text)
        bubble.closed.connect(self._on_bubble_closed)

        self._toasts.insert(0, bubble)

        # 计算目标位置（内部会先 setFixedWidth 从而稳定几何）
        popup_duration = duration_ms if duration_ms is not None else bubble._default_duration

        targets = self._compute_targets()
        for i, tb in enumerate(self._toasts):
            if tb is bubble:
                tb.popup(targets[i], popup_duration)
            else:
                tb.shift_to(targets[i], animate=True)

        if self._max_visible > 0 and len(self._toasts) > self._max_visible:
            over = self._toasts[self._max_visible:]
            for tb in over:
                tb.fade_out()

        # 保险：在进入事件循环后再对齐一次（处理 DPI/字体回退导致的极少数像素误差）
        QtCore.QTimer.singleShot(0, lambda: self._reflow(animated=False))

        return bubble

    def eventFilter(self, obj, event):
        if obj is self._anchor and event.type() in (
            QtCore.QEvent.Move,
            QtCore.QEvent.Resize,
            QtCore.QEvent.Show,
            QtCore.QEvent.WindowStateChange,
        ):
            self._reflow(animated=False)
        return super().eventFilter(obj, event)

    def _on_bubble_closed(self, bubble):
        try:
            self._toasts.remove(bubble)
        except ValueError:
            pass
        self._reflow(animated=True)

    def _shadow_margins_of(self, tb):
        # 兼容性：没有该属性就当 0
        if hasattr(tb, "_shadow_margins"):
            l, t, r, b = tb._shadow_margins
            return l, t, r, b
        return 0, 0, 0, 0

    def _compute_targets(self):
        br_global = self._anchor.mapToGlobal(self._anchor.rect().bottomRight())
        right = br_global.x() - self._margin    # 右侧对齐基准（内容面板的右边）
        bottom = br_global.y() - self._margin   # 底部对齐基准（内容面板的底边）

        targets = []
        y_cursor = bottom
        for tb in self._toasts:
            tb.setFixedWidth(self._width)
            # 不再调用 adjustSize；用稳定的 sizeHint（按宽算高）
            W = tb.width()
            H = tb.sizeHint().height()
            l, t, r, b = self._shadow_margins_of(tb)

            # 让“内容面板”的右、下分别对齐到 right/bottom
            x = right - (W - r)
            y = y_cursor - (H - b)
            targets.append(QtCore.QPoint(x, y))

            # 下一条的“内容面板底”= 本条“内容面板顶” - spacing
            panel_h = H - t - b
            y_cursor -= (panel_h + self._spacing)

        return targets

    def _reflow(self, animated=True):
        targets = self._compute_targets()
        for tb, pos in zip(self._toasts, targets):
            tb.shift_to(pos, animate=animated)

    def setOptions(self, width=None, margin=None, spacing=None, max_visible=None):
        if width is not None:
            self._width = width
        if margin is not None:
            self._margin = margin
        if spacing is not None:
            self._spacing = spacing
        if max_visible is not None:
            self._max_visible = max_visible
        self._reflow(animated=False)

# --------- Log管理器 ----------
# 预定义 SUCCESS 等级（介于 INFO 与 WARNING 之间）
SUCCESS = 25
logging.addLevelName(SUCCESS, "SUCCESS")

class LogManager:
    """
    LogManager
    ==========
    基于 Python logging 的日志管理器。提供字符串级别到具体日志级别的映射，
    支持运行时扩展级别、控制台/文件输出、文件轮转以及可选的异步写入。

    功能特性
    --------
    - 级别感知：通过字符串级别（“debug”、“info”、“success”、“warning”、“error”）
      映射到 `logging` 的数值等级（其中 `success` 为自定义等级 25）。
    - 运行时注册：通过 `registerLevel()` 动态添加新的字符串级别（并注册到 logging）。
    - 输出配置：支持控制台与文件双通道输出，文件可按大小轮转。
    - 异步写入：可选 QueueHandler/QueueListener，降低 UI/主线程阻塞。
    - 便捷 API：`log()` 通用入口，亦提供 `debug()/info()/success()/warning()/error()` 便捷方法。
    - 与 InfoManager 的关系：可被未来的 `InfoManager` 作为子组件持有与协调（本类独立可用）。

    用法示例
    --------
    >>> log = LogManager(name="myapp", enable_console=True, file_path="logs/app.log",
    ...                  rotate_max_bytes=2_000_000, rotate_backup_count=3, async_mode=True)
    >>> log.info("应用启动")
    >>> log.success("文件已保存")
    >>> log.warning("磁盘空间不足")
    >>> log.error("写入失败", extra={"file": "data.bin"})
    >>> log.debug("调试信息", extra={"step": 2})

    公开 API
    --------
    log(msg, level="info", *, exc_info=None, extra=None, stacklevel=2)
        以指定字符串级别写日志。
    debug/info/success/warning/error(msg, *, exc_info=None, extra=None, stacklevel=2)
        各级别便捷方法。
    registerLevel(level, numeric=None)
        注册新的字符串级别（若 numeric 为空，将自动分配一个未使用的等级值）。
    setOptions(level=None, fmt=None, datefmt=None, enable_console=None,
               file_path=None, rotate_max_bytes=None, rotate_backup_count=None,
               async_mode=None)
        动态更新配置并重建 handler。
    getLogger()
        获取底层 logger，以便与原生 `logging` 生态配合。
    close()
        关闭队列监听器与已创建的 handler。

    注意事项
    --------
    - `success` 为自定义等级（25），多数日志查看器/处理链可正常使用，但若有外部统一化处理，
      请确保注册了该等级。
    - `async_mode=True` 时使用队列异步转发，注意在退出前调用 `close()` 以确保缓冲完整落盘。
    """

    def __init__(
        self,
        name: str = "app",
        *,
        level: str | int = "debug",
        enable_console: bool = True,
        file_path: str | Path | None = None,
        rotate_max_bytes: int = 5_000_000,
        rotate_backup_count: int = 5,
        fmt: str = "[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt: str = "%Y-%m-%d %H:%M:%S",
        async_mode: bool = False,
    ) -> None:
        self._logger: Logger = logging.getLogger(name)
        self._logger.propagate = False  # 独立管理，不向根 logger 传播

        # 字符串级别 -> 数值等级映射
        self._level_map: Dict[str, int] = {
            "debug": logging.DEBUG,
            "info": logging.INFO,
            "success": SUCCESS,
            "warning": logging.WARNING,
            "error": logging.ERROR,
        }

        # 运行时状态
        self._enable_console = enable_console
        self._file_path: Optional[Path] = Path(file_path).resolve() if file_path else None
        self._rotate_max_bytes = int(rotate_max_bytes)
        self._rotate_backup_count = int(rotate_backup_count)
        self._fmt = fmt
        self._datefmt = datefmt
        self._async_mode = bool(async_mode)

        # 异步相关
        self._queue: Optional[_queue.Queue] = None
        self._queue_listener: Optional[logging.handlers.QueueListener] = None

        # 初始化等级与 Handler
        self._set_logger_level(level)
        self._rebuild_handlers()

    # -------------------- 公共 API --------------------

    def log(
        self,
        msg: str,
        level: str = "info",
        *,
        exc_info: Any = None,
        extra: Optional[Dict[str, Any]] = None,
        stacklevel: int = 2,
    ) -> None:
        num = self._normalize_level(level)
        self._logger.log(num, msg, exc_info=exc_info, extra=extra or {}, stacklevel=stacklevel)

    def debug(self, msg: str, *, exc_info: Any = None, extra: Optional[Dict[str, Any]] = None, stacklevel: int = 2) -> None:
        self.log(msg, "debug", exc_info=exc_info, extra=extra, stacklevel=stacklevel)

    def info(self, msg: str, *, exc_info: Any = None, extra: Optional[Dict[str, Any]] = None, stacklevel: int = 2) -> None:
        self.log(msg, "info", exc_info=exc_info, extra=extra, stacklevel=stacklevel)

    def success(self, msg: str, *, exc_info: Any = None, extra: Optional[Dict[str, Any]] = None, stacklevel: int = 2) -> None:
        self.log(msg, "success", exc_info=exc_info, extra=extra, stacklevel=stacklevel)

    def warning(self, msg: str, *, exc_info: Any = None, extra: Optional[Dict[str, Any]] = None, stacklevel: int = 2) -> None:
        self.log(msg, "warning", exc_info=exc_info, extra=extra, stacklevel=stacklevel)

    def error(self, msg: str, *, exc_info: Any = None, extra: Optional[Dict[str, Any]] = None, stacklevel: int = 2) -> None:
        self.log(msg, "error", exc_info=exc_info, extra=extra, stacklevel=stacklevel)

    def registerLevel(self, level: str, numeric: Optional[int] = None) -> int:
        """
        注册自定义字符串级别，并返回其数值等级。
        若未指定 numeric，将自动分配一个未使用的等级值（尝试在 INFO 与 WARNING 间）。
        """
        key = level.strip().lower()
        if key in self._level_map:
            return self._level_map[key]

        if numeric is None:
            candidate = 25
            used = set(self._level_map.values()) | set(logging._nameToLevel.values())
            while candidate in used and candidate < logging.WARNING:
                candidate += 1
            if candidate in used:
                candidate = max(used) + 1
            numeric = candidate

        numeric = int(numeric)
        self._level_map[key] = numeric
        logging.addLevelName(numeric, key.upper())
        return numeric

    def setOptions(
        self,
        *,
        level: str | int | None = None,
        fmt: Optional[str] = None,
        datefmt: Optional[str] = None,
        enable_console: Optional[bool] = None,
        file_path: str | Path | None | object = None,  # 允许明确传入 None 以移除文件输出
        rotate_max_bytes: Optional[int] = None,
        rotate_backup_count: Optional[int] = None,
        async_mode: Optional[bool] = None,
    ) -> None:
        """
        更新配置并重建输出通道（必要时）。
        仅对传入的参数生效，未提供的参数保持不变。
        """
        need_rebuild = False

        if level is not None:
            self._set_logger_level(level)

        if fmt is not None:
            self._fmt = fmt
            need_rebuild = True

        if datefmt is not None:
            self._datefmt = datefmt
            need_rebuild = True

        if enable_console is not None and enable_console != self._enable_console:
            self._enable_console = bool(enable_console)
            need_rebuild = True

        if file_path is not None or file_path is None:
            # 显式 None 表示移除文件输出
            new_path = Path(file_path).resolve() if isinstance(file_path, (str, Path)) else None
            if (new_path or None) != self._file_path:
                self._file_path = new_path
                need_rebuild = True

        if rotate_max_bytes is not None:
            self._rotate_max_bytes = int(rotate_max_bytes)
            if self._file_path:
                need_rebuild = True

        if rotate_backup_count is not None:
            self._rotate_backup_count = int(rotate_backup_count)
            if self._file_path:
                need_rebuild = True

        if async_mode is not None and bool(async_mode) != self._async_mode:
            self._async_mode = bool(async_mode)
            need_rebuild = True

        if need_rebuild:
            self._rebuild_handlers()

    def getLogger(self) -> Logger:
        return self._logger

    def close(self) -> None:
        """停止队列监听并关闭所有 handler。"""
        try:
            if self._queue_listener:
                self._queue_listener.stop()
                self._queue_listener = None
        except Exception:
            pass

        # 关闭并移除 logger handlers
        for h in list(self._logger.handlers):
            try:
                h.flush()
                h.close()
            except Exception:
                pass
            finally:
                self._logger.removeHandler(h)

        self._queue = None

    # -------------------- 内部实现 --------------------

    def _normalize_level(self, level: str | int) -> int:
        if isinstance(level, int):
            return level
        key = str(level).strip().lower()
        if key not in self._level_map:
            raise ValueError(f"未知日志级别: {level!r}. 可用: {sorted(self._level_map.keys())}")
        return self._level_map[key]

    def _set_logger_level(self, level: str | int) -> None:
        lvl = self._normalize_level(level) if isinstance(level, str) else int(level)
        self._logger.setLevel(lvl)

    def _make_formatter(self) -> logging.Formatter:
        return logging.Formatter(self._fmt, self._datefmt)

    def _build_target_handlers(self) -> Iterable[logging.Handler]:
        fmt = self._make_formatter()
        handlers: list[logging.Handler] = []

        if self._enable_console:
            ch = logging.StreamHandler()
            ch.setLevel(logging.NOTSET)  # 使用 logger 的 level 控制
            ch.setFormatter(fmt)
            handlers.append(ch)

        if self._file_path:
            self._file_path.parent.mkdir(parents=True, exist_ok=True)
            fh = logging.handlers.RotatingFileHandler(
                self._file_path,
                maxBytes=self._rotate_max_bytes,
                backupCount=self._rotate_backup_count,
                encoding="utf-8",
            )
            fh.setLevel(logging.NOTSET)
            fh.setFormatter(fmt)
            handlers.append(fh)

        return handlers

    def _rebuild_handlers(self) -> None:
        # 清理旧的
        self.close()

        targets = list(self._build_target_handlers())

        if self._async_mode and targets:
            self._queue = _queue.Queue(-1)
            qh = logging.handlers.QueueHandler(self._queue)
            self._logger.addHandler(qh)
            self._queue_listener = logging.handlers.QueueListener(self._queue, *targets, respect_handler_level=True)
            self._queue_listener.start()
        else:
            for h in targets:
                self._logger.addHandler(h)

# --------- 模块管理器 ----------
class InfoManager:
    """
    InfoManager
    ===========
    面向 UI 与日志的统一信息管理器。内部协调 LogManager 与 ToastManager，
    根据路由策略将消息写入日志、弹出 toast，或两者同时进行。

    适用场景
    --------
    - 在 UI 工程中统一“日志 + 及时反馈”的信息出口
    - 根据消息级别自动决定是否弹出气泡
    - 动态调整 toast 布局与日志输出策略

    默认路由策略
    ------------
    - debug: 仅写日志，不弹 toast
    - info/success/warning/error: 写日志 + 弹 toast

    公开 API
    --------
    notify(text, level="info", *, duration_ms=None, toast=None, log=True,
           extra=None, exc_info=None, stacklevel=2) -> Optional[object]
        统一信息出口。toast=None 表示使用路由策略；显式 True/False 可覆盖。
        返回创建的 toast 实例（若有），否则为 None。
    log(msg, level="info", *, exc_info=None, extra=None, stacklevel=2) -> None
        仅写日志（透传给 LogManager）。
    show(text, level="info", duration_ms=None) -> object
        仅弹 toast（透传给 ToastManager）。
    setToastAnchor(widget) / setToastOptions(...) / setLogOptions(...)
        运行时配置。
    setRouting(*, toast_levels=None, level_durations=None)
        更新“哪些级别弹 toast”与“级别默认时长”。
    registerToastBubbleClass(level, cls)
        运行时注册/覆盖 level -> ToastBubble 子类映射（透传）。
    registerLogLevel(level, numeric=None)
        运行时注册/覆盖字符串日志级别（透传）。
    getLogger() -> logging.Logger
        获取底层 logger。
    close() -> None
        关闭日志队列监听器与 handler（如果启用了异步日志）。

    注意
    ----
    - 若未设置锚点（anchor），则不会弹出 toast，只写日志。
    - 如需从工作线程安全地显示 UI toast，请在调用方确保切换到 UI 线程。
      （本类不强制做线程切换，以保持简洁与零依赖）
    """

    # 默认哪些级别会弹出 toast
    DEFAULT_TOAST_LEVELS: Set[str] = {"info","success", "warning", "error"}

    # 各级别默认展示时长（毫秒）
    DEFAULT_LEVEL_DURATIONS: Dict[str, int] = {
        "debug": 2000,
        "info": 2500,
        "success": 2500,
        "warning": 4000,
        "error": 5000,
    }

    def __init__(
        self,
        *,
        anchor_widget: Optional["object"] = None,
        log_manager: Optional["LogManager"] = None,
        toast_manager: Optional["ToastManager"] = None,
        toast_levels: Optional[Set[str]] = None,
        level_durations: Optional[Mapping[str, int]] = None,
    ) -> None:
        """
        参数
        ----
        anchor_widget : QWidget, 可选
            ToastManager 用于锚定气泡的父级控件。
            若未提供，可后续通过 `setToastAnchor` 指定。
        log_manager : LogManager, 可选
            已配置完成的 LogManager 实例。
            如省略，将在首次使用时按需创建默认实例。
        toast_manager : ToastManager, 可选
            外部构造的 ToastManager 实例。
            通常无需手动传入，除非需使用自定义实现。
        toast_levels : set[str], 可选
            触发气泡提示的日志级别集合。
            若未指定，则采用类默认配置。
        level_durations : Mapping[str, int], 可选
            各级别默认展示时长（毫秒）。
            所提供值将覆盖内置默认值。
        """
        self._anchor_widget = anchor_widget
        self._log: Optional["LogManager"] = log_manager
        self._toast: Optional["ToastManager"] = toast_manager

        self._toast_levels: Set[str] = set(toast_levels) if toast_levels else set(self.DEFAULT_TOAST_LEVELS)
        self._level_durations: Dict[str, int] = dict(self.DEFAULT_LEVEL_DURATIONS)
        if level_durations:
            self._level_durations.update(level_durations)

        # 若已提供 anchor 但未提供 toast_manager，则延迟创建（首次需要时）
        # 日志同理：如果 _log 为空，将在首次使用 notify/log 时由外部代码显式传入或自行创建。

        # 缓存的几何配置（在 toast manager 创建后再应用）
        self._pending_toast_options: Dict[str, Union[int, None]] = {}

    # -------------------------
    # 底层实例的获取与懒创建
    # -------------------------
    def _ensure_toast(self) -> Optional["ToastManager"]:
        if self._toast is not None:
            return self._toast
        if self._anchor_widget is None:
            return None
        # 创建并回放几何配置
        self._toast = ToastManager(self._anchor_widget)
        if self._pending_toast_options:
            self._toast.setOptions(**self._pending_toast_options)
        return self._toast

    def _ensure_log(self) -> "LogManager":
        if self._log is None:
            # 为了不绑定具体构造签名，尽量只用最小参数。
            # 如果你的 LogManager 需要 name 等参数，请在外部先构造再传入。
            self._log = LogManager()  # 依照你的实现，通常会有合理的默认值
        return self._log

    # -------------------------
    # 统一入口
    # -------------------------
    def notify(
        self,
        text: str,
        level: str = "info",
        *,
        duration_ms: Optional[int] = None,
        toast: Optional[bool] = None,
        log: bool = True,
        extra: Optional[Dict[str, Any]] = None,
        exc_info: Any = None,
        stacklevel: int = 2,
    ) -> Optional[object]:
        """
        统一通知：写日志 + 可选弹 toast。返回创建的 toast 实例（若有），否则 None。
        """
        bubble = None

        # 1) 写日志
        if log:
            self._ensure_log().log(
                text,
                level=level,
                exc_info=exc_info,
                extra=extra,
                stacklevel=stacklevel,
            )

        # 2) 弹 toast：显式参数优先，其次路由策略
        should_toast = (level in self._toast_levels) if toast is None else bool(toast)
        if should_toast:
            tm = self._ensure_toast()
            if tm is not None:
                dur = duration_ms if duration_ms is not None else self._level_durations.get(level)
                bubble = tm.show(text, level=level, duration_ms=dur)
        return bubble

    # -------------------------
    # 便捷方法（可链式调用）
    # -------------------------
    def debug(self, text: str, **kw) -> Optional[object]:
        return self.notify(text, level="debug", **kw)

    def info(self, text: str, **kw) -> Optional[object]:
        return self.notify(text, level="info", **kw)

    def success(self, text: str, **kw) -> Optional[object]:
        return self.notify(text, level="success", **kw)

    def warning(self, text: str, **kw) -> Optional[object]:
        return self.notify(text, level="warning", **kw)

    def error(self, text: str, **kw) -> Optional[object]:
        return self.notify(text, level="error", **kw)

    # -------------------------
    # 直通能力
    # -------------------------
    def log(
        self,
        msg: str,
        level: str = "info",
        *,
        exc_info: Any = None,
        extra: Optional[Dict[str, Any]] = None,
        stacklevel: int = 2,
    ) -> None:
        self._ensure_log().log(msg, level=level, exc_info=exc_info, extra=extra, stacklevel=stacklevel)

    def show(self, text: str, level: str = "info", duration_ms: Optional[int] = None) -> object:
        tm = self._ensure_toast()
        if tm is None:
            raise RuntimeError("Toast anchor 未设置，无法显示气泡。请先调用 setToastAnchor(widget)。")
        return tm.show(text, level=level, duration_ms=duration_ms)

    # -------------------------
    # 配置：路由与默认时长
    # -------------------------
    def setRouting(
        self,
        *,
        toast_levels: Optional[Set[str]] = None,
        level_durations: Optional[Mapping[str, int]] = None,
    ) -> "InfoManager":
        if toast_levels is not None:
            self._toast_levels = set(toast_levels)
        if level_durations is not None:
            self._level_durations.update(level_durations)
        return self

    # -------------------------
    # 配置：Toast 与 Log
    # -------------------------
    def setToastAnchor(self, widget: "object") -> "InfoManager":
        self._anchor_widget = widget
        # 每次切换 anchor 都重建 ToastManager
        self._toast = ToastManager(widget)
        if self._pending_toast_options:
            self._toast.setOptions(**self._pending_toast_options)
        return self

    def setToastOptions(
        self,
        *,
        width: Optional[int] = None,
        margin: Optional[int] = None,
        spacing: Optional[int] = None,
        max_visible: Optional[int] = None,
    ) -> "InfoManager":
        opts = dict(width=width, margin=margin, spacing=spacing, max_visible=max_visible)
        # 缓存，便于未创建 toast_manager 时也能先设定
        self._pending_toast_options.update({k: v for k, v in opts.items() if v is not None})
        if self._toast is not None:
            self._toast.setOptions(**opts)
        return self

    def setLogOptions(
        self,
        *,
        level: Optional[str] = None,
        fmt: Optional[str] = None,
        datefmt: Optional[str] = None,
        enable_console: Optional[bool] = None,
        file_path: Optional[str] = None,
        rotate_max_bytes: Optional[int] = None,
        rotate_backup_count: Optional[int] = None,
        async_mode: Optional[bool] = None,
    ) -> "InfoManager":
        self._ensure_log().setOptions(
            level=level,
            fmt=fmt,
            datefmt=datefmt,
            enable_console=enable_console,
            file_path=file_path,
            rotate_max_bytes=rotate_max_bytes,
            rotate_backup_count=rotate_backup_count,
            async_mode=async_mode,
        )
        return self

    # -------------------------
    # 注册能力透传
    # -------------------------
    def registerToastBubbleClass(self, level: str, cls: type) -> "InfoManager":
        tm = self._ensure_toast()
        if tm is None:
            raise RuntimeError("Toast anchor 未设置，无法注册气泡类。请先调用 setToastAnchor(widget)。")
        tm.registerBubbleClass(level, cls)
        return self

    def registerLogLevel(self, level: str, numeric: Optional[int] = None) -> "InfoManager":
        self._ensure_log().registerLevel(level, numeric=numeric)
        return self

    # -------------------------
    # 辅助与生命周期
    # -------------------------
    def getLogger(self):
        return self._ensure_log().getLogger()

    def getToastManager(self) -> Optional["ToastManager"]:
        return self._toast

    def close(self) -> None:
        """关闭日志队列监听/handler。"""
        if self._log is not None:
            self._log.close()