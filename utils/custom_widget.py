from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import sys
import json
import html
import os
from typing import Any, Dict, List, Tuple,Optional
from urllib.parse import quote
from pygments import highlight
from pygments.lexers import get_lexer_by_name
from pygments.formatters import HtmlFormatter
import markdown,re
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
        anim.setEasingCurve(QEasingCurve.InOutQuad)  # 平滑过渡
        
        # 启动动画
        anim.start()
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
        self.setSizePolicy(QSizePolicy.MinimumExpanding, QSizePolicy.Fixed)
        
        # 计算文本所需尺寸
        font = self.font()
        fm = QFontMetrics(font)
        self.texta_width = fm.width(texta) + self.SPACING
        self.textb_width = fm.width(textb) + self.SPACING
        
        # 计算滑块尺寸（根据文本高度）
        slider_height = self.HEIGHT - 2 * self.SLIDER_MARGIN
        slider_width = slider_height  # 保持正方形滑块
        
        # 创建滑块按钮
        self._slider = QPushButton(self)
        self._slider.setFixedSize(slider_width, slider_height)
        self._slider.setSizePolicy(QSizePolicy.Fixed, QSizePolicy.Fixed)
        
        # 创建文本标签
        self._label = QLabel(self)
        self._label.setAlignment(Qt.AlignCenter)
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

#markdown重做
class MarkdownProcessorThread(QThread):
    processingFinished = pyqtSignal(str, int)  # 参数：处理后的HTML和请求ID

    def __init__(self, raw_text, code_style, request_id, parent=None):
        super().__init__(parent)
        self.raw_text = raw_text
        self.code_style = code_style
        self.request_id = request_id
        # 初始化代码格式化工具
        self.code_formatter = HtmlFormatter(
            style=self.code_style,
            noclasses=True,
            nobackground=True,
            linenos=False
        )

    def run(self):
        """执行Markdown处理"""
        processed_html = ChatapiTextBrowser._process_markdown_internal(
            self.raw_text, self.code_formatter
        )
        self.processingFinished.emit(processed_html, self.request_id)

class ChatapiTextBrowser(QTextBrowser):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_settings()
        self.current_request_id = 0  # 当前请求标识
        self.setup_ui()

    def setup_ui(self):
        """界面样式设置"""
        self.setStyleSheet("""
            /* 原有样式保持不变 */
        """)

    def init_settings(self):
        """初始化配置"""
        self.code_style = "vs"
        self.code_formatter = HtmlFormatter(
            style=self.code_style,
            noclasses=True,
            nobackground=True,
            linenos=False
        )

    def setMarkdown(self, text: str) -> None:
        """启动线程处理Markdown"""
        self.current_request_id += 1
        current_id = self.current_request_id

        # 创建并启动处理线程
        thread = MarkdownProcessorThread(text, self.code_style, current_id, self)
        thread.processingFinished.connect(
            lambda html, rid: self.handle_processed_html(html, rid),
            Qt.QueuedConnection  # 确保跨线程信号安全
        )
        thread.start()

    def handle_processed_html(self, html_content: str, request_id: int):
        """处理完成的HTML内容"""
        if request_id != self.current_request_id:
            return  # 忽略过期请求

        super().setHtml(html_content)
        # 自动滚动到底部
        self.moveCursor(QTextCursor.End)
        self.ensureCursorVisible()
        #self.verticalScrollBar().setValue(
        #    self.verticalScrollBar().maximum()
        #)

    @staticmethod
    def _process_markdown_internal(raw_text: str, code_formatter) -> str:
        """Markdown处理核心方法（线程安全）"""
        code_blocks = []
        def code_replacer(match):
            code = match.group(0)
            if not code.endswith('```'):
                code += '```'
            code_blocks.append(code)
            return f"CODE_BLOCK_PLACEHOLDER_{len(code_blocks)-1}"
        # 第一阶段：预处理代码块
        temp_text = re.sub(r'```[\s\S]*?(?:```|$)', code_replacer, raw_text)

        # 转义数字序号
        temp_text = re.sub(
            r'^(\d+)\. (.*[\u4e00-\u9fa5])',
            r'<span class="fake-ol">\1.</span> \2',
            temp_text,
            flags=re.MULTILINE
        )

        # 转换基础Markdown
        extensions = ['tables', 'fenced_code', 'md_in_html', 'nl2br']
        html_content = markdown.markdown(temp_text, extensions=extensions)

        # 处理代码块
        for i, code in enumerate(code_blocks):
            if code.startswith('```math') or code.startswith('```bash'):
                content = code[7:-3].strip()
                replacement = f'<div class="math-formula">{html.escape(content)}</div>'
            else:
                match = re.match(r'```(\w*)[\s\n]*([\s\S]*?)```', code, re.DOTALL)
                if match:
                    lang, code_content = match.group(1) or 'text', match.group(2).strip()
                else:
                    lang, code_content = 'text', code[3:-3].strip()
                replacement = ChatapiTextBrowser.highlight_code(code_content, lang, code_formatter)
            
            html_content = html_content.replace(f"CODE_BLOCK_PLACEHOLDER_{i}", replacement)

        # 处理行内公式
        html_content = re.sub(
            r'\$\$(.*?)\$\$',
            lambda m: f'<span class="math-formula">{html.escape(m.group(1))}</span>',
            html_content,
            flags=re.DOTALL
        )

        return html_content

    @staticmethod
    def highlight_code(code: str, lang: str, code_formatter) -> str:
        """代码高亮（线程安全）"""
        try:
            if lang == 'math':
                return f'<div class="math-formula">{html.escape(code)}</div>'
            lexer = get_lexer_by_name(lang, stripall=True)
            return highlight(code, lexer, code_formatter)
        except Exception:
            return f'<div class="math-formula">{html.escape(code)}</div>'

    def setSource(self, url):
        """禁用自动链接导航"""
        pass

