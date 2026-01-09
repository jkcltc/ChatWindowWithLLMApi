from PyQt6.QtWidgets import (
    QApplication, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout, QFrame,
    QLabel, QPushButton, QToolButton, QScrollArea, QTextEdit, QStackedWidget,
    QSizePolicy, QGraphicsOpacityEffect,QTextBrowser,QScrollBar
)
from PyQt6.QtCore import (
    Qt, QTimer, QThread, pyqtSignal, QPoint, QSize, QPropertyAnimation,QEasingCurve, QRectF,QEvent
)
from PyQt6.QtGui import (
    QFont, QFontMetrics, QPixmap, QIcon, QColor, QPainter, QPainterPath,
    QLinearGradient, QTextCursor, QTextOption, QPalette
)
import sys
import json
import html
import os
from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters import HtmlFormatter
import markdown,re

from utils.assets.user_input import MultiModalTextEdit
from utils.assets.chathistory_widget import ChatHistoryWidget,ChatapiTextBrowser


#窗口大小过渡器
class WindowAnimator:
    @staticmethod
    def animate_resize(window: QWidget, 
                      start_size: QSize, 
                      end_size: QSize, 
                      duration: int = 300):
        """
        窗口尺寸平滑过渡动画
        :param window: 要应用动画的窗口对象
        :param start_size: 起始尺寸（QSize）
        :param end_size: 结束尺寸（QSize）
        :param duration: 动画时长（毫秒，默认300）
        """
        # 创建并配置动画
        anim = QPropertyAnimation(window, b"size", window)
        anim.setDuration(duration)
        anim.setStartValue(start_size)
        anim.setEndValue(end_size)
        anim.setEasingCurve(QEasingCurve.Type.InOutQuad)  # 平滑过渡
        
        # 启动动画
        anim.start()
#流动标签
class GradientLabel(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setMinimumSize(100, 40)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setStyleSheet("""
            font-size: 15px;
            font-weight: bold;
            max-height: 25px;
        """)
        
        self.offset = 0
        self.gradient_width = self.width()  # 渐变条宽度
        self.colors = [
            QColor("#1a2980"),  # 深蓝
            QColor("#26d0ce"),  # 青色
            QColor("#1a2980")   # 深蓝(循环)
        ]
        root_style = QApplication.instance().styleSheet()
        
        # 提取变量值 (简化示例)
        primary = self.extract_color(root_style, "--color-primary", "#1a2980")
        accent = self.extract_color(root_style, "--color-accent", "#26d0ce")
        
        self.colors = [primary, accent, primary]
        
        # 设置定时器实现动画
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_gradient)
        self.timer.start(3)  # 每3ms更新一次
    
    def extract_color(self, css, var_name, default):
        """从CSS中提取颜色值"""
        import re
        match = re.search(f"{var_name}:\\s*(#[0-9a-fA-F]+|\\w+);", css)
        return QColor(match.group(1)) if match else QColor(default)
    
    def update_gradient(self):
        """更新渐变偏移量，实现从左到右的循环动画"""
        self.offset = (self.offset + 1) % (self.gradient_width * 2)
        self.update()  # 触发重绘
    
    def paintEvent(self, event):
        """自定义绘制事件，高光从左侧开始"""
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        
        # 创建圆角矩形路径
        path = QPainterPath()
        path.addRoundedRect(QRectF(self.rect()), 15, 15)
        
        # 创建动态渐变（高光从左侧开始）
        gradient = QLinearGradient(
            -self.gradient_width + self.offset, 0,  # 起点从左侧开始
            self.offset, 0                         # 终点向右移动
        )
        gradient.setColorAt(0.0, self.colors[0])
        gradient.setColorAt(0.5, self.colors[1])
        gradient.setColorAt(1.0, self.colors[2])
        
        # 填充背景
        painter.fillPath(path, gradient)
        
        # 绘制文本
        painter.setPen(Qt.GlobalColor.white)
        painter.drawText(self.rect(), Qt.AlignmentFlag.AlignCenter, self.text())

    def hide(self):
        """重写hide方法，停止动画定时器"""
        self.timer.stop()      # 停止动画
        super().hide()         # 调用原始隐藏逻辑
    
    def show(self):
        """重写show方法，重新开始动画定时器"""
        super().show()         # 调用原始显示逻辑
        self.timer.start(5)    # 重新开始动画

