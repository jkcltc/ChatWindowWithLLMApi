import os,time

from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *

from core.multimodal_coordination.avatar import (
    AvatarCreatorText,ImageProcessor,AvatarImageGenerator
)
from service.text_to_image import ImageAgent


class ImagePreviewer(QLabel):
    """图像预览控件 - 修改版"""
    selectionChanged = pyqtSignal(QRect)  # 选择区域变化信号
    
    def __init__(self, label_text="", parent=None):
        super().__init__(parent)
        self.setText(label_text)
        self.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.setMinimumSize(100, 100)
        self.setFrameShape(QFrame.Shape.Box)
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Expanding)
        
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
            Qt.AspectRatioMode.KeepAspectRatio, 
            Qt.TransformationMode.SmoothTransformation
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
        
    def map_to_original(self, widget_rect:QRect):
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
            
    def mousePressEvent(self, event:QMouseEvent):
        """鼠标按下时开始选择区域"""
        if event.button() == Qt.MouseButton.LeftButton and not self._original_image.isNull():
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
            
    def mouseMoveEvent(self, event:QMouseEvent):
        """鼠标移动时更新选择区域"""
        if self._is_selecting:
            self._end_point = event.pos()
            self._draw_rect = QRect(self._start_point, self._end_point).normalized()
            self.update()
            
    def mouseReleaseEvent(self, event:QMouseEvent):
        """鼠标释放时结束选择并发送信号"""
        if self._is_selecting and event.button() == Qt.MouseButton.LeftButton:
            self._is_selecting = False
            self._end_point = event.pos()
            self._draw_rect = QRect(self._start_point, self._end_point).normalized()
            
            # 映射坐标并发送信号
            orig_rect = self.map_to_original(self._draw_rect)
            if not orig_rect.isNull() and orig_rect.isValid():
                self.selectionChanged.emit(orig_rect)
                
            self.update()
            
    def paintEvent(self, event:QPaintEvent):
        """绘制选择框"""
        super().paintEvent(event)
        
        if self._is_selecting and not self._draw_rect.isNull():
            painter = QPainter(self)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            
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
            selection_brush = QBrush(Qt.BrushStyle.NoBrush)
            painter.setBrush(selection_brush)
            
            # 设置选择框样式
            pen = QPen(Qt.GlobalColor.red, 2, Qt.PenStyle.DashLine)
            painter.setPen(pen)
            
            # 绘制选择框
            painter.drawRect(self._draw_rect)
            
            # 清除选择区域内容
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_Clear)
            painter.fillRect(self._draw_rect, Qt.GlobalColor.transparent)
            
            # 绘制尺寸文本
            painter.setCompositionMode(QPainter.CompositionMode.CompositionMode_SourceOver)
            pen.setColor(Qt.GlobalColor.black)
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