class MarkdownTextBrowser(ChatapiTextBrowser):
    """自定义 Markdown 渲染文本框"""
    def __init__(self, parent=None):
        super().__init__(parent)

        # 气泡特定的设置
        self.setFrameShape(QFrame.NoFrame)
        self.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.setOpenExternalLinks(False)
        self.anchorClicked.connect(lambda url: os.startfile(url.toString()))

        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)

        self._is_streaming = False

        self.document().contentsChanged.connect(self._handle_contents_changed)

        
    def sizeHint(self):
        """
        重写sizeHint，返回基于文档内容的理想尺寸。
        """
        # 获取文档的理想高度

        doc_height = self.document().size().height()
        
        # 获取控件的边距 (通常是0，但最好包含以防万一)
        margins = self.contentsMargins()

        total_height = doc_height + margins.top() + margins.bottom()

        return QSize(self.width(), int(total_height))

    def setMarkdown(self, text, is_streaming=False):
        """
        设置Markdown内容，并根据流式状态决定是否立即更新几何尺寸。
        :param text: Markdown 文本
        :param is_streaming: bool, 是否处于流式更新中
        """
        self._is_streaming = is_streaming
        super().setMarkdown(text) # 调用父类的方法来处理文本

        # 如果流式传输已结束，手动触发一次最终的几何更新
        if not self._is_streaming:
            QTimer.singleShot(0, self.updateGeometry) # 使用 QTimer 确保在当前事件循环完成后执行
    
    def _handle_contents_changed(self):
        """
        仅在非流式状态下，根据内容变化更新几何尺寸。
        """
        if not self._is_streaming:
            self.updateGeometry()

