# test_api_config.py
import sys
from PyQt6.QtWidgets import QApplication
from utils.setting import APP_SETTINGS, ConfigManager
from utils.model_map_manager import APIConfigWidget


app = QApplication(sys.argv)
# 创建窗口
window = APIConfigWidget(
    application_path=r"C:\Users\kcji\Desktop\te\ChatWindowWithLLMApi"
)
# 监听信号，打印看看
def on_config_updated(data):
    print("=" * 50)
    print("收到 configUpdated 信号：")
    for name, info in data.items():
        print(f"  {name}:")
        print(f"    URL: {info['url'][:30]}..." if len(info['url']) > 30 else f"    URL: {info['url']}")
        print(f"    Key: ***{info['key'][-4:]}" if len(info['key']) > 4 else f"    Key: {info['key']}")
        print(f"    Models: {info['models']}")
    print("=" * 50)
window.configUpdated.connect(on_config_updated)
window.notificationRequested.connect(lambda msg, lvl: print(f"[{lvl}] {msg}"))

window.show()
# 退出时打印最终状态
app.aboutToQuit.connect(
    lambda: print(f"\n最终 model_map:\n{APP_SETTINGS.api.model_map}")
)
sys.exit(app.exec())