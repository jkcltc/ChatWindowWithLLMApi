import json
import os
import time
import traceback
from typing import Any, List, Optional, Tuple, Dict

from PyQt6.QtCore import (
    Qt, QTimer, pyqtSignal, QPoint, QPropertyAnimation, QEvent
)
from PyQt6.QtGui import (
    QFont, QPixmap, QIcon, QColor, QPainter, QTextOption, QGuiApplication,
)
from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFrame,
    QLabel, QPushButton, QToolButton, QScrollArea, QTextEdit, QStackedWidget,
    QSizePolicy, QGraphicsOpacityEffect,
    QPlainTextEdit, QFormLayout, QTextBrowser,
    QGroupBox, QCheckBox, QRadioButton, QListWidget, QListWidgetItem
)
from config.settings import APP_SETTINGS
from ui.chat.markdown_browser import MarkdownTextBrowser

ChatapiTextBrowser = MarkdownTextBrowser

class CurrentPageStackedWidget(QStackedWidget):

    def __init__(self, parent=None):
        super().__init__(parent)
        self.currentChanged.connect(lambda _: self.updateGeometry())

    def sizeHint(self):
        w=self.widget(0)
        return w.sizeHint() if w else super().sizeHint()

    def minimumSizeHint(self):
        w = self.currentWidget()
        return w.minimumSizeHint() if w else super().minimumSizeHint()



def _clear_layout(layout) -> None:
    while layout.count():
        item = layout.takeAt(0)
        w = item.widget()
        if w is not None:
            w.deleteLater()
            continue
        child_layout = item.layout()
        if child_layout is not None:
            _clear_layout(child_layout)
            child_layout.deleteLater()
            continue


def _qcolor_to_rgba(c: QColor, alpha: int) -> str:
    return f"rgba({c.red()}, {c.green()}, {c.blue()}, {alpha})"


# ============================ InfoPopup ============================

class InfoPopup(QWidget):
    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)
        self.setMaximumSize(560, 480)
        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(0)
        self.container = QFrame(self)
        self.container.setObjectName("InfoPopupContainer")
        self.container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(10, 10, 10, 10)
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)
        self.title_label = QLabel("消息详情", self.container)
        font = self.title_label.font()
        font.setBold(True)
        self.title_label.setFont(font)
        title_row.addWidget(self.title_label, 1)
        container_layout.addLayout(title_row)
        sep = QFrame(self.container)
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        container_layout.addWidget(sep)
        self.scroll = QScrollArea(self.container)
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.Shape.NoFrame)
        self.scroll_body = QWidget()
        self.form = QFormLayout(self.scroll_body)
        self.form.setContentsMargins(0, 0, 0, 0)
        self.form.setRowWrapPolicy(QFormLayout.RowWrapPolicy.WrapLongRows)
        self.scroll.setWidget(self.scroll_body)
        container_layout.addWidget(self.scroll)
        root.addWidget(self.container)
        self._apply_palette_style()

    def _apply_palette_style(self) -> None:
        pal = self.palette()
        bg = pal.color(self.backgroundRole())
        fg = pal.color(self.foregroundRole())
        bg_rgba = _qcolor_to_rgba(bg, 245)
        border_rgba = _qcolor_to_rgba(fg, 70)
        self.container.setStyleSheet(f"""
        QFrame#InfoPopupContainer {{
            background-color: {bg_rgba};
            border: 1px solid {border_rgba};
        }}
        QLabel {{ color: {_qcolor_to_rgba(fg, 255)}; }}
        QPlainTextEdit {{
            border: 1px solid {border_rgba};
            background: {_qcolor_to_rgba(bg, 255)};
            color: {_qcolor_to_rgba(fg, 255)};
        }}
        """)

    def _make_value_widget(self, value: Any) -> QWidget:
        if value is None:
            lab = QLabel("null")
            lab.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            lab.setWordWrap(True)
            return lab
        if isinstance(value, (dict, list)):
            txt = QPlainTextEdit()
            txt.setReadOnly(True)
            txt.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
            txt.setPlainText(json.dumps(value, ensure_ascii=False, indent=2))
            txt.setMaximumHeight(140)
            return txt
        lab = QLabel(str(value))
        lab.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lab.setWordWrap(True)
        return lab

    def show_info(self, info_data: Any, anchor_global_pos: QPoint, title: str = "消息详情") -> None:
        self.title_label.setText(title)
        _clear_layout(self.form)
        if isinstance(info_data, dict):
            keys = list(info_data.keys())
            fm = self.fontMetrics()
            max_key_px = max((fm.horizontalAdvance(str(k)) for k in keys), default=0)
            key_width = min(max_key_px + 10, 220)
            for key in keys:
                val = info_data.get(key)
                key_label = QLabel(f"{key}:")
                key_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
                key_label.setMinimumWidth(key_width)
                self.form.addRow(key_label, self._make_value_widget(val))
        else:
            key_label = QLabel("value:")
            key_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
            self.form.addRow(key_label, self._make_value_widget(info_data))
        self._apply_palette_style()
        self.adjustSize()
        self._move_near_anchor(anchor_global_pos)
        self.show()

    def _move_near_anchor(self, anchor_global_pos: QPoint) -> None:
        screen = QGuiApplication.screenAt(anchor_global_pos) or QGuiApplication.primaryScreen()
        if screen is None:
            self.move(anchor_global_pos)
            return
        avail = screen.availableGeometry()
        margin = 6
        w, h = self.width(), self.height()
        x = anchor_global_pos.x() - w // 2
        y_below = anchor_global_pos.y() + 8
        y_above = anchor_global_pos.y() - h - 8
        y = y_above if y_below + h > avail.bottom() else y_below
        x = max(avail.left() + margin, min(x, avail.right() - w - margin))
        y = max(avail.top() + margin, min(y, avail.bottom() - h - margin))
        self.move(x, y)


# ============================ 子控件 ============================

class EditWidget(QTextEdit):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)


class ReasoningDisplay(MarkdownTextBrowser):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVisible(False)

    def setMarkdown(self, text, is_streaming=False):
        self._is_streaming = is_streaming
        super().setMarkdown(text)


