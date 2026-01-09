import json
import os
from typing import Any, List, Optional, Tuple

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
    QPlainTextEdit, QFormLayout
)
from utils.assets.markdown_browser import MarkdownTextBrowser
ChatapiTextBrowser=MarkdownTextBrowser

def _clear_layout(layout) -> None:
    """安全清空布局：递归删除 widget / 子布局 / spacer，避免残留。"""
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

        # spacerItem 无需 deleteLater，丢弃即可


def _qcolor_to_rgba(c: QColor, alpha: int) -> str:
    return f"rgba({c.red()}, {c.green()}, {c.blue()}, {alpha})"


class InfoPopup(QWidget):
    """用于显示消息详情信息的悬浮窗（可滚动、自动贴边、可显示任意结构）"""

    def __init__(self, parent: Optional[QWidget] = None):
        super().__init__(parent, Qt.WindowType.Popup | Qt.WindowType.FramelessWindowHint)

        # 让外层透明，由内部 container 负责绘制背景（圆角更自然）
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)

        self.setSizePolicy(QSizePolicy.Policy.Maximum, QSizePolicy.Policy.Maximum)
        self.setMaximumSize(560, 480)  # 防止超大内容把弹窗撑爆屏幕

        root = QVBoxLayout(self)
        root.setContentsMargins(6, 6, 6, 6)
        root.setSpacing(0)

        # 内容容器
        self.container = QFrame(self)
        self.container.setObjectName("InfoPopupContainer")
        self.container.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)

        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(10, 10, 10, 10)

        # 标题栏
        title_row = QHBoxLayout()
        title_row.setContentsMargins(0, 0, 0, 0)

        self.title_label = QLabel("消息详情", self.container)
        font = self.title_label.font()
        font.setBold(True)
        self.title_label.setFont(font)

        title_row.addWidget(self.title_label, 1)

        container_layout.addLayout(title_row)

        # 分隔线
        sep = QFrame(self.container)
        sep.setFrameShape(QFrame.Shape.HLine)
        sep.setFrameShadow(QFrame.Shadow.Sunken)
        container_layout.addWidget(sep)

        # 可滚动区域
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
        """基于 palette 生成稳定的背景/边框/文字样式，避免解析 stylesheet 字符串的脆弱逻辑。"""
        pal = self.palette()
        bg = pal.color(self.backgroundRole())  # 通常接近 Window
        fg = pal.color(self.foregroundRole())  # 通常接近 WindowText/Text

        # 背景稍微带一点不透明度，兼顾“悬浮感”和可读性
        bg_rgba = _qcolor_to_rgba(bg, 245)

        # 边框颜色用文字色的半透明近似
        border_rgba = _qcolor_to_rgba(fg, 70)

        self.container.setStyleSheet(f"""
        QFrame#InfoPopupContainer {{
            background-color: {bg_rgba};
            border: 1px solid {border_rgba};
        }}
        QLabel {{
            color: {_qcolor_to_rgba(fg, 255)};
        }}
        QPlainTextEdit {{
            border: 1px solid {border_rgba};
            background: {_qcolor_to_rgba(bg, 255)};
            color: {_qcolor_to_rgba(fg, 255)};
        }}
        """)

    def _make_value_widget(self, value: Any) -> QWidget:
        """根据值类型生成合适的展示控件。"""
        # None 显示为 null（比空白更清晰）
        if value is None:
            lab = QLabel("null")
            lab.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
            lab.setWordWrap(True)
            return lab

        # dict/list：用只读文本块显示 JSON，保留缩进
        if isinstance(value, (dict, list)):
            txt = QPlainTextEdit()
            txt.setReadOnly(True)
            txt.setLineWrapMode(QPlainTextEdit.LineWrapMode.NoWrap)
            txt.setPlainText(json.dumps(value, ensure_ascii=False, indent=2))
            txt.setMaximumHeight(140)  # 防止单个字段无限拉高
            return txt

        # 其它标量：label + 可选择 + 自动换行
        lab = QLabel(str(value))
        lab.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        lab.setWordWrap(True)
        return lab

    def show_info(self, info_data: Any, anchor_global_pos: QPoint, title: str = "消息详情") -> None:
        """显示信息悬浮窗。anchor_global_pos 通常传按钮下沿的全局坐标。"""
        self.title_label.setText(title)

        _clear_layout(self.form)

        # 兼容不同供应商：dict 展开成 key/value；其它类型作为单值显示
        if isinstance(info_data, dict):
            keys = list(info_data.keys())

            # 动态算一列 key 的合理宽度（避免硬编码 80）
            fm = self.fontMetrics()
            max_key_px = 0
            for k in keys:
                max_key_px = max(max_key_px, fm.horizontalAdvance(str(k)))
            key_width = min(max_key_px + 10, 220)

            for key in keys:
                val = info_data.get(key)
                key_label = QLabel(f"{key}:")
                key_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
                key_label.setFixedWidth(key_width)

                val_widget = self._make_value_widget(val)
                self.form.addRow(key_label, val_widget)
        else:
            key_label = QLabel("value:")
            key_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
            val_widget = self._make_value_widget(info_data)
            self.form.addRow(key_label, val_widget)

        self._apply_palette_style()  # 主题可能会动态变化，弹出前刷新一下

        self.adjustSize()
        self._move_near_anchor(anchor_global_pos)
        self.show()

    def _move_near_anchor(self, anchor_global_pos: QPoint) -> None:
        """尽量显示在 anchor 下方，放不下就上方，并裁剪到屏幕可用区域内。"""
        screen = QGuiApplication.screenAt(anchor_global_pos) or QGuiApplication.primaryScreen()
        if screen is None:
            self.move(anchor_global_pos)
            return

        avail = screen.availableGeometry()
        margin = 6

        # 先按“下方居中”算
        w = self.width()
        h = self.height()

        x = anchor_global_pos.x() - w // 2
        y_below = anchor_global_pos.y() + 8
        y_above = anchor_global_pos.y() - h - 8

        # 如果下方放不下，尝试上方
        if y_below + h > avail.bottom():
            y = y_above
        else:
            y = y_below

        # 再裁剪到屏幕内
        x = max(avail.left() + margin, min(x, avail.right() - w - margin))
        y = max(avail.top() + margin, min(y, avail.bottom() - h - margin))

        self.move(x, y)


