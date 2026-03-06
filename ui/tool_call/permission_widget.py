
"""tool_permission_panel.py — 工具权限审批面板"""
from __future__ import annotations

import json
from copy import deepcopy
from functools import partial

from PyQt6.QtCore import (
    QEasingCurve,
    QParallelAnimationGroup,
    QPropertyAnimation,
    QSequentialAnimationGroup,
    Qt,
    QTimer,
    pyqtSignal,
    pyqtSlot,
)
from PyQt6.QtWidgets import (
    QFrame,
    QGraphicsOpacityEffect,
    QHBoxLayout,
    QLabel,
    QPlainTextEdit,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)


# --------------------------------------------------
#  卡片（纯视觉，不管理动画生命周期）
# --------------------------------------------------
class ToolPermissionCard(QFrame):

    responded = pyqtSignal(int, str)  # (index, decision)

    def __init__(self, tool_item: dict, parent: QWidget | None = None):
        super().__init__(parent)
        self._tool_item = tool_item
        self._index: int = tool_item.get("index", 0)
        self._responded = False
        self.setObjectName("ToolPermissionCard")
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Maximum)
        self._build_ui()

    # ── UI ────────────────────────────────────────────
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(16, 14, 16, 14)
        root.setSpacing(10)

        tc = self._tool_item["tool_call"]
        func = tc["function"]
        func_name: str = func["name"]
        call_id: str = tc.get("id", "")

        # header
        hdr = QHBoxLayout()
        hdr.setSpacing(6)
        icon = QLabel("⚡");  icon.setObjectName("ToolCardIcon")
        name = QLabel(func_name); name.setObjectName("ToolCardName")
        cid = QLabel(call_id[-12:] if len(call_id) > 12 else call_id)
        cid.setObjectName("ToolCardId")
        hdr.addWidget(icon); hdr.addWidget(name, 1); hdr.addWidget(cid)
        root.addLayout(hdr)

        # separator
        sep = QFrame()
        sep.setObjectName("ToolCardSeparator")
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFixedHeight(1)
        root.addWidget(sep)

        # arguments
        try:
            args: dict = json.loads(func["arguments"])
        except (json.JSONDecodeError, TypeError, KeyError):
            args = {"arguments": func.get("arguments", "")}

        for key, val in args.items():
            vs = str(val)
            kl = QLabel(key); kl.setObjectName("ToolCardArgKey")
            root.addWidget(kl)
            if "\n" in vs or len(vs) > 100:
                ed = QPlainTextEdit()
                ed.setObjectName("ToolCardCodeView")
                ed.setPlainText(vs); ed.setReadOnly(True)
                ed.setMinimumHeight(60); ed.setMaximumHeight(220)
                root.addWidget(ed)
            else:
                vl = QLabel(vs); vl.setObjectName("ToolCardArgValue")
                vl.setWordWrap(True); root.addWidget(vl)

        # buttons
        row = QHBoxLayout(); row.setSpacing(8); row.addStretch()
        for txt, obj, dec in [
            ("允许",    "btnAllow",       "approved"),
            ("拒绝",    "btnDeny",        "denied"),
            ("总是允许", "btnAlwaysAllow", "always"),
        ]:
            b = QPushButton(txt); b.setObjectName(obj)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.clicked.connect(partial(self._on_click, dec))
            row.addWidget(b)
        root.addLayout(row)

    def _on_click(self, decision: str) -> None:
        if self._responded:
            return
        self._responded = True
        self.responded.emit(self._index, decision)


