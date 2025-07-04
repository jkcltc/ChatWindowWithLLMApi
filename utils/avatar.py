
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from custom_widget import SwitchButton

class ImageProcessor:
    """图像处理工具类"""
    @staticmethod
    def crop_and_scale(image_path, target_size=(24, 24)):
        """
        裁切并缩放图像：
        1. 载入图像
        2. 裁切为正方形（保留中心）
        3. 缩放至目标尺寸
        """
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            return QPixmap()
        
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


class ImageSelector(QWidget):
    """图像选择控件"""
    imageSelected = pyqtSignal(str)  # 发送选择的图像路径
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.btn_select = QPushButton("选择图片")
        self.btn_select.clicked.connect(self._select_image)
        layout = QVBoxLayout()
        layout.addWidget(self.btn_select)
        self.setLayout(layout)
    
    def _select_image(self):
        """打开文件对话框选择图片"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择头像", "", 
            "图片文件 (*.png *.jpg *.jpeg *.bmp)"
        )
        if file_path:
            self.imageSelected.emit(file_path)


class ImagePreviewer(QLabel):
    """图像预览控件"""
    def __init__(self, label_text="", parent=None):
        super().__init__(parent)
        self.setText(label_text)
        self.setAlignment(Qt.AlignCenter)
        self.setMinimumSize(100, 100)
        self.setFrameShape(QLabel.Box)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

    def display_image(self, pixmap):
        """
        Displays a QPixmap image within the widget, scaling it to fit the widget's current size while maintaining the aspect ratio.

        Args:
            pixmap (QPixmap): The image to be displayed.

        Notes:
            If the provided pixmap is null, the function does nothing.
        """
        if not pixmap.isNull():
            self.setPixmap(pixmap.scaled(
                self.width(), self.height(),
                Qt.KeepAspectRatio, Qt.SmoothTransformation
            ))


class AIGeneratorWidget(QWidget):
    """AI生成控件"""
    generateRequested = pyqtSignal(str)  # 发送生成请求及风格描述
    
    def __init__(self, parent=None):
        super().__init__(parent)
        layout = QHBoxLayout()
        
        self.style_edit = QLineEdit()
        self.style_edit.setPlaceholderText("输入图片风格描述...")
        
        self.btn_generate = QPushButton("AI生成头像")
        self.btn_generate.clicked.connect(self._emit_generate_signal)
        
        layout.addWidget(self.style_edit, 70)
        layout.addWidget(self.btn_generate, 30)
        self.setLayout(layout)
    
    def _emit_generate_signal(self):
        """发送生成信号"""
        style_text = self.style_edit.text().strip()
        if style_text:
            self.generateRequested.emit(style_text)

class AvatarCreatorWindow(QWidget):
    """头像创建窗口"""
    avatarCreated = pyqtSignal(QPixmap)        # 头像创建完成信号
    generateRequested = pyqtSignal(str)        # AI生成请求信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("创建头像")
        
        # 初始化UI组件
        self._init_ui()
        
        # 连接信号槽
        self._connect_signals()

    def _init_ui(self):
        """使用GridLayout初始化UI布局"""
        main_layout = QGridLayout()
        main_layout.setColumnStretch(0, 7)  # 左侧列占70%宽度
        main_layout.setColumnStretch(1, 3)   # 右侧列占30%宽度
        main_layout.setRowStretch(1, 3)      # 预览行占更大高度比例
        
        # === 左侧区域 ===
        # 原图选择控件
        self.image_selector = ImageSelector()
        self.image_selector.setToolTip("选择本地图片作为头像源文件")
        main_layout.addWidget(self.image_selector, 0, 0)
        
        # 原图预览区域
        self.original_preview = ImagePreviewer("原始图片预览")
        self.original_preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.original_preview.setToolTip("显示原始图片，支持拖拽调整裁剪区域")
        main_layout.addWidget(self.original_preview, 1, 0, 2, 1)  # 跨2行
        
        # 裁切后预览区域
        preview_label = QLabel("处理结果:")
        preview_label.setToolTip("最终生成的头像效果预览")
        main_layout.addWidget(preview_label, 1, 1)
        
        self.cropped_preview = ImagePreviewer("裁切后预览")
        self.cropped_preview.setToolTip("24x24像素的头像最终效果")
        main_layout.addWidget(self.cropped_preview, 2, 1)
        
        # AI生成控件
        self.ai_generator = AIGeneratorWidget()
        self.ai_generator.setToolTip("输入描述词生成个性化AI头像")
        main_layout.addWidget(self.ai_generator, 3, 0, 1, 2)  # 跨2列
        
        # 确认按钮
        self.btn_confirm = QPushButton("使用此头像")
        self.btn_confirm.setEnabled(False)
        self.btn_confirm.setToolTip("确认使用当前显示的头像")
        main_layout.addWidget(self.btn_confirm, 4, 0, 1, 2)  # 跨2列
        
        # === 右侧区域 ===
        # 说明信息区域 (放在单独的frame中)
        instruction_frame = QFrame()
        instruction_frame.setFrameShape(QFrame.StyledPanel)
        instruction_layout = QVBoxLayout(instruction_frame)
        
        instructions = QLabel(
            "<h3>使用说明</h3>"
            "<ol>"
            "<li>点击<b>选择图片</b>按钮上传本地图片</li>"
            "<li>系统将自动裁切并缩放为24x24头像</li>"
            "<li>预览框将显示原始图片和处理后效果</li>"
            "<li>使用<b>AI生成头像</b>可创建个性化头像</li>"
            "<li>确认后头像将应用到您的账户</li>"
            "</ol>"
        )
        instructions.setWordWrap(True)
        instructions.setAlignment(Qt.AlignTop)
        instruction_layout.addWidget(instructions)
        
        # 添加提示图标
        tip_icon = QLabel()
        tip_icon.setPixmap(QApplication.style().standardIcon(QStyle.SP_MessageBoxInformation).pixmap(32, 32))
        tip_icon.setAlignment(Qt.AlignCenter)
        instruction_layout.addWidget(tip_icon)
        
        instruction_frame.setLayout(instruction_layout)
        instruction_frame.setToolTip("头像创建指南和注意事项")
        main_layout.addWidget(instruction_frame, 0, 1, 1, 1)  # 位于右上角
        
        self.setLayout(main_layout)

    def _connect_signals(self):
        """连接信号和槽函数"""
        # 图片选择信号
        self.image_selector.imageSelected.connect(self._load_and_process_image)
        
        # AI生成请求信号
        self.ai_generator.generateRequested.connect(self.generateRequested)
        
        # 确认按钮
        self.btn_confirm.clicked.connect(self._confirm_avatar)

    def _load_and_process_image(self, image_path):
        """加载并处理图片"""
        # 加载原始图片
        original_pixmap = QPixmap(image_path)
        if not original_pixmap.isNull():
            # 显示原图预览
            self.original_preview.display_image(original_pixmap)
            
            # 处理图片并显示结果
            processed = ImageProcessor.crop_and_scale(image_path)
            self.cropped_preview.display_image(processed)
            
            # 保存当前处理结果
            self.current_avatar = processed
            self.btn_confirm.setEnabled(True)

    def _confirm_avatar(self):
        """确认使用当前头像"""
        if hasattr(self, 'current_avatar') and not self.current_avatar.isNull():
            self.avatarCreated.emit(self.current_avatar)
            QMessageBox.information(self, "头像设置", "头像已成功应用！")
            self.close()

    def set_generated_avatar(self, pixmap):
        """设置AI生成的头像"""
        if not pixmap.isNull():
            # 显示处理后的AI头像
            processed = pixmap.scaled(24, 24, Qt.IgnoreAspectRatio, Qt.SmoothTransformation)
            self.cropped_preview.display_image(processed)
            
            # 保存当前处理结果
            self.current_avatar = processed
            self.btn_confirm.setEnabled(True)
            
            # 在原始预览区显示提示
            self.original_preview.setText("AI生成头像\n(原始尺寸)")


class SizeConstraintWidget(QWidget):
    """用于保持宽高比约束的组件"""
    def __init__(self, width_ratio, height_ratio, parent=None):
        super().__init__(parent)
        self.width_ratio = width_ratio
        self.height_ratio = height_ratio
        self.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        
    def sizeHint(self):
        return QSize(100 * self.width_ratio, 100 * self.height_ratio)


class AvatarCreatorWindow(QWidget):
    """头像创建窗口"""
    avatarCreated = pyqtSignal(QPixmap)        # 头像创建完成信号
    generateRequested = pyqtSignal(str)        # AI生成请求信号

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("创建头像")
        self.setMinimumSize(600, 400)
        
        # 初始化UI组件
        self._init_ui()
        
        # 连接信号槽
        self._connect_signals()

    def _init_ui(self):
        """初始化UI布局"""
        main_layout = QGridLayout()
        main_layout.setColumnStretch(0, 1)  # 控制区域
        main_layout.setColumnStretch(1, 2)  # 预览区域
        main_layout.setColumnStretch(2, 1)  # 说明区域
        
        # 左侧控制面板
        control_panel = QVBoxLayout()
        
        # 图片选择器
        self.image_selector = ImageSelector()
        self.image_selector.setToolTip("从本地文件选择头像图片")
        
        # AI生成控件
        self.ai_generator = AIGeneratorWidget()
        self.ai_generator.setToolTip("通过AI提示生成个性化头像")
        
        # 处理结果预览（使用容器保持1:1比例）
        self.cropped_container = QWidget()
        self.cropped_container.setLayout(QVBoxLayout())
        self.cropped_container.layout().setContentsMargins(0, 0, 0, 0)
        
        self.cropped_preview = ImagePreviewer("裁切后预览 (24x24)")
        self.cropped_preview.setAlignment(Qt.AlignCenter)
        self.cropped_container.layout().addWidget(self.cropped_preview)
        
        # 比例约束（1:1）
        self.cropped_container.setSizePolicy(QSizePolicy.Ignored, QSizePolicy.Ignored)
        self.sizeConstraint = SizeConstraintWidget(1, 1)  # 1:1比例
        self.sizeConstraint.hide()  # 仅用于约束，不需要显示
        
        # 确认按钮
        self.btn_confirm = QPushButton("使用此头像")
        self.btn_confirm.setToolTip("确认使用当前头像")
        self.btn_confirm.setEnabled(False)
        
        # 添加到控制面板
        control_panel.addWidget(self.image_selector)
        control_panel.addWidget(self.ai_generator)
        control_panel.addWidget(QLabel("处理结果:"))
        control_panel.addWidget(self.cropped_container)
        control_panel.addWidget(self.btn_confirm)
        control_panel.addStretch(1)
        
        # 中间预览区域
        self.original_preview = ImagePreviewer("原始图片预览")
        self.original_preview.setToolTip("原始图片预览区域")
        self.original_preview.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        
        # 右侧说明区域
        instructions = QLabel(
            "<h3>使用说明</h3>"
            "<ol>"
            "<li>点击<b>选择图片</b>按钮上传本地图片</li>"
            "<li>系统将自动裁切并缩放为24x24头像</li>"
            "<li>在右侧区域预览原始图片和处理后效果</li>"
            "<li>使用<b>AI生成头像</b>可创建个性化头像</li>"
            "<li>确认后头像将应用到您的账户</li>"
            "</ol>"
        )
        instructions.setWordWrap(True)
        instructions.setAlignment(Qt.AlignTop)
        instructions.setObjectName("instructionLabel")  # 用于样式表
        instructions.setToolTip("头像创建使用指南")
        
        # 添加到主布局
        main_layout.addLayout(control_panel, 0, 0)
        main_layout.addWidget(self.original_preview, 0, 1)
        main_layout.addWidget(instructions, 0, 2)
        
        # 设置列和行的伸缩因子
        main_layout.setRowStretch(0, 1)
        main_layout.setColumnStretch(0, 1)  # 控制区域
        main_layout.setColumnStretch(1, 3)  # 预览区域 - 更大的空间
        main_layout.setColumnStretch(2, 1)  # 说明区域
        
        self.setLayout(main_layout)

    def resizeEvent(self, event):
        """确保裁剪预览保持1:1比例"""
        super().resizeEvent(event)
        
        # 保持裁剪预览区域的1:1比例
        container_size = self.cropped_container.size()
        side = min(container_size.width(), container_size.height())
        self.cropped_preview.setFixedSize(side, side)

    def _connect_signals(self):
        """连接信号和槽函数"""
        # 图片选择信号
        self.image_selector.imageSelected.connect(self._load_and_process_image)
        
        # AI生成请求信号
        self.ai_generator.generateRequested.connect(self.generateRequested)
        
        # 确认按钮
        self.btn_confirm.clicked.connect(self._confirm_avatar)

    def _load_and_process_image(self, image_path):
        """加载并处理图片"""
        # 加载原始图片
        original_pixmap = QPixmap(image_path)
        if not original_pixmap.isNull():
            # 显示原图预览（适应预览区域大小）
            preview_size = self.original_preview.size()
            scaled_pixmap = original_pixmap.scaled(
                preview_size, 
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.original_preview.display_image(scaled_pixmap)
            
            # 处理图片并显示结果
            processed = ImageProcessor.crop_and_scale(image_path)
            
            # 保持裁剪区域的1:1比例
            container_size = self.cropped_container.size()
            side = min(container_size.width(), container_size.height())
            scaled_avatar = processed.scaled(
                side, side, 
                Qt.KeepAspectRatio, 
                Qt.SmoothTransformation
            )
            
            self.cropped_preview.display_image(scaled_avatar)
            
            # 保存当前处理结果
            self.current_avatar = processed
            self.btn_confirm.setEnabled(True)

    def _confirm_avatar(self):
        """确认使用当前头像"""
        if hasattr(self, 'current_avatar') and not self.current_avatar.isNull():
            self.avatarCreated.emit(self.current_avatar)
            QMessageBox.information(self, "头像设置", "头像已成功应用！")
            self.close()

    def set_generated_avatar(self, pixmap):
        """设置AI生成的头像"""
        if not pixmap.isNull():
            # 保存原始尺寸
            self.fullsize_avatar = pixmap
            
            # 显示处理后的AI头像（1:1比例）
            container_size = self.cropped_container.size()
            side = min(container_size.width(), container_size.height())
            scaled_avatar = pixmap.scaled(
                side, side, 
                Qt.KeepAspectRatio, 
                Qt.SmoothTransformation
            )
            
            self.cropped_preview.display_image(scaled_avatar)
            
            # 在原始预览区显示（适应预览区域）
            preview_size = self.original_preview.size()
            scaled_original = pixmap.scaled(
                preview_size, 
                Qt.KeepAspectRatio,
                Qt.SmoothTransformation
            )
            self.original_preview.display_image(scaled_original)
            
            # 保存当前处理结果
            self.current_avatar = pixmap.scaled(
                24, 24, 
                Qt.IgnoreAspectRatio, 
                Qt.SmoothTransformation
            )
            self.btn_confirm.setEnabled(True)
            
            # 在原始预览区显示提示
            self.original_preview.setText("AI生成头像\n(原始尺寸)")


class AvatarCreatorWindow(QWidget):
    """头像创建工具主界面"""
    # 信号定义
    styleRequested = pyqtSignal(str)  # 生成风格请求信号
    
    def __init__(self, 
                 target_size=(256, 256), 
                 parent=None,
                 avatar_info={
                     'user':{'name':'user','image':''},
                     'assistant':{'name':'assistant','image':''}
                    }
                 ):
        super().__init__(parent)
        self.target_size = target_size  # 可配置的目标尺寸
        self.setWindowTitle('自定义头像')

        self._init_vars(avatar_info)
        self._init_ui()
        self._setup_layout()
        self._connect_signals()
    
    def _init_vars(self,avatar_info):
        self.avatar_info=avatar_info
        self.character_for_names=[]
        for key,items in avatar_info.items():
            self.character_for_names+=[items['name']]

    def _init_ui(self):
        """初始化UI控件"""
        # 控制区组件
        self.character_for = QComboBox()
        self.character_for.addItems(self.character_for_names)

        # 创建模式切换组合框
        self.mode_combo = QComboBox()
        self.mode_combo.addItems(["手动选择", "AI生成"])
        
        # 创建堆栈窗口
        self.mode_stack = QStackedWidget()
        
        # 第一页：手动选择模式
        self.manual_page = QWidget()
        manual_layout = QVBoxLayout(self.manual_page)
        
        self.selector_btn = QPushButton("选择图片")
        self.selector_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)
        self.selector_btn.setToolTip("从本地文件系统选择一张头像图片")
        manual_layout.addWidget(self.selector_btn)
        
        self.mode_stack.addWidget(self.manual_page)
        
        # 第二页：AI生成模式
        self.ai_page = QWidget()
        ai_layout = QVBoxLayout(self.ai_page)
        
        self.style_edit = QLineEdit()
        self.style_edit.setPlaceholderText("输入图片风格描述...")
        self.style_edit.setToolTip("描述您希望生成的风格，例如'卡通风格'或'像素风格'")
        ai_layout.addWidget(self.style_edit)
        
        self.generate_btn = QPushButton("生成头像")
        self.generate_btn.setToolTip("根据描述生成头像图片")
        ai_layout.addWidget(self.generate_btn)

        self.character_source_combo = QComboBox()
        self.character_source_combo.addItems(['完整对话','选择的对话'])
        
        self.character_include_syspromt = QCheckBox("携带系统提示")
        ai_layout.addWidget(QLabel('形象生成自'))
        ai_layout.addWidget(self.character_source_combo)

        ai_layout.addWidget(self.character_include_syspromt)

        
        self.mode_stack.addWidget(self.ai_page)
        
        
        
        # 预览区组件
        self.original_preview_label = QLabel("原始图片")
        self.original_preview = ImagePreviewer("原始图片预览")
        self.result_preview_label = QLabel('处理结果')
        self.result_preview = ImagePreviewer("处理结果预览")

    def _setup_layout(self):
        """设置网格布局系统"""
        main_layout = QGridLayout(self)
        
        # 控制区
        control_box = QGroupBox("设置")
        control_layout = QGridLayout(control_box)
        row = 0

        # 第一行：模式选择
        control_layout.addWidget(QLabel('模式选择'), row, 0, 1, 1)
        control_layout.addWidget(self.mode_combo, row, 1, 1, 1)
        row += 1
        
        # 第二行：角色选择
        control_layout.addWidget(QLabel('角色'), row, 0, 1, 1)
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
        
        
        # 预览区 - 水平布局
        preview_box = QGroupBox("预览区域")
        preview_layout = QGridLayout(preview_box)
        preview_layout.addWidget(QLabel('原始图像'), 0,0,1,1)
        preview_layout.addWidget(self.original_preview, 1,0,1,1)
        preview_layout.addWidget(QLabel('处理后图像'), 0,1,1,1)
        preview_layout.addWidget(self.result_preview,1,1,1,1)
        
        # 添加到主网格布局
        main_layout.addWidget(control_box, 0, 0)
        main_layout.addWidget(preview_box, 0, 1)
        
    def _connect_signals(self):
        """连接信号与槽函数"""
        self.selector_btn.clicked.connect(self._select_image)
        self.generate_btn.clicked.connect(self._emit_style_request)
        self.mode_combo.currentIndexChanged.connect(self.mode_stack.setCurrentIndex) 
        #self.character_source_combo.currentIndexChanged.connect(self._save_avatar_info)
        
    def _select_image(self):
        """打开文件选择对话框"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择头像", "", 
            "图片文件 (*.png *.jpg *.jpeg *.bmp)"
        )
        if file_path:
            self._process_image(file_path)
            
    def _process_image(self, file_path: str):
        """处理图片并更新预览"""
        # 使用图像处理工具类
        result_pixmap = ImageProcessor.crop_and_scale(file_path, self.target_size)
        
        # 显示原始图片和处理结果
        self.original_preview.display_image(QPixmap(file_path))
        self.result_preview.display_image(result_pixmap)
        
    def _emit_style_request(self):
        """发送AI生成请求信号"""
        style_text = self.style_edit.text().strip()
        if style_text:
            self.styleRequested.emit(style_text)
    def recall(self,names={},file_path='',):
        super().show()

    #def _update_names(self,names):
    
    
if __name__ == "__main__":

    app = QApplication([])

    window = AvatarCreatorWindow()

    window.show()
    app.exec_()