class EditWidget(QTextEdit):
    """可编辑文本框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)

class ReasoningDisplay(MarkdownTextBrowser):
    """思考内容显示控件"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.Shape.NoFrame)
        self.setWordWrapMode(QTextOption.WrapMode.WrapAtWordBoundaryOrAnywhere)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.setVisible(False)

    def setMarkdown(self, text, is_streaming=False):
        self._is_streaming = is_streaming
        super().setMarkdown(text) # 调用父类的方法来处理文本

class BubbleControlButtons(QFrame):
    """气泡控制按钮组（带内部对齐控制）"""
    regenerateClicked = pyqtSignal()
    editToggleClicked = pyqtSignal(bool)  # bool: 是否进入编辑模式
    detailToggleClicked = pyqtSignal(bool) # bool: 是否显示思考内容
    infoClicked = pyqtSignal()

    def __init__(self, parent=None):
        super().__init__(parent)
        
        # 主布局
        self.main_layout = QHBoxLayout()
        self.main_layout.setContentsMargins(0, 0, 0, 0)
        self.main_layout.setSpacing(0)
        self.setLayout(self.main_layout)
        
        # 内部容器用于控制对齐
        self.inner_widget = QFrame()
        self.layout:QHBoxLayout = QHBoxLayout(self.inner_widget)
        self.layout.setContentsMargins(0, 0, 0, 0)
        self.layout.setSpacing(0)
        
        # 创建按钮
        self.regenerate_button = QToolButton()
        self.regenerate_button.setText("🔃")
        self.regenerate_button.setToolTip("重新生成")
        
        self.copy_button = QToolButton()
        self.copy_button.setText("📋")
        self.copy_button.setToolTip("复制内容")
        
        self.edit_button = QToolButton()
        self.edit_button.setText("📝​​")
        self.edit_button.setToolTip("编辑消息")
        self.edit_button.setCheckable(True)

        self.info_button = QToolButton()
        self.info_button.setText("📊")
        self.info_button.setToolTip("消息详情")
        
        self.detail_button = QToolButton()
        self.detail_button.setText("💡")
        self.detail_button.setToolTip("显示思考过程")
        self.detail_button.setCheckable(True)
        
        # 添加按钮到内部布局
        self.layout.addWidget(self.regenerate_button)
        self.layout.addWidget(self.copy_button)
        self.layout.addWidget(self.edit_button)
        self.layout.addWidget(self.detail_button)
        self.layout.addWidget(self.info_button)
        self.layout.addStretch()
        
        # 添加内部容器到主布局
        self.main_layout.addWidget(self.inner_widget)
        
        # 连接信号
        self.regenerate_button.clicked.connect(self.regenerateClicked.emit)
        self.edit_button.toggled.connect(self._on_edit_toggled)
        self.detail_button.toggled.connect(self._on_detail_toggled)
        self.info_button.clicked.connect(self.infoClicked.emit)
        self.copy_button.clicked.connect(self._on_copy_clicked)
        
        # 默认状态
        self.detail_button.setVisible(False)
        
    def set_alignment(self, align_left):
        """设置内部控件的对齐方式"""
        if align_left:
            # 用户气泡：内部控件左贴靠
            self.layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
            self.main_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
        else:
            # AI气泡：内部控件右贴靠
            self.layout.setAlignment(Qt.AlignmentFlag.AlignRight)
            self.main_layout.setAlignment(Qt.AlignmentFlag.AlignRight)
            
    def set_has_reasoning(self, has_reasoning):
        """设置是否有思考内容"""
        self.detail_button.setVisible(has_reasoning)
        self.detail_button.setChecked(False)
        
    def set_editing(self, editing):
        """设置编辑状态"""
        self.edit_button.setChecked(editing)
        
    def _on_edit_toggled(self, checked):
        """编辑按钮切换处理"""
        if checked:
            self.edit_button.setText("✅​")
            self.edit_button.setToolTip("完成编辑")
        else:
            self.edit_button.setText("📝")
            self.edit_button.setToolTip("编辑消息")
        self.editToggleClicked.emit(checked)
        
    def _on_detail_toggled(self, checked):
        """详情按钮切换处理"""
        self.detailToggleClicked.emit(checked)

    def _on_copy_clicked(self):
        """处理复制按钮点击的动画"""

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
        """恢复原始复制按钮状态"""
        # 恢复原始图标和提示
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
    """聊天气泡控件"""
    regenerateRequested = pyqtSignal(str)  # 参数: 消息ID
    editFinished = pyqtSignal(str, str)    # 参数: 消息ID, 新内容
    detailToggled = pyqtSignal(str, bool)   # 参数: 消息ID, 是否显示详情
    RequestAvatarChange = pyqtSignal(str,str)    # 参数: 消息ID, 头像来源

    def __init__(self, message_data, nickname=None, 
                 avatar_path="", parent=None,
                 msg_id=None):
        super().__init__(parent)
        self.id = str(message_data['info']['id'])
        self.role = message_data['role']
        self.message_data:dict = message_data
        self.setMouseTracking(True)  # 启用鼠标跟踪
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.MinimumExpanding)
        self.setObjectName('chatbubble')
        self.manual_expand_reasoning=False
        self.msg_id=msg_id
        
        # 使用GridLayout作为主布局
        layout = QGridLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(0)
        self.setLayout(layout)
        
        # 顶部信息栏（角色/昵称）
        self.top_bar = QFrame()
        self.top_bar_container = QFrame()
        top_bar_layout = QHBoxLayout(self.top_bar_container)
        top_bar_layout.setContentsMargins(0, 0, 0, 0)
        top_bar_layout.addWidget(self.top_bar)

        top_layout = QHBoxLayout()
        top_layout.setContentsMargins(5, 0, 5, 5)
        top_layout.setSpacing(5)
        self.top_bar.setLayout(top_layout)
        
        # 头像处理
        self.avatar = QPushButton()
        self.avatar.setFixedSize(24, 24)
        self.avatar.setCursor(Qt.CursorShape.PointingHandCursor)  # 显示手型指针
        self.avatar_path = avatar_path  # 存储头像路径
        self._setup_avatar()
        
        # 创建角色标签
        self.role_label = QLabel(self._get_patched_name(nickname))
        font = self.role_label.font()
        font.setBold(True)
        self.role_label.setFont(font)
        
        # 添加控制按钮
        self.buttons = BubbleControlButtons()
        
        # 按钮占位空间
        self.button_container = QStackedWidget()
        self.button_container.addWidget(QWidget())  # 索引0: 一个空的占位符
        self.button_container.addWidget(self.buttons)   # 索引1: 真实的按钮
        self.button_container.setCurrentIndex(0) 
        self.button_container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)

        
        # 根据角色决定布局方向
        if self.role == "user":
            # 用户消息：头像在右，按钮在左
            top_layout.addWidget(self.button_container) 
            top_layout.addStretch()
            top_layout.addWidget(self.role_label)
            top_layout.addWidget(self.avatar)
            top_layout.setAlignment(Qt.AlignmentFlag.AlignRight)
            # 顶部栏贴靠右侧
            layout.addWidget(self.top_bar_container, 0, 0, 1, 1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignTop)
        else:
            # AI消息：头像在左，按钮在右
            top_layout.addWidget(self.avatar)
            top_layout.addWidget(self.role_label)
            top_layout.addStretch()
            top_layout.addWidget(self.button_container)
            top_layout.setAlignment(Qt.AlignmentFlag.AlignLeft)
            # 顶部栏贴靠左侧
            layout.addWidget(self.top_bar_container, 0, 0, 1, 1, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignTop)


        # 内容区 - 使用自定义 Markdown 渲染控件
        self.content = MarkdownTextBrowser()
        self.content.setMarkdown(message_data['content'])
        self.content.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Expanding)
        
        # 编辑控件（初始隐藏）
        self.editor = EditWidget()
        self.editor.setVisible(False)
        self.editor.setPlainText(message_data['content'])
        
        # 思考内容显示区（初始隐藏）
        self.reasoning_display = ReasoningDisplay()
        self.reasoning_display.setVisible(False)

        # 创建内容容器（用于管理内容区和编辑区的切换）
        self.content_container = QStackedWidget()
        self.content_container.addWidget(self.content)
        self.content_container.addWidget(self.editor)
        self.content_container.setCurrentIndex(0)  # 默认显示内容区
        self.content_container.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        
        # 添加内容容器到网格布局
        layout.addWidget(self.content_container, 2, 0, 1, 1)
        
        # 添加思考内容显示区
        layout.addWidget(self.reasoning_display, 1, 0, 1, 1)

        # 创建信息悬浮窗（初始隐藏）
        self.info_popup = InfoPopup(self)
        self.info_popup.setVisible(False)
        
        # 检查是否有思考内容数据
        reasoning_content = message_data.get("reasoning_content", "")
        if reasoning_content:
            # tool 角色的内容是 JSON 格式，需要特殊处理
            if self.role == 'tool':
                try:
                    reasoning_json = json.loads(message_data['reasoning_content'])
                    formatted_json = json.dumps(reasoning_json, indent=2, ensure_ascii=False)
                    readable_json = formatted_json.replace('\\n', '\n').replace('\\t', '\t')
                    reasoning_display_text = f"```json\n{readable_json}\n```"  
                except ValueError as e:
                    reasoning_display_text = f"```json\n{reasoning_content}\n```"
                self.reasoning_display.setMarkdown(reasoning_display_text)
            else:
                self.reasoning_display.setMarkdown(reasoning_content)
            self.buttons.set_has_reasoning(True)

        if not message_data['content']:
            self.content.hide()
        
        # 连接信号
        self._connect_signals()

    def _get_patched_name(self,nickname):
        """
        用户和工具直接大写返回，AI提取个模型名称
        """
        if self.role=='user':
            if not nickname:
                return self.role.upper()
            return nickname
        if self.role=='tool':
            info = self.message_data.get('info', {})
            if 'function' in info:
                return info['function']['name'].upper()
            return self.role.upper()
        if self.role=='assistant':
            info_data = self.message_data.get('info', {})
            if not nickname :
                if "model" in info_data:
                    nickname=info_data['model']
                else:
                    nickname='AI'
                    print(
                        'ChatBubble | _get_patched_name: can not find "model" in message_data:\n',
                        json.dumps(self.message_data,indent=2)
                    )
            return nickname
    
    def _setup_avatar(self):
        """设置头像显示（无圆形效果）"""
        if self.avatar_path and os.path.exists(self.avatar_path):
            pixmap = QPixmap(self.avatar_path)
        else:
            # 创建默认头像
            pixmap = QPixmap(24, 24)
            color = QColor("#4285F4") if self.role == "user" else QColor("#34A853")
            pixmap.fill(color)
            
            # 添加简单文字标识
            painter = QPainter(pixmap)
            painter.setPen(Qt.GlobalColor.white)
            painter.setFont(QFont("Arial", 10, QFont.Weight.Bold))
            painter.drawText(pixmap.rect(), Qt.AlignmentFlag.AlignCenter, self.role[0].upper())
            painter.end()
            
        # 缩放图片以适应显示大小
        size = self.avatar.size()
        scaled = pixmap.scaled(size.width(), size.height(), 
                             Qt.AspectRatioMode.KeepAspectRatio, Qt.TransformationMode.SmoothTransformation)
        
        self.avatar.setIcon(QIcon(scaled))
        self.avatar.setIconSize(size)

    def _connect_signals(self):
        """连接所有信号槽"""
        self.buttons.regenerateClicked.connect(
            lambda: self.regenerateRequested.emit(self.id))
        
        # 连接复制按钮（使用内置方法）
        self.buttons.copy_button.clicked.connect(self._handle_copy)
        
        self.buttons.editToggleClicked.connect(self._handle_edit_toggle)
        self.buttons.detailToggleClicked.connect(self._handle_detail_toggle)
        
        # 连接头像点击信号
        self.avatar.clicked.connect(self._on_avatar_clicked)

        self.buttons.infoClicked.connect(self._show_info_popup)
    
    def _on_avatar_clicked(self):
        """处理头像点击事件 - 弹出文件选择对话框"""
        self.RequestAvatarChange.emit(self.id,self.role)
    
    def _handle_copy(self):
        """处理复制操作"""
        if self.editor.isVisible():
            text = self.editor.toPlainText()
        else:
            text = self.content.content  # 获取纯文本内容
            
        QApplication.clipboard().setText(text)
    
    def _handle_edit_toggle(self, editing):
        """处理编辑状态切换"""
        if editing:
            self.content_container.setCurrentIndex(1)  # 显示编辑器
        else:
            self.content_container.setCurrentIndex(0)  # 显示内容区
            new_content = self.editor.toPlainText()
            self.editFinished.emit(self.id, new_content)
            self.content.setMarkdown(new_content)
    
    def _handle_detail_toggle(self, showing):
        """处理详情显示切换"""
        real_showing=(not self.reasoning_display.isVisible())
        self.manual_expand_reasoning=real_showing
        self.reasoning_display.setVisible(real_showing)
        self.detailToggled.emit(self.id, real_showing)
    
    def _show_info_popup(self):
        """显示信息悬浮窗"""
        # 获取info_data（从消息数据的info字段）
        info_data = self.message_data.get('info', {})
        
        # 获取info_button的全局位置
        button_global_pos = self.buttons.info_button.mapToGlobal(QPoint(0, 0))
        
        # 显示悬浮窗
        self.info_popup.show_info(info_data, button_global_pos)

    def enterEvent(self, event):
        """鼠标进入事件"""
        self.button_container.setCurrentIndex(1) 
        super().enterEvent(event)
        
    def leaveEvent(self, event):
        """鼠标离开事件"""
        if not self.buttons.edit_button.isChecked():
            self.button_container.setCurrentIndex(0) 
        super().leaveEvent(event)
        
    def update_nickname(self, new_nickname):
        """更新昵称显示"""
        self.role_label.setText(self._get_patched_name(new_nickname))
    
    def getcontent(self):
        """获取当前消息内容"""
        return self.message_data['content']

    def getinfo(self):
        if 'info' in self.message_data:
            return self.message_data['info']

    def update_avatar(self, new_path):
        """更新头像路径并刷新显示"""
        self.avatar_path = new_path
        self._setup_avatar()
    
    def update_content(self, content_data:dict):
        """
        更新内容显示
        :param content_data: 包含 content 和 state 的字典
        """

        if self.buttons.edit_button.isChecked():  # 编辑状态下不更新
            return
        if not self.content.isVisible():
            self.content.show()
        self.reasoning_display.setVisible(self.manual_expand_reasoning)
        content = content_data.get('content', '')

        # 获取流式状态，默认为 'finished' 如果没有提供
        state = content_data.get('state', 'finished')
        
        # 将状态传递给 MarkdownTextBrowser
        is_streaming = (state == 'streaming')
        self.content.setMarkdown(content, is_streaming=is_streaming)

        # 只有在流式传输非进行中时，才更新编辑器备用内容
        if not is_streaming:
            self.editor.setPlainText(content)

    def update_reasoning(self, reasoning_data:dict):
        """
        更新思考内容
        :param reasoning_data: 包含 reasoning_content
        """
        reasoning_content = reasoning_data.get('reasoning_content', '')
        if reasoning_content:
            self.buttons.set_has_reasoning(True)
            self.reasoning_display.setMarkdown(reasoning_content)
            self.reasoning_display.setVisible(True)
            if not self.content.toPlainText().strip():
                self.content.hide()
            else:
                self.content.show()
        
        # 如果是流式结束状态，确保内容刷新
        if reasoning_data.get('state') == 'finished':
            self.reasoning_display.setMarkdown(reasoning_content)
    
    def mousePressEvent(self, event):   
        """点击气泡外部时关闭悬浮窗"""
        if self.info_popup.isVisible():
            self.info_popup.hide()
        super().mousePressEvent(event)

    def hideEvent(self, event):
        """组件隐藏时关闭悬浮窗"""
        self.info_popup.hide()
        super().hideEvent(event)