# --------------------------------------------------
#  卡片包装器 —— 管理三阶段动画 + 布局占位
# --------------------------------------------------
class _CardWrapper(QWidget):
    """
    Phase 1  ─ Pop   : 卡片从中心放大 8 %          (120 ms)
    Phase 2  ─ Shrink: 卡片缩至 0 + 淡出            (300 ms)
    Phase 3  ─ Collapse: 包装器高度归零，弹性回弹     (450 ms)
    """

    responded = pyqtSignal(int, str)
    fully_dismissed = pyqtSignal()

    def __init__(self, tool_item: dict, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("ToolCardWrapper")
        self._alive = True
        self._dismissing = False

        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 4, 0, 4)   # 上下留 4 px 给 pop 留空间
        lay.setAlignment(Qt.AlignmentFlag.AlignCenter)

        self.card = ToolPermissionCard(tool_item, self)
        lay.addWidget(self.card)
        self.card.responded.connect(self._on_responded)

        # prevent GC
        self._anim_phase12: QSequentialAnimationGroup | None = None
        self._anim_phase3: QParallelAnimationGroup | None = None

    @property
    def alive(self) -> bool:
        return self._alive

    # ── Phase 0 ──────────────────────────────────────
    def _on_responded(self, index: int, decision: str) -> None:
        if self._dismissing:
            return
        self._dismissing = True
        self.responded.emit(index, decision)

        # 锁定包装器高度，卡片消失期间布局不移动
        h = self.height()
        self.setMinimumHeight(h)
        self.setMaximumHeight(int(h * 1.15))  # 给 pop 膨胀留余量
        self._locked_h = h

        self._run_phase12()

    # ── Phase 1 + 2 ─────────────────────────────────
    def _run_phase12(self) -> None:
        card = self.card
        card.setMinimumSize(0, 0)
        cw, ch = card.width(), card.height()

        if cw <= 0 or ch <= 0:          # 尚未布局
            self._run_phase3()
            return

        # opacity effect
        eff = QGraphicsOpacityEffect(card)
        card.setGraphicsEffect(eff)
        eff.setOpacity(1.0)

        pop_w, pop_h = int(cw * 1.08), int(ch * 1.08)

        seq = QSequentialAnimationGroup(self)

        # ---- Phase 1: Pop ----
        p1 = QParallelAnimationGroup()
        for prop, s, e in [
            (b"maximumWidth",  cw, pop_w),
            (b"maximumHeight", ch, pop_h),
        ]:
            a = QPropertyAnimation(card, prop)
            a.setDuration(120)
            a.setStartValue(s)
            a.setEndValue(e)
            a.setEasingCurve(QEasingCurve.Type.OutCubic)
            p1.addAnimation(a)
        seq.addAnimation(p1)

        # ---- Phase 2: Shrink + Fade ----
        p2 = QParallelAnimationGroup()

        a_op = QPropertyAnimation(eff, b"opacity")
        a_op.setDuration(300)
        a_op.setStartValue(1.0)
        a_op.setEndValue(0.0)
        a_op.setEasingCurve(QEasingCurve.Type.InCubic)
        p2.addAnimation(a_op)

        curve_back = QEasingCurve(QEasingCurve.Type.InBack)
        curve_back.setOvershoot(1.8)

        for prop, s in [(b"maximumWidth", pop_w), (b"maximumHeight", pop_h)]:
            a = QPropertyAnimation(card, prop)
            a.setDuration(300)
            a.setStartValue(s)
            a.setEndValue(0)
            a.setEasingCurve(curve_back)
            p2.addAnimation(a)
        seq.addAnimation(p2)

        seq.finished.connect(self._run_phase3)
        self._anim_phase12 = seq
        seq.start()

    # ── Phase 3: 弹性折叠 ───────────────────────────
    def _run_phase3(self) -> None:
        h = self._locked_h if hasattr(self, "_locked_h") else self.height()
        if h <= 0:
            self._on_done()
            return

        grp = QParallelAnimationGroup(self)

        for prop in (b"minimumHeight", b"maximumHeight"):
            a = QPropertyAnimation(self, prop)
            a.setDuration(450)
            a.setStartValue(h)
            a.setEndValue(0)
            a.setEasingCurve(QEasingCurve.Type.OutBounce)
            grp.addAnimation(a)

        grp.finished.connect(self._on_done)
        self._anim_phase3 = grp
        grp.start()

    # ── 清理 ─────────────────────────────────────────
    def _on_done(self) -> None:
        self._alive = False
        self.hide()
        self.fully_dismissed.emit()
        self.deleteLater()


