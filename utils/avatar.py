
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import os,json

from image_agents import ImageAgent


try:    #waiting 0.25.2 patch 
    from .novita_model_manager import NovitaModelManager
except:
    print('ahh..testing?')
    from novita_model_manager import NovitaModelManager

class ImageProcessor:
    """图像处理工具类"""
    @staticmethod
    def crop_and_scale(image_path, target_size=(256, 256), selection_rect=QRect()):
        """
        裁切并缩放图像：
        1. 载入图像
        2. 裁切为正方形（保留中心或用户选择的区域）
        3. 缩放至目标尺寸
        
        参数:
            image_path: 图像文件路径
            target_size: 目标尺寸
            selection_rect: 用户选择的裁剪区域 (QRect)，若为空则使用中心正方形裁切
        """
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            return QPixmap()
        
        # 如果提供了有效的选择区域
        if selection_rect and selection_rect.isValid() and not selection_rect.isNull():
            # 获取用户选择的矩形区域
            rect = selection_rect
            # 计算选择区域的中心点
            center = rect.center()
            
            # 获取该区域的宽高中较大值作为边长
            if rect.width() > rect.height():
                size = rect.width()
            else:
                size = rect.height()
            
            # 计算以中心点为中心的正方形区域
            square_rect = QRect(
                center.x() - size // 2,
                center.y() - size // 2,
                size,
                size
            )
            
            # 确保正方形在图像边界内
            square_rect = square_rect.intersected(QRect(0, 0, pixmap.width(), pixmap.height()))
            
            # 裁切正方形区域
            cropped = pixmap.copy(square_rect)
        
        # 如果没有提供选择区域，使用中心裁切
        else:
            # 获取较短边尺寸
            size = min(pixmap.width(), pixmap.height())
            
            # 裁切为正方形
            cropped = pixmap.copy(
                (pixmap.width() - size) // 2,
                (pixmap.height() - size) // 2,
                size, size
            )
        
        # 缩放至目标尺寸
        return cropped.scaled(
            target_size[0], target_size[1],
            Qt.IgnoreAspectRatio, Qt.SmoothTransformation
        )

