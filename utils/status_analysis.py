import time
from collections import deque
from utils.str_tools import StrTools
from typing import TYPE_CHECKING

class StatusAnalyzer:
    def __init__(self):
        self.reset()
        
    def reset(self):
        self.request_send_time = 0.0
        self.first_token_time = 0.0
        
        self.total_chars = 0
        self.last_chars = 0
        self.last_update_time = 0.0
        
        self.current_rate = 0.0
        self.peak_rate = 0.0
        
        self.model = ''
        self.provider = ''
        self.req_id=''

    def start_record(self, model='', provider='', send_time=0):
        self.reset()
        self.model = model
        self.provider = provider
        self.request_send_time = send_time if send_time else time.time()

    def process_stream(self, req_id:str , delta: str):

        if not delta:
            return
        
        curr_time = time.time()
        self.total_chars += len(delta)

        # 1. 记录首字时间 (TTFT)
        if self.first_token_time == 0.0:
            self.first_token_time = curr_time
            self.last_update_time = curr_time

        # 2. 计算瞬时速率
        dt = curr_time - self.last_update_time
        # 防跳, eg. 5 token/0.2s 然后 100 token/0.001s
        if dt > 0.1:
            instant_speed = (self.total_chars - self.last_chars) / dt
            if instant_speed > self.peak_rate:
                self.peak_rate = instant_speed
            
            self.last_update_time = curr_time
            self.last_chars = self.total_chars
            
        # 3. 计算全局平均速率 (TPS)
        total_dt = curr_time - self.first_token_time
        self.current_rate = self.total_chars / total_dt if total_dt > 0 else 0.0

        return self._status_pack()
    
    def process_full(self,cr,cl):
        return self._status_pack(cr,cl)

    def _status_pack(self,cr=None,cl=None):
        ttft = (self.first_token_time - self.request_send_time) if self.first_token_time > 0 else 0.0

        
        stats = {
            "model": self.model,
            "provider": self.provider,
            "ttft": max(ttft, 0.0),
            "tps": self.current_rate,
            "peak_tps": self.peak_rate,
            "total_chars": self.total_chars
        }

        if cr and cl:
            stats['total_rounds']=cr

            stats['total_length']=cl

        return stats