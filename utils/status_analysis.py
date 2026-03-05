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
        self.end_time = 0.0

        self.content_chars = 0
        self.reasoning_chars = 0
        self.tool_chars = 0
        self.total_chars =0
        self.last_chars = 0
        self.last_update_time = 0.0

        self.current_rate = 0.0
        self.peak_rate = 0.0

        self.model = ''
        self.provider = ''

    def start_record(self, model='', provider='', send_time=0):
        self.reset()
        self.model = model
        self.provider = provider
        self.request_send_time = send_time if send_time else time.time()

    def process_stream(self, req_id:str , delta: str, content_type:str):

        if not delta:
            return
        
        curr_time = time.time()
        self.total_chars += len(delta)

        if content_type == 'reasoning': self.reasoning_chars += len(delta)
        elif content_type == 'tool':    self.tool_chars += len(delta)
        else:                          self.content_chars += len(delta)


        # 1. 记录首字时间 (TTFT)
        if self.first_token_time == 0.0:
            self.first_token_time = curr_time
            self.last_update_time = curr_time

        # 2. 计算瞬时速率
        dt = curr_time - self.last_update_time
        # 防跳, eg. 5 token/0.2s 然后 100 token/0.001s
        if dt > 0.3:
            instant_speed = (self.total_chars - self.last_chars) / dt
            if instant_speed > self.peak_rate:
                self.peak_rate = instant_speed
            
            self.last_update_time = curr_time
            self.last_chars = self.total_chars
            
        # 3. 计算全局平均速率 (TPS)
        total_dt = curr_time - self.first_token_time
        self.current_rate = self.total_chars / total_dt if total_dt > 0 else 0.0

        return self._status_pack()
    
    def process_full(self):
        if self.end_time == 0.0: self.end_time = time.time()
        return self._status_pack()

    def _status_pack(self):
        ttft = (self.first_token_time - self.request_send_time) if self.first_token_time > 0 else 0.0
        calc_end = self.end_time if self.end_time > 0 else time.time()
        duration = (calc_end - self.request_send_time) if self.request_send_time > 0 else 0.0

        
        stats = {
            "model": self.model,
            "provider": self.provider,
            "ttft_ms": int(max(ttft, 0.0) * 1000),
            "tps": round(self.current_rate, 2),
            "peak_tps": round(self.peak_rate, 2),
            "duration_s": round(max(duration, 0.0), 2),

            "content_chars": self.content_chars,
            "reasoning_chars": self.reasoning_chars,
            "tool_chars": self.tool_chars,
        }

        return stats