class ImagePreviewer(QLabel):
    """图像预览控件 - 修改版"""
    selectionChanged = pyqtSignal(QRect)  # 选择区域变化信号
    
    def __init__(self, label_text="", parent=None):
        super().__init__(parent)
        self.setText(label_text)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(100, 100)
        self.setFrameShape(QLabel.Box)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # 框选相关变量
        self._is_selecting = False
        self._start_point = QPoint()
        self._end_point = QPoint()
        self._draw_rect = QRect()  # 当前绘制的矩形框
        self._original_image = QPixmap()  # 原始图像缓存
        self._scaled_size = QSize()  # 缩放后的尺寸
        
        # 确保在鼠标拖拽时能够触发鼠标移动事件
        self.setMouseTracking(True)
        minsize=min(self.size().height(),self.size().width())
        self.setMinimumSize(QSize(minsize,minsize))
        
    def display_image(self, pixmap):
        """显示图像并维护原始图像缓存"""
        if not pixmap.isNull():
            self._original_image = pixmap
            self._update_pixmap()
            
            # 重置选择区域
            self.reset_selection()
            
    def _update_pixmap(self):
        """更新显示的图像"""
        if self._original_image.isNull():
            return
            
        # 计算合适的尺寸
        widget_size = self.size()
        img_size = self._original_image.size()
        
        # 计算等比例缩放后的尺寸
        if widget_size.width() / img_size.width() < widget_size.height() / img_size.height():
            # 宽度为限制因素
            scale_factor = widget_size.width() / img_size.width()
        else:
            # 高度为限制因素
            scale_factor = widget_size.height() / img_size.height()
            
        scaled_width = int(img_size.width() * scale_factor)
        scaled_height = int(img_size.height() * scale_factor)
        self._scaled_size = QSize(scaled_width, scaled_height)
        
        # 应用缩放
        scaled_pix = self._original_image.scaled(
            self._scaled_size,
            Qt.KeepAspectRatio, 
            Qt.SmoothTransformation
        )
        
        self.setPixmap(scaled_pix)
            
    def reset_selection(self):
        """重置选择区域"""
        self._is_selecting = False
        self._start_point = QPoint()
        self._end_point = QPoint()
        self._draw_rect = QRect()
        self.update()  # 重绘清除选择框
        self.selectionChanged.emit(QRect())
            
    def get_selection(self):
        """
        获取选择区域相对于原始图像的矩形
        无选择时返回空QRect
        """
        if self._draw_rect.isNull():
            return QRect()
            
        # 将显示的矩形坐标转换为原始图像坐标
        return self.map_to_original(self._draw_rect)
        
    def map_to_original(self, widget_rect):
        """
        将控件坐标映射回原始图像坐标
        """
        if self._original_image.isNull() or self._scaled_size.isNull():
            return QRect()
            
        # 获取图像在控件中的实际位置
        pixmap = self.pixmap()
        if pixmap is None or pixmap.isNull():
            return QRect()
            
        # 计算图像在控件中的起始位置（居中显示）
        pixmap_width = pixmap.width()
        pixmap_height = pixmap.height()
        widget_width = self.width()
        widget_height = self.height()
        
        x_offset = (widget_width - pixmap_width) // 2
        y_offset = (widget_height - pixmap_height) // 2
        
        # 计算缩放比例
        original_width = self._original_image.width()
        original_height = self._original_image.height()
        scale_x = original_width / pixmap_width
        scale_y = original_height / pixmap_height
        
        # 计算映射后的坐标（考虑控件上的图像偏移）
        x = (widget_rect.x() - x_offset) * scale_x
        y = (widget_rect.y() - y_offset) * scale_y
        width = widget_rect.width() * scale_x
        height = widget_rect.height() * scale_y
        
        # 四舍五入为整数（QRect要求整数坐标）
        x = int(round(x))
        y = int(round(y))
        width = int(round(width))
        height = int(round(height))
        
        # 确保矩形在原始图像范围内
        x = max(0, min(x, original_width - 1))
        y = max(0, min(y, original_height - 1))
        width = min(width, original_width - x)
        height = min(height, original_height - y)
        
        # 确保尺寸至少为1像素
        width = max(1, width)
        height = max(1, height)
        
        return QRect(x, y, width, height)
        
    def resizeEvent(self, event):
        """控件尺寸变化时更新图像"""
        super().resizeEvent(event)
        self._update_pixmap()
            
    def mousePressEvent(self, event):
        """鼠标按下时开始选择区域"""
        if event.button() == Qt.LeftButton and not self._original_image.isNull():
            # 检查点击是否在图像区域内
            pixmap = self.pixmap()
            if pixmap is None or pixmap.isNull():
                return
                
            # 计算图像在控件中的位置
            x_offset = (self.width() - pixmap.width()) // 2
            y_offset = (self.height() - pixmap.height()) // 2
            
            pos = event.pos()
            # 检查点击是否在图像范围内
            if not (x_offset <= pos.x() < x_offset + pixmap.width() and 
                    y_offset <= pos.y() < y_offset + pixmap.height()):
                return
                
            self._is_selecting = True
            self._start_point = event.pos()
            self._end_point = event.pos()
            self._draw_rect = QRect(self._start_point, self._end_point).normalized()
            self.update()
            
    def mouseMoveEvent(self, event):
        """鼠标移动时更新选择区域"""
        if self._is_selecting:
            self._end_point = event.pos()
            self._draw_rect = QRect(self._start_point, self._end_point).normalized()
            self.update()
            
    def mouseReleaseEvent(self, event):
        """鼠标释放时结束选择并发送信号"""
        if self._is_selecting and event.button() == Qt.LeftButton:
            self._is_selecting = False
            self._end_point = event.pos()
            self._draw_rect = QRect(self._start_point, self._end_point).normalized()
            
            # 映射坐标并发送信号
            orig_rect = self.map_to_original(self._draw_rect)
            if not orig_rect.isNull() and orig_rect.isValid():
                self.selectionChanged.emit(orig_rect)
                
            self.update()
            
    def paintEvent(self, event):
        """绘制选择框"""
        super().paintEvent(event)
        
        if self._is_selecting and not self._draw_rect.isNull():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.Antialiasing)
            
            # 获取图像位置
            pixmap = self.pixmap()
            if pixmap is None or pixmap.isNull():
                return
                
            pixmap_width = pixmap.width()
            pixmap_height = pixmap.height()
            widget_width = self.width()
            widget_height = self.height()
            
            x_offset = (widget_width - pixmap_width) // 2
            y_offset = (widget_height - pixmap_height) // 2
            
            # 创建半透明覆盖层
            fill_color = QColor(0, 120, 215, 70)  # 半透明蓝色
            painter.fillRect(QRect(x_offset, y_offset, pixmap_width, pixmap_height), fill_color)
            
            # 绘制选择区域
            selection_brush = QBrush(Qt.NoBrush)
            painter.setBrush(selection_brush)
            
            # 设置选择框样式
            pen = QPen(Qt.red, 2, Qt.DashLine)
            painter.setPen(pen)
            
            # 绘制选择框
            painter.drawRect(self._draw_rect)
            
            # 清除选择区域内容
            painter.setCompositionMode(QPainter.CompositionMode_Clear)
            painter.fillRect(self._draw_rect, Qt.transparent)
            
            # 绘制尺寸文本
            painter.setCompositionMode(QPainter.CompositionMode_SourceOver)
            pen.setColor(Qt.black)
            painter.setPen(pen)
            
            # 显示像素尺寸
            orig_rect = self.map_to_original(self._draw_rect)
            if not orig_rect.isNull():
                size_text = f"{orig_rect.width()}×{orig_rect.height()}"
                text_rect = painter.fontMetrics().boundingRect(size_text)
                
                # 将文本放置在矩形左上角
                text_point = QPoint(
                    self._draw_rect.x() + 5,
                    self._draw_rect.y() + text_rect.height() + 5
                )
                painter.drawText(text_point, size_text)
                
                # 在矩形右下角显示位置信息
                pos_text = f"({orig_rect.x()},{orig_rect.y()})"
                pos_point = QPoint(
                    self._draw_rect.right() - painter.fontMetrics().horizontalAdvance(pos_text) - 5,
                    self._draw_rect.bottom() - 5
                )
                painter.drawText(pos_point, pos_text)