#搜索按钮
class SearchButton(QPushButton):
    def __init__(self, text):
        super().__init__(text)
        self._is_checked = False  # 自定义变量来跟踪选中状态
        self.setStyleSheet("background-color: gray")
        self.clicked.connect(self.toggle_state)
 
    def toggle_state(self):
        # 切换自定义变量的状态
        self._is_checked = not self._is_checked
        if self._is_checked:
            self.setStyleSheet("background-color: green")
        else:
            self.setStyleSheet("background-color: gray")
        # 发射自定义信号，传递当前状态
        self.toggled.emit(self._is_checked)


class EPDropdownMenu(QWidget):
    """下拉菜单组件"""
    itemSelected = pyqtSignal(str)  # 项目选择信号
    
    def __init__(self, parent=None):
        super().__init__(parent, Qt.WindowType.Popup)  # 设置为弹出窗口
        self.layout:QVBoxLayout = QVBoxLayout(self)
        self.layout.setSpacing(0)
        self.layout.setContentsMargins(0, 0, 0, 0)
        
    def set_items(self, items):
        """设置菜单项"""
        # 清除现有项目
        for i in reversed(range(self.layout.count())):
            widget = self.layout.itemAt(i).widget()
            if widget:
                widget.deleteLater()
        
        # 添加新项目
        for item in items:
            label = QLabel(item)
            label.setCursor(Qt.CursorShape.PointingHandCursor)
            label.mousePressEvent = lambda event, text=item: self._on_item_clicked(event, text)
            self.layout.addWidget(label)

    def _on_item_clicked(self, event, text):
        """处理菜单项点击"""
        self.itemSelected.emit(text)
        self.hide()

class ExpandableButton(QWidget):
    """可扩展按钮控件"""
    toggled = pyqtSignal(bool)  # 状态切换信号
    itemSelected = pyqtSignal(str)  # 项目选择信号
    indexChanged = pyqtSignal(int)  # 索引变化信号
    def __init__(self, items=None, parent=None):
        super().__init__(parent)
        
        # 默认菜单项
        if items is None:
            items = ["选项1", "选项2", "选项3", "选项4"]
        
        self._is_checked = False
        self._items = items
        self._current_text = items[0] if items else ""
        
        self._setup_ui()
        self._connect_signals()
        
    def _setup_ui(self):
        """设置UI界面"""
        # 主布局
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0,0,0)
        layout.setSpacing(0)
        
        # 左侧按钮
        self.left_button = QPushButton(self._current_text)
        self.left_button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self._update_button_style()
        
        # 右侧下拉按钮
        self.dropdown_button = QPushButton()
        self.dropdown_button.setContentsMargins(0, 0, 0, 0)
        self.dropdown_button.setStyleSheet("padding: 5px 5px;")
        self.dropdown_button.setSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding)

        # 设置下拉图标
        self.dropdown_button.setText("▼")
        #self.dropdown_button.setFont(QFont("Arial", 10))
        
        # 创建下拉菜单
        self.dropdown_menu = EPDropdownMenu(self)
        self.dropdown_menu.set_items(self._items)
        
        # 添加到布局
        layout.addWidget(self.left_button)
        layout.addWidget(self.dropdown_button)
        
    def _connect_signals(self):
        """连接信号槽"""
        self.left_button.clicked.connect(self._toggle_state)
        self.dropdown_button.clicked.connect(self._show_dropdown_menu)
        self.dropdown_menu.itemSelected.connect(self._on_item_selected)
        
    def _toggle_state(self):
        """切换左侧按钮状态"""
        self._is_checked = not self._is_checked
        self._update_button_style()
        self.toggled.emit(self._is_checked)
        
    def _update_button_style(self):
        """更新按钮样式"""
        if self._is_checked:
            self.left_button.setStyleSheet("""background-color: green""")
        else:
            self.left_button.setStyleSheet("""background-color: gray""")
            
    def _show_dropdown_menu(self):
        """显示下拉菜单"""
        # 计算菜单位置（在整个widget下方）
        pos = self.mapToGlobal(QPoint(0, self.height()))
        self.dropdown_menu.move(pos)
        
        # 设置菜单宽度与控件相同
        self.dropdown_menu.setFixedWidth(self.width())
        
        # 显示菜单
        self.dropdown_menu.show()
        
    def _on_item_selected(self, text):
        """处理菜单项选择"""
        self._current_text = text
        self.left_button.setText(text)
        # 发出文本与索引变化信号
        try:
            idx = self._items.index(text)
        except ValueError:
            idx = -1
        self.itemSelected.emit(text)
        if idx >= 0:
            self.indexChanged.emit(idx)
        
    # 公共方法
    def setItems(self, items):
        """设置下拉菜单项"""
        self._items = items
        if items and self._current_text not in items:
            self._current_text = items[0]
            self.left_button.setText(self._current_text)
            # 当前索引已变为0
            self.indexChanged.emit(0)
        self.dropdown_menu.set_items(items)
        
    def get_items(self):
        """获取下拉菜单项"""
        return self._items.copy()
        
    def setCurrentText(self, text):
        """设置当前显示的文本"""
        if text in self._items:
            self._current_text = text
            self.left_button.setText(text)
            # 发出相应索引变化
            self.indexChanged.emit(self._items.index(text))
    
    def setCurrentIndex(self, index):
        """设置当前显示的索引"""
        if 0 <= index < len(self._items):
            text = self._items[index]
            self._current_text = text
            self.left_button.setText(text)
            # 发出文本与索引变化信号
            self.itemSelected.emit(text)
            self.indexChanged.emit(index)
        else:
            raise IndexError("Index out of range")

    def currentText(self):
        """获取当前显示的文本"""
        return self._current_text

    def currentIndex(self):
        return self._items.index(self._current_text)
        
    def isChecked(self):
        """获取左侧按钮状态"""
        return self._is_checked
        
    def setChecked(self, checked):
        """设置左侧按钮状态"""
        if self._is_checked != checked:
            self._is_checked = checked
            self._update_button_style()
            self.toggled.emit(checked)