class BubbleControlButtons(QFrame):
    regenerateClicked = pyqtSignal()
    editToggleClicked = pyqtSignal(bool)
    detailToggleClicked = pyqtSignal(bool)
    infoClicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        self.main_layout = QHBoxLayout()
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        self.setLayout(self.main_layout)
        self.inner_widget = QFrame()
        self.layout: QHBoxLayout = QHBoxLayout(self.inner_widget)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        self.regenerate_button = QToolButton(); self.regenerate_button.setText("🔃"); self.regenerate_button.setToolTip("重新生成")
        self.copy_button = QToolButton(); self.copy_button.setText("📋"); self.copy_button.setToolTip("复制内容")
        self.edit_button = QToolButton(); self.edit_button.setText("📝​​"); self.edit_button.setToolTip("编辑消息"); self.edit_button.setCheckable(True)
        self.info_button = QToolButton(); self.info_button.setText("📊"); self.info_button.setToolTip("消息详情")
        self.detail_button = QToolButton(); self.detail_button.setText("💡"); self.detail_button.setToolTip("显示思考过程"); self.detail_button.setCheckable(True)
        self.layout.addWidget(self.regenerate_button)
        self.layout.addWidget(self.copy_button)
        self.layout.addWidget(self.edit_button)
        self.layout.addWidget(self.detail_button)
        self.layout.addWidget(self.info_button)
        self.layout.addStretch()
        self.main_layout.addWidget(self.inner_widget)
        self.regenerate_button.clicked.connect(self.regenerateClicked.emit)
        self.edit_button.toggled.connect(self._on_edit_toggled)
        self.detail_button.toggled.connect(self._on_detail_toggled)
        self.info_button.clicked.connect(self.infoClicked.emit)
        self.copy_button.clicked.connect(self._on_copy_clicked)
        self.detail_button.setVisible(False)

    def set_alignment(self, align_left):
        if align_left:
            self.layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
            self.main_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        else:
            self.layout.setAlignment(Qt.AlignmentFlag.AlignRight)
            self.main_layout.setAlignment(Qt.AlignmentFlag.AlignRight)

    def set_has_reasoning(self, has_reasoning):
        self.detail_button.setVisible(has_reasoning)
        self.detail_button.setChecked(False)

    def set_editing(self, editing):
        self.edit_button.setChecked(editing)

    def _on_edit_toggled(self, checked):
        self.edit_button.setText("✅​" if checked else "📝")
        self.edit_button.setToolTip("完成编辑" if checked else "编辑消息")
        self.editToggleClicked.emit(checked)

    def _on_detail_toggled(self, checked):
        self.detailToggleClicked.emit(checked)

    def _on_copy_clicked(self):
        effect = QGraphicsOpacityEffect(self.copy_button)
        effect.setOpacity(1.0)
        self.copy_button.setGraphicsEffect(effect)
        self._copy_animation = QPropertyAnimation(effect, b"opacity")
        self._copy_animation.setDuration(100)
        self._copy_animation.setStartValue(1.0)
        self._copy_animation.setEndValue(0.0)
        self._copy_animation.finished.connect(self._change_button_to_yes)
        self._copy_animation.start()

    def _change_button_to_yes(self):
        self.copy_button.setText("✅")
        effect = QGraphicsOpacityEffect(self.copy_button)
        effect.setOpacity(1.0)
        self.copy_button.setGraphicsEffect(effect)
        self._copy_animation = QPropertyAnimation(effect, b"opacity")
        self._copy_animation.setDuration(150)
        self._copy_animation.setStartValue(0.0)
        self._copy_animation.setEndValue(1.0)
        self._copy_animation.finished.connect(self._change_button_to_hide)
        self._copy_animation.start()

    def _change_button_to_hide(self):
        effect = QGraphicsOpacityEffect(self.copy_button)
        effect.setOpacity(1.0)
        self.copy_button.setGraphicsEffect(effect)
        self._copy_animation = QPropertyAnimation(effect, b"opacity")
        self._copy_animation.setDuration(300)
        self._copy_animation.setStartValue(1.0)
        self._copy_animation.setEndValue(0.0)
        self._copy_animation.finished.connect(self._restore_copy_button)
        self._copy_animation.start()

    def _restore_copy_button(self):
        self.copy_button.setText("📋")
        self.copy_button.setToolTip("复制内容")
        effect = QGraphicsOpacityEffect(self.copy_button)
        effect.setOpacity(1.0)
        self.copy_button.setGraphicsEffect(effect)
        self._copy_animation = QPropertyAnimation(effect, b"opacity")
        self._copy_animation.setDuration(100)
        self._copy_animation.setStartValue(0.0)
        self._copy_animation.setEndValue(1.0)
        self._copy_animation.start()