class AvatarCreatorText:
    # 窗口名
    WINDOW_TITLE= '自定义头像'
    # 模式选择
    MODE_COMBO = ["手动选择", "AI生成"]
    
    # 按钮文本
    BUTTON_SELECT_IMAGE = "选择图片"
    BUTTON_GENERATE_AVATAR = "生成头像"
    BUTTON_CONFIRM_USE = "确认使用"
    
    # 提示文本
    TOOLTIP_SELECT_IMAGE = "从本地文件系统选择一张头像图片"
    TOOLTIP_PROVIDER_COMBO = "等待开放其他供应商"
    PLACEHOLDER_STYLE_EDIT = "输入风格描述..."
    TOOLTIP_STYLE_EDIT = "描述您希望生成的风格，例如'卡通风格'或'像素风格'"
    TOOLTIP_GENERATE_BUTTON = "根据描述生成头像图片"
    STATUS_WAITING_REQUEST = "等待请求发送..."
    
    # 标签文本
    LABEL_CHARACTER_SOURCE = "形象生成自"
    LABEL_PROVIDER = "供应商"
    LABEL_MODEL = "模型"
    LABEL_STYLE = "指定风格"
    LABEL_ORIGINAL_PREVIEW = "原始图片"
    LABEL_RESULT_PREVIEW = "处理结果"
    LABEL_SETTINGS = "设置"
    LABEL_CREATE_MODE = "创建模式"
    LABEL_ROLE = "角色"
    LABEL_PREVIEW_AREA = "预览区域"
    LABEL_ORIGINAL_IMAGE = "原始图像"
    LABEL_PROCESSED_IMAGE = "处理后图像"
    
    # 复选框文本
    CHECKBOX_INCLUDE_SYSPROMPT = "携带系统提示"
    
    # 下拉选项
    SOURCE_OPTIONS = ["完整对话", "选择的对话"]
    PROVIDER_OPTIONS = ["Novita"]

    #图像生成要求
    IMAGE_GENERATE_SYSTEM_PROMPT='''
# 角色
你是一位专业的AI绘画提示词（Prompt）工程师。你的专长是将用户的自然语言想法，转化为能够被AI绘画模型（如Midjourney, Stable Diffusion）精确理解和执行的、结构化的提示词。

# 核心任务
你的核心任务是接收用户提供的任何场景描述，并将其转换为一个结构化的JSON对象。这个对象包含一个用于生成图像的“prompt”和一个用于排除多余元素的“negative_prompt”。

# 工作流程
1.  **分析与提炼**: 仔细阅读并分析用户的场景描述。提炼出其中最关键的视觉元素，包括：
    *   **主体**: 人物、动物、物品等。
    *   **风格**: 写实、动漫、赛博朋克、水墨画、油画等。
    *   **环境/背景**: 森林、城市街道、室内、宇宙等。
    *   **构图与视角**: 特写、全身像、鸟瞰、远景等。
    *   **光照与氛围**: 电影感光照、柔和的光、黄昏、神秘、愉快等。
    *   **画质与细节**: 8K、超精细细节、照片级真实感等。

2.  **构建 `prompt`**:
    *   将上述提炼出的所有积极元素，用精准、描述性的**英文单词或短语**组合起来。
    *   按照“主体, 细节描述, 风格, 环境, 构图, 光照, 画质”的大致顺序组织，使逻辑更清晰。
    *   使用逗号 `,` 分隔每个关键词。

3.  **构建 `negative_prompt`**:
    *   **推理排除项**: 根据用户期望的风格，推断出应该排除的对立风格。例如，如果用户想要“写实”，则应排除“动漫、卡通、绘画”。
    *   **添加通用排除项**: 默认加入一些能提升基础画质的排除词，如避免畸形、低质量、模糊、水印等。
    *   **组合与格式化**: 将所有排除项用英文单词或短语组合，并用逗号 `,` 分隔。

4.  **输出**: 严格按照下面指定的JSON格式输出最终结果。

# 目标格式详解
你必须严格按照以下JSON格式进行输出，不要添加任何额外的解释或文字。

```json
{
  "prompt": "一个由英文关键词组成的字符串，详细描述了画面的核心内容、风格和细节。关键词用逗号分隔，例如：'masterpiece, best quality, 1girl, solo, cute, standing on the beach, sunset, cinematic lighting, photorealistic, 8k'。",
  "negative_prompt": "一个由英文关键词组成的字符串，用于排除不想要的风格、元素和低质量结果。关键词用逗号分隔，例如：'painting, sketches, (worst quality:2), (low quality:2), lowres, normal quality, monochrome, grayscale, skin spots, acnes, skin blemishes, age spot, glans, nsfw, text, error, extra digit, fewer digits, cropped, jpeg artifacts, signature, watermark, username, blurry'"
}
```

# 规则与约束
*   **语言**: `prompt` 和 `negative_prompt` 的内容**必须**是英文。
*   **分隔符**: 关键词之间**必须**使用英文逗号 `, ` 进行分隔。
*   **简洁性**: 避免冗余，但要确保包含所有必要的描述性细节。
*   **直接输出**: 你的回答应该只有JSON代码块，不包含任何其他内容。

# 示例
**用户输入:**
> 我想要一张头像，是一个可爱的宇航员猫咪，它坐在月球上，背景是地球。风格要偏向卡通一点，色彩鲜艳。

**你的输出:**
```json
{
  "prompt": "chibi astronaut cat, sitting on the moon, looking at earth, cute, cartoon style, vibrant colors, starry sky, detailed, masterpiece, best quality",
  "negative_prompt": "photorealistic, realistic, dark, grayscale, monochrome, blurry, ugly, deformed, text, watermark"
}
```
'''