class InfoPopup(QWidget):
    """用于显示消息详情信息的悬浮窗"""
    def __init__(self, parent=None):
        super().__init__(parent, Qt.Popup | Qt.FramelessWindowHint | Qt.WindowStaysOnTopHint)
        self.setAttribute(Qt.WA_TranslucentBackground)
        
        # 主布局
        layout = QVBoxLayout(self)
        layout.setContentsMargins(6, 6, 6, 6)
        layout.setSpacing(5)
        
        # 内容容器（带背景色）
        self.container = QWidget()
        self.container.setStyleSheet(self.init_style_sheet())
        container_layout = QVBoxLayout(self.container)
        container_layout.setContentsMargins(8, 8, 8, 8)
        
        # 标题
        self.title_label = QLabel("消息详情")
        font = self.title_label.font()
        font.setBold(True)
        self.title_label.setFont(font)
        container_layout.addWidget(self.title_label)
        
        # 分隔线
        separator = QFrame()
        separator.setFrameShape(QFrame.HLine)
        separator.setFrameShadow(QFrame.Sunken)
        container_layout.addWidget(separator)
        
        # 详细信息区域
        self.info_layout = QVBoxLayout()
        self.info_layout.setSpacing(4)
        container_layout.addLayout(self.info_layout)
        
        # 布局嵌套
        layout.addWidget(self.container)
    def init_style_sheet(self):
        label_style = QApplication.instance().styleSheet()
        is_transparent = (
            "rgba" in label_style or 
            "transparent" in label_style.lower() or 
            "hsla" in label_style
        )
        
        # 如果包含透明元素，设置为字体颜色的反色且不透明
        if is_transparent:
            # 获取默认 label 的字体颜色
            default_color = QLabel().palette().color(QPalette.Text)
            # 计算反色
            inverted_color = QColor(
                255 - default_color.red(),
                255 - default_color.green(),
                255 - default_color.blue()
            )
            container_style = f"""
                background-color: rgba({inverted_color.red()}, 
                {inverted_color.green()}, 
                {inverted_color.blue()}, 255);
                border-radius: 4px;
                color: rgba({default_color.red()}, 
                       {default_color.green()}, 
                       {default_color.blue()}, 255);
            """
        
        return container_style

    def show_info(self, info_data, button_global_pos):
        """显示信息悬浮窗"""
        # 清空现有内容
        while self.info_layout.count():
            child = self.info_layout.takeAt(0).widget()
            if child:
                child.deleteLater()
        
        # 动态填充信息
        if isinstance(info_data, dict):
            for key, value in info_data.items():
                if key == "tokens_details" or value is None:
                    continue
                    
                # 创建行布局
                row_layout = QHBoxLayout()
                row_layout.setContentsMargins(0, 0, 0, 0)
                
                # 键标签
                key_label = QLabel(f"{key}:")
                key_label.setMinimumWidth(80)
                key_label.setAlignment(Qt.AlignRight | Qt.AlignTop)
                row_layout.addWidget(key_label)
                
                # 值显示
                value_str = json.dumps(value, indent=2) if isinstance(value, dict) else str(value)
                value_label = QLabel(value_str)
                value_label.setAlignment(Qt.AlignLeft | Qt.AlignTop)
                value_label.setWordWrap(True)
                row_layout.addWidget(value_label)
                
                self.info_layout.addLayout(row_layout)
        
        # 调整大小并定位
        self.adjustSize()
        self.move(button_global_pos.x() - self.width()//2, 
                 button_global_pos.y() + 10)
        self.show()

    def mousePressEvent(self, event):
        """点击任意位置关闭弹窗"""
        self.hide()
        super().mousePressEvent(event)