# --------------------------------------------------
#  可淡出的请求 ID 标签
# --------------------------------------------------
class _FadingLabel(QWidget):

    def __init__(self, text: str, obj_name: str, parent: QWidget | None = None):
        super().__init__(parent)
        self._alive = True
        self._anim: QParallelAnimationGroup | None = None
        lay = QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lbl = QLabel(text)
        lbl.setObjectName(obj_name)
        lay.addWidget(lbl)

    @property
    def alive(self) -> bool:
        return self._alive

    def collapse(self) -> None:
        if not self._alive:
            return
        h = self.height()
        self.setMinimumHeight(0)
        self.setMaximumHeight(h)

        eff = QGraphicsOpacityEffect(self)
        self.setGraphicsEffect(eff)
        eff.setOpacity(1.0)

        grp = QParallelAnimationGroup(self)

        a_op = QPropertyAnimation(eff, b"opacity")
        a_op.setDuration(250)
        a_op.setStartValue(1.0)
        a_op.setEndValue(0.0)
        a_op.setEasingCurve(QEasingCurve.Type.InCubic)
        grp.addAnimation(a_op)

        a_h = QPropertyAnimation(self, b"maximumHeight")
        a_h.setDuration(300)
        a_h.setStartValue(h)
        a_h.setEndValue(0)
        a_h.setEasingCurve(QEasingCurve.Type.OutCubic)
        grp.addAnimation(a_h)

        grp.finished.connect(self._done)
        self._anim = grp
        grp.start()

    def _done(self) -> None:
        self._alive = False
        self.hide()
        self.deleteLater()


# --------------------------------------------------
#  审批面板（对外接口）
# --------------------------------------------------
class ToolPermissionPanel(QWidget):
    """
    信号
    ----
    permission_result(request_id, allowed_tools, dangerous_tools)

    槽
    --
    handle_permission_request(request_id, allowed_tools, dangerous_tools)
    """

    permission_result = pyqtSignal(str, list, list)

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("ToolPermissionPanel")
        self._requests: dict[str, dict] = {}
        self._build_ui()

    # ── 布局 ─────────────────────────────────────────
    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(0, 0, 0, 0)
        root.setSpacing(0)

        header = QLabel("⚠  工具权限审批")
        header.setObjectName("ToolPanelHeader")
        header.setAlignment(
            Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter
        )
        header.setContentsMargins(16, 14, 16, 14)
        root.addWidget(header)

        self._scroll = QScrollArea()
        self._scroll.setObjectName("ToolPanelScroll")
        self._scroll.setWidgetResizable(True)
        self._scroll.setFrameShape(QFrame.Shape.NoFrame)
        self._scroll.setHorizontalScrollBarPolicy(
            Qt.ScrollBarPolicy.ScrollBarAlwaysOff
        )

        container = QWidget()
        container.setObjectName("ToolPanelContainer")
        self._card_layout = QVBoxLayout(container)
        self._card_layout.setContentsMargins(12, 8, 12, 8)
        self._card_layout.setSpacing(10)
        self._card_layout.addStretch()

        self._scroll.setWidget(container)
        root.addWidget(self._scroll, 1)

        self._empty_hint = QLabel("暂无待审批的工具调用")
        self._empty_hint.setObjectName("ToolPanelEmptyHint")
        self._empty_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._card_layout.insertWidget(0, self._empty_hint)

    def _insert_pos(self) -> int:
        return self._card_layout.count() - 1   # stretch 之前

    # ── 公开槽 ────────────────────────────────────────
    @pyqtSlot(str, list, list)
    def handle_permission_request(
        self,
        request_id: str,
        allowed_tools: list,
        dangerous_tools: list,
    ) -> None:
        if not dangerous_tools:
            self.permission_result.emit(request_id, list(allowed_tools), [])
            return

        self._empty_hint.hide()

        req: dict = {
            "allowed":   list(allowed_tools),
            "dangerous": {it["index"]: deepcopy(it) for it in dangerous_tools},
            "decisions": {},
            "total":     len(dangerous_tools),
            "label":     None,
        }
        self._requests[request_id] = req

        # 请求 ID 标签
        lbl = _FadingLabel(f"请求  {request_id}", "ToolPanelRequestId", self)
        self._card_layout.insertWidget(self._insert_pos(), lbl)
        req["label"] = lbl

        # 卡片
        for item in dangerous_tools:
            wrapper = _CardWrapper(item, self)
            wrapper.responded.connect(
                partial(self._on_card_responded, request_id)
            )
            self._card_layout.insertWidget(self._insert_pos(), wrapper)

    # ── 内部逻辑 ──────────────────────────────────────
    def _on_card_responded(
        self, request_id: str, index: int, decision: str
    ) -> None:
        req = self._requests.get(request_id)
        if req is None:
            return

        req["decisions"][index] = decision

        # 总是允许 → 持久化
        if decision == "always":
            fn = req["dangerous"][index]["tool_call"]["function"]["name"]
            self._persist_always_allow(fn)

        # 还有未审批的
        if len(req["decisions"]) < req["total"]:
            return

        # ── 全部完成 ──
        final_allowed:   list[dict] = list(req["allowed"])
        final_dangerous: list[dict] = []

        for idx, item in req["dangerous"].items():
            dec = req["decisions"].get(idx, "denied")
            if dec in ("approved", "always"):
                item["status"] = "approved"
                final_allowed.append(item)
            else:
                item["status"] = "denied"
                final_dangerous.append(item)

        self.permission_result.emit(request_id, final_allowed, final_dangerous)

        # 延迟折叠标签（等卡片动画放完）
        lbl = req.get("label")
        if lbl is not None and lbl.alive:
            QTimer.singleShot(900, lbl.collapse)

        del self._requests[request_id]
        QTimer.singleShot(1500, self._check_empty)

    def _check_empty(self) -> None:
        if not self._requests:
            self._empty_hint.show()

    @staticmethod
    def _persist_always_allow(func_name: str) -> None:
        from config import APP_SETTINGS

        perm = APP_SETTINGS.tool_permission
        if func_name not in perm.names:
            perm.names.append(func_name)


