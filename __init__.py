__version__ = "0.25.4"
__author__ = "jkcltc"

from CWLA_main import start
import sys
import ctypes

def setup_app_id():
    if sys.platform == 'win32':
        appid = f'CWLA.{__version__}'
        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(appid)

__all__ = [
    "start", 
    "setup_app_id", 
    "__version__", 
    "__author__"
]