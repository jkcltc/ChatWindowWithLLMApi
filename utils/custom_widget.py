from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import sys

#流动标签
class GradientLabel(QLabel):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.setMinimumSize(100, 40)
        self.setAlignment(Qt.AlignCenter)
        self.setStyleSheet("""
            font-size: 15px;
            font-weight: bold;
            color: white;
            padding: 2px;
            border-radius: 15px;
            max-height: 25px;
            max-width: 400px
        """)
        
        self.offset = 0
        self.gradient_width = self.width()  # 渐变条宽度
        self.colors = [
            QColor("#1a2980"),  # 深蓝
            QColor("#26d0ce"),  # 青色
            QColor("#1a2980")   # 深蓝(循环)
        ]
        root_style = qApp.styleSheet()
        
        # 提取变量值 (简化示例)
        primary = self.extract_color(root_style, "--color-primary", "#1a2980")
        accent = self.extract_color(root_style, "--color-accent", "#26d0ce")
        
        self.colors = [primary, accent, primary]
        
        # 设置定时器实现动画
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_gradient)
        self.timer.start(3)  # 每5ms更新一次
    
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
        painter.setRenderHint(QPainter.Antialiasing)
        
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
        painter.setPen(Qt.white)
        painter.drawText(self.rect(), Qt.AlignCenter, self.text())

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

#背景标签
class AspectLabel(QLabel):
    def __init__(self, master_pixmap, parent=None):
        super().__init__(parent)
        self.master_pixmap = master_pixmap
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.setMinimumSize(1, 1)
        self.setAlignment(Qt.AlignCenter)  # 居中显示
        self.locked = False
        
    def lock(self):
        """锁定图片内容（允许缩放）"""
        self.locked = True

    def unlock(self):
        """解锁图片内容"""
        self.locked = False
        
    def resizeEvent(self, event):
        # 计算覆盖尺寸
        target_size = self.master_pixmap.size().scaled(
            event.size(),
            Qt.KeepAspectRatioByExpanding  # 关键模式
        )
        
        # 执行高质量缩放
        scaled_pix = self.master_pixmap.scaled(
            target_size,
            Qt.KeepAspectRatioByExpanding,
            Qt.SmoothTransformation
        )
        
        self.setPixmap(scaled_pix)
        super().resizeEvent(event)
    
    def update_icon(self,pic):
        """ 根据当前尺寸更新显示图标 """
        if not self.locked:
            self.master_pixmap=pic
        target_size = self.master_pixmap.size().scaled(
            self.size(),
            Qt.KeepAspectRatioByExpanding  # 关键模式
        )
        
        # 执行高质量缩放
        scaled_pix = self.master_pixmap.scaled(
            target_size,
            Qt.KeepAspectRatioByExpanding,
            Qt.SmoothTransformation
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
        self.setSizePolicy(QSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding))
        self.setMinimumSize(40, 30)  # 合理的最小尺寸
        self.setIconSize(QSize(0, 0))  # 初始图标尺寸清零
 
        # 视觉效果
        self.setFlat(True)  # 移除默认按钮样式
        self.setCursor(Qt.PointingHandCursor)

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
            Qt.KeepAspectRatio,
            Qt.SmoothTransformation
        )
        self.setIcon(QIcon(scaled_pix))
        self.setIconSize(scaled_pix.size())
 
    def resizeEvent(self, event):
        """ 动态调整按钮比例 """
        # 计算保持宽高比的目标尺寸
        target_width = min(event.size().width(), int(event.size().height() * self.aspect_ratio))
        target_height = int(target_width / self.aspect_ratio)
 
        # 注意：这里我们不应该再次调用 self.resize()，因为这会导致无限递归。
        # 相反，我们应该让父类的 resizeEvent 处理实际的尺寸调整。
        # 我们只需要确保图标在调整大小后得到更新。
 
        # 更新显示内容
        self.update_icon(self.original_pixmap)
        super().resizeEvent(event)  # 这应该放在最后，以允许父类处理尺寸调整
 
    def sizeHint(self):
        """ 提供合理的默认尺寸 """
        # 注意：这里返回的尺寸应该基于当前的 aspect_ratio，但不应该在构造函数之外修改它。
        # 如果需要基于某个默认宽度来计算高度，可以这样做：
        default_width = 200
        default_height = int(default_width / self.aspect_ratio)
        return QSize(default_width, default_height)

#滑动按钮
class SwitchButton(QPushButton):
    def __init__(self, texta='on', textb='off'):
        super().__init__()
        self.texta = texta
        self.textb = textb
        self.setCheckable(True)
        #self.setStyleSheet("""
        #    SwitchButton {
        #        border: 2px solid #ccc;
        #        border-radius: 15px;
        #        background-color: #ccc;
        #        height: 30px;
        #    }
        #    SwitchButton:checked {
        #        background-color: #4CAF50;
        #    }
        #""")

        # 计算文本所需宽度
        font = self.font()
        fm = QFontMetrics(font)
        self.texta_width = fm.width(texta)
        self.textb_width = fm.width(textb)
        self.max_text_width = max(self.texta_width, self.textb_width)

        # 初始化滑块
        self._slider = QPushButton(self)
        self._slider.setFixedSize(28, 28)
        #self._slider.setStyleSheet("""
        #    QPushButton {
        #        border-radius: 14px;
        #        background-color: white;
        #    }
        #""")
        slider_width = self._slider.width()
        # 计算总宽度：滑块宽度 + 左右边距(各2px) + 文本最大宽度
        total_width = slider_width + 4 + self.max_text_width
        self.setFixedSize(total_width, 30)
        self._slider.move(2, 1)

        # 初始化标签
        self._label = QLabel(textb, self)
        #self._label.setStyleSheet("QLabel { color: white; font-weight: bold; }")
        self._label.setFixedSize(self.max_text_width, 30)
        self._label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
        # 初始位置在右侧
        self._label.move(self.width() - self.max_text_width - 2, 0)

        self.animation = QPropertyAnimation(self._slider, b"pos")
        self.animation.setDuration(200)
        self.clicked.connect(self.toggle)

    def toggle(self):
        slider_width = self._slider.width()
        if self.isChecked():
            # 滑块移至右侧，显示texta
            end_x = self.width() - slider_width - 2
            self._label.setText(self.texta)
            self._label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
            self._label.move(2, 0)
        else:
            # 滑块移至左侧，显示textb
            end_x = 2
            self._label.setText(self.textb)
            self._label.setAlignment(Qt.AlignRight | Qt.AlignVCenter)
            self._label.move(self.width() - self.max_text_width - 2, 0)
        self.animation.setEndValue(QPoint(end_x, self._slider.y()))
        self.animation.start()