#背景标签
class AspectLabel(QLabel):
    def __init__(self, master_pixmap='', parent=None,text=''):
        super().__init__(parent)
        self.master_pixmap = master_pixmap
        self.setText(text)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        self.setMinimumSize(1, 1)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)  # 居中显示
        self.locked = False
        
    def lock(self):
        """锁定图片内容（允许缩放）"""
        self.locked = True

    def unlock(self):
        """解锁图片内容"""
        self.locked = False
        
    def _image_resize(self,event):
        if not type(self.master_pixmap)==QPixmap:
            return
        target_size = self.master_pixmap.size().scaled(
            event.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding
        )
        
        scaled_pix = self.master_pixmap.scaled(
            target_size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation
        )
        
        self.setPixmap(scaled_pix)

    def resizeEvent(self, event):
        # 计算覆盖尺寸
        self._image_resize(event)
        super().resizeEvent(event)
    
    def update_icon(self,pic):
        """ 根据当前尺寸更新显示图标 """
        if not self.locked:
            self.master_pixmap=pic
        target_size = self.master_pixmap.size().scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatioByExpanding  # 关键模式
        )
        
        # 执行高质量缩放
        scaled_pix = self.master_pixmap.scaled(
            target_size,
            Qt.AspectRatioMode.KeepAspectRatioByExpanding,
            Qt.TransformationMode.SmoothTransformation
        )
        
        self.setPixmap(scaled_pix)
#按钮：打开背景
class AspectRatioButton(QPushButton):
    def __init__(self, pixmap_path, parent=None):
        super().__init__(parent)
        # 加载原始图片
        self.original_pixmap = QPixmap(pixmap_path)
        if not self.original_pixmap.isNull():
            self.aspect_ratio = self.original_pixmap.width() / self.original_pixmap.height()
        else:
            # 处理图像加载失败的情况
            self.aspect_ratio = 1.0  # 或者其他默认值
 
        # 初始化配置
        self.setSizePolicy(QSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding))
        self.setMinimumSize(40, 30)  # 合理的最小尺寸
        self.setIconSize(QSize(0, 0))  # 初始图标尺寸清零
 
        # 视觉效果
        self.setFlat(True)  # 移除默认按钮样式
        self.setCursor(Qt.CursorShape.PointingHandCursor)

        self.setStyleSheet("""
    QPushButton {
        border: none;
        background: rgba(0,0,0,0);
    }
    QPushButton:hover {
        background: rgba(200,200,200,30);
    }
""")
 
        # 初始图片设置
        self.update_icon(self.original_pixmap)

 
    def update_icon(self,pic):
        """ 根据当前尺寸更新显示图标 """
        self.original_pixmap=pic
        scaled_pix = self.original_pixmap.scaled(
            self.size(),
            Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation
        )
        self.setIcon(QIcon(scaled_pix))
        self.setIconSize(scaled_pix.size())
 
    def resizeEvent(self, event):
        """ 动态调整按钮比例 """
        # 计算保持宽高比的目标尺寸
        target_width = min(event.size().width(), int(event.size().height() * self.aspect_ratio))
        target_height = int(target_width / self.aspect_ratio)
 
        # 更新显示内容
        self.update_icon(self.original_pixmap)
        super().resizeEvent(event)  # 这应该放在最后，以允许父类处理尺寸调整
 
    def sizeHint(self):
        """ 提供合理的默认尺寸 """
        default_width = 200
        default_height = int(default_width / self.aspect_ratio)
        return QSize(default_width, default_height)

