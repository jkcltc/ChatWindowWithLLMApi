import os
import json
import requests
import time
import threading
from PyQt5.QtCore import QObject,pyqtSignal

class BaiduImageGenerator(QObject):
    request_emit=pyqtSignal(str)
    pull_success=pyqtSignal(str)#path
    failure=pyqtSignal(str,str)

    def __init__(self, api_key,application_path,parent=None,save_folder='pics'):
        super.__init__()

    
    def _save_image(self, url, filename):
        """保存图片到指定目录"""
        pass

    def generate(self, a_lot_of_params):
        return 'task_id'

    def poll_result(self, task_id, timeout=600, interval=5):
        """轮询任务结果并返回图片路径"""
        return 'file_ptah'
