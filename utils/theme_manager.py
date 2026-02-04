# utils/theme_manager.py
import os
import configparser
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
from utils.setting import APP_SETTINGS,APP_RUNTIME

class ThemeSelector(QWidget):
    def __init__(self, init_path=None):
        super().__init__()
        self.current_theme = ""
        self.applied_theme = "" 
        self.init_path = init_path or os.getcwd() # 确保有路径
        self.setWindowTitle("主题选择器")
        self.setMinimumSize(800, 600)

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

        self.ok_button = QPushButton("确定")
        self.ok_button.setMinimumHeight(40)
        self.ok_button.clicked.connect(self.apply_and_close)

        self.cancel_button = QPushButton("取消")
        self.cancel_button.setMinimumHeight(40)
        self.cancel_button.clicked.connect(self.close)

        button_layout.addWidget(self.apply_button)
        button_layout.addWidget(self.ok_button)
        button_layout.addWidget(self.cancel_button)

        # 组装右侧布局
        right_layout.addWidget(self.preview_group)
        right_layout.addLayout(button_layout)

        # 添加到主布局
        main_layout.addWidget(left_panel)
        main_layout.addWidget(right_panel, 1)

        # 加载可用主题
        self.load_themes()

        # 设置初始样式 (保持不变)
        self.setStyleSheet("""
            QWidget { background-color: #f0f0f0; }
            QGroupBox { border: 1px solid #aaa; border-radius: 5px; margin-top: 1ex; font-weight: bold; }
            QGroupBox::title { subcontrol-origin: margin; left: 10px; padding: 0 5px; }
            QListWidget { border: 1px solid #ccc; border-radius: 3px; background-color: white; }
            QPushButton { min-width: 80px; padding: 5px; border-radius: 4px; background-color: white; color: black; border: 1px solid #CCCCCC; }
        """)

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
        # 转换为绝对路径以便比较
        abs_current_theme = os.path.abspath(current_config_theme)

        target_row = 0

        files = [f for f in os.listdir(theme_dir) if f.endswith(".qss")]

        for index, file in enumerate(files):
            theme_path = os.path.join(theme_dir, file)
            abs_path = os.path.abspath(theme_path)

            item = QListWidgetItem(os.path.splitext(file)[0])
            item.setData(Qt.ItemDataRole.UserRole, theme_path)
            self.theme_list.addItem(item)

            # 比较路径是否一致（处理 / 和 \ 的差异）
            if os.path.normpath(abs_path) == os.path.normpath(abs_current_theme):
                target_row = index

        # 选中当前配置的主题
        if self.theme_list.count() > 0:
            self.theme_list.setCurrentRow(target_row)

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
            print(f"加载预览主题失败: {e}")

    def apply_theme(self):
        """将主题应用到整个应用程序并更新全局配置"""
        if self.current_theme:
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
                print(f"应用主题失败: {e}")

    def apply_and_close(self):
        """应用主题并关闭窗口"""
        self.apply_theme()
        self.close()


    @staticmethod
    def apply_saved_theme():
        """
        静态方法：从 APP_SETTINGS 读取并应用主题
        """
        # 从全局配置获取路径
        theme_path = APP_SETTINGS.ui.theme

        if not theme_path:
            return

        # 如果是相对路径，转换为绝对路径
        if not os.path.isabs(theme_path):
            theme_path = os.path.abspath(theme_path)

        if os.path.exists(theme_path):
            try:
                with open(theme_path, "r", encoding="utf-8") as f:
                    qss = f.read()
                    QApplication.instance().setStyleSheet(qss)
            except Exception as e:
                print(f"应用保存的主题失败: {e}")
        else:
            print(f"配置的主题文件不存在: {theme_path}")

# 使用示例
if __name__ == "__main__":
    import sys
    from PyQt6.QtWidgets import QMainWindow, QTextEdit
    
    class MainWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("主应用窗口")
            self.setGeometry(100, 100, 800, 600)
            
            # 创建中央部件
            central_widget = QTextEdit()
            central_widget.setPlaceholderText("这里是主应用内容区域...")
            self.setCentralWidget(central_widget)
            
            # 添加主题选择按钮
            theme_button = QPushButton("更换主题", self)
            theme_button.move(20, 20)
            theme_button.clicked.connect(self.open_theme_selector)
        
        def open_theme_selector(self):
            selector = ThemeSelector(self,init_path=r'C:\Users\Administrator\Desktop\chatApi\ChatWindowWithLLMApi')
            selector.show()
    
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec())