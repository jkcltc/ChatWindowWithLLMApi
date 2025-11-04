from PyQt6.QtWidgets import *
from PyQt6.QtGui import *
from PyQt6.QtCore import *
#from image_agents import ImageAgent
from PyQt6.QtWidgets import (
    QApplication, QWidget, QGridLayout, QGroupBox, QComboBox, QTextEdit, 
    QFrame, QLabel, QSpinBox, QCheckBox, QPushButton, QSizePolicy, QVBoxLayout
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QFont


class SingleImageGenerateWindow(QWidget):
    generate_clicked = pyqtSignal(dict)        # 发射包含所有参数的字典
    save_clicked = pyqtSignal()
    save_as_clicked = pyqtSignal()
    delete_clicked = pyqtSignal()
    set_background_clicked = pyqtSignal()
    llm_toggled = pyqtSignal(bool) 
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setup_ui()
        self.setup_connections()
        
    def setup_ui(self):
        # 主窗口设置
        self.setWindowTitle("单图生成")
        
        # 主布局 - QGridLayout
        main_layout = QGridLayout(self)
        main_layout.setSpacing(10)
        main_layout.setContentsMargins(15, 15, 15, 15)

        # 模型设置区域
        model_settings = self.create_model_settings()
        main_layout.addWidget(model_settings, 0, 0)  # row=0, column=0

        # 垂直线
        vertical_line = self.create_vertical_line()
        main_layout.addWidget(vertical_line, 0, 1, 5, 1)  # row=0, column=1, rowspan=5

        # 生成结果区域
        result_preview = self.create_result_preview()
        main_layout.addWidget(result_preview, 0, 3, 3, 2)  # row=0, column=3, rowspan=3, colspan=2

        # 提示词设置区域
        prompt_settings = self.create_prompt_settings()
        main_layout.addWidget(prompt_settings, 1, 0)  # row=1, column=0

        # 其他参数设置
        advanced_params = self.create_advanced_params()
        main_layout.addWidget(advanced_params, 2, 0, 3, 1)  # row=2, column=0, rowspan=3

        # 操作按钮区域
        action_buttons = self.create_action_buttons()
        main_layout.addWidget(action_buttons, 3, 4, 2, 1)  # row=3, column=4, rowspan=2

        # 右侧占位符 - 使用 QSpacerItem
        spacer = QSpacerItem(40, 20, QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Minimum)
        main_layout.addItem(spacer, 4, 3)  # row=4, column=3
        
        # 设置列比例
        main_layout.setColumnStretch(0, 0)  # 左侧面板宽度
        main_layout.setColumnStretch(3, 2)  # 预览区域宽度
        main_layout.setColumnStretch(4, 1)  # 按钮区域宽度
        main_layout.setRowStretch(3,0)
        main_layout.setRowStretch(0,0)
        main_layout.setRowStretch(1,1)

    def create_model_settings(self):
        """模型设置区域"""
        group_box = QGroupBox("模型设置")
        layout = QVBoxLayout(group_box)
        
        # 文生图模型
        text_to_image_group = QGroupBox("文生图模型")
        text_layout = QGridLayout(text_to_image_group)
        self.image_provider_combo = QComboBox()
        self.image_model_combo = QComboBox()
        text_layout.addWidget(self.image_provider_combo, 0, 0)
        text_layout.addWidget(self.image_model_combo, 1, 0)
        
        # LLM优化
        self.llm_group = QGroupBox("使用LLM优化prompt")
        self.llm_group.setCheckable(True)
        llm_layout = QGridLayout(self.llm_group)
        self.llm_provider_combo = QComboBox()
        self.llm_model_combo = QComboBox()
        llm_layout.addWidget(self.llm_provider_combo, 0, 0)
        llm_layout.addWidget(self.llm_model_combo, 1, 0)
        
        # 在模型设置区域的底部添加一个垂直弹簧
        layout.addWidget(text_to_image_group)
        layout.addWidget(self.llm_group)
        
        return group_box

    def create_prompt_settings(self):
        """提示词设置区域"""
        group_box = QGroupBox("提示词设置（必要）")
        layout = QVBoxLayout(group_box)
        
        # Prompt输入
        prompt_group = QGroupBox("prompt")
        prompt_layout = QVBoxLayout(prompt_group)
        self.prompt_edit = QTextEdit()
        prompt_layout.addWidget(self.prompt_edit)
        
        # Negative Prompt
        negative_group = QGroupBox("negative prompt")
        negative_layout = QVBoxLayout(negative_group)
        self.negative_prompt_edit = QTextEdit()
        negative_layout.addWidget(self.negative_prompt_edit)
        
        layout.addWidget(prompt_group)
        layout.addWidget(negative_group)
        
        return group_box

    def create_advanced_params(self):
        """高级参数设置"""
        group_box = QGroupBox("其他参数")
        layout = QGridLayout(group_box)
        layout.setSpacing(10)
        
        # 添加分隔线
        layout.addWidget(self.create_horizontal_line(), 0, 0, 1, 3)
        
        # 图片尺寸设置
        size_label = QLabel("图片大小")
        size_label.setSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Minimum)
        layout.addWidget(size_label, 1, 0, 1, 3)
        
        width_label = QLabel("宽")
        width_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(width_label, 2, 1)
        
        self.image_width_spin = QSpinBox()
        self.image_width_spin.setMinimum(100)
        self.image_width_spin.setMaximum(4096)
        self.image_width_spin.setValue(1024)
        layout.addWidget(self.image_width_spin, 2, 2)
        
        height_label = QLabel("高")
        height_label.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        layout.addWidget(height_label, 3, 1)
        
        self.image_height_spin = QSpinBox()
        self.image_height_spin.setMinimum(100)
        self.image_height_spin.setMaximum(4096)
        self.image_height_spin.setValue(768)
        layout.addWidget(self.image_height_spin, 3, 2)
        
        # 分隔线
        layout.addWidget(self.create_horizontal_line(), 4, 0, 1, 3)
        
        # 步数设置
        steps_label = QLabel("步数")
        layout.addWidget(steps_label, 5, 0)
        
        self.inference_steps_spin = QSpinBox()
        self.inference_steps_spin.setMinimum(1)
        self.inference_steps_spin.setMaximum(200)
        self.inference_steps_spin.setValue(25)
        layout.addWidget(self.inference_steps_spin, 5, 2)
        
        # 分隔线
        layout.addWidget(self.create_horizontal_line(), 6, 0, 1, 3)
        
        # 导引强度
        guidance_label = QLabel("导引强度")
        layout.addWidget(guidance_label, 7, 0)
        
        self.guidance_scale_spin = QSpinBox()
        self.guidance_scale_spin.setMinimum(1)
        self.guidance_scale_spin.setMaximum(30)
        self.guidance_scale_spin.setValue(7)
        layout.addWidget(self.guidance_scale_spin, 7, 2)
        
        # 分隔线
        layout.addWidget(self.create_horizontal_line(), 8, 0, 1, 3)
        
        # NSFW选项
        self.nsfw_checkbox = QCheckBox("NSFW")
        layout.addWidget(self.nsfw_checkbox, 9, 0)
        
        # 底部弹簧 - 使用 QSpacerItem
        layout.addItem(QSpacerItem(2, 4, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding), 10, 0, 1, 3)
        
        return group_box

    def create_result_preview(self):
        """生成结果预览区域"""
        group_box = QGroupBox("生成结果")
        layout = QVBoxLayout(group_box)
        
        # 预览标签
        self.preview_label = QLabel("预览图")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setMinimumHeight(500)
        layout.addWidget(self.preview_label)
        
        # 在预览图和按钮之间添加弹簧
        layout.addItem(QSpacerItem(2, 2, QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Expanding))
        
        # 生成按钮
        self.generate_button = QPushButton("生成图像")
        layout.addWidget(self.generate_button)
        
        return group_box

    def create_action_buttons(self):
        """操作按钮区域"""
        group_box = QGroupBox("操作结果")
        layout = QGridLayout(group_box)
        
        # 保存按钮
        self.save_button = QPushButton("保存")
        layout.addWidget(self.save_button, 0, 0)  # row=0, col=0
        
        # 垂直线
        vertical_line = self.create_vertical_line()
        layout.addWidget(vertical_line, 0, 1, 3, 1)  # row=0, col=1, rowspan=3
        
        # 另存为按钮
        self.save_as_button = QPushButton("另存为...")
        layout.addWidget(self.save_as_button, 0, 2)  # row=0, col=2

        
        # 删除按钮
        self.delete_button = QPushButton("删除")
        layout.addWidget(self.delete_button, 2, 0)  # row=2, col=0
        
        # 设置背景按钮
        self.set_background_button = QPushButton("更新为主界面背景")
        layout.addWidget(self.set_background_button, 2, 2)  # row=2, col=2
        
        # 添加水平分隔线
        horizontal_line = self.create_horizontal_line()
        layout.addWidget(horizontal_line, 1, 0, 1, 3)  # row=1, col=0, colspan=3
        
        return group_box

    def setup_connections(self):
        """初始化信号连接 - 更新为发射信号"""
        # 连接LLM启用状态变化
        self.llm_group.toggled.connect(self.llm_toggled.emit)
        self.llm_group.toggled.connect(self.llm_provider_combo.setEnabled)
        self.llm_group.toggled.connect(self.llm_model_combo.setEnabled)
        
        # 连接按钮信号 - 发射对应的信号而不是直接调用方法
        self.generate_button.clicked.connect(self.emit_generate_signal)
        self.save_button.clicked.connect(self.save_clicked.emit)
        self.save_as_button.clicked.connect(self.save_as_clicked.emit)
        self.delete_button.clicked.connect(self.delete_clicked.emit)
        self.set_background_button.clicked.connect(self.set_background_clicked.emit)
        
        # 默认禁用LLM选项相关控件
        self.llm_provider_combo.setEnabled(True)
        self.llm_model_combo.setEnabled(True)

    def emit_generate_signal(self):
        """收集所有参数并发射生成信号"""
        params = {
            'prompt': self.prompt_edit.toPlainText(),
            'negative_prompt': self.negative_prompt_edit.toPlainText(),
            'width': self.image_width_spin.value(),
            'height': self.image_height_spin.value(),
            'steps': self.inference_steps_spin.value(),
            'guidance_scale': self.guidance_scale_spin.value(),
            'nsfw': self.nsfw_checkbox.isChecked(),
            'use_llm': self.llm_group.isChecked(),
            'llm_provider': self.llm_provider_combo.currentText(),
            'llm_model': self.llm_model_combo.currentText(),
            'image_provider': self.image_provider_combo.currentText(),
            'image_model': self.image_model_combo.currentText(),
        }
        self.generate_clicked.emit(params)

    # 辅助函数
    def create_vertical_line(self):
        """创建垂直分隔线"""
        line = QFrame()
        line.setFrameShape(QFrame.Shape.VLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setMaximumWidth(2)
        return line

    def create_horizontal_line(self):
        """创建水平分隔线"""
        line = QFrame()
        line.setFrameShape(QFrame.Shape.HLine)
        line.setFrameShadow(QFrame.Shadow.Sunken)
        line.setMaximumHeight(2)
        return line



if __name__=='__main__':
    
    import sys
    app = QApplication([])
    a=SingleImageGenerateWindow()
    a.show()
    sys.exit(app.exec())