# utils/theme_manager.py
import os
import configparser
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *

class ThemeSelector(QWidget):
    def __init__(self, init_path=None):
        super().__init__()
        self.current_theme = ""
        self.applied_theme = ""  # 记录已应用的主题路径
        self.init_path = init_path
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
        
        # 设置初始样式
        self.setStyleSheet("""
            QWidget {
                background-color: #f0f0f0;
            }
            QGroupBox {
                border: 1px solid #aaa;
                border-radius: 5px;
                margin-top: 1ex;
                font-weight: bold;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                left: 10px;
                padding: 0 5px;
            }
            QListWidget {
                border: 1px solid #ccc;
                border-radius: 3px;
                background-color: white;
            }
            QPushButton {
                min-width: 80px;
                padding: 5px;
                border-radius: 4px;
                background-color: white;  
                color: black;             
                border: 1px solid #CCCCCC;
            }
        """)

    def get_theme_dir(self):
        """获取主题目录路径"""
        theme_dir = "theme"
        if self.init_path:
            theme_dir = os.path.join(self.init_path, "theme")
        return theme_dir

    def get_config_path(self):
        """获取配置文件路径"""
        return os.path.join(self.get_theme_dir(), "theme_setting.ini")

    def load_themes(self):
        """从theme目录加载所有QSS主题文件"""
        theme_dir = self.get_theme_dir()
        if not os.path.exists(theme_dir):
            os.makedirs(theme_dir)
            return
            
        for file in os.listdir(theme_dir):
            if file.endswith(".qss"):
                theme_path = os.path.join(theme_dir, file)
                item = QListWidgetItem(os.path.splitext(file)[0])
                item.setData(Qt.ItemDataRole.UserRole, theme_path)
                self.theme_list.addItem(item)
                
        # 默认选择第一个主题
        if self.theme_list.count() > 0:
            self.theme_list.setCurrentRow(0)

    def preview_theme(self):
        """预览选中的主题"""
        selected_items = self.theme_list.selectedItems()
        if not selected_items:
            return
            
        selected_item = selected_items[0]
        theme_path = selected_item.data(Qt.ItemDataRole.UserRole)
        self.current_theme = theme_path
        
        try:
            with open(theme_path, "r", encoding="utf-8") as f:
                qss = f.read()
                # 仅应用到预览区域
                self.preview_group.setStyleSheet(qss)
        except Exception as e:
            print(f"加载主题失败: {e}")

    def apply_theme(self):
        """将主题应用到整个应用程序"""
        if self.current_theme:
            try:
                with open(self.current_theme, "r", encoding="utf-8") as f:
                    qss = f.read()
                    # 应用到整个应用程序
                    QApplication.instance().setStyleSheet(qss)
                    self.applied_theme = self.current_theme
            except Exception as e:
                print(f"应用主题失败: {e}")

    def apply_and_close(self):
        """应用主题并关闭窗口"""
        self.apply_theme()
        self.close()

    def closeEvent(self, event):
        """重写关闭事件，保存当前主题设置"""
        if self.applied_theme:
            self.save_current_theme(self.applied_theme)
        super().closeEvent(event)

    def save_current_theme(self, theme_path):
        """保存当前主题到配置文件"""
        config_path = self.get_config_path()
        config = configparser.ConfigParser()
        
        # 如果配置文件存在，读取现有内容
        if os.path.exists(config_path):
            config.read(config_path, encoding="utf-8")
        
        # 更新或添加主题设置
        if not config.has_section("Theme"):
            config.add_section("Theme")
        config.set("Theme", "current_theme", theme_path)
        
        # 确保主题目录存在
        theme_dir = self.get_theme_dir()
        if not os.path.exists(theme_dir):
            os.makedirs(theme_dir)
        
        # 写入配置文件
        with open(config_path, "w", encoding="utf-8") as configfile:
            config.write(configfile)

    @staticmethod
    def apply_saved_theme(init_path=None):
        """
        静态方法：应用保存的主题到主UI
        :param init_path: 主题目录的基础路径
        """
        # 确定主题目录
        theme_dir = "theme"
        if init_path:
            theme_dir = os.path.join(init_path, "theme")
        
        config_path = os.path.join(theme_dir, "theme_setting.ini")
        
        # 如果配置文件不存在，直接返回
        if not os.path.exists(config_path):
            return
        
        # 读取配置文件
        config = configparser.ConfigParser()
        config.read(config_path, encoding="utf-8")
        
        # 检查是否有保存的主题
        if config.has_option("Theme", "current_theme"):
            theme_path = config.get("Theme", "current_theme")
            
            # 检查主题文件是否存在
            if os.path.exists(theme_path):
                try:
                    with open(theme_path, "r", encoding="utf-8") as f:
                        qss = f.read()
                        QApplication.instance().setStyleSheet(qss)
                except Exception as e:
                    print(f"应用保存的主题失败: {e}")
            else:
                print(f"保存的主题文件不存在: {theme_path}")

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