class AvatarCreatorWindow(QWidget):
    """
    头像创建工具主界面
    需要在模型库请求完成后创建
    """
    # 信号定义
    styleRequested = pyqtSignal(str)  # 生成风格请求信号
    avatarCreated = pyqtSignal(str,str)  # 添加头像创建完成信号,user/assistant,path
    selectionChanged = pyqtSignal(QRect)  # 添加选择区域变化信号
    ai_generate_status=pyqtSignal(str)
    error_log=pyqtSignal(str,str)
    
    def __init__(
                self,
                target_size=(256, 256),
                parent=None,
                avatar_info={
                    'user': {'name': 'user', 'image': ''},
                    'assistant': {'name': 'assistant', 'image': ''}
                },
                application_path='',  # AutoLoad
                init_character={'lock': False, 'character': 'user'},
                model_map={'无供应商': ['检查调用节点']},
                default_apis={
                    "暂无": {
                        "url": "no.url.provided",
                        "key": "unknown"
                    }
                },
                msg_id='',
                chathistory=[{'role':'user','content':'what'}]
        ):
        super().__init__(parent)
        self.target_size = target_size  # 可配置的目标尺寸
        self.setWindowTitle(AvatarCreatorText.WINDOW_TITLE)

        # 初始化变量
        self.current_image_path = ""    # 当前处理的图像路径
        self.avatar_info:dict = avatar_info   # 头像信息字典
        self.init_character = init_character  # 初始角色设置
        self.application_path = application_path  # 应用路径
        self.model_map = model_map       # 模型映射关系
        self.defalt_apis = default_apis  # 默认API配置
        self.msg_id = msg_id             # 消息ID
        self.chathistory=chathistory

        # UI相关
        self.selection_rect = QRect()    # 用户选择的裁切区域
        
        self._init_environment()
        self._init_ui()
        self._setup_layout()
        self._connect_signals()
    
    def _init_environment(self):
        """初始化环境，创建文件夹和自身变量"""

        #初始化变量
        self.avatar_folder=os.path.join(self.application_path,'pics','avatar')
        self.temp_folder=os.path.join(self.application_path,'pics','work_temp')

        #初始化文件夹
        os.makedirs(self.avatar_folder, exist_ok=True)
        os.makedirs(self.temp_folder, exist_ok=True)

        
        self.character_for_names = []
        self.character_for_map = {}
        # 创建角色名称映射
        for key, items in self.avatar_info.items():
            self.character_for_names.append(items['name'])
            self.character_for_map[items['name']] = key

        if not 'tool' in self.avatar_info:
            self.avatar_info['tool']={'name':'tool','image':self.avatar_info['assistant']['image']}

        # 当前选择的角色
        self.current_character = self.character_for_names[0] if self.character_for_names else ""

        #生成器
        self.generator=ImageAgent()
    
    def _init_ui(self):
        """初始化UI控件"""
        # 控制区组件
        self.character_for = QComboBox()
        self.character_for.addItems(self.character_for_names)
        self.character_for.setEnabled(not self.init_character['lock'])
        self.character_for.setCurrentText(self.avatar_info[self.init_character['character']]['name'])

        # 创建模式切换组合框
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(AvatarCreatorText.MODE_COMBO)
        
        # 创建堆栈窗口
        self.mode_stack = QStackedWidget()
        
        # 第一页：手动选择模式
        self.manual_page = QWidget()
        manual_layout = QVBoxLayout(self.manual_page)
        
        self.selector_btn = QPushButton(AvatarCreatorText.BUTTON_SELECT_IMAGE)
        self.selector_btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
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

        self.character_cut_label=QLabel(AvatarCreatorText.LABEL_CUT_SETTING)
        self.character_cut_spin = QSpinBox()
        self.character_cut_spin.setMinimum(1)
        self.character_cut_spin.setValue(10)
        ai_layout.addWidget(self.character_cut_label)
        ai_layout.addWidget(self.character_cut_spin)
        
        self.character_include_syspromt = QCheckBox(AvatarCreatorText.CHECKBOX_INCLUDE_SYSPROMPT)
        ai_layout.addWidget(self.character_include_syspromt)
        
        qfa=QFrame()
        qfa.setFrameShape(QFrame.Shape.HLine)
        ai_layout.addWidget(qfa)

        ai_layout.addWidget(QLabel(AvatarCreatorText.LABEL_SUMMARY_PROVIDER))

        self.prompt_summarizer_provider=QComboBox()
        self.prompt_summarizer_provider.addItems(list(self.model_map.keys()))
        ai_layout.addWidget(self.prompt_summarizer_provider)

        self.prompt_summarizer_model=QComboBox()
        self.prompt_summarizer_model.addItems(self.model_map[self.prompt_summarizer_provider.currentText()])
        ai_layout.addWidget(self.prompt_summarizer_model)

        self.prompt_summarizer_provider.currentTextChanged.connect(
            lambda text: self.prompt_summarizer_model.clear() 
            or 
            self.prompt_summarizer_model.addItems(self.model_map[text])
            )

        self.model_provider=QComboBox()
        self.model_provider.addItems(
            list(
                self.generator.generator_dict.keys()
                )
        )
        self.model_provider.setToolTip(AvatarCreatorText.TOOLTIP_PROVIDER_COMBO)

        self.model_choice=QComboBox()
        self.model_choice.addItems(
            self.generator.get_model_list(
                self.model_provider.currentText()
            )
        )

        
        self.model_provider.currentTextChanged.connect(
            lambda text: self.model_choice.clear() 
            or 
            self.model_choice.addItems(self.generator.get_model_list(text))
            )

        qf0 = QFrame()
        qf0.setFrameShape(QFrame.Shape.HLine)
        ai_layout.addWidget(qf0)
        ai_layout.addWidget(QLabel(AvatarCreatorText.LABEL_PROVIDER))
        ai_layout.addWidget(self.model_provider)
        ai_layout.addWidget(QLabel(AvatarCreatorText.LABEL_MODEL))
        ai_layout.addWidget(self.model_choice)
        qf1 = QFrame()
        qf1.setFrameShape(QFrame.Shape.HLine)
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
        self.original_preview_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        self.original_preview = ImagePreviewer(AvatarCreatorText.LABEL_ORIGINAL_PREVIEW)
        
        # 在原始预览控件上添加一个标签说明
        self.selection_hint = QLabel("")
        self.selection_hint.setStyleSheet("background-color: rgba(255,255,255,150);")
        self.selection_hint.setAlignment(Qt.AlignmentFlag.AlignCenter)
        
        
        self.result_preview_label = QLabel(AvatarCreatorText.LABEL_RESULT_PREVIEW)
        self.original_preview_label.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
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
        qf0.setFrameShape(QFrame.Shape.HLine)
        control_layout.addWidget(qf0, row, 0, 1, 2)
        row += 1
        
        # 第三行：模式堆栈
        control_layout.addWidget(self.mode_stack, row, 0, 1, 2)
        row += 1
        
        # 添加额外设置
        qf1 = QFrame()
        qf1.setFrameShape(QFrame.Shape.HLine)
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

        self.error_log.connect(
                lambda error_func,error_intel:QMessageBox.critical(
                    self, "Error", f"Error in {error_func}: {error_intel}"
                    )
                )
        self.generate_btn.clicked.connect(self.start_img_creation)

        self.character_source_combo.currentIndexChanged.connect(
            lambda i: [c.setVisible(i == 0) 
             for c in [self.character_cut_label, self.character_cut_spin]
             ]
            )
        
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
        self.ai_page.setEnabled(False)
            
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
            char_id = self.character_for_map.get(self.character_for.currentText(), "")
            result_path=os.path.join(
                    self.avatar_folder,
                    f"{self.character_for.currentText()}-{int(time.time())}.jpg"
                    )
            self.result_preview.pixmap().save(
                 result_path
                )
            if char_id:
                # 发出信号通知头像已创建
                self.avatarCreated.emit(char_id,result_path)
                #self.avartarInfoResult.emit(self.character_for.currentText(),result_path)
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
        self.ai_page.setEnabled(True)
    
    def start_img_creation(self):
        #初始化生成类
        if (not hasattr(self,'image_generator')):
            do_update=True
        
        elif self.model_provider.currentText()!=self.image_generator.generator_name or\
        self.model_provider.model !=self.model_choice.currentText():
            do_update=True
        
        if do_update:
            self.image_generator=AvatarImageGenerator(
                generator=self.model_provider.currentText(),
                application_path=self.application_path,
                model=self.model_choice.currentText()
            )
            self.image_generator.status_update.connect(self.ai_generate_status_label.setText)
            self.image_generator.failure.connect(
                lambda error_func,error_intel:QMessageBox.critical(
                    self, "Error", f"Error in {error_func}: {error_intel}"
                    )
                )
            self.image_generator.pull_success.connect(self.load_ai_generated_image)
        if self.character_source_combo.currentIndex()==1:
            msg_id=self.msg_id
        else:
            msg_id=''
        self.image_generator.prepare_message(
                      target=self.character_for_map[self.character_for.currentText()],
                      chathistory_list=self.chathistory,
                      style=self.style_edit.text(),
                      charactors={'user':self.avatar_info['user']['name'],'assistant':self.avatar_info['assistant']['name']},
                      msg_id=msg_id
                      )
        self.image_generator.send_image_workflow_request(api_config={
            'url':self.defalt_apis[self.prompt_summarizer_provider.currentText()].url,
            'key':self.defalt_apis[self.prompt_summarizer_provider.currentText()].key
        },
        summary_model=self.prompt_summarizer_model.currentText())
        
    def showEvent(self, event):
        # 获取屏幕几何信息
        screen = QApplication.primaryScreen().geometry()
        # 获取窗口几何信息
        window = self.geometry()
        # 计算居中位置
        x = (screen.width() - window.width()) // 2
        y = (screen.height() - window.height()) // 2
        # 移动窗口到屏幕中心
        self.move(x, y)
        super().showEvent(event)

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
