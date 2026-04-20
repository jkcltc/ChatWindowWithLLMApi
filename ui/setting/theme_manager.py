# ui\setting\theme_manager.py
import os
from PyQt6.QtWidgets import (
    QWidget,QHBoxLayout,QFrame,
    QVBoxLayout,QListWidget,QPushButton,
    QGroupBox,QMessageBox,QLabel,
    QLineEdit,QComboBox,QCheckBox,
    QListWidgetItem,QApplication
)
from PyQt6.QtCore import QSize,Qt
from PyQt6.QtGui import QFont
from config import APP_SETTINGS, APP_RUNTIME

class ThemeSelector(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.current_theme = ""
        self.applied_theme = ""
        self.init_path = os.getcwd()
        
        self.init_ui()
        self.load_themes()
        
        # 基础样式
        self.setStyleSheet("""
            QWidget { background-color: #f0f0f0; }
            QGroupBox { border: 1px solid #aaa; border-radius: 5px; margin-top: 1ex; font-weight: bold; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
            QListWidget { border: 1px solid #ccc; border-radius: 3px; background-color: white; }
            QPushButton { min-width: 80px; padding: 5px; border-radius: 4px; background-color: white; color: black; border: 1px solid #CCCCCC; }
        """)

    def init_ui(self):
        # 创建主布局
        main_layout = QHBoxLayout()
        self.setLayout(main_layout)

        # 左侧主题列表区域
        left_panel = QFrame()
        left_panel.setMinimumWidth(250)
        left_layout = QVBoxLayout(left_panel)

        self.theme_list = QListWidget()
        self.theme_list.setIconSize(QSize(24, 24))
        self.theme_list.itemSelectionChanged.connect(self.preview_theme)
        left_layout.addWidget(QLabel("可用主题:"))
        left_layout.addWidget(self.theme_list)

        # 右侧预览区域
        right_panel = QFrame()
        right_layout = QVBoxLayout(right_panel)

        # 预览控件组
        self.preview_group = QGroupBox("主题预览")
        preview_layout = QVBoxLayout(self.preview_group)

        # 添加各种控件用于预览
        self.preview_label = QLabel("Deepseek:\n你好，我是一个AI助手。")
        self.preview_label.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.preview_label.setFont(QFont("Arial", 12))

        self.preview_button = QPushButton("发送消息")
        self.preview_button.setFixedHeight(40)

        self.preview_line_edit = QLineEdit("介绍一下你自己")
        self.preview_line_edit.setPlaceholderText("输入文本...")

        self.preview_combo = QComboBox()
        self.preview_combo.addItems(["deepseek-chat", "deepseek-code", "deepseek-reasoner"])

        self.preview_checkbox = QCheckBox("使用轮换模型")
        self.preview_checkbox.setChecked(True)

        # 添加到布局
        preview_layout.addWidget(self.preview_label)
        preview_layout.addWidget(self.preview_button)
        preview_layout.addWidget(self.preview_line_edit)
        preview_layout.addWidget(self.preview_combo)
        preview_layout.addWidget(self.preview_checkbox)

        # 按钮区域
        button_layout = QHBoxLayout()
        
        self.apply_button = QPushButton("应用主题")
        self.apply_button.setMinimumHeight(40)
        self.apply_button.clicked.connect(self.apply_theme)

        self.reset_button = QPushButton("重置为默认")
        self.reset_button.setMinimumHeight(40)
        self.reset_button.clicked.connect(self.reset_theme)

        button_layout.addWidget(self.apply_button)
        button_layout.addWidget(self.reset_button)
        button_layout.addStretch()

        # 组装右侧布局
        right_layout.addWidget(self.preview_group)
        right_layout.addLayout(button_layout)

        # 添加到主布局
        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_panel, 1)

    def get_theme_dir(self):
        """获取主题目录路径"""
        return APP_RUNTIME.paths.theme_path

    def load_themes(self):
        """从theme目录加载所有QSS主题文件，并选中当前配置的主题"""
        theme_dir = self.get_theme_dir()
        if not os.path.exists(theme_dir):
            os.makedirs(theme_dir)
            return

        # 获取当前配置中的主题文件名（用于回显选中状态）
        current_config_theme = APP_SETTINGS.ui.theme
        abs_current_theme = os.path.abspath(current_config_theme) if current_config_theme else ""

        target_row = 0

        files = [f for f in os.listdir(theme_dir) if f.endswith(".qss")]

        for index, file in enumerate(files):
            theme_path = os.path.join(theme_dir, file)
            abs_path = os.path.abspath(theme_path)

            item = QListWidgetItem(os.path.splitext(file)[0])
            item.setData(Qt.ItemDataRole.UserRole, theme_path)
            self.theme_list.addItem(item)

            if abs_path == abs_current_theme:
                target_row = index

        # 选中当前配置的主题
        if self.theme_list.count() > 0:
            self.theme_list.setCurrentRow(target_row)
            # 立即预览当前选中的主题
            self.preview_theme()

    def preview_theme(self):
        """预览选中的主题（仅对预览区域生效）"""
        selected_items = self.theme_list.selectedItems()
        if not selected_items:
            return

        selected_item = selected_items[0]
        theme_path = selected_item.data(Qt.ItemDataRole.UserRole)
        self.current_theme = theme_path

        try:
            with open(theme_path, "r", encoding="utf-8") as f:
                qss = f.read()
                self.preview_group.setStyleSheet(qss)
        except Exception as e:
            QMessageBox.warning(self, "预览失败", f"加载预览主题失败: {e}")

    def apply_theme(self):
        """将主题应用到整个应用程序并更新全局配置"""
        try:
            with open(self.current_theme, "r", encoding="utf-8") as f:
                qss = f.read()
                QApplication.instance().setStyleSheet(qss)
                self.applied_theme = self.current_theme

            # 为了保持配置文件的可移植性，存储相对路径
            try:
                rel_path = os.path.relpath(self.current_theme, os.getcwd())
                APP_SETTINGS.ui.theme = rel_path
            except ValueError:
                # 如果跨驱动器等情况无法计算相对路径，则存储绝对路径
                APP_SETTINGS.ui.theme = self.current_theme
                
        except Exception as e:
            QMessageBox.critical(self, "应用失败", f"应用主题失败: {e}")

    def reset_theme(self):
        """重置为系统默认主题（清除全局样式表）"""
        QApplication.instance().setStyleSheet("")
        self.applied_theme = ""
        APP_SETTINGS.ui.theme = ""
        # 取消列表选中状态
        self.theme_list.clearSelection()
        # 清除预览区域的样式
        self.preview_group.setStyleSheet("")
        self.current_theme = ""
