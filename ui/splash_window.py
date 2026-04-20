from PyQt6.QtWidgets import(
    QSplashScreen, QApplication, QProgressBar, 
    QLabel, QVBoxLayout, QWidget
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QPixmap


class SplashScreen(QSplashScreen):
    def __init__(self, image_path="ui/assets/splash.jpeg"):
        # 加载图片
        pixmap = QPixmap(image_path)
        
        super().__init__(pixmap)
        
        # 设置窗口标志 - 无边框、置顶
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint | 
            Qt.WindowType.WindowStaysOnTopHint
        )
        
        # 创建中心部件用于布局
        self.central_widget = QWidget(self)
        self.central_widget.setGeometry(0, 0, pixmap.width(), pixmap.height())
        
        # 创建布局
        layout = QVBoxLayout(self.central_widget)
        layout.setContentsMargins(20, 20, 20, 20)
        layout.setSpacing(10)
        
        # 添加弹性空间，将控件推到底部
        layout.addStretch()
        
        # 创建任务标签
        self.task_label = QLabel("正在初始化...")
        self.task_label.setStyleSheet("""
            QLabel {
                color: white;
                font-size: 14px;
                font-weight: bold;
                background-color: rgba(0, 0, 0, 150);
                padding: 8px 12px;
                border-radius: 4px;
            }
        """)
        self.task_label.setAlignment(Qt.AlignmentFlag.AlignLeft)
        layout.addWidget(self.task_label)
        
        # 创建进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setValue(0)
        self.progress_bar.setTextVisible(True)
        self.progress_bar.setFixedHeight(20)

        layout.addWidget(self.progress_bar)
        
    def update_progress(self, value: int):
        """更新进度条值 (0-100)"""
        self.progress_bar.setValue(max(0, min(100, value)))
        # 处理事件，确保UI更新
        QApplication.processEvents()
        
    def update_message(self, message: str):
        """更新当前任务显示文本"""
        self.task_label.setText(message)
        # 处理事件，确保UI更新
        QApplication.processEvents()
        
    def show_message(self, message: str, alignment=Qt.AlignmentFlag.AlignBottom | Qt.AlignmentFlag.AlignCenter, color=Qt.GlobalColor.white):
        """原生方法：在图片上显示文字（可选使用）"""
        super().showMessage(message, alignment, color)
    
    def progress(self, value: int, message: str = None):
        """更新进度条和消息"""
        self.update_progress(value)
        self.update_message(message)