class EditWidget(QTextEdit):
    """可编辑文本框"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.NoFrame)
        self.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        
    def sizeHint(self):
        doc = self.document()
        return QSize(0, int(doc.size().height()))

class ReasoningDisplay(MarkdownTextBrowser):
    """思考内容显示控件"""
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setFrameShape(QFrame.NoFrame)
        self.setWordWrapMode(QTextOption.WrapAtWordBoundaryOrAnywhere)
        self.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.setVisible(False)
        min_height=min(QApplication.primaryScreen().availableGeometry().height() * 0.1,100)
        self.setMinimumHeight(min_height)


    def setMarkdown(self, text, is_streaming=False):
        """
        设置Markdown内容，并根据流式状态决定是否立即更新几何尺寸。
        :param text: Markdown 文本
        :param is_streaming: bool, 是否处于流式更新中
        """
        self._is_streaming = is_streaming
        super().setMarkdown(text) # 调用父类的方法来处理文本

class BubbleControlButtons(QWidget):
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
        self.inner_widget = QWidget()
        self.layout = QHBoxLayout(self.inner_widget)
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
        
        # 默认状态
        self.detail_button.setVisible(False)
        
    def set_alignment(self, align_left):
        """设置内部控件的对齐方式"""
        if align_left:
            # 用户气泡：内部控件左贴靠
            self.layout.setAlignment(Qt.AlignLeft)
            self.main_layout.setAlignment(Qt.AlignLeft)
        else:
            # AI气泡：内部控件右贴靠
            self.layout.setAlignment(Qt.AlignRight)
            self.main_layout.setAlignment(Qt.AlignRight)
            
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

class ChatBubble(QWidget):
    """聊天气泡控件"""
    regenerateRequested = pyqtSignal(str)  # 参数: 消息ID
    editFinished = pyqtSignal(str, str)    # 参数: 消息ID, 新内容
    detailToggled = pyqtSignal(str, bool)   # 参数: 消息ID, 是否显示详情
    avatarChanged = pyqtSignal(str, str)    # 参数: 消息ID, 新头像路径

    def __init__(self, message_data, nickname=None, 
                 avatar_path="", parent=None,
                 msg_id=None):
        super().__init__(parent)
        self.id = str(message_data['info']['id'])
        self.role = message_data['role']
        self.message_data = message_data
        self.setMouseTracking(True)  # 启用鼠标跟踪
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.MinimumExpanding)
        self.setObjectName('chatbubble')
        self.manual_expand_reasoning=False
        self.msg_id=msg_id
        
        # 使用GridLayout作为主布局
        layout = QGridLayout()
        layout.setContentsMargins(5, 5, 5, 5)
        layout.setSpacing(0)
        self.setLayout(layout)
        
        # 顶部信息栏（角色/昵称）
        self.top_bar = QWidget()
        self.top_bar_container = QWidget()
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
        self.avatar.setCursor(Qt.PointingHandCursor)  # 显示手型指针
        self.avatar_path = avatar_path  # 存储头像路径
        self._setup_avatar()
        
        # 创建角色标签
        self.role_label = QLabel(nickname if nickname else self.role)
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
        self.button_container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)

        
        # 根据角色决定布局方向
        if self.role == "user":
            # 用户消息：头像在右，按钮在左
            top_layout.addWidget(self.button_container) 
            top_layout.addStretch()
            top_layout.addWidget(self.role_label)
            top_layout.addWidget(self.avatar)
            top_layout.setAlignment(Qt.AlignRight)
            # 顶部栏贴靠右侧
            layout.addWidget(self.top_bar_container, 0, 0, 1, 1, Qt.AlignRight | Qt.AlignTop)
        else:
            # AI消息：头像在左，按钮在右
            top_layout.addWidget(self.avatar)
            top_layout.addWidget(self.role_label)
            top_layout.addStretch()
            top_layout.addWidget(self.button_container)
            top_layout.setAlignment(Qt.AlignLeft)
            # 顶部栏贴靠左侧
            layout.addWidget(self.top_bar_container, 0, 0, 1, 1, Qt.AlignLeft | Qt.AlignTop)


        # 内容区 - 使用自定义 Markdown 渲染控件
        self.content = MarkdownTextBrowser()
        self.content.setMarkdown(message_data['content'])
        self.content.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Expanding)
        
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
        self.content_container.setSizePolicy(QSizePolicy.Preferred, QSizePolicy.Preferred)
        
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
            self.reasoning_display.setMarkdown(reasoning_content)
            self.buttons.set_has_reasoning(True)

        if not message_data['content']:
            self.content.hide()
        
        # 连接信号
        self._connect_signals()


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
            painter.setPen(Qt.white)
            painter.setFont(QFont("Arial", 10, QFont.Bold))
            painter.drawText(pixmap.rect(), Qt.AlignCenter, self.role[0].upper())
            painter.end()
            
        # 缩放图片以适应显示大小
        size = self.avatar.size()
        scaled = pixmap.scaled(size.width(), size.height(), 
                             Qt.KeepAspectRatio, Qt.SmoothTransformation)
        
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
        # 设置文件过滤器支持常见图片格式
        filters = "Image Files (*.png *.jpg *.jpeg *.bmp *.gif)"
        file_path, _ = QFileDialog.getOpenFileName(
            self, 
            "选择头像图片", 
            QStandardPaths.writableLocation(QStandardPaths.PicturesLocation),
            filters
        )
        
        if file_path:
                
            # 尝试加载图片验证有效性
            pixmap = QPixmap(file_path)
            if pixmap.isNull():
                QMessageBox.warning(self, "无效图片", "无法加载该图片文件，请选择有效的图片格式")
                return
                
            # 更新头像并发射信号
            self.avatar_path = file_path
            self._setup_avatar()
            self.avatarChanged.emit(self.id, file_path)
    
    def _handle_copy(self):
        """处理复制操作"""
        if self.editor.isVisible():
            text = self.editor.toPlainText()
        else:
            text = self.content.toPlainText()  # 获取纯文本内容
            
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
        self.role_label.setText(new_nickname)
    
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
    
    def update_content(self, content_data):
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

    def update_reasoning(self, reasoning_data):
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

class ChatHistoryWidget(QWidget):
    # 定义信号用于与主分发类通信
    regenerateRequested = pyqtSignal(str)  # 消息ID
    editFinished = pyqtSignal(str, str)    # 消息ID, 新内容
    detailToggled = pyqtSignal(str, bool)   # 消息ID, 是否显示详情
    avatarChanged = pyqtSignal(str, str)    # 消息ID, 新头像路径

    def __init__(self, parent=None):
        super().__init__(parent)
        self.bubbles = {}  # 存储气泡控件 {消息ID: 气泡实例}
        self.bubble_list = []
        self.nicknames = {'user': '用户', 'assistant': '助手'}  # 默认昵称
        self.avatars = {'user': '', 'assistant': ''}  # 默认头像路径
        self.setStyleSheet("""
            QWidget {
                background-color: rgba(255, 255, 255, 0);
                border-radius: 5px;         
            } 
        """)
        
        self.init_ui()
        self.connect_signals()

    def init_ui(self):
        """初始化UI布局"""
        self.setLayout(QVBoxLayout())
        self.layout().setContentsMargins(0, 0, 0, 0)
        self.layout().setSpacing(0)
        
        # 创建滚动区域
        scroll_area = QScrollArea()
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.NoFrame)
        scroll_area.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        scroll_area.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        
        # 内容容器
        content_widget = QWidget()
        self.content_layout = QVBoxLayout(content_widget)
        self.content_layout.setContentsMargins(20, 10, 20, 20)
        self.content_layout.setSpacing(15)
        self.content_layout.setAlignment(Qt.AlignBottom)
        
        # 设置滚动区域
        scroll_area.setWidget(content_widget)
        self.layout().addWidget(scroll_area)
        
        # 占位控件
        self.spacer = QLabel()
        self.spacer.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Expanding)
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
        # 创建新历史记录的ID到内容的映射
        try:
            new_ids = {msg['info']['id']: msg for msg in history}
        except:
            print(history)
        
        old_ids = {bubble.msg_id: bubble for bubble in self.bubble_list}
        
        
        # 识别要更新的消息和要删除的消息
        to_update = []
        to_remove = []
        
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
        existing_msg_ids = [bubble.msg_id for bubble in self.bubble_list]
        new_messages = [msg for msg in history if msg['info']['id'] not in existing_msg_ids]
        
        # 添加新消息
        for new_msg in new_messages:
            self.add_message(new_msg)
            
        # 确保气泡按历史顺序排列
        self._reorder_bubbles(history)

        msg_id=history[-1]['info']['id']
        if not str(msg_id)=='999999':#猴子补丁，999999是system prompt气泡编号
            self.bubbles[msg_id].setMaximumHeight(int(self.height()*1.2))
        self.updateGeometry()
        self.content_layout.update()

        QTimer.singleShot(100, self.scroll_to_bottom)

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

    def add_message(self, message_data,streaming=False):
        """添加单条消息到聊天历史"""
        role = message_data['role']
        if role not in ['user', 'assistant','tool']:  # 跳过系统消息
            return
        msg_id = message_data['info']['id']
        
        # 创建气泡控件
        bubble = ChatBubble(
            message_data,
            nickname=self.nicknames.get(role, role.capitalize()),
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
        bubble.avatarChanged.connect(self.avatarChanged.emit)

        target_height = int(self.height() * 1.2)
        if streaming:
            self.bubbles[msg_id].setMaximumHeight(target_height)
        else:
            if hasattr(self, '_last_max_height_bubble') and self._last_max_height_bubble:
                try:
                    self._last_max_height_bubble.setMaximumHeight(99999)
                except:
                    pass
            
            bubble.setMaximumHeight(target_height)
            
            self._last_max_height_bubble = bubble

        return bubble

    def update_bubble_content(self, msg_id, content_data):
        """更新特定气泡的内容"""
        bubble = self.bubbles.get(msg_id)
        if bubble:
            bubble.update_content(content_data)
    
    def update_bubble_reasoning(self, msg_id, reasoning_data):
        """更新特定气泡的思考内容"""
        bubble = self.bubbles.get(msg_id)
        if bubble:
            bubble.update_reasoning(reasoning_data)
    
    def update_bubble_info(self, msg_id, info_data):
        """更新气泡的元信息"""
        bubble = self.bubbles.get(msg_id)
        if bubble:
            bubble.message_data['info'] = info_data
    
    def update_bubble(self,message='',msg_id=0, content='', reasoning_content='',info='',streaming='streaming'):
        QTimer.singleShot(100,self.scroll_to_bottom)
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
                'role': 'assistant',  # 默认为assistant
                'content': content,
                'reasoning_content': reasoning_content,
                'info': {'id': msg_id},
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
                self.update_bubble_info(msg_id, 
                        {'info': info,
                'streaming':streaming})
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
    
    def update_all_avatars(self):
        """更新所有气泡的头像显示"""
        for bubble in self.bubbles.values():
            role = bubble.role
            avatar_path = self.avatars.get(role, '')
            bubble.update_avatar(avatar_path)

    def scroll_to_bottom(self):
        """滚动到底部"""
        scroll_area = self.findChild(QScrollArea)
        if scroll_area:
            scroll_bar = scroll_area.verticalScrollBar()
            scroll_bar.setValue(scroll_bar.maximum())

if __name__=='__main__':
    app = QApplication(sys.argv)
    window = ChatHistoryWidget()
    window.show()
    sys.exit(app.exec_())