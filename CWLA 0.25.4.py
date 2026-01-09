import sys,ctypes
if sys.platform == 'win32':
    appid = 'CWLA 0.25.4'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(appid)
else:
    # 孩子们 鼠鼠不想跑linux和mac测试
    sys.exit(1)
from CWLA_main import start
start()