class ChatBubble(QWidget):
    regenerateRequested = pyqtSignal(str)
    editFinished = pyqtSignal(str, str)
    detailToggled = pyqtSignal(str, bool)
    RequestAvatarChange = pyqtSignal(str, str)
    bubbleRenderStarted = pyqtSignal()
    bubbleRenderFinished = pyqtSignal()

    def __init__(self, message_data, nickname=None,
                 avatar_path="", parent=None,
                 msg_id=None, defer_render=False):
        super().__init__(parent)
        self.id = str(message_data['info']['id'])
        self.role = message_data['role']
        self.message_data: dict = message_data
        self.setMouseTracking(True)
        self.setSizePolicy(QSizePolicy.Policy.Expanding,
                      QSizePolicy.Policy.MinimumExpanding)
        self.setObjectName('chatbubble')
        self.manual_expand_reasoning = False
        self.msg_id = msg_id

        self._content_fp: str = ''
        self._reasoning_fp: str = ''
        self._rendered: bool = False
        self._pending_content: str = ''
        self._pending_reasoning: str = ''
        self._editor_dirty: bool = True          # 编辑器脏标记

        grid = QGridLayout()
        grid.setContentsMargins(5, 5, 5, 5)
        grid.setSpacing(0)
        self.setLayout(grid)

        self.top_bar = QFrame()
        self.top_bar_container = QFrame()
        top_bar_layout = QHBoxLayout(self.top_bar_container)
        top_bar_layout.setContentsMargins(0, 0, 0, 0)
        top_bar_layout.addWidget(self.top_bar)

        self.top_layout = QHBoxLayout()
        self.top_layout.setContentsMargins(5, 0, 5, 5)
        self.top_layout.setSpacing(5)
        self.top_bar.setLayout(self.top_layout)

        self.avatar = QPushButton()
        self.avatar.setFixedSize(24, 24)
        self.avatar.setCursor(Qt.CursorShape.PointingHandCursor)
        self.avatar_path = avatar_path
        self._setup_avatar()

        self.role_label = QLabel(self._get_patched_name(nickname))
        font = self.role_label.font()
        font.setBold(True)
        self.role_label.setFont(font)

        self.buttons = BubbleControlButtons()
        self.button_container = QStackedWidget()
        self.button_container.addWidget(QWidget())
        self.button_container.addWidget(self.buttons)
        self.button_container.setCurrentIndex(0)
        self.button_container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

        if self.role == "user":
            self.top_layout.addWidget(self.button_container)
            self.top_layout.addStretch()
            self.top_layout.addWidget(self.role_label)
            self.top_layout.addWidget(self.avatar)
            self.top_layout.setAlignment(Qt.AlignmentFlag.AlignRight)
            grid.addWidget(self.top_bar_container, 0, 0, 1, 1,
                           Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        else:
            self.top_layout.addWidget(self.avatar)
            self.top_layout.addWidget(self.role_label)
            self.top_layout.addStretch()
            self.top_layout.addWidget(self.button_container)
            self.top_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
            grid.addWidget(self.top_bar_container, 0, 0, 1, 1,
                           Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)

        self.content = MarkdownTextBrowser()
        self.content.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)

        self.editor = EditWidget()
        self.editor.setVisible(False)

        self.reasoning_display = ReasoningDisplay()
        self.reasoning_display.setVisible(False)

        self.content_container = CurrentPageStackedWidget()
        self.content_container.addWidget(self.content)
        self.content_container.addWidget(self.editor)
        self.content_container.setCurrentIndex(0)
        self.content_container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

        grid.addWidget(self.content_container, 2, 0, 1, 1)
        grid.addWidget(self.reasoning_display, 1, 0, 1, 1)

        self.info_popup = InfoPopup(self)
        self.info_popup.setVisible(False)

        self._pending_content = message_data.get('content', '')
        self._pending_reasoning = self._preprocess_reasoning(
            message_data.get('reasoning_content', ''))

        if self._pending_reasoning:
            self.buttons.set_has_reasoning(True)
        if not self._pending_content:
            self.content_container.hide()

        self._connect_signals()

        if not defer_render:
            self.render_content()

    def _preprocess_reasoning(self, raw: str) -> str:
        if not raw:
            return ''
        if self.role == 'tool':
            try:
                rj = json.loads(raw)
                fmt = json.dumps(rj, indent=2, ensure_ascii=False)
                readable = (fmt.replace('\\n', '\n')
                               .replace('\\t', '\t')
                               .replace('\\\\', '\\')
                               .replace(r'\"', '"'))
                return f"```json\n{readable}\n```"
            except (ValueError, TypeError):
                return f"```json\n{raw}\n```"
        return raw

    def render_content(self):
        if self._rendered:
            return
        self._rendered = True

        content = self._pending_content
        self._content_fp = content
        self.message_data['content'] = content

        if content:
            self.content.setMarkdown(content)
            self.content_container.show()
        else:
            self.content_container.hide()

        # 标记编辑器为脏，不立即填充内容
        self._editor_dirty = True
        reasoning = self._pending_reasoning
        self._reasoning_fp = reasoning
        if reasoning:
            self.reasoning_display.setMarkdown(reasoning)
            self.buttons.set_has_reasoning(True)

    def reset(self, message_data, nickname='', avatar_path='', msg_id=None):
        self.id = str(message_data['info']['id'])
        self.message_data = message_data
        self.msg_id = msg_id
        self.manual_expand_reasoning = False
        self._rendered = False
        self._content_fp = ''
        self._reasoning_fp = ''

        self.content.invalidate_pending_renders()
        self.reasoning_display.invalidate_pending_renders()

        self.role_label.setText(self._get_patched_name(nickname))
        if avatar_path != self.avatar_path:
            self.avatar_path = avatar_path
            self._setup_avatar()

        self.buttons.edit_button.setChecked(False)
        self.buttons.detail_button.setChecked(False)
        self.button_container.setCurrentIndex(0)
        self.content_container.setCurrentIndex(0)
        self.reasoning_display.setVisible(False)
        self.reasoning_display.clear()
        self.info_popup.hide()

        self._pending_content = message_data.get('content', '')
        self._pending_reasoning = self._preprocess_reasoning(
            message_data.get('reasoning_content', ''))

        self.buttons.set_has_reasoning(bool(self._pending_reasoning))

        # 不调用 setPlainText，只做轻量占位
        # 截取前 200 字符做高度估算占位，避免排版大量字符时卡顿
        if self._pending_content:
            preview = self._pending_content[:200]
            if len(self._pending_content) > 200:
                preview += '\n...'
            self.content.setPlainText(preview)
            self.content_container.show()
        else:
            self.content.clear()
            self.content_container.hide()

        # 标记编辑器为脏，延迟填充
        self.editor.clear()

    def _ensure_editor_content(self):
        """编辑器按需填充：仅在用户点击编辑时才 setPlainText"""
        if self._editor_dirty:
            self._editor_dirty = False
            self.editor.setPlainText(self.message_data.get('content', ''))

    def _get_patched_name(self, nickname):
        if self.role == 'user' or self.role == 'system':
            return nickname if nickname else self.role.upper()
        if self.role == 'tool':
            info = self.message_data.get('info', {})
            if 'function' in info:
                return info['function']['name'].upper()
            return self.role.upper()
        if self.role == 'assistant':
            info_data = self.message_data.get('info', {})
            if not nickname:
                if "model" in info_data:
                    nickname = info_data['model']
                else:
                    nickname = 'AI'
                    print('ChatBubble | _get_patched_name: can not find "model":\n',
                          json.dumps(self.message_data, indent=2))
            return nickname

    def _setup_avatar(self):
        if self.avatar_path and os.path.exists(self.avatar_path):
            pixmap = QPixmap(self.avatar_path)
        else:
            pixmap = QPixmap(24, 24)
            color = QColor("#4285F4") if self.role == "user" else QColor("#34A853")
            pixmap.fill(color)
            painter = QPainter(pixmap)
            painter.setPen(Qt.GlobalColor.white)
            painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, self.role[0].upper())
            painter.end()
        size = self.avatar.size()
        scaled = pixmap.scaled(size.width(), size.height(),
                               Qt.AspectRatioMode.KeepAspectRatio,
                               Qt.TransformationMode.SmoothTransformation)
        self.avatar.setIcon(QIcon(scaled))
        self.avatar.setIconSize(size)

    def _connect_signals(self):
        self.buttons.regenerateClicked.connect(
            lambda: self.regenerateRequested.emit(self.id))
        self.buttons.copy_button.clicked.connect(self._handle_copy)
        self.buttons.editToggleClicked.connect(self._handle_edit_toggle)
        self.buttons.detailToggleClicked.connect(self._handle_detail_toggle)
        self.avatar.clicked.connect(self._on_avatar_clicked)
        self.buttons.infoClicked.connect(self._show_info_popup)
        self.content.renderStarted.connect(self.bubbleRenderStarted)
        self.content.renderFinished.connect(self.bubbleRenderFinished)
        self.reasoning_display.renderStarted.connect(self.bubbleRenderStarted)
        self.reasoning_display.renderFinished.connect(self.bubbleRenderFinished)

    def _on_avatar_clicked(self):
        self.RequestAvatarChange.emit(self.id, self.role)

    def _handle_copy(self):
        text = (self.editor.toPlainText() if self.editor.isVisible()
                else self.content.content)
        QApplication.clipboard().setText(text)

    def _handle_edit_toggle(self, editing):
        if editing:
            # 进入编辑模式时才填充编辑器内容
            self._ensure_editor_content()
            self.content_container.show()
            self.content_container.setCurrentIndex(1)
        else:
            self.content_container.setCurrentIndex(0)
            new_content = self.editor.toPlainText()
            self.editFinished.emit(self.id, new_content)
            self.content.setMarkdown(new_content)
            if not new_content:
                self.content_container.hide()

    def _handle_detail_toggle(self, showing):
        real_showing = not self.reasoning_display.isVisible()
        self.manual_expand_reasoning = real_showing
        self.reasoning_display.setVisible(real_showing)
        self.detailToggled.emit(self.id, real_showing)

    def _show_info_popup(self):
        info_data = self.message_data.get('info', {})
        pos = self.buttons.info_button.mapToGlobal(QPoint(0, 0))
        self.info_popup.show_info(info_data, pos)

    def enterEvent(self, event):
        self.button_container.setCurrentIndex(1)
        super().enterEvent(event)

    def leaveEvent(self, event):
        if not self.buttons.edit_button.isChecked():
            self.button_container.setCurrentIndex(0)
        super().leaveEvent(event)

    def update_nickname(self, new_nickname):
        self.role_label.setText(self._get_patched_name(new_nickname))

    def getcontent(self):
        return self.message_data['content']

    def getinfo(self):
        return self.message_data.get('info')

    def update_avatar(self, new_path):
        self.avatar_path = new_path
        self._setup_avatar()

    def update_content(self, content_data: dict):
        if self.buttons.edit_button.isChecked():
            return
        if not self.content.isVisible():
            self.content.show()
        self.reasoning_display.setVisible(self.manual_expand_reasoning)
        content = content_data.get('content', '')
        state = content_data.get('state', 'finished')
        is_streaming = (state == 'streaming')
        if not is_streaming and content == self._content_fp:
            return
        self._content_fp = content
        self.message_data['content'] = content
        self._rendered = True

        if content:
            self.content_container.show()
        else:
            self.content_container.hide()

        self.content.setMarkdown(content, is_streaming=is_streaming)
        if not is_streaming:
            # 标记编辑器为脏，避免立即填充
            self._editor_dirty = True

    def update_reasoning(self, reasoning_data: dict):
        reasoning_content = reasoning_data.get('reasoning_content', '')
        if reasoning_content == self._reasoning_fp:
            return
        self._reasoning_fp = reasoning_content
        self.message_data['reasoning_content'] = reasoning_content
        if reasoning_content:
            self.buttons.set_has_reasoning(True)
            self.reasoning_display.setMarkdown(reasoning_content)
            self.reasoning_display.setVisible(True)
            #if not self.content.toPlainText().strip():
            #    self.content.hide()
            #else:
            #    self.content.show()
        if reasoning_data.get('state') == 'finished':
            self.reasoning_display.setMarkdown(reasoning_content)

    def mousePressEvent(self, event):
        if self.info_popup.isVisible():
            self.info_popup.hide()
        super().mousePressEvent(event)

    def hideEvent(self, event):
        self.info_popup.hide()
        super().hideEvent(event)