# --------------------------------------------------
#  快速测试
# --------------------------------------------------
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QApplication

    app = QApplication(sys.argv)

    panel = ToolPermissionPanel()
    panel.resize(520, 600)
    panel.show()

    panel.permission_result.connect(
        lambda rid, a, d: print(
            f"\n{'=' * 50}\n"
            f"审批完成: {rid}\n"
            f"  放行: {len(a)}  拒绝: {len(d)}\n"
            f"{'=' * 50}"
        )
    )

    mock_id = "CWLA_req_14734a17-0636-4640-9b25-726ec6b707c7"
    mock_dangerous = [
        {
            "tool_call": {
                "id": "call_00_zgIkmJxUjVhPuxbZdqtT8n0i",
                "type": "function",
                "function": {
                    "name": "python_cmd",
                    "arguments": json.dumps(
                        {
                            "code": (
                                "import datetime\n"
                                "\n"
                                "current_time = datetime.datetime.now()\n"
                                'print(f"当前时间: {current_time}")\n'
                                'print(f"时间戳: {current_time.timestamp()}")'
                            )
                        }
                    ),
                },
            },
            "status": "denied",
            "index": 0,
        },
        {
            "tool_call": {
                "id": "call_01_abcdefghij1234567890",
                "type": "function",
                "function": {
                    "name": "shell_cmd",
                    "arguments": json.dumps({"command": "rm -rf /tmp/test"}),
                },
            },
            "status": "denied",
            "index": 2,
        },
        {
            "tool_call": {
                "id": "call_01_abcdefghij1234567890",
                "type": "function",
                "function": {
                    "name": "shell_cmd",
                    "arguments": json.dumps({"command": "rm -rf /tmp/test"}),
                },
            },
            "status": "denied",
            "index": 3,
        },
        {
            "tool_call": {
                "id": "call_01_abcdefghij1234567890",
                "type": "function",
                "function": {
                    "name": "shell_cmd",
                    "arguments": json.dumps({"command": "rm -rf /tmp/test"}),
                },
            },
            "status": "denied",
            "index": 4,
        },
    ]

    panel.handle_permission_request(mock_id, [], mock_dangerous)
    sys.exit(app.exec())
