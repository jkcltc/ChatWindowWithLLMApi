# Created by GPT-5 & Gemini 2.5 Pro
# Introduced in 0.25.3
import sys
from PyQt5 import QtCore, QtGui, QtWidgets

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
        修改显示文本并重新计算尺寸。
    setFixedWidth(w: int)
        覆盖固定宽度，并将约束同步到内部控件。
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
    - Toast 设计为一次性使用；调用 `fade_out` 后会自动删除。
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

    def setText(self, text: str):
        self._label.setText(text)
        self._label.adjustSize()
        self.adjustSize()

    def setFixedWidth(self, w: int):
        # 外层窗口固定宽度
        super().setFixedWidth(w)

        # panel 和 label 实际可用宽度
        sl, st, sr, sb = self._shadow_margins
        inner_w = max(60, w - sl - sr)
        self._panel.setFixedWidth(inner_w)

        l, t, r, b = self._padding
        self._label.setFixedWidth(max(30, inner_w - l - r))

        self._label.adjustSize()
        self.adjustSize()

    def sizeHint(self):
        return super().sizeHint()

    # 顶层不再绘制任何内容，避免 layered 更新问题
    def paintEvent(self, e: QtGui.QPaintEvent):
        return

    def popup(self, end_pos: QtCore.QPoint, duration_ms=None):
        if duration_ms is None:
            duration_ms = self._default_duration

        self.adjustSize()
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
            bg_color=QtGui.QColor(216, 144, 0, 235), # Amber color
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
            bg_color=QtGui.QColor(180, 40, 40, 235), # Dark red color
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
        # MODIFIED: Map levels to bubble classes
        self._bubble_classes = {
            "info": ToastBubble,
            "success": SuccessToast,
            "warning": WarningToast,
            "error": ErrorToast,
        }
        
        self._toasts = []
        self._anchor.installEventFilter(self)

    def registerBubbleClass(self, level: str, cls: type):
        """Register a custom bubble class for a given level string."""
        if issubclass(cls, ToastBubble):
            self._bubble_classes[level.lower()] = cls
        else:
            raise TypeError("The provided class must be a subclass of ToastBubble.")

    def show(self, text: str, level: str = "info", duration_ms: int = None):
        """
        Creates and shows a toast bubble.
        
        Args:
            text (str): The message to display.
            level (str): The type of toast ('info', 'success', 'warning', 'error').
                         Defaults to 'info'.
            duration_ms (int, optional): Duration in milliseconds. If None, uses the
                                         default duration of the specific toast class.
        """
        level = level.lower()
        bubble_cls = self._bubble_classes.get(level, self._bubble_classes["info"])
        
        # Instantiate the bubble. We don't pass duration here, so it uses its own default.
        # The duration passed to popup() below will override it if provided.
        bubble = bubble_cls(parent=self._anchor, width=self._width)
        bubble.setText(text)
        bubble.closed.connect(self._on_bubble_closed)

        self._toasts.insert(0, bubble)

        # The duration for the popup animation timer.
        # Priority: 1. `duration_ms` arg -> 2. Bubble's own default
        popup_duration = duration_ms if duration_ms is not None else bubble._default_duration

        targets = self._compute_targets()
        for i, tb in enumerate(self._toasts):
            if tb is bubble:
                # Use the resolved duration for the new bubble
                tb.popup(targets[i], popup_duration)
            else:
                tb.shift_to(targets[i], animate=True)

        if self._max_visible > 0 and len(self._toasts) > self._max_visible:
            over = self._toasts[self._max_visible:]
            for tb in over:
                tb.fade_out()

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
            tb.adjustSize()

            W = tb.width()
            H = tb.sizeHint().height()  # 或 tb.height()；两者均可
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