class ChatHistoryWidget(QFrame):
    """
    聊天历史记录视图组件。
    负责管理和展示所有聊天气泡，支持对象池复用、性能优化渲染、平滑滚动及动态分页加载。
    """
    regenerateRequested = pyqtSignal(str)
    editFinished = pyqtSignal(str, str)
    detailToggled = pyqtSignal(str, bool)
    RequestAvatarChange = pyqtSignal(str, str)

    def __init__(self, parent=None):
        """初始化聊天历史视图及其内部状态机和计时器。"""
        super().__init__(parent)
        self.bubbles: Dict[str, ChatBubble] = {}
        self.bubble_list: List[ChatBubble] = []
        self.nicknames = {'user': '用户', 'assistant': '助手'}
        self.avatars = {'user': '', 'assistant': ''}
        self.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0);
                border-radius: 5px;
            }
        """)

        self.scroll_timer = QTimer()
        self.scroll_timer.setInterval(10)
        self.scroll_timer.timeout.connect(self.scroll_to_bottom)
        self.is_scroll_update_active = False

        self.is_auto_scroll_enabled = True
        self.not_streaming_dont_scroll = True
        self.wheel_timer = QTimer()
        self.wheel_timer.setInterval(500)
        self.wheel_timer.setSingleShot(True)

        self._bubble_pools: Dict[str, List[ChatBubble]] = {}

        self._render_queue: List[ChatBubble] = []
        self._render_timer = QTimer()
        self._render_timer.setInterval(0)
        self._render_timer.timeout.connect(self._process_render_queue)

        self._full_history: List[dict] = []
        self._displayed_count: int = 0
        self._load_more_timer = QTimer()
        self._load_more_timer.setInterval(200)
        self._load_more_timer.setSingleShot(True)
        self._load_more_timer.timeout.connect(self._load_earlier_messages)
        self._is_loading_more: bool = False

        self._scroll_mode: str = 'none'
        self._keep_pos_old_max: int = 0
        self._keep_pos_old_val: int = 0
        self._pending_renders: int = 0

        self._scroll_stable_timer = QTimer()
        self._scroll_stable_timer.setInterval(200)
        self._scroll_stable_timer.setSingleShot(True)
        self._scroll_stable_timer.timeout.connect(self._end_scroll_mode)

        self._perf_start: float = 0

        self._pool_container = QWidget(self)
        self._pool_container.setVisible(False)

        self._pool_hits: int = 0
        self._pool_misses: int = 0
        self._deleted_ids = {}                   # 孤儿更新拦截黑名单

        # 预热相关变量
        self._preheat_queue: List[str] = []       
        self._preheat_timer = QTimer()
        self._preheat_timer.setInterval(0)         
        self._preheat_timer.timeout.connect(self._process_preheat)

        self.init_ui()
        self.connect_signals()

        # 启动预热流程
        self._start_preheat()

    def _start_preheat(self):
        """
        构建预热队列，延迟到事件循环空闲时分批创建对象，
        以应对各种极端比例的对话历史，确保首次加载具有极高命中率。
        """
        count = APP_SETTINGS.ui.display_message_count

        user_count = max(1, int(count * 0.6))
        assistant_count = max(1, int(count * 0.6))
        tool_count = max(1, int(count * 0.3))

        self._preheat_queue = (
            ['user'] * user_count +
            ['assistant'] * assistant_count +
            ['tool'] * tool_count
        )

        QTimer.singleShot(500, self._preheat_timer.start)

    def _process_preheat(self):
        """每次空闲时创建 1 个气泡并放入对象池中。"""
        if not self._preheat_queue:
            self._preheat_timer.stop()
            return

        role = self._preheat_queue.pop(0)

        dummy_id = f'_preheat_{role}_{len(self._preheat_queue)}'
        dummy_msg = {
            'role': role,
            'content': '',
            'info': {
                'id': dummy_id,
                'model':''
            },
        }

        bubble = ChatBubble(
            dummy_msg,
            nickname='',
            avatar_path='',
            msg_id=dummy_id,
            defer_render=True)

        bubble.regenerateRequested.connect(self.regenerateRequested.emit)
        bubble.editFinished.connect(self.editFinished.emit)
        bubble.detailToggled.connect(self.detailToggled.emit)
        bubble.RequestAvatarChange.connect(self.RequestAvatarChange.emit)
        bubble.bubbleRenderStarted.connect(self._on_render_started)
        bubble.bubbleRenderFinished.connect(self._on_render_finished)

        bubble.setVisible(False)
        bubble.setParent(self._pool_container)

        pool = self._bubble_pools.setdefault(role, [])
        pool.append(bubble)

    # =========== 对象池 ===========

    def _pool_status(self) -> str:
        """获取当前对象池的缓存状态。"""
        parts = []
        for role in ('user', 'assistant', 'tool','system'):
            pool = self._bubble_pools.get(role, [])
            if pool:
                parts.append(f'{role}={len(pool)}')
        return '{' + ', '.join(parts) + '}' if parts else '{空}'

    def _acquire_bubble(self, role: str, message_data: dict, msg_id: str) -> ChatBubble:
        """从对象池获取或者实例化一个新的气泡控件。"""
        pool = self._bubble_pools.get(role, [])
        if pool:
            self._pool_hits += 1
            bubble = pool.pop()
            bubble.reset(
                message_data,
                nickname=self.nicknames.get(role, ''),
                avatar_path=self.avatars.get(role, ''),
                msg_id=msg_id)
            return bubble

        self._pool_misses += 1
        bubble = ChatBubble(
            message_data,
            nickname=self.nicknames.get(role, ''),
            avatar_path=self.avatars.get(role, ''),
            msg_id=msg_id,
            defer_render=True)

        bubble.regenerateRequested.connect(self.regenerateRequested.emit)
        bubble.editFinished.connect(self.editFinished.emit)
        bubble.detailToggled.connect(self.detailToggled.emit)
        bubble.RequestAvatarChange.connect(self.RequestAvatarChange.emit)
        bubble.bubbleRenderStarted.connect(self._on_render_started)
        bubble.bubbleRenderFinished.connect(self._on_render_finished)
        return bubble

    def _release_bubble(self, bubble: ChatBubble):
        """回收气泡控件到对象池中，超过最大容量则销毁。"""
        self.content_layout.removeWidget(bubble)
        bubble.content.invalidate_pending_renders()
        bubble.reasoning_display.invalidate_pending_renders()
        bubble.setVisible(False)
        bubble.setParent(self._pool_container)
        pool = self._bubble_pools.setdefault(bubble.role, [])
        max_pool = APP_SETTINGS.ui.display_message_count
        if len(pool) < max_pool:
            pool.append(bubble)
        else:
            bubble.setParent(None)
            bubble.deleteLater()

    def _attach_bubble(self, bubble: ChatBubble):
        """将气泡控件附加到底部显示。"""
        self.content_layout.addWidget(bubble)
        bubble.setVisible(True)

    def _insert_bubble(self, bubble: ChatBubble, position: int):
        """将气泡控件插入到指定位置显示。"""
        self.content_layout.insertWidget(position, bubble)
        bubble.setVisible(True)

    # =========== 延迟调度 ===========

    def _schedule_deferred_render(self):
        """调度延迟渲染任务，优化大规模消息加载时的卡顿现象。"""
        IMMEDIATE_COUNT = 3
        if len(self.bubble_list) <= IMMEDIATE_COUNT:
            immediate = self.bubble_list
            deferred = []
        else:
            immediate = self.bubble_list[-IMMEDIATE_COUNT:]
            deferred = self.bubble_list[:-IMMEDIATE_COUNT]
        for b in immediate:
            if not b._rendered:
                b.render_content()
        self._render_queue = [b for b in deferred if not b._rendered]
        if self._render_queue:
            self._render_timer.start()

    def _process_render_queue(self):
        """处理渲染队列，逐批次完成内容渲染。"""
        BATCH = 2
        for _ in range(BATCH):
            if not self._render_queue:
                self._render_timer.stop()
                return
            bubble = self._render_queue.pop(0)
            if not bubble._rendered:
                bubble.render_content()

    # =========== 渲染计数 ===========

    def _on_render_started(self):
        """渲染开始时增加等待计数。"""
        self._pending_renders += 1

    def _on_render_finished(self):
        """渲染结束时减少等待计数并在符合条件时触发滚动。"""
        if self._pending_renders > 0:
            self._pending_renders -= 1
        if self._pending_renders == 0 and self._scroll_mode == 'scroll_bottom':
            self.scroll_to_bottom()

    # =========== 滚动状态机 ===========

    def _on_range_changed(self, new_min: int, new_max: int):
        """处理滚动条范围变化事件，以维持滚动模式状态。"""
        if self._scroll_mode == 'scroll_bottom':
            self.scroll_bar.setValue(new_max)
            if self._pending_renders == 0:
                self._scroll_stable_timer.start()
        elif self._scroll_mode == 'keep_position':
            delta = new_max - self._keep_pos_old_max
            if delta > 0:
                new_val = self._keep_pos_old_val + delta
                self.scroll_bar.setValue(new_val)
                self._keep_pos_old_max = new_max
                self._keep_pos_old_val = new_val
            if self._pending_renders == 0:
                self._scroll_stable_timer.start()

    def _begin_scroll_bottom(self):
        """启动滚动到底部模式。"""
        self._scroll_mode = 'scroll_bottom'
        self._scroll_stable_timer.stop()

    def _begin_keep_position(self):
        """启动保持当前视图相对位置模式。"""
        self._keep_pos_old_max = self.scroll_bar.maximum()
        self._keep_pos_old_val = self.scroll_bar.value()
        self._scroll_mode = 'keep_position'
        self._scroll_stable_timer.stop()

    def _end_scroll_mode(self):
        """结束自动滚动模式并计算真实性能耗时。"""
        if self._scroll_mode == 'scroll_bottom':
            self.scroll_bar.setValue(self.scroll_bar.maximum())
            #if self._perf_start > 0:
            #    real_total = (time.time() - self._perf_start) * 1000
            #    #print(f'[布局完成] 真实总耗时={real_total:.2f}ms '
            #    #      f'(pending={self._pending_renders})')
            #    self._perf_start = 0
        self._scroll_mode = 'none'

    # =========== UI ===========

    def init_ui(self):
        """初始化聊天记录视图界面布局及核心组件。"""
        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().setSpacing(0)
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        content_widget = QFrame()
        self.content_layout = QVBoxLayout(content_widget)
        self.content_layout.setContentsMargins(20, 10, 20, 20)
        self.content_layout.setSpacing(15)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignBottom)
        scroll_area.setWidget(content_widget)
        self.layout().addWidget(scroll_area)
        self.scroll_area = self.findChild(QScrollArea)
        self.scroll_bar = self.scroll_area.verticalScrollBar()
        if self.scroll_area:
            self.scroll_area.viewport().installEventFilter(self)
            self.scroll_area.verticalScrollBar().installEventFilter(self)
        self.scroll_bar.rangeChanged.connect(self._on_range_changed)
        self.spacer = QLabel()
        self.spacer.setMaximumHeight(200)
        self.spacer.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        self.spacer.setStyleSheet("QWidget { background-color: rgba(255, 255, 255, 0); }")
        self.content_layout.addWidget(self.spacer, stretch=0)

    def connect_signals(self):
        """连接内部及外部的信号槽。"""
        self.editFinished.connect(
            lambda msg_id, content: self.update_bubble_content(
                msg_id, {'content': content}))

    # =========== 向上加载 ===========

    def _get_displayable_history(self) -> List[dict]:
        """获取可以展示的聊天历史过滤列表。"""
        return [m for m in self._full_history
                if m.get('role') in ('user', 'assistant', 'tool','system') and m.get('info')['id'] != 'system_prompt']

    def _has_earlier_messages(self) -> bool:
        """检查是否还有更早的未展示消息。"""
        displayable = self._get_displayable_history()
        return self._displayed_count < len(displayable)

    def _load_earlier_messages(self):
        """向上滚动触发时，从历史数据中分页加载旧消息。"""
        if self._is_loading_more:
            return
        if not self._has_earlier_messages():
            return
        self._is_loading_more = True
        batch_size = APP_SETTINGS.ui.display_message_count
        displayable = self._get_displayable_history()
        total = len(displayable)
        new_end = total - self._displayed_count
        new_start = max(0, new_end - batch_size)
        batch = displayable[new_start:new_end]
        if not batch:
            self._is_loading_more = False
            return
            
        self._begin_keep_position()
        self.setUpdatesEnabled(False)
        try:
            insert_pos = 1
            new_bubbles = []
            for msg in batch:
                mid = msg['info']['id']

                if mid in self.bubbles:
                    continue
                role = msg['role']
                reasoning = msg.get('reasoning_content', '')
                if role == 'tool' and 'function' in msg.get('info', {}):
                    reasoning = msg['info']['function']['arguments']
                if reasoning:
                    msg['reasoning_content'] = reasoning
                bubble = self._acquire_bubble(role, msg, mid)
                bubble.render_content()
                self.bubbles[mid] = bubble
                new_bubbles.append(bubble)
                self._insert_bubble(bubble, insert_pos)
                insert_pos += 1
            self.bubble_list = new_bubbles + self.bubble_list
            self._displayed_count += len(new_bubbles)
        except Exception:
            traceback.print_exc()
        finally:
            self.setUpdatesEnabled(True)
        self._is_loading_more = False

    # ==================================================
    #  set_chat_history
    # ==================================================

    def set_chat_history(self, history: list):
        """
        全量覆盖或更新当前聊天历史记录。
        通过比对差异进行增量布局及气泡复用更新。
        """
        st = time.time()
        self._perf_start = st
        self.is_auto_scroll_enabled = True
        self.not_streaming_dont_scroll = True

        self._render_timer.stop()
        self._render_queue.clear()
        self._pending_renders = 0
        self._pool_hits = 0
        self._pool_misses = 0

        if self._preheat_timer.isActive():
            self._preheat_timer.stop()
            self._preheat_queue.clear()

        self._full_history = list(history)

        display_count = APP_SETTINGS.ui.display_message_count
        displayable = self._get_displayable_history()
        tail = displayable[-display_count:]

        try:
            new_id_map: Dict[str, dict] = {
                msg['info']['id']: msg for msg in tail}
        except (KeyError, TypeError):
            traceback.print_exc()
            return

        new_id_set = set(new_id_map.keys())
        old_id_set = set(self.bubbles.keys())

        self._begin_scroll_bottom()

        self.setUpdatesEnabled(False)
        try:
            t_del_start = time.time()
            for dead_id in old_id_set - new_id_set:
                self._deleted_ids[dead_id] = None

                if len(self._deleted_ids) > 1000:
                    self._deleted_ids.pop(next(iter(self._deleted_ids)))

                bubble = self.bubbles.pop(dead_id)
                self.bubble_list = [b for b in self.bubble_list if b.msg_id != dead_id]
                self._release_bubble(bubble)
            t_del = (time.time() - t_del_start) * 1000

            t_upd_start = time.time()
            
            for alive_id in old_id_set & new_id_set:
                bubble = self.bubbles[alive_id]
                new_msg = new_id_map[alive_id]
                role = new_msg.get('role', '')
 
                if role == 'tool' and 'function' in new_msg.get('info', {}):
                    new_r = new_msg['info']['function']['arguments']
                else:
                    new_r = new_msg.get('reasoning_content', '')
                
                if new_r != bubble._reasoning_fp:
                    bubble.update_reasoning({
                        'reasoning_content': new_r, 'state': 'finished'})
                
                
                new_c = new_msg.get('content', '')

                if new_c != bubble._content_fp:
                    bubble.update_content({
                        'content': new_c,
                        'state': 'finished'})

                new_info = new_msg.get('info', {})
                if new_info != bubble.message_data.get('info', {}):
                    bubble.message_data['info'] = new_info
            t_upd = (time.time() - t_upd_start) * 1000

            t_add_start = time.time()
            existing = set(self.bubbles.keys())
            for msg in tail:
                mid = msg['info']['id']
                self._deleted_ids.pop(mid, None) 
                if mid not in existing:
                    role = msg['role']
                    reasoning = msg.get('reasoning_content', '')
                    if role == 'tool' and 'function' in msg.get('info', {}):
                        reasoning = msg['info']['function']['arguments']
                    if reasoning:
                        msg['reasoning_content'] = reasoning
                    bubble = self._acquire_bubble(role, msg, mid)
                    self.bubbles[mid] = bubble
                    self.bubble_list.append(bubble)
                    self._attach_bubble(bubble)
            t_add = (time.time() - t_add_start) * 1000

            self._reorder_bubbles_by_list(tail)
            self._force_sync(new_id_set)

            t_render_start = time.time()
            self._schedule_deferred_render()
            t_render = (time.time() - t_render_start) * 1000

        except Exception:
            traceback.print_exc()
        finally:
            self.setUpdatesEnabled(True)

        self._displayed_count = len(self.bubble_list)

        self.update_all_nicknames()
        self.scroll_to_bottom()

        #t_sync = (time.time() - st) * 1000
        #remaining = len(displayable) - self._displayed_count
        #print(f'[同步调度完成] {t_sync:.2f}ms '
        #      f'(删={t_del:.1f} 更新={t_upd:.1f} '
        #      f'新增={t_add:.1f} 渲染调度={t_render:.1f}ms), '
        #      f'pool命中={self._pool_hits} 未命中={self._pool_misses}, '
        #      f'气泡数={len(self.bubble_list)}, '
        #      f'pending={self._pending_renders}, '
        #      f'未加载={remaining}, '
        #      f'池={self._pool_status()}'
        #      f'已显示数量：{self._count_visible_bubbles_in_layout()}')
    
    def _count_visible_bubbles_in_layout(self) -> int:
        """从 UI 布局中真实统计当前可见的 ChatBubble 数量，用于 DEBUG 校对"""
        count = 0
        for i in range(self.content_layout.count()):
            item = self.content_layout.itemAt(i)
            w = item.widget()
            if isinstance(w, ChatBubble) and w.isVisible():
                count += 1
        return count

    def _force_sync(self, expected_ids: set):
        """强制清理并同步布局中任何游离的无用气泡和控件。"""
        valid_widgets = {self.spacer} | {b for b in self.bubble_list}
        stale_dict_ids = set(self.bubbles.keys()) - expected_ids
        for stale_id in stale_dict_ids:
            bubble = self.bubbles.pop(stale_id)
            self._release_bubble(bubble)
            
        valid_bubbles = set(self.bubbles.values())
        stale_in_list = [b for b in self.bubble_list if b not in valid_bubbles]
        if stale_in_list:
            for b in stale_in_list:
                self._release_bubble(b)
            self.bubble_list = [b for b in self.bubble_list if b in valid_bubbles]
            
        to_remove = []
        for i in range(self.content_layout.count()):
            item = self.content_layout.itemAt(i)
            w = item.widget()
            if w is not None and w not in valid_widgets:
                to_remove.append(w)
        for w in to_remove:
            self.content_layout.removeWidget(w)
            w.setVisible(False)
            w.setParent(self._pool_container)
            
        content_widget = self.scroll_area.widget()
        if content_widget:
            for child in content_widget.findChildren(ChatBubble):
                if child not in valid_bubbles and child.isVisible():
                    child.setVisible(False)
                    child.setParent(self._pool_container)

    def _reorder_bubbles_by_list(self, ordered_msgs: list):
        """根据传入列表对视图中的气泡顺序进行重排。"""
        desired_ids = [
            msg['info']['id'] for msg in ordered_msgs
            if msg['info']['id'] in self.bubbles]
        current_ids = [b.msg_id for b in self.bubble_list]
        if desired_ids == current_ids:
            return
        for bubble in self.bubble_list:
            self.content_layout.removeWidget(bubble)
        new_bubble_list = [self.bubbles[mid] for mid in desired_ids]
        for bubble in new_bubble_list:
            self.content_layout.addWidget(bubble)
        self.bubble_list = new_bubble_list

    def clear_history(self):
        """公开方法：清空历史。"""
        self.clear()

    def clear(self):
        """
        清空当前显示的聊天历史。
        显示中的气泡归还到池（不销毁），以便下次复用。
        """
        self._render_timer.stop()
        self._render_queue.clear()
        self._preheat_timer.stop()
        self._preheat_queue.clear()
        self._scroll_mode = 'none'
        self._scroll_stable_timer.stop()
        self._pending_renders = 0
        self._full_history = []
        self._displayed_count = 0
        self._perf_start = 0

        for bubble in self.bubble_list:
            self._deleted_ids[bubble.msg_id] = None
            if len(self._deleted_ids) > 1000:
                self._deleted_ids.pop(next(iter(self._deleted_ids)))

        self.bubbles = {}
        self.bubble_list = []

        if self.content_layout.indexOf(self.spacer) < 0:
            self.content_layout.addWidget(self.spacer)

    def destroy_pools(self):
        """真正销毁池（仅在 ChatHistoryWidget 本身被销毁时调用）。"""
        for pool in self._bubble_pools.values():
            for b in pool:
                b.setParent(None)
                b.deleteLater()
        self._bubble_pools.clear()
    
    def pop_bubble(self, msg_id):
        """弹出移除指定ID的聊天气泡并回收。"""
        if msg_id in self.bubbles:
            bubble = self.bubbles.pop(msg_id)
            self.bubble_list = [b for b in self.bubble_list if b.msg_id != msg_id]
            self._displayed_count = len(self.bubble_list)
            self._release_bubble(bubble)

    def add_message(self, message_data: dict, streaming=False):
        """向当前聊天列表中添加单个新消息气泡。"""
        role = message_data['role']
        if role not in ('user', 'assistant', 'tool','system'):
            return
        
        msg_id = message_data['info']['id']
        if not msg_id or msg_id in self._deleted_ids:
            return
        
        reasoning_content = message_data.get('reasoning_content', '')
        if role == 'tool' and 'function' in message_data.get('info', {}):
            reasoning_content = message_data['info']['function']['arguments']
        if reasoning_content:
            message_data['reasoning_content'] = reasoning_content
        bubble = self._acquire_bubble(role, message_data, msg_id)
        bubble.render_content()
        self.bubble_list.append(bubble)
        self.bubbles[msg_id] = bubble
        self._attach_bubble(bubble)
        self._displayed_count = len(self.bubble_list)
        return bubble

    def update_bubble_content(self, msg_id, content_data):
        """更新指定气泡的主体内容。"""
        bubble = self.bubbles.get(msg_id)
        if bubble:
            bubble.update_content(content_data)

    def update_bubble_reasoning(self, msg_id, reasoning_data):
        """更新指定气泡的推理(Reasoning)过程内容。"""
        bubble = self.bubbles.get(msg_id)
        if bubble:
            bubble.update_reasoning(reasoning_data)

    def update_bubble_info(self, msg_id, info_data):
        """更新指定气泡的附加信息（如模型等）。"""
        bubble = self.bubbles.get(msg_id)
        if bubble:
            bubble.message_data['info'] = info_data

    def update_bubble(
            self, message='',
            msg_id='', content='', reasoning_content='',
            tool_content='', info='', streaming='streaming',
            model='', role='assistant'):
        """流式输出时的综合气泡内容更新接口，支持全量字典覆盖或按字段更新。"""
        if tool_content:
            reasoning_content = tool_content
        
        target_id = msg_id
        if message:
            if isinstance(message, dict):
                target_id = message.get('info', {}).get('id', message.get('id', target_id))

        if target_id in self._deleted_ids:
            # 命中黑名单，放弃任何更新或新建
            return


        if message and message['id'] not in self.bubbles:
            self.add_message(message)
            return
        
        if message and message['id'] in self.bubbles:
            if 'content' in message:
                self.update_bubble_content(
                    message['id'], {'content': message['content']})
            if 'reasoning_content' in message:
                self.update_bubble_reasoning(
                    message['id'],
                    {'reasoning_content': message['reasoning_content']})
            return
        if not message and msg_id not in self.bubbles:
            build_message = {
                'role': role,
                'content': content,
                'reasoning_content': reasoning_content,
                'info': {'id': msg_id, 'model': model},
                'streaming': streaming}
            self.add_message(build_message)
            return
        if not message and msg_id in self.bubbles:
            if reasoning_content:
                self.update_bubble_reasoning(msg_id, {
                    'reasoning_content': reasoning_content,
                    'streaming': streaming})
            if content:
                self.update_bubble_content(msg_id, {
                    'content': content, 'streaming': streaming})
            if info:
                self.update_bubble_info(msg_id, info)
            return
        if info:
            self.update_bubble_info(msg_id, info)

    def set_role_nickname(self, role, nickname):
        """设置特定角色的昵称并更新已有的所有对应气泡。"""
        if nickname != self.nicknames[role]:
            self.nicknames[role] = nickname
            self.update_all_nicknames()

    def set_role_avatar(self, role, avatar_path):
        """设置特定角色的头像并更新已有的所有对应气泡。"""
        self.avatars[role] = avatar_path
        self.update_all_avatars()

    def update_all_nicknames(self):
        """同步更新所有显示气泡中的角色昵称。"""
        for bubble in self.bubbles.values():
            bubble.update_nickname(
                self.nicknames.get(bubble.role, bubble.role.capitalize()))

    def update_all_avatars(self, new_path={}):
        """同步更新所有显示气泡中的角色头像。"""
        if new_path:
            self.avatars = new_path
        for bubble in self.bubbles.values():
            bubble.update_avatar(self.avatars.get(bubble.role, ''))

    def scroll_to_bottom(self):
        """立即滚动到视图底部。"""
        if self.scroll_area:
            self.scroll_bar.setValue(self.scroll_bar.maximum())

    def streaming_scroll(self, run=True, scroll_time=10):
        """控制流式输出时的平滑自动滚动特性。"""
        self.not_streaming_dont_scroll = not run
        if not self.is_auto_scroll_enabled:
            self.scroll_timer.stop()
            return
        if self.scroll_timer.interval() != scroll_time:
            self.scroll_timer.stop()
            self.scroll_timer.setInterval(scroll_time)
            self.scroll_timer.start()
        if run:
            if self.is_scroll_update_active:
                return
            self.is_scroll_update_active = True
            self.scroll_timer.start()
        else:
            self.is_scroll_update_active = False
            self.scroll_timer.stop()

    def eventFilter(self, obj, event: QEvent):
        """捕获底层事件（如鼠标滚轮事件），以便处理自动加载和解除锁定到底部状态。"""
        if event.type() == QEvent.Type.Wheel:
            if (self._scroll_mode == 'scroll_bottom'
                    and event.angleDelta().y() > 0):
                self._scroll_mode = 'none'
                self._scroll_stable_timer.stop()
            self._handle_wheel_event(event)
            if (event.angleDelta().y() > 0
                    and self.scroll_bar.value() <= 50
                    and self._has_earlier_messages()
                    and not self._is_loading_more):
                self._load_more_timer.start()
            return False
        return super().eventFilter(obj, event)

    def _handle_wheel_event(self, event):
        """处理鼠标滚轮的具体逻辑，决定是否中断流式自动滚动。"""
        if self.wheel_timer.isActive() or self.not_streaming_dont_scroll:
            return
        if self.is_auto_scroll_enabled and event.angleDelta().y() > 0:
            self.wheel_timer.start()
            self.scroll_timer.stop()
            self.is_auto_scroll_enabled = False
            self.is_scroll_update_active = False
        elif (int(self.scroll_bar.value()) == int(self.scroll_bar.maximum())
              and event.angleDelta().y() < 0):
            self.wheel_timer.start()
            self.is_auto_scroll_enabled = True
            self.streaming_scroll()

    

class ChatHistoryTextView(QWidget):
    """A dialog window for displaying full chat history with right-aligned controls."""
    
    def __init__(self, chat_history):
        super().__init__()
        self.chat_history = chat_history
        self.user_name = 'USER'
        self.ai_name = 'ASSISTANT'

        if chat_history and isinstance(chat_history[0], dict):
            first_msg = chat_history[0]
            info = first_msg.get('info', {})
            name_data = info.get('name', {}) if isinstance(info, dict) else {}
            
            if isinstance(name_data, dict):
                if name_data.get('user'):
                    self.user_name = name_data['user']
                if name_data.get('assistant'):
                    self.ai_name = name_data['assistant']
        
        self.setWindowTitle("聊天历史-文本")
        self.setMinimumSize(1280, 720)  # 增加最小宽度以适应右侧面板
        
        # 显示选项默认值
        self.show_reasoning = False
        self.show_tools = True
        self.show_metadata = False
        self.use_markdown = True
        
        self._init_ui()
        self._load_chat_history()
    
    def _init_ui(self):
        """初始化UI组件，控制面板在右侧"""
        main_layout = QHBoxLayout()  # 使用水平布局
        
        # 创建文本浏览区域（左侧）
        self.text_browser = QTextBrowser()
        self.text_browser.setOpenExternalLinks(True)
        main_layout.addWidget(self.text_browser, 3)  # 文本区域占3/4宽度
        
        # 创建右侧面板布局
        controls_layout = QVBoxLayout()
        controls_layout.setAlignment(Qt.AlignmentFlag.AlignTop)
        
        # 添加"显示选项"分组框（右侧）
        options_group = QGroupBox("显示选项")
        options_layout = QVBoxLayout()
        
        # 添加思考链选项
        reasoning_group = QGroupBox("思考链")
        reasoning_layout = QVBoxLayout()
        self.reasoning_cb = QCheckBox("显示思考链")
        self.reasoning_cb.stateChanged.connect(self._toggle_reasoning)
        reasoning_layout.addWidget(self.reasoning_cb)
        reasoning_group.setLayout(reasoning_layout)
        options_layout.addWidget(reasoning_group)
        
        # 添加工具调用选项
        tools_group = QGroupBox("工具调用")
        tools_layout = QVBoxLayout()
        self.tools_cb = QCheckBox("显示工具调用")
        self.tools_cb.setChecked(True)
        self.tools_cb.stateChanged.connect(self._toggle_tools)
        tools_layout.addWidget(self.tools_cb)
        tools_group.setLayout(tools_layout)
        options_layout.addWidget(tools_group)
        
        # 添加元数据显示选项
        metadata_group = QGroupBox("元数据")
        metadata_layout = QVBoxLayout()
        self.metadata_cb = QCheckBox("显示消息元数据")
        self.metadata_cb.stateChanged.connect(self._toggle_metadata)
        metadata_layout.addWidget(self.metadata_cb)
        metadata_group.setLayout(metadata_layout)
        options_layout.addWidget(metadata_group)
        
        # 添加格式选项（右下角）
        format_group = QGroupBox("显示格式")
        format_layout = QVBoxLayout()
        
        self.markdown_rb = QRadioButton("Markdown格式")
        self.markdown_rb.setChecked(True)
        self.markdown_rb.toggled.connect(self._toggle_format)
        
        self.plaintext_rb = QRadioButton("纯文本格式")
        self.plaintext_rb.toggled.connect(self._toggle_format)
        
        format_layout.addWidget(self.markdown_rb)
        format_layout.addWidget(self.plaintext_rb)
        format_group.setLayout(format_layout)
        options_layout.addWidget(format_group)
        
        # 添加重载按钮
        reload_btn = QPushButton("刷新视图")
        reload_btn.clicked.connect(self._load_chat_history)
        options_layout.addWidget(reload_btn)
        
        # 添加间距
        options_layout.addSpacing(20)

        options_group.setLayout(options_layout)
        controls_layout.addWidget(options_group)
        
        # 创建右侧容器
        controls_container = QWidget()
        controls_container.setLayout(controls_layout)
        
        main_layout.addWidget(controls_container, 1)  # 右侧面板占1/4宽度
        
        self.setLayout(main_layout)
    
    def _toggle_reasoning(self, state):
        self.show_reasoning = (state == Qt.CheckState.Checked)
        self._load_chat_history()
    
    def _toggle_tools(self, state):
        self.show_tools = (state == Qt.CheckState.Checked)
        self._load_chat_history()
    
    def _toggle_metadata(self, state):
        self.show_metadata = (state == Qt.CheckState.Checked)
        self._load_chat_history()
    
    def _toggle_format(self):
        self.use_markdown = self.markdown_rb.isChecked()
        self._load_chat_history()
    
    def _load_chat_history(self):
        """根据选项加载和格式化聊天历史"""
        buffer = []
        
        for index, msg in enumerate(self.chat_history):
            # 获取发送者名称
            role = msg.get('role', '')
            name = self._get_sender_name(role)
            
            # 过滤工具调用消息（如果不显示）
            if role == 'tool' and not self.show_tools:
                continue
                
            # 添加消息头部标识
            if self.use_markdown:
                buffer.append(f"\n\n**{name}**")
            else:
                buffer.append(f"\n\n{name}")

            # 添加思考链（如果存在且需要显示）
            msg: Dict[str, str]
            if self.show_reasoning and 'reasoning_content' in msg:
                reasoning_content = msg['reasoning_content'].replace('### AI 思考链\n---', '').strip()
                if reasoning_content:
                    if self.use_markdown:
                        buffer.append(f"\n```  \n Think: {reasoning_content}  \n  ```  \n---  \n  ")
                    else:
                        buffer.append(f"\n```  \n Think: {reasoning_content}  \n  ```  \n---  \n  ")
            
            # 添加消息内容
            content = msg.get('content', '')
            if content:
                buffer.append(f"\n\n{content}")
            
            # 添加元数据（如果存在且需要显示）
            if self.show_metadata and 'info' in msg:
                info:dict = msg['info']
                if info:
                    if self.use_markdown:
                        buffer.append("\n\n<small>")
                        buffer.append("\n \n ")
                        if msg['role'] == 'system':
                            buffer.append("系统提示设置")
                        else:
                            parts = []
                            if info.get('model'):
                                parts.append(f"模型: {info['model']}")
                            if info.get('time'):
                                parts.append(f"时间: {info['time']}")
                            if info.get('id'):
                                parts.append(f"ID: {info['id']}")
                            buffer.append(" | ".join(parts))
                        buffer.append("</small>")
                    else:
                        buffer.append("\n[元数据]")
                        if msg['role'] == 'system':
                            buffer.append("系统提示设置")
                        else:
                            if info.get('model'):
                                buffer.append(f"  模型: {info['model']}")
                            if info.get('time'):
                                buffer.append(f"  时间: {info['time']}")
                            if info.get('id'):
                                buffer.append(f"  消息ID: {info['id']}")
            
            # 添加消息分隔线（不是最后一条消息）
            if index < len(self.chat_history) - 1:
                buffer.append("\n" + ("---" if self.use_markdown else "="*10))
        
        # 根据格式设置文本
        full_text = '\n'.join(buffer).strip()
        if self.use_markdown:
            self.text_browser.setMarkdown(full_text)
        else:
            self.text_browser.setPlainText(full_text)
    
    def _get_sender_name(self, role):
        if role == 'system':
            return '系统提示'
        elif role == 'user':
            return self.user_name
        elif role == 'assistant':
            return self.ai_name
        elif role == 'tool':
            return f"{self.ai_name} called tool"
        return role


class HistoryListWidget(QListWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # 性能与体验优化（可选）
        self.setUniformItemSizes(True)  # 每项统一高度，加速布局计算
        self.setAlternatingRowColors(True)
        self._history_signature = None  # 用于跳过重复刷新

    def populate_history(self, history_data):
        """
        高效填充历史记录：
        - 增量更新：只改动变化的项
        - 暂停重绘/信号，减少 UI 开销
        - 保留当前选中项
        """
        # 若数据完全一致，则跳过
        sig = tuple(
            (item.get('file_path'), item.get('modification_time'), item.get('title'))
            for item in history_data or []
        )
        if sig == self._history_signature:
            return
        self._history_signature = sig

        # 记录当前选中项（按 file_path）
        selected_fp = None
        cur = self.currentItem()
        if cur:
            data = cur.data(Qt.ItemDataRole.UserRole)
            if isinstance(data, dict):
                selected_fp = data.get('file_path')

        # 暂停信号与重绘
        self.blockSignals(True)
        self.setUpdatesEnabled(False)
        sorting_prev = self.isSortingEnabled()
        self.setSortingEnabled(False)  # 防止排序影响插入顺序

        try:
            # 新数据的顺序与精简映射
            new_order = []
            new_map = {}
            for d in (history_data or []):
                fp = d.get('file_path')
                if not fp:
                    continue  # 跳过无效数据
                lean = {
                    'file_path': fp,
                    'title': d.get('title', 'Untitled Chat'),
                    'modification_time': d.get('modification_time', 0),
                }
                new_order.append(fp)
                new_map[fp] = lean

            # 旧项映射：file_path -> QListWidgetItem
            old_map = {}
            for row in range(self.count()):
                item = self.item(row)
                data = item.data(Qt.ItemDataRole.UserRole)
                fp = data.get('file_path') if isinstance(data, dict) else None
                if fp:
                    old_map[fp] = item

            # 删除不再存在的项（从底部开始避免重排成本）
            to_remove_rows = sorted(
                (self.row(item) for fp, item in old_map.items() if fp not in new_map),
                reverse=True
            )
            for row in to_remove_rows:
                it = self.takeItem(row)
                del it  # 提示 GC 回收

            # 按新顺序逐个处理：更新/移动/新增
            for target_row, fp in enumerate(new_order):
                data = new_map[fp]
                if fp in old_map:
                    item:QListWidgetItem = old_map[fp]
                    # 文本变化才更新，减少不必要的刷新
                    if item.text() != data['title']:
                        item.setText(data['title'])
                    # 更新存储数据
                    item.setData(Qt.ItemDataRole.UserRole, data)
                    # 若位置不对，移动到目标位置
                    cur_row = self.row(item)
                    if cur_row != target_row:
                        self.takeItem(cur_row)
                        self.insertItem(target_row, item)
                else:
                    # 新增项
                    item = QListWidgetItem(data['title'])
                    item.setData(Qt.ItemDataRole.UserRole, data)
                    self.insertItem(target_row, item)

            # 恢复选中项（若仍存在）
            if selected_fp and selected_fp in new_map:
                for row in range(self.count()):
                    item = self.item(row)
                    data = item.data(Qt.ItemDataRole.UserRole)
                    if isinstance(data, dict) and data.get('file_path') == selected_fp:
                        self.setCurrentRow(row)
                        break
            else:
                # 无选中项则选择第一项（可按需调整）
                if self.count() and self.currentRow() < 0:
                    self.setCurrentRow(0)

        finally:
            self.setSortingEnabled(sorting_prev)
            self.setUpdatesEnabled(True)
            self.blockSignals(False)
    
    def get_selected_file_path(self):
        """获取当前选中项的文件路径"""
        current_item = self.currentItem()
        if current_item:
            item_data = current_item.data(Qt.ItemDataRole.UserRole)
            return item_data.get('file_path')
        return None

    def get_selected_item_data(self):
        """获取当前选中项的完整数据"""
        current_item = self.currentItem()
        if current_item:
            return current_item.data(Qt.ItemDataRole.UserRole)
        return None