class ChatHistoryWidget(QFrame):
    # 定义信号用于与主分发类通信
    regenerateRequested = pyqtSignal(str)  # 消息ID
    editFinished = pyqtSignal(str, str)    # 消息ID, 新内容
    detailToggled = pyqtSignal(str, bool)   # 消息ID, 是否显示详情
    RequestAvatarChange = pyqtSignal(str,str)    # 消息ID,名字

    def __init__(self, parent=None):
        super().__init__(parent)
        self.bubbles = {}  # 存储气泡控件 {消息ID: 气泡实例}
        self.bubble_list = []
        self.nicknames = {'user': '用户', 'assistant': '助手'}  # 默认昵称
        self.avatars = {'user': '', 'assistant': ''}  # 默认头像路径
        self.setStyleSheet("""
            QFrame {
                background-color: rgba(255, 255, 255, 0);
                border-radius: 5px;         
            } 
        """)
        
        self.scroll_timer = QTimer()
        self.scroll_timer.setInterval(10)  # 10毫秒滚动一次,抖得够狠就等于没抖
        self.scroll_timer.timeout.connect(self.scroll_to_bottom)
        self.is_scroll_update_active = False
        self.init_ui()
        self.connect_signals()


        self.is_auto_scroll_enabled = True  # 自动滚动是否启用
        self.not_streaming_dont_scroll=True
        self.wheel_timer=QTimer()
        self.wheel_timer.setInterval(500)
        self.wheel_timer.setSingleShot(True)


    def init_ui(self):
        """初始化UI布局"""

        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().setSpacing(0)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAsNeeded)
        
        # 内容容器
        content_widget = QFrame()
        self.content_layout = QVBoxLayout(content_widget)
        self.content_layout.setContentsMargins(20, 10, 20, 20)
        self.content_layout.setSpacing(15)
        self.content_layout.setAlignment(Qt.AlignmentFlag.AlignBottom)
        
        # 设置滚动区域
        scroll_area.setWidget(content_widget)
        self.layout().addWidget(scroll_area)

        self.scroll_area = self.findChild(QScrollArea)
        self.scroll_bar = self.scroll_area.verticalScrollBar()
        if self.scroll_area:
            self.scroll_area.viewport().installEventFilter(self)
            self.scroll_area.verticalScrollBar().installEventFilter(self)
        
        # 占位控件
        self.spacer = QLabel()
        self.spacer.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)
        self.spacer.setStyleSheet("""
            /* 添加半透明背景 */
            QWidget {
                background-color: rgba(255, 255, 255, 0);      
            }
        """)
        self.content_layout.addWidget(self.spacer,stretch=0)

    def connect_signals(self):
        """连接内部信号转发"""
        self.editFinished.connect(
            lambda msg_id, content: self.update_bubble_content(
                msg_id, {'content': content}
            )
        )
        
    def set_chat_history(self, history):
        """
        设置完整的聊天历史记录，高效更新UI
        :param history: 新的聊天历史记录列表
        """
        # 恢复自动滚动功能
        self.is_auto_scroll_enabled = True
        self.not_streaming_dont_scroll=True
        # 创建新历史记录的ID到内容的映射
        try:
            history=history[-30:]#优化不动，先截了
            try:
                new_ids = {msg['info']['id']: msg for msg in history}
            except:
                print('new_ids_fail',history)
            h1=history
            old_ids = {bubble.msg_id: bubble for bubble in self.bubble_list}
            
            
            # 识别要更新的消息和要删除的消息
            to_update = []
            to_remove = []
            h2=history
            # 检查新历史中的每条消息
            for new_msg in history:
                msg_id = new_msg['info']['id']
                # 如果消息在旧历史中存在且内容不同
                if msg_id in old_ids and (new_msg['content'] != old_ids[msg_id].getcontent() or new_msg['info'] != old_ids[msg_id].getinfo()):
                    to_update.append(new_msg)
            
            # 检查旧历史中哪些消息不再存在
            for msg_id in old_ids:
                if msg_id not in new_ids:
                    to_remove.append(msg_id)
            
            # 移除不再需要的消息
            for msg_id in to_remove:
                self.pop_bubble(msg_id)
            
            # 更新内容不同的消息
            for updated_msg in to_update:
                self.update_bubble(
                    msg_id=updated_msg['info']['id'],
                    content=updated_msg['content'],
                    reasoning_content=updated_msg.get('reasoning_content', ''),
                    info=updated_msg['info']
                )
            
            # 找出要添加的新消息
            h3=history
            existing_msg_ids = [bubble.msg_id for bubble in self.bubble_list]
            new_messages = []
            for msg in history:
                if msg['info']['id'] not in existing_msg_ids:
                    new_messages.append(msg)
            
            # 添加新消息
            for new_msg in new_messages:
                self.add_message(new_msg)
                
            # 确保气泡按历史顺序排列
            self._reorder_bubbles(history)

            h4=history

            msg_id=history[-1]['info']['id']
            self.content_layout.update()
            
            QTimer.singleShot(300, self.scroll_to_bottom)
        except Exception as e:
            with open('chat_history_error_h1.json', 'w', encoding='utf-8') as f:
                json.dump(h1, f, ensure_ascii=False, indent=2)
                print(e,'\nset chat history fail,payload dumped to chat_history_error_h1.json')
            with open('chat_history_error_h2.json', 'w', encoding='utf-8') as f:
                json.dump(h2, f, ensure_ascii=False, indent=2)
                print('set chat history fail,payload dumped to chat_history_error_h2.json')
            if not hasattr('h3'):
                return
            with open('chat_history_error_h3.json', 'w', encoding='utf-8') as f:
                json.dump(h3, f, ensure_ascii=False, indent=2)
                print('set chat history fail,payload dumped to chat_history_error_h3.json')
            if not hasattr('h4'):
                return
            with open('chat_history_error_h4.json', 'w', encoding='utf-8') as f:
                json.dump(h4, f, ensure_ascii=False, indent=2)
                print('set chat history fail,payload dumped to chat_history_error_h4.json')

    def _reorder_bubbles(self, history):
        """
        按历史顺序重新排列气泡
        :param history: 排序后的历史记录列表
        """
        # 创建新的气泡列表（按历史顺序）
        new_bubble_list = []
        for msg in history:
            msg_id = msg['info']['id']
            if msg_id in self.bubbles:
                new_bubble_list.append(self.bubbles[msg_id])
        
        # 如果顺序没有变化则提前返回
        if new_bubble_list == self.bubble_list:
            return

        # 从布局中移除所有气泡
        for bubble in self.bubble_list:
            self.content_layout.removeWidget(bubble)
        
        # 按新顺序添加气泡
        for bubble in new_bubble_list:
            self.content_layout.addWidget(bubble)
        
        self.bubble_list = new_bubble_list
    
    def clear_history(self):
        self.clear()

    def clear(self):
        """清空聊天历史"""
        # 移除所有气泡
        for i in reversed(range(self.content_layout.count())):
            item = self.content_layout.itemAt(i)
            if item.widget() and item.widget() != self.spacer:
                item.widget().deleteLater()
        
        # 重置气泡字典
        self.bubbles = {}
        self.bubble_list = []
        
        # 确保占位控件存在
        self.content_layout.addWidget(self.spacer)

    def pop_bubble(self, msg_id):
        if msg_id in self.bubbles:
            # 获取气泡实例
            bubble = self.bubbles[msg_id]
            
            # 从布局中移除并删除控件
            self.content_layout.removeWidget(bubble)
            bubble.deleteLater()
            
            # 清理数据结构中的引用
            del self.bubbles[msg_id]
            self.bubble_list = [b for b in self.bubble_list if b.msg_id != msg_id]

    def add_message(self, message_data:dict,streaming=False):
        """添加单条消息到聊天历史"""
        role = message_data['role']
        if role not in ['user', 'assistant','tool']:  # 跳过系统消息
            return
        msg_id = message_data['info']['id']
        
        # 把tool call 参数作为reasoning_content植入tool消息
        reasoning_content=message_data.get('reasoning_content', '')
        if message_data['role'] == 'tool':
            if 'function' in message_data.get('info', {}):
                reasoning_content=message_data['info']['function']['arguments']

        if reasoning_content:
            message_data['reasoning_content']=reasoning_content

        # 创建气泡控件
        bubble = ChatBubble(
            message_data,
            nickname=self.nicknames.get(role, ''),
            avatar_path=self.avatars.get(role, ''),
            msg_id=msg_id
        )
        
        # 存储气泡引用
        self.bubble_list.append(bubble)
        self.bubbles[msg_id] = bubble
        
        self.content_layout.addWidget(bubble)
        
        # 连接气泡的信号
        bubble.regenerateRequested.connect(self.regenerateRequested.emit)
        bubble.editFinished.connect(self.editFinished.emit)
        bubble.detailToggled.connect(self.detailToggled.emit)
        bubble.RequestAvatarChange.connect(self.RequestAvatarChange.emit)
        return bubble

    def update_bubble_content(self, msg_id, content_data):
        """更新特定气泡的内容"""
        bubble:ChatBubble = self.bubbles.get(msg_id)
        if bubble:
            bubble.update_content(content_data)
    
    def update_bubble_reasoning(self, msg_id, reasoning_data):
        """更新特定气泡的思考内容"""
        bubble:ChatBubble = self.bubbles.get(msg_id)
        if bubble:
            bubble.update_reasoning(reasoning_data)
    
    def update_bubble_info(self, msg_id, info_data):
        """更新气泡的元信息"""
        bubble:ChatBubble = self.bubbles.get(msg_id)
        if bubble:
            bubble.message_data['info'] = info_data
    
    def update_bubble(self,message='',msg_id=0, content='', reasoning_content='',info='',streaming='streaming',model='',role='assistant'):
        #处理输入方式为message
        #输入方式为message，未初始化

        if message and not message['id'] in self.bubbles:
            self.add_message(message)
            return
        
        #输入方式为message，已经初始化
        if message and message['id'] in self.bubbles:
            # 更新现有消息气泡
            if 'content' in message:
                self.update_bubble_content(message['id'], {'content': message['content']})
            
            if 'reasoning_content' in message:
                self.update_bubble_reasoning(message['id'], 
                    {'reasoning_content': message['reasoning_content']})
            return
        
        #处理输入方式不是message
        #输入方式不是message，未初始化
        if not message and not msg_id in self.bubbles.keys():
            build_message = {
                'role': role,  # 默认为assistant
                'content': content,
                'reasoning_content': reasoning_content,
                'info': {
                    'id': msg_id,
                    'model':model
                    },
                'streaming':streaming
            }
            self.add_message(build_message)

            return
        
        #输入方式不是message，已初始化
        if not message and msg_id in self.bubbles.keys():
            if reasoning_content:   
                self.update_bubble_reasoning(msg_id, 
                        {'reasoning_content': reasoning_content,
                'streaming':streaming})
            if content:
                self.update_bubble_content(msg_id,
                        {'content':content,
                'streaming':streaming
                         })      
            if info:
                self.update_bubble_info(msg_id, info)
            return

        if info:  # 确保info更新被处理
            self.update_bubble_info(msg_id, info)

    
    def set_role_nickname(self, role, nickname):
        """设置角色的昵称"""
        if nickname!=self.nicknames[role]:
            self.nicknames[role] = nickname
            self.update_all_nicknames()
    
    def set_role_avatar(self, role, avatar_path):
        """设置角色的头像"""
        self.avatars[role] = avatar_path
        self.update_all_avatars()
    
    def update_all_nicknames(self):
        """更新所有气泡的昵称显示"""
        for bubble in self.bubbles.values():
            role = bubble.role
            nickname = self.nicknames.get(role, role.capitalize())
            bubble.update_nickname(nickname)
    
    def update_all_avatars(self,new_path={}):
        """更新所有气泡的头像显示"""
        if new_path:
            self.avatars=new_path
        for bubble in self.bubbles.values():
            role = bubble.role
            avatar_path = self.avatars.get(role, '')
            bubble.update_avatar(avatar_path)

    def scroll_to_bottom(self):
        """滚动到底部"""
        if self.scroll_area:
            self.scroll_bar.setValue(self.scroll_bar.maximum())

    def streaming_scroll(self,run=True,scroll_time=10):
        self.not_streaming_dont_scroll=False
        if not self.is_auto_scroll_enabled:
            self.scroll_timer.stop()
            return  # 自动滚动被禁用，不执行任何操作
        
        if self.scroll_timer.interval()!=scroll_time:
            self.scroll_timer.stop()
            self.scroll_timer.setInterval(scroll_time)
            self.scroll_timer.start()

        if run :
            if self.is_scroll_update_active:
                return
            self.is_scroll_update_active=True
            self.scroll_timer.start()
        else:
            self.is_scroll_update_active=False
            self.scroll_timer.stop()
    
    def eventFilter(self, obj, event:QEvent):
        """事件过滤器，检测鼠标滚轮事件"""
        if event.type() == QEvent.Type.Wheel:
            self._handle_wheel_event(event)
            return False  # 继续传递事件
        
        return super().eventFilter(obj, event)
    
    def _handle_wheel_event(self,event):
        """处理鼠标滚轮事件"""
        if self.wheel_timer.isActive() or self.not_streaming_dont_scroll:
            return
        if self.is_auto_scroll_enabled and event.angleDelta().y() > 0:
            self.wheel_timer.start()
            # 停止自动滚动计时器
            self.scroll_timer.stop()
            self.is_auto_scroll_enabled = False
            self.is_scroll_update_active = False
        elif int(self.scroll_bar.value())==int(self.scroll_bar.maximum()) and event.angleDelta().y() < 0:
            self.wheel_timer.start()
            self.is_auto_scroll_enabled = True
            self.streaming_scroll()