class AvartarImageGenerator:
    def __init__(self,generator,prompt,application_path):
        self.generator=ImageAgent(application_path)
        self.generator.set_generator(generator)
        self.prompt=prompt
    
    def create_params(self):
        pass

    



class AvatarCreatorWindow(QWidget):
    """头像创建工具主界面"""
    # 信号定义
    styleRequested = pyqtSignal(str)  # 生成风格请求信号
    avatarCreated = pyqtSignal(dict)  # 添加头像创建完成信号
    selectionChanged = pyqtSignal(QRect)  # 添加选择区域变化信号
    ai_generate_status=pyqtSignal(str)
    error_log=pyqtSignal(str,str)
    
    def __init__(self, 
                 target_size=(256, 256), 
                 parent=None,
                 avatar_info={
                     'user':{'name':'user','image':''},
                     'assistant':{'name':'assistant','image':''}
                    },
                application_path='',#AutoLoad
                init_character={'lock':False,'character':'user'}
                 ):
        super().__init__(parent)
        self.target_size = target_size  # 可配置的目标尺寸
        self.setWindowTitle(AvatarCreatorText.WINDOW_TITLE)
        self.current_image_path = ""  # 当前处理的图像路径
        self.avatar_info = avatar_info
        self.init_character=init_character
        self.application_path=application_path
        self.avatar_folder=os.path.join(self.application_path,'pics','avatar')
        self.temp_folder=os.path.join(self.application_path,'pics','work_temp')
        self.selection_rect = QRect()  # 用户选择的裁切区域
        
        self._init_environment()
        self._init_ui()
        self._setup_layout()
        self._connect_signals()
    
    def _init_environment(self):
        """初始化环境，创建文件夹和自身变量"""
        #初始化文件夹
        os.makedirs(self.avatar_folder, exist_ok=True)
        os.makedirs(self.temp_folder, exist_ok=True)

        #初始化变量
        self.character_for_names = []
        self.character_for_map = {}
        # 创建角色名称映射
        for key, items in self.avatar_info.items():
            self.character_for_names.append(items['name'])
            self.character_for_map[items['name']] = key
            
        # 当前选择的角色
        self.current_character = self.character_for_names[0] if self.character_for_names else ""
    
    def _init_ui(self):
        """初始化UI控件"""
        # 控制区组件
        self.character_for = QComboBox()
        self.character_for.addItems(self.character_for_names)
        self.character_for.setEnabled(not self.init_character['lock'])
        self.character_for.setCurrentText(self.init_character['character'])

        # 创建模式切换组合框
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(AvatarCreatorText.MODE_COMBO)
        
        # 创建堆栈窗口
        self.mode_stack = QStackedWidget()
        
        # 第一页：手动选择模式
        self.manual_page = QWidget()
        manual_layout = QVBoxLayout(self.manual_page)
        
        self.selector_btn = QPushButton(AvatarCreatorText.BUTTON_SELECT_IMAGE)
        self.selector_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.selector_btn.setToolTip(AvatarCreatorText.TOOLTIP_SELECT_IMAGE)
        manual_layout.addWidget(self.selector_btn)
        
        manual_layout.addStretch()
        
        self.mode_stack.addWidget(self.manual_page)
        
        # 第二页：AI生成模式
        self.ai_page = QWidget()
        ai_layout = QVBoxLayout(self.ai_page)

        self.character_source_combo = QComboBox()
        self.character_source_combo.addItems(AvatarCreatorText.SOURCE_OPTIONS)
        ai_layout.addWidget(QLabel(AvatarCreatorText.LABEL_CHARACTER_SOURCE))
        ai_layout.addWidget(self.character_source_combo)
        
        self.character_include_syspromt = QCheckBox(AvatarCreatorText.CHECKBOX_INCLUDE_SYSPROMPT)
        ai_layout.addWidget(self.character_include_syspromt)

        self.model_provider=QComboBox()
        self.model_provider.addItems(AvatarCreatorText.PROVIDER_OPTIONS)
        self.model_provider.setToolTip(AvatarCreatorText.TOOLTIP_PROVIDER_COMBO)
        self.model_provider.setEnabled(False)

        self.model_choice=QComboBox()
        self.model_choice.addItems(NovitaModelManager().get_model_options())

        qf0 = QFrame()
        qf0.setFrameShape(QFrame.HLine)
        ai_layout.addWidget(qf0)
        ai_layout.addWidget(QLabel(AvatarCreatorText.LABEL_PROVIDER))
        ai_layout.addWidget(self.model_provider)
        ai_layout.addWidget(QLabel(AvatarCreatorText.LABEL_MODEL))
        ai_layout.addWidget(self.model_choice)
        qf1 = QFrame()
        qf1.setFrameShape(QFrame.HLine)
        ai_layout.addWidget(qf1)

        ai_layout.addWidget(QLabel(AvatarCreatorText.LABEL_STYLE))
        self.style_edit = QLineEdit()
        self.style_edit.setPlaceholderText(AvatarCreatorText.PLACEHOLDER_STYLE_EDIT)
        self.style_edit.setToolTip(AvatarCreatorText.TOOLTIP_STYLE_EDIT)
        ai_layout.addWidget(self.style_edit)
        
        self.generate_btn = QPushButton(AvatarCreatorText.BUTTON_GENERATE_AVATAR)
        self.generate_btn.setToolTip(AvatarCreatorText.TOOLTIP_GENERATE_BUTTON)
        ai_layout.addWidget(self.generate_btn)

        ai_layout.addStretch()
        self.ai_generate_status_label=QLabel(AvatarCreatorText.STATUS_WAITING_REQUEST)
        ai_layout.addWidget(self.ai_generate_status_label)

        self.mode_stack.addWidget(self.ai_page)
        
        # 预览区组件
        self.original_preview_label = QLabel(AvatarCreatorText.LABEL_ORIGINAL_PREVIEW)
        self.original_preview_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.original_preview = ImagePreviewer(AvatarCreatorText.LABEL_ORIGINAL_PREVIEW)
        
        # 在原始预览控件上添加一个标签说明
        self.selection_hint = QLabel("")
        self.selection_hint.setStyleSheet("background-color: rgba(255,255,255,150);")
        self.selection_hint.setAlignment(Qt.AlignCenter)
        
        
        self.result_preview_label = QLabel(AvatarCreatorText.LABEL_RESULT_PREVIEW)
        self.original_preview_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Minimum)
        self.result_preview = ImagePreviewer(AvatarCreatorText.LABEL_RESULT_PREVIEW)

        # 添加确认按钮
        self.confirm_btn = QPushButton(AvatarCreatorText.BUTTON_CONFIRM_USE)
        self.confirm_btn.setEnabled(False)

    def _setup_layout(self):
        """设置网格布局系统"""
        main_layout = QGridLayout(self)
        
        # 控制区
        control_box = QGroupBox(AvatarCreatorText.LABEL_SETTINGS)
        control_layout = QGridLayout(control_box)
        row = 0

        # 第一行：模式选择
        control_layout.addWidget(QLabel(AvatarCreatorText.LABEL_CREATE_MODE), row, 0, 1, 1)
        control_layout.addWidget(self.mode_combo, row, 1, 1, 1)
        row += 1
        
        # 第二行：角色选择
        control_layout.addWidget(QLabel(AvatarCreatorText.LABEL_ROLE), row, 0, 1, 1)
        control_layout.addWidget(self.character_for, row, 1, 1, 1)
        row += 1

        # 分隔线
        qf0 = QFrame()
        qf0.setFrameShape(QFrame.HLine)
        control_layout.addWidget(qf0, row, 0, 1, 2)
        row += 1
        
        # 第三行：模式堆栈
        control_layout.addWidget(self.mode_stack, row, 0, 1, 2)
        row += 1
        
        # 添加额外设置
        qf1 = QFrame()
        qf1.setFrameShape(QFrame.HLine)
        control_layout.addWidget(qf1, row, 0, 1, 2)
        row += 1

        control_layout.addWidget(self.confirm_btn, row, 0, 1, 2)
        
        # 预览区
        preview_box = QGroupBox(AvatarCreatorText.LABEL_PREVIEW_AREA)
        preview_layout = QGridLayout(preview_box)
        preview_layout.addWidget(QLabel(AvatarCreatorText.LABEL_ORIGINAL_IMAGE), 0, 0, 1, 1)

        preview_layout.addWidget(self.original_preview, 1, 0, 1, 1)
        preview_layout.addWidget(self.selection_hint, 2, 0, 1, 2)

        preview_layout.addWidget(QLabel(AvatarCreatorText.LABEL_PROCESSED_IMAGE), 0, 1, 1, 1)
        preview_layout.addWidget(self.result_preview, 1, 1, 1, 1)

        preview_layout.setRowStretch(0, 0)
        preview_layout.setRowStretch(1, 1)

        # 添加到主网格布局
        main_layout.addWidget(control_box, 0, 0, 1, 1)
        main_layout.addWidget(preview_box, 0, 1, 1, 1)

        main_layout.setColumnStretch(0, 0)
        main_layout.setColumnStretch(1, 1)  

    def _connect_signals(self):
        """连接信号与槽函数"""
        self.selector_btn.clicked.connect(self._select_image)
        self.generate_btn.clicked.connect(self._emit_style_request)
        self.mode_combo.currentIndexChanged.connect(self._mode_changed)
        self.confirm_btn.clicked.connect(self._save_avatar)
        
        # 连接原始预览的选择区域变化信号
        self.original_preview.selectionChanged.connect(self._handle_selection)
        
        # 连接角色选择变化
        self.character_for.currentTextChanged.connect(self._update_character)

        self.ai_generate_status.connect(lambda status: self.ai_generate_status_label.setText(status))
        
        # 添加更新标志，防止递归
        self.updating_selection = False
        
    def _mode_changed(self, index):
        """处理模式切换事件"""
        self.mode_stack.setCurrentIndex(index)

        # 更新确认按钮状态
        self._update_confirm_button()
        
    def _update_character(self, name):
        """更新当前选择的角色"""
        self.current_character = name
        self._update_confirm_button()
        
    def _update_confirm_button(self):
        """根据当前状态更新确认按钮的启用状态"""
        manual_ready = bool(self.result_preview.pixmap())
        self.confirm_btn.setEnabled(manual_ready)
        
    def _select_image(self):
        """打开文件选择对话框"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择头像", "", 
            "图片文件 (*.png *.jpg *.jpeg *.bmp)"
        )
        if file_path:
            # 重置选择区域
            self.selection_rect = QRect()
            
            # 处理新图片
            self._process_image(file_path)
            self.selection_hint.setText('拖动鼠标框选区域创建外接正方形裁切')
            
    def _process_image(self, file_path: str):
        """处理图片并更新预览"""
        self.current_image_path = file_path
        
        # 显示原始图片
        self.original_preview.display_image(QPixmap(file_path))
        
        # 使用图像处理工具类，传递当前选择区域
        result_pixmap = ImageProcessor.crop_and_scale(
            file_path, 
            self.target_size, 
            self.selection_rect
        )
        self.result_preview.display_image(result_pixmap)
        
        # 更新确认按钮状态
        self._update_confirm_button()
            
    def _emit_style_request(self):
        """发送AI生成请求信号"""
        style_text = self.style_edit.text().strip()
        if style_text:
            self.styleRequested.emit(style_text)
        self.generate_btn.setEnabled(False)
            
    def _handle_selection(self, rect):
        """处理选择区域变化事件"""
        # 防止递归更新
        if self.updating_selection:
            return
            
        self.updating_selection = True
        
        try:
            # 保存选择区域
            self.selection_rect = rect
            
            # 如果当前有有效的图像路径，重新处理图片
            if self.current_image_path:
                # 使用图像处理工具类，传递当前选择区域
                result_pixmap = ImageProcessor.crop_and_scale(
                    self.current_image_path, 
                    self.target_size, 
                    rect
                )
                self.result_preview.display_image(result_pixmap)
                
                # 更新确认按钮状态
                self._update_confirm_button()
        finally:
            self.updating_selection = False
    
    def _save_avatar(self):
        """保存当前头像到角色信息"""
        if not self.result_preview.pixmap().isNull():
            # 获取角色ID
            char_id = self.character_for_map.get(self.current_character, "")
            result_path=os.path.join(
                    self.avatar_folder,
                    f"{self.character_for.currentText()}.jpg"
                    )
            self.result_preview.pixmap().save(
                 result_path
                )
            if char_id:
                # 发出信号通知头像已创建
                self.avatarCreated.emit({
                    'character': char_id,
                    'pixmap': self.result_preview.pixmap(),
                    'image_path': result_path
                })
                
                self.close()
    
    def load_ai_generated_image(self, pixmap):
        """加载AI生成的图片"""
        #信号可以是路径
        if type(pixmap)==str:
            if os.path.exists(pixmap):
                pixmap=QPixmap(pixmap)
        # 保存到临时文件以便后续处理
        try:
            self.ai_temp_path = os.path.join(
                self.temp_folder,
                f"{self.character_for.currentText()}.jpg"
                )
            pixmap.save(self.ai_temp_path)
        except Exception as e:
            self.error_log.emit('error','ai_generated_image save failed'+str(e))
            return

        self.current_image_path = self.ai_temp_path
        self._process_image(self.ai_temp_path)

        self.selection_hint.setText('拖动鼠标框选区域创建外接正方形裁切')
        
        # 重置选择区域
        self.original_preview.reset_selection()
        self.generate_btn.setEnabled(True)
    
    def clean_up(self):
        for filename in os.listdir(self.temp_folder):
            file_path = os.path.join(self.temp_folder, filename)
            try:
                if os.path.isfile(file_path):
                    os.remove(file_path)
            except Exception as e:
                self.error_log.emit('warning',f'{file_path}:{str(e)}')
 
    def closeEvent(self, a0):
        self.clean_up()
        return super().closeEvent(a0)

if __name__ == "__main__":

    app = QApplication([])

    window = AvatarCreatorWindow(
        application_path=r'C:\Users\Administrator\Desktop\github\ChatWindowWithLLMApi',
        init_character={'lock':True,'character':'assistant'}
    )
    window.error_log.connect(print)#调试时顺便打印内容
    window.show()
    app.exec_()