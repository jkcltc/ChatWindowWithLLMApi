import time
from collections import deque
#tps处理
class StatusAnalyzer:
    def __init__(self):
        self.history = deque()  # 存储(time, char_count)的队列
        self.current_rate = 0.0
        self.peak_rate = 0.0     # 速率峰值（绝对值最大）
        self.model=''
        self.provider=''
        self.request_send_time=0.0 #time.time()
        self.first_token_receive_time=0.0 #time.time()

    def start_record(self,model='',provider='',request_send_time=0):
        self.history = deque()
        if model:
            self.model=model
        if provider:
            self.provider=provider
        self.request_send_time=request_send_time if request_send_time else time.time()


    def process_input(self, input_str):
        current_time = time.time()
        current_char_count = len(input_str)

        # 添加新数据
        self.history.append((current_time, current_char_count))

        # 当前对话内的平均速率
        if len(self.history) >= 2:
            oldest = self.history[0]
            newest = self.history[-1]
            total_time = newest[0] - oldest[0]
            total_chars = newest[1] - oldest[1]
            self.current_rate = total_chars / total_time if total_time > 0 else 0.0
        else:
            self.current_rate = 0.0

        # 当前对话内的速率峰值（取绝对值）
        self.peak_rate = 0.0
        if len(self.history) >= 2:
            max_speed = 0.0
            for i in range(1, len(self.history)):
                prev = self.history[i-1]
                curr = self.history[i]
                delta_time = curr[0] - prev[0]
                
                if delta_time > 0:
                    speed = max((curr[1] - prev[1]) / delta_time,0)
                    if speed > max_speed:
                        max_speed = speed
            self.peak_rate = max_speed

    def get_current_rate(self):
        return self.current_rate

    def get_peak_rate(self):
        return self.peak_rate

    def get_first_token(self):
        if self.history:
            self.first_token_receive_time=abs(self.history[0][0]-self.request_send_time)
            return self.first_token_receive_time
        else:
            return 0
    
    def get_completion_time(self):
        if self.history:
            self.first_token_receive_time=abs(self.history[-1][0]-self.request_send_time)
            return self.first_token_receive_time
        else:
            return 0

    def get_chat_rounds(self,history):
        return len(history)
    
    def get_chat_length(self,history):
        total_length=0
        for item in history:
            total_length+=len(item['content'])
        return total_length