#滑动按钮
class SwitchButton(QPushButton):
    # 定义类常量
    MARGIN = 4             # 控件外边距
    SPACING = 8            # 滑块与文本间距
    SLIDER_MARGIN = 2      # 滑块内边距
    HEIGHT = 30            # 推荐高度

    def __init__(self, texta='on', textb='off'):
        super().__init__()
        self.texta = texta
        self.textb = textb
        self.setCheckable(True)
        self.setSizePolicy(QSizePolicy.Policy.MinimumExpanding, QSizePolicy.Policy.Fixed)
        
        # 计算文本所需尺寸
        font = self.font()
        fm = QFontMetrics(font)
        self.texta_width = fm.horizontalAdvance(texta) + self.SPACING
        self.textb_width = fm.horizontalAdvance(textb) + self.SPACING
        
        # 计算滑块尺寸（根据文本高度）
        slider_height = self.HEIGHT - 2 * self.SLIDER_MARGIN
        slider_width = slider_height  # 保持正方形滑块
        
        # 创建滑块按钮
        self._slider = QPushButton(self)
        self._slider.setFixedSize(slider_width, slider_height)
        self._slider.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        
        # 创建文本标签
        self._label = QLabel(self)
        self._label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._label.setFixedHeight(self.HEIGHT)
        
        # 初始状态
        self._updateLabelPosition()
        self.setLabelText()

        # 动画设置
        self.animation = QPropertyAnimation(self._slider, b"pos")
        self.animation.setDuration(200)
        self.clicked.connect(self.animateSlider)

    def sizeHint(self):
        """计算推荐尺寸"""
        slider_width = self._slider.width()
        max_text_width = max(self.texta_width, self.textb_width)
        width = 2 * self.MARGIN + slider_width + max_text_width
        return QSize(width, self.HEIGHT)

    def _updateLabelPosition(self):
        """更新标签位置（避开滑块区域）"""
        slider_width = self._slider.width()
        if self.isChecked():
            # 滑块在右侧，标签在左侧
            self._label.setGeometry(
                self.MARGIN, 0,
                self.width() - slider_width - 2 * self.MARGIN - self.SPACING, 
                self.height()
            )
        else:
            # 滑块在左侧，标签在右侧
            self._label.setGeometry(
                slider_width + self.SPACING + self.MARGIN, 0,
                self.width() - slider_width - 2 * self.MARGIN - self.SPACING, 
                self.height()
            )

    def setLabelText(self):
        """根据状态设置文本"""
        self._label.setText(self.texta if self.isChecked() else self.textb)

    def animateSlider(self):
        """执行滑块动画"""
        end_x = self.width() - self._slider.width() - self.MARGIN if self.isChecked() else self.MARGIN
        self.animation.setEndValue(QPoint(end_x, self._slider.y()))
        self.animation.start()
        self.setLabelText()
        self._updateLabelPosition()

    def resizeEvent(self, event):
        """处理尺寸变化事件"""
        super().resizeEvent(event)
        self._updateLabelPosition()
        # 更新滑块垂直位置（保持居中）
        ypos = (self.height() - self._slider.height()) // 2
        self._slider.move(self._slider.x(), ypos)
        
    def setChecked(self, checked):
        """设置选中状态并更新界面"""
        super().setChecked(checked)
        # 立即更新位置（不使用动画）
        end_x = self.width() - self._slider.width() - self.MARGIN if checked else self.MARGIN
        ypos = (self.height() - self._slider.height()) // 2
        self._slider.move(end_x, ypos)
        self.setLabelText()
        self._updateLabelPosition()


if __name__=='__main__':
    app = QApplication(sys.argv)
    window = ChatHistoryWidget()
    window.show()
    sys.exit(app.exec())