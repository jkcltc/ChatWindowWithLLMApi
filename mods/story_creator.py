import sys,os
import json
from typing import Dict, Any, Optional
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import threading
import openai

class StoryCreatorGlobalVar:
    DEFAULT_APIS = {
        "baidu": {
            "url": "https://qianfan.baidubce.com/v2",
            "key": "unknown"
        },
        "deepseek": {
            "url": "https://api.deepseek.com/v1",
            "key": "unknown"
        },
        "siliconflow": {
            "url": "https://api.siliconflow.cn/v1",
            "key": "unknown"
        },
        "tencent": {
            "url": "https://api.lkeap.cloud.tencent.com/v1",
            "key": "unknown"
        },
        "novita":{
            "url": "https://api.novita.ai/v3",
            "key": "unknown"
        }
    }
    MODEL_MAP = {
        "baidu": [
    "ernie-4.5-turbo-32k",
    "deepseek-r1",
    "deepseek-v3",
    "ernie-4.5-8k-preview",
    "ernie-4.0-8k",
    "ernie-3.5-8k",
    "ernie-speed-pro-128k",
    "ernie-4.0-turbo-8k",
    "qwq-32b",
    "ernie-4.5-turbo-vl-32k",
    "aquilachat-7b",
    "bloomz-7b",
    "chatglm2-6b-32k",
    "codellama-7b-instruct",
    "deepseek-r1-distill-llama-70b",
    "deepseek-r1-distill-llama-8b",
    "deepseek-r1-distill-qianfan-70b",
    "deepseek-r1-distill-qianfan-8b",
    "deepseek-r1-distill-qianfan-llama-70b",
    "deepseek-r1-distill-qianfan-llama-8b",
    "deepseek-r1-distill-qwen-1.5b",
    "deepseek-r1-distill-qwen-14b",
    "deepseek-r1-distill-qwen-32b",
    "deepseek-r1-distill-qwen-7b",
    "deepseek-v3-241226",
    "deepseek-vl2",
    "deepseek-vl2-small",
    "enrie-irag-edit",
    "ernie-3.5-128k",
    "ernie-3.5-128k-preview",
    "ernie-3.5-8k-0613",
    "ernie-3.5-8k-0701",
    "ernie-3.5-8k-preview",
    "ernie-4.0-8k-0613",
    "ernie-4.0-8k-latest",
    "ernie-4.0-8k-preview",
    "ernie-4.0-turbo-128k",
    "ernie-4.0-turbo-8k-0628",
    "ernie-4.0-turbo-8k-0927",
    "ernie-4.0-turbo-8k-latest",
    "ernie-4.0-turbo-8k-preview",
    "ernie-4.5-8k-preview",
    "ernie-4.5-turbo-128k",
    "ernie-x1-32k",
    "ernie-x1-32k-preview",
    "ernie-x1-turbo-32k",
    "gemma-7b-it",
    "glm-4-32b-0414",
    "glm-z1-32b-0414",
    "glm-z1-rumination-32b-0414",
    "internvl2.5-38b-mpo",
    "llama-2-13b-chat",
    "llama-2-70b-chat",
    "llama-2-7b-chat",
    "llama-4-maverick-17b-128e-instruct",
    "llama-4-scout-17b-16e-instruct",
    "meta-llama-3-70b",
    "meta-llama-3-8b",
    "mixtral-8x7b-instruct",
    "qianfan-70b",
    "qianfan-8b",
    "qianfan-agent-lite-8k",
    "qianfan-agent-speed-32k",
    "qianfan-agent-speed-8k",
    "qianfan-bloomz-7b-compressed",
    "qianfan-chinese-llama-2-13b",
    "qianfan-chinese-llama-2-70b",
    "qianfan-chinese-llama-2-7b",
    "qianfan-llama-vl-8b",
    "qianfan-sug-8k",
    "qwen2.5-7b-instruct",
    "qwen2.5-vl-32b-instruct",
    "qwen2.5-vl-7b-instruct",
    "sqlcoder-7b",
    "xuanyuan-70b-chat-4bit",
    "ernie-speed-128k",
    "ernie-speed-8k",
    "ernie-lite-8k",
    "ernie-lite-pro-128k",
    "qwen3-235b-a22b",
    "qwen3-30b-a3b",
    "qwen3-32b",
    "qwen3-14b",
    "qwen3-8b",
    "qwen3-4b",
    "qwen3-1.7b",
    "qwen3-0.6b",

    ],
        "deepseek": ["deepseek-chat", "deepseek-reasoner"],
        "tencent": ["deepseek-r1", "deepseek-v3"]
    }

class APIRequestHandler(QObject):
    # 定义信号用于跨线程通信
    response_received = pyqtSignal(str)  # 接收到部分响应
    request_completed = pyqtSignal(str)  # 请求完成
    error_occurred = pyqtSignal(str)  # 发生错误
    
    def __init__(self, api_config, parent=None):
        """
        初始化API请求处理器
        :param api_config: API配置信息
        :param parent: 父对象
        """
        super().__init__(parent)
        self.api_config = api_config
        self.client = None
        self.current_thread = None
        self.full_response = ""  # 用于存储完整响应

    def send_request(self, message, model):
        """
        发送API请求（线程安全方式）
        :param message: 提示词
        :param model: 使用的模型
        """
        threading.Thread(
            target=self._send_request_thread,
            args=(message, model)
        ).start()
    
    def special_block_handler(self,content,                      #incoming content                     #function to call
                                  starter='<think>', 
                                  ender='</think>',
                                  extra_params=None             #extra params to fullfill
                                  ):
        """处理自定义块内容"""
        if starter in content :
            content = content.split(starter)[1]
            if ender in content:
                return {"starter":True,"ender":True}
            if extra_params:
                if hasattr(self, extra_params):
                    setattr(self, extra_params, content)

            return {"starter":True,"ender":False}
        return {"starter":False,"ender":False}


    def _send_request_thread(self, messages, model):
        
        def handle_response(content,temp_response):
            if hasattr(content, "content") and content.content:
                special_block_handler_result=self.special_block_handler(temp_response,
                                      starter='<think>', ender='</think>',
                                      extra_params='think_response'
                                      )
                if special_block_handler_result["starter"] and special_block_handler_result["ender"]:#如果思考链结束
                    self.full_response+= content.content
                    self.full_response.replace('</think>\n\n', '')
                elif not (special_block_handler_result["starter"]):#如果没有思考链
                    self.full_response += content.content
                print(content.content, end='', flush=True)
                        # 处理思考链内容
            if hasattr(content, "reasoning_content") and content.reasoning_content:
                self.think_response += content.reasoning_content
                print(content.reasoning_content, end='', flush=True)
        #try:
        client = openai.Client(
            api_key=self.api_config['key'],  # 替换为实际的 API 密钥
            base_url=self.api_config['url']  # 替换为实际的 API 基础 URL
        )
        try: 
            print('AI回复(流式):')
            self.response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    #response_format={
                    #    'type': 'json_object'
                    #},
                    stream=True,  # 启用流式响应
                )
            self.full_response = ""
            self.think_response = "### AI 思考链\n---\n"
            temp_response = ""


            for event in self.response:
                if not hasattr(event, "choices") or not event.choices:
                    print("无效的响应事件:", event)
                    continue

                content = getattr(event.choices[0], "delta", None)
                if not content:
                    print("无效的内容:", event.choices[0])
                    continue
                if hasattr(content, "content") and content.content:
                    temp_response += content.content
                    handle_response(content,temp_response)
                if hasattr(content, "reasoning_content") and content.reasoning_content:
                    self.think_response += content.reasoning_content
                    print(content.reasoning_content, end='', flush=True)
            self.request_completed.emit(self.full_response)
        except Exception as e:
            print("主线API请求错误:", str(e))
            self.error_occurred.emit(f"API请求错误: {str(e)}")

class AnimatedPushButton(QPushButton):
    def __init__(self, text="", parent=None):
        super().__init__(text, parent)
        self.init_ui()
        self.setup_animation()
        self._is_animating = False
        
        # 连接点击信号
        self.clicked.connect(self.start_loop_animation)

    def init_ui(self):
        # 创建高光覆盖层
        self.highlight_overlay = QWidget(self)
        self.highlight_overlay.setStyleSheet("background-color: rgba(100, 200, 255, 100);")
        self.highlight_overlay.hide()
        self.highlight_overlay.setAttribute(Qt.WA_TransparentForMouseEvents)
        
        # 添加透明度效果
        self.opacity_effect = QGraphicsOpacityEffect(self.highlight_overlay)
        self.opacity_effect.setOpacity(1.0)
        self.highlight_overlay.setGraphicsEffect(self.opacity_effect)

    def setup_animation(self):
        # 创建动画组
        self.animation_group = QSequentialAnimationGroup(self)
        self.animation_group.setLoopCount(-1)  # 无限循环

        # 宽度展开动画
        self.width_animation = QPropertyAnimation(self.highlight_overlay, b"geometry")
        self.width_animation.setDuration(400)
        self.width_animation.setEasingCurve(QEasingCurve.OutCubic)

        # 淡出动画
        self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_animation.setDuration(450)
        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.setEasingCurve(QEasingCurve.OutQuad)

        self.animation_group.addAnimation(self.width_animation)
        self.animation_group.addAnimation(self.fade_animation)

    def start_loop_animation(self):
        """开始循环动画"""
        if self._is_animating:
            return
            
        self._is_animating = True
        
        # 重置覆盖层状态
        self.highlight_overlay.setGeometry(0, 0, 0, self.height())
        self.opacity_effect.setOpacity(1.0)
        self.highlight_overlay.show()
        self.highlight_overlay.raise_()

        # 设置动画参数
        end_width = self.width()
        self.width_animation.setStartValue(QRect(0, 0, 0, self.height()))
        self.width_animation.setEndValue(QRect(0, 0, end_width, self.height()))
        
        self.animation_group.start()

    def stop_animation(self):
        """停止动画"""
        if not self._is_animating:
            return
            
        self._is_animating = False
        self.animation_group.stop()
        self.highlight_overlay.hide()
        self.opacity_effect.setOpacity(1.0)

    def set_highlight_color(self, color):
        """设置高光颜色"""
        if isinstance(color, QColor):
            style = f"background-color: rgba({color.red()}, {color.green()}, {color.blue()}, {color.alpha()});"
            self.highlight_overlay.setStyleSheet(style)
        elif isinstance(color, str):
            self.highlight_overlay.setStyleSheet(f"background-color: {color};")

    def is_animating(self):
        """返回当前是否在动画中"""
        return self._is_animating

class MainStoryCreater(QObject):
    """
    主线剧情创建类，负责与AI交互生成主线剧情节点
    """
    request_completed = pyqtSignal(list)  # 请求完成信号
    error_occurred = pyqtSignal(str)  # 错误发生信号

    def __init__(self, api_config: Dict[str, str], parent=None):
        super().__init__(parent)
        self.api_config = api_config
        self.request_handler = APIRequestHandler(api_config)
        self.request_handler.error_occurred.connect(self.error_occurred.emit)
        self.request_handler.request_completed.connect(self.handle_request_completed)


    def create_story_message(self, prompt: str,pervious_result= None):
        """创建主线剧情节点"""
        system_prompt = '''
你是一个剧情创作专家，擅长生成复杂的故事情节。请根据以下提示生成一个完整的剧情。确保剧情连贯且富有创意。
你创建的剧情将被用于角色扮演，因此剧情需要有一个详尽的世界观细节。
核心角色数量为两个，其中一个为用户，可以有配角，提供名字，第三人称视角，非对话。
你需要将主角的各个决定和策略留给用户，将用户的行动具体行动留白，但不创建分支节点。
节点之间要有留白，供用户发挥。可以使用只有起因没有结果的形式。
生成的node数量越多越好，但要严格按照用户提供的格式。
输出时不需要解释思路。
'''
        user_prompt =r'''按照以下json格式生成剧情：\n
```json
[{"node_id": "01",
"content": "剧情内容"},
{"node_id": "02",
"content": "剧情内容"},
...
{"node_id": "n",
"content": "剧情内容"}]
```
'''
        if pervious_result:
            user_prompt += f"结合之前的结果：{pervious_result},请根据要求“{prompt}”,生成剧情。"
        else:
            user_prompt += f"请根据这个要求生成剧情{prompt}"
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        return messages
    
    def send_request(self, prompt: str, model: str, pervious_result: Optional[str] = None):
        message = self.create_story_message(prompt, pervious_result)
        self.request_handler.send_request(message, model)

    def handle_request_completed(self, response: str) -> Optional[Dict[str, Any]]:
        """
        尝试从响应中提取JSON对象
        :param response: 响应字符串
        :return: JSON对象或None
        """

        try:
            from jsonfinder import jsonfinder
            for _, __, obj in jsonfinder(response, json_only=True):
                if isinstance(obj, list):  # 确保我们提取到的是JSON数组
                    self.request_completed.emit(obj)
        except json.JSONDecodeError:
            print("无法解析JSON:", response)
            self.request_completed.emit(['failed to parse json'])

class Analysier(QObject):
    """
    剧情分析器，负责分析剧情节点并生成更新请求
    """
    request_completed = pyqtSignal(str)  # 请求完成信号
    error_occurred = pyqtSignal(str)  # 错误发生信号

    def __init__(self, api_config: Dict[str, str], parent=None):
        super().__init__(parent)
        self.api_config = api_config
        self.request_handler = APIRequestHandler(api_config)
        self.request_handler.error_occurred.connect(self.error_occurred.emit)
        self.request_handler.request_completed.connect(self.handle_request_completed)

    
    def format_history(self, current_chathisory:list, length: int) -> str:
        """格式化对话历史"""
        if not current_chathisory:
            return ""
        temp_history = []
        total_length = 0
        # 截取最近的对话，总长度为lenth
        for i in reversed(current_chathisory):
            total_length += len(i['content'])
            temp_history.append(i)
            if total_length > length:
                break
        # 反转回原来的顺序
        temp_history.reverse()
        # 格式化为字符串
        formatted_history = "\n".join(
            f"{item['role']}:\n {item['content']}" for item in temp_history
        )
        return formatted_history

    def analyse_story_message(self, story_nodes: str,current_chathisory, length: int):
        """创建剧情分析请求消息"""
        system_prompt = '''
你是一个剧情节点分析专家，负责分析剧情内容并生成更新请求。
你会分析剧情内容，并返回一个JSON对象，包含以下字段：
{"node_id": "当前节点的ID"}

'''
        sort_history = self.format_history(current_chathisory, length)
        user_prompt = f'''
对话信息：
"""
{sort_history}
"""
节点信息：
"""
{story_nodes}
"""'''+'''
根据提供的信息分析对话属于哪个剧情节点:
将结果返回为一个JSON对象，包含以下字段：
{"node_id": "当前节点的ID"}
'''
        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]
        return messages
    def send_request(self, model, story_nodes: str,current_chathisory, length: int):
        self.story_nodes = story_nodes
        message = self.analyse_story_message(story_nodes, current_chathisory, length)
        self.request_handler.send_request(message, model)
    
    def handle_request_completed(self, response: str) -> Optional[Dict[str, Any]]:
        """
        尝试从响应中提取JSON对象
        :param response: 响应字符串
        :return: JSON对象或None
        """
        try:
            from jsonfinder import jsonfinder
            for _, __, obj in jsonfinder(response, json_only=True):
                if isinstance(obj, dict):  # 确保我们提取到的是JSON对象
                    self.format_returned_node_to_external(obj)
        except json.JSONDecodeError:
            print("无法解析JSON:", response)
            self.error_occurred.emit(f"API请求错误: 无法解析JSON: {response}")
            return None

    def format_returned_node_to_external(self, node):
        """
        格式化返回的节点字符串
        :param node: 返回的节点ID
        :return: 格式化后的字符串
        """
        if not node:
            return None
        for i in range(len(self.story_nodes)):
            if self.story_nodes[i]['node_id'] == node['node_id']:
                result=f'''{"上一主线节点："+self.story_nodes[i-1]['content'] if i > 0 else ""}
当前主线节点: {self.story_nodes[i]['content']}
{"下一主线节点："+self.story_nodes[i+1]['content'] if i < len(self.story_nodes)-1 else ""}'''
        self.request_completed.emit(result)
        return result
        
class Ui_story_manager(QWidget):
    def setupUi(self, story_manager):
        story_manager.setObjectName("story_manager")
        story_manager.resize(847, 514)
        self.gridLayout_7 = QGridLayout(story_manager)
        self.gridLayout_7.setObjectName("gridLayout_7")
        self.gridLayout_2 = QGridLayout()
        self.gridLayout_2.setObjectName("gridLayout_2")
        self.label = QLabel(story_manager)
        self.label.setObjectName("label")
        self.gridLayout_2.addWidget(self.label, 0, 0, 1, 1)
        self.gridLayout = QGridLayout()
        self.gridLayout.setObjectName("gridLayout")
        self.import_story_json = QPushButton(story_manager)
        self.import_story_json.setObjectName("import_story_json")
        self.gridLayout.addWidget(self.import_story_json, 0, 1, 1, 1)
        self.export_story_json = QPushButton(story_manager)
        self.export_story_json.setObjectName("export_story_json")
        self.gridLayout.addWidget(self.export_story_json, 0, 2, 1, 1)
        self.gridLayout_2.addLayout(self.gridLayout, 2, 0, 1, 1)
        self.story_treeview = QTreeWidget(story_manager)
        self.story_treeview.setObjectName("story_treeview")
        self.story_treeview.headerItem().setText(0, "1")
        self.gridLayout_2.addWidget(self.story_treeview, 1, 0, 1, 1)
        self.gridLayout_7.addLayout(self.gridLayout_2, 0, 0, 4, 1)
        self.groupBox_4 = QGroupBox(story_manager)
        self.groupBox_4.setObjectName("groupBox_4")
        self.gridLayout_6 = QGridLayout(self.groupBox_4)
        self.gridLayout_6.setObjectName("gridLayout_6")
        self.ai_create_story = AnimatedPushButton('',self.groupBox_4)
        self.ai_create_story.setObjectName("ai_create_story")
        self.gridLayout_6.addWidget(self.ai_create_story, 5, 1, 1, 1)
        self.request_modify = AnimatedPushButton('',self.groupBox_4)
        self.request_modify.setObjectName("request_modify")
        self.gridLayout_6.addWidget(self.request_modify, 5, 0, 1, 1)
        self.respond_json = QTextEdit(self.groupBox_4)
        self.respond_json.setObjectName("respond_json")
        self.gridLayout_6.addWidget(self.respond_json, 1, 0, 1, 2)
        self.preview = QPushButton(self.groupBox_4)
        self.preview.setObjectName("preview")
        self.gridLayout_6.addWidget(self.preview, 2, 0, 1, 2)
        self.label_10 = QLabel(self.groupBox_4)
        self.label_10.setObjectName("label_10")
        self.gridLayout_6.addWidget(self.label_10, 3, 0, 1, 2)
        self.user_input = QLineEdit(self.groupBox_4)
        self.user_input.setObjectName("user_input")
        self.gridLayout_6.addWidget(self.user_input, 4, 0, 1, 2)
        self.label_11 = QLabel(self.groupBox_4)
        self.label_11.setObjectName("label_11")
        self.gridLayout_6.addWidget(self.label_11, 0, 0, 1, 2)
        self.gridLayout_7.addWidget(self.groupBox_4, 0, 1, 4, 1)
        self.groupBox = QGroupBox(story_manager)
        self.groupBox.setObjectName("groupBox")
        self.gridLayout_3 = QGridLayout(self.groupBox)
        self.gridLayout_3.setObjectName("gridLayout_3")
        self.label_2 = QLabel(self.groupBox)
        self.label_2.setObjectName("label_2")
        self.gridLayout_3.addWidget(self.label_2, 0, 0, 1, 1)
        self.label_4 = QLabel(self.groupBox)
        self.label_4.setObjectName("label_4")
        self.gridLayout_3.addWidget(self.label_4, 1, 0, 1, 1)
        self.story_create_api_provider = QComboBox(self.groupBox)
        self.story_create_api_provider.setObjectName("story_create_api_provider")
        self.gridLayout_3.addWidget(self.story_create_api_provider, 1, 1, 1, 1)
        self.label_5 = QLabel(self.groupBox)
        self.label_5.setObjectName("label_5")
        self.gridLayout_3.addWidget(self.label_5, 2, 0, 1, 1)
        self.story_create_model = QComboBox(self.groupBox)
        self.story_create_model.setObjectName("story_create_model")
        self.gridLayout_3.addWidget(self.story_create_model, 2, 1, 1, 1)
        self.gridLayout_7.addWidget(self.groupBox, 0, 2, 1, 2)
        self.groupBox_2 = QGroupBox(story_manager)
        self.groupBox_2.setObjectName("groupBox_2")
        self.gridLayout_4 = QGridLayout(self.groupBox_2)
        self.gridLayout_4.setObjectName("gridLayout_4")
        self.label_8 = QLabel(self.groupBox_2)
        self.label_8.setObjectName("label_8")
        self.gridLayout_4.addWidget(self.label_8, 3, 0, 1, 1)
        self.story_update_model = QComboBox(self.groupBox_2)
        self.story_update_model.setObjectName("story_update_model")
        self.gridLayout_4.addWidget(self.story_update_model, 2, 1, 1, 1)
        self.story_update_api_provider = QComboBox(self.groupBox_2)
        self.story_update_api_provider.setObjectName("story_update_api_provider")
        self.gridLayout_4.addWidget(self.story_update_api_provider, 1, 1, 1, 1)
        self.label_7 = QLabel(self.groupBox_2)
        self.label_7.setObjectName("label_7")
        self.gridLayout_4.addWidget(self.label_7, 2, 0, 1, 1)
        self.label_6 = QLabel(self.groupBox_2)
        self.label_6.setObjectName("label_6")
        self.gridLayout_4.addWidget(self.label_6, 1, 0, 1, 1)
        self.label_3 = QLabel(self.groupBox_2)
        self.label_3.setObjectName("label_3")
        self.gridLayout_4.addWidget(self.label_3, 0, 0, 1, 1)
        self.story_update_story_lenth = QSpinBox(self.groupBox_2)
        self.story_update_story_lenth.setMaximum(99999)
        self.story_update_story_lenth.setProperty("value", 300)
        self.story_update_story_lenth.setObjectName("story_update_story_lenth")
        self.gridLayout_4.addWidget(self.story_update_story_lenth, 3, 1, 1, 1)
        self.label_12 = QLabel(self.groupBox_2)
        self.label_12.setObjectName("label_12")
        self.gridLayout_4.addWidget(self.label_12, 4, 0, 1, 1)
        self.update_rounds = QSpinBox(self.groupBox_2)
        self.update_rounds.setObjectName("update_rounds")
        self.update_rounds.setProperty("value", 5)
        self.gridLayout_4.addWidget(self.update_rounds, 4, 1, 1, 1)
        self.gridLayout_7.addWidget(self.groupBox_2, 1, 2, 1, 2)
        self.groupBox_3 = QGroupBox(story_manager)
        self.groupBox_3.setChecked(False)
        self.groupBox_3.setObjectName("groupBox_3")
        self.gridLayout_5 = QGridLayout(self.groupBox_3)
        self.gridLayout_5.setObjectName("gridLayout_5")
        self.story_hint_current = QRadioButton(self.groupBox_3)
        self.story_hint_current.setChecked(False)
        self.story_hint_current.setObjectName("story_hint_current")
        self.gridLayout_5.addWidget(self.story_hint_current, 0, 0, 1, 1)
        self.story_hint_system = QRadioButton(self.groupBox_3)
        self.story_hint_system.setChecked(True)
        self.story_hint_system.setObjectName("story_hint_system")
        self.gridLayout_5.addWidget(self.story_hint_system, 1, 0, 1, 1)
        self.story_hint_status_manager = QRadioButton(self.groupBox_3)
        self.story_hint_status_manager.setObjectName("story_hint_status_manager")
        self.gridLayout_5.addWidget(self.story_hint_status_manager, 2, 0, 1, 1)
        self.story_hint_var_text = QLineEdit(self.groupBox_3)
        self.story_hint_var_text.setObjectName("story_hint_var_text")
        self.gridLayout_5.addWidget(self.story_hint_var_text, 2, 1, 1, 1)
        self.gridLayout_7.addWidget(self.groupBox_3, 2, 2, 1, 2)
        self.label_9 = QLabel(story_manager)
        self.label_9.setText("")
        self.label_9.setObjectName("label_9")
        self.gridLayout_7.addWidget(self.label_9, 3, 2, 1, 1)
        self.debug_update_models = QPushButton(story_manager)
        self.debug_update_models.setObjectName("debug_update_models")
        self.gridLayout_7.addWidget(self.debug_update_models, 3, 3, 1, 1)

        self.retranslateUi(story_manager)
        QMetaObject.connectSlotsByName(story_manager)

    def retranslateUi(self, story_manager):
        _translate = QCoreApplication.translate
        story_manager.setWindowTitle(_translate("story_manager", "剧情管理"))
        self.label.setText(_translate("story_manager", "当前主线"))
        self.import_story_json.setText(_translate("story_manager", "导入"))
        self.export_story_json.setText(_translate("story_manager", "导出"))
        self.groupBox_4.setTitle(_translate("story_manager", "主线创建"))
        self.ai_create_story.setText(_translate("story_manager", "创建主线"))
        self.request_modify.setText(_translate("story_manager", "要求修改"))
        self.preview.setText(_translate("story_manager", "导入左侧预览"))
        self.label_10.setText(_translate("story_manager", "创建要求"))
        self.label_11.setText(_translate("story_manager", "AI JSON响应"))
        self.groupBox.setTitle(_translate("story_manager", "主线创建设置"))
        self.label_2.setText(_translate("story_manager", "指定AI：主线创建"))
        self.label_4.setText(_translate("story_manager", "提供商"))
        self.label_5.setText(_translate("story_manager", "模型"))
        self.groupBox_2.setTitle(_translate("story_manager", "主线节点设置"))
        self.label_8.setText(_translate("story_manager", "参考对话长度"))
        self.label_7.setText(_translate("story_manager", "模型"))
        self.label_6.setText(_translate("story_manager", "提供商"))
        self.label_3.setText(_translate("story_manager", "指定AI：主线节点更新"))
        self.story_update_story_lenth.setSuffix(_translate("story_manager", "字"))
        self.label_12.setText(_translate("story_manager", "更新周期"))
        self.update_rounds.setSuffix(_translate("story_manager", "次对话"))
        self.groupBox_3.setTitle(_translate("story_manager", "挂载位置"))
        self.story_hint_current.setText(_translate("story_manager", "当前对话"))
        self.story_hint_system.setText(_translate("story_manager", "system prompt"))
        self.story_hint_status_manager.setText(_translate("story_manager", "状态栏(mod)          "))
        self.story_hint_var_text.setText(_translate("story_manager", "主线节点"))
        self.debug_update_models.setText(_translate("story_manager", "debug:更新模型列表"))

class StoryManagerBackend(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # 初始化UI
        self.ui = Ui_story_manager()
        self.ui.setupUi(self)  # 将UI设置到当前窗口实例
        
        self.default_apis = StoryCreatorGlobalVar.DEFAULT_APIS
        self.model_map = StoryCreatorGlobalVar.MODEL_MAP
        self.current_config = {
            "create_provider": "baidu",
            "create_model": "",
            "update_provider": "baidu",
            "update_model": "",
            "analysis_length": 2000,
            "status_field": "story_node"
        }
        self.ui.gridLayout_7.setColumnStretch(0, 1)  # 第一列拉伸因子为1
        self.ui.gridLayout_7.setColumnStretch(1, 1)  # 第二列拉伸因子为1
        self.ui.gridLayout_7.setColumnStretch(2, 0)  # 第三列拉伸因子为0（不拉伸）
        self.ui.gridLayout_7.setColumnStretch(3, 0)  # 第四列拉伸因子为0（不拉伸

        #内部数据
        self.income_round = 0  # 当前对话轮数
        self.last_node_analysis=''
        self.auto_save_path = "auto_save_story.json"

        # 初始化组件
        self._init_providers()
        self._connect_signals()
        self._load_default_models()
        self._load_settings()

    def _init_providers(self):
        """初始化API提供商下拉框"""
        providers = list(self.model_map.keys())
        for combo in [self.ui.story_create_api_provider, self.ui.story_update_api_provider]:
            combo.addItems(providers)
            combo.setCurrentIndex(providers.index("baidu"))

    def _load_default_models(self):
        """加载默认模型到下拉框"""
        self._update_model_combo(
            provider=self.current_config["create_provider"],
            combo=self.ui.story_create_model,
            default_model="deepseek-chat"
        )
        self._update_model_combo(
            provider=self.current_config["update_provider"],
            combo=self.ui.story_update_model,
            default_model="qwen3-4b"
        )

    def _update_model_combo(self, provider: str, combo: QComboBox, default_model: str):
        """更新模型下拉框选项"""
        combo.clear()
        models = self.model_map.get(provider, [])
        if not models:
            models = ["default_model"]  # 回退方案
        combo.addItems(models)
        try:
            combo.setCurrentText(default_model)
        except:
            combo.setCurrentIndex(0)

    def _connect_signals(self):
        """连接UI信号与槽函数"""
        # API提供商选择变化
        self.ui.story_create_api_provider.currentIndexChanged.connect(self._on_create_provider_changed)
        self.ui.story_update_api_provider.currentIndexChanged.connect(self._on_update_provider_changed)
        
        # 模型更新按钮
        self.ui.debug_update_models.clicked.connect(self._update_models)
        
        # 导入/导出按钮
        self.ui.import_story_json.clicked.connect(self._import_story)
        self.ui.export_story_json.clicked.connect(self._export_story)
        self.ui.preview.clicked.connect(
    lambda: self.update_story_treeview(json.loads(self.ui.respond_json.toPlainText()))
)

        #创建剧情按钮
        self.ui.ai_create_story.clicked.connect(self.create_story_node)
        self.ui.request_modify.clicked.connect(self.modify_story_node)

    def _on_create_provider_changed(self, index: int):
        """处理提供商选择变化"""
        provider = self.ui.story_create_api_provider.currentText()
        self._update_model_combo(provider, self.ui.story_create_model, "deepseek-reasoner")
        self.current_config["create_provider"] = provider
    def _on_update_provider_changed(self, index: int):
        provider = self.ui.story_update_api_provider.currentText()
        self._update_model_combo(provider, self.ui.story_update_model, "qwen3-4b")
        self.current_config["update_provider"] = provider

    def _update_models(self):
        """调试：强制刷新模型列表"""
        self._load_default_models()

    def get_api_config(self, provider: str) -> Dict[str, str]:
        """获取指定提供商的API配置"""
        return {
            "url": self.default_apis[provider]["url"],
            "key": self.default_apis[provider]["key"]
        }

    def set_analysis_length(self, length: int):
        """设置分析长度"""
        self.current_config["analysis_length"] = length
        self.ui.story_update_story_lenth.setValue(length)

    def get_current_config(self) -> Dict[str, Any]:
        """获取当前配置快照"""
        return {
            "create": {
                "provider": self.current_config["create_provider"],
                "model": self.ui.story_create_model.currentText()
            },
            "update": {
                "provider": self.current_config["update_provider"],
                "model": self.ui.story_update_model.currentText()
            },
            "analysis_length": self.current_config["analysis_length"],
            "status_field": self.current_config["status_field"]
        }

    def _import_story(self):
        """导入剧情文件"""
        path, _ = QFileDialog.getOpenFileName(None, "导入剧情", "", "JSON Files (*.json)")
        if path:
            try:
                with open(path, "r", encoding="utf-8") as f:
                    data = json.load(f)
                # 这里应添加数据验证逻辑
                self._load_story_data(data)
            except Exception as e:
                self._show_error(f"导入失败: {str(e)}")

    def _export_story(self):
        """导出剧情文件"""
        path, _ = QFileDialog.getSaveFileName(None, "导出剧情", "", "JSON Files (*.json)")
        if path:
            try:
                story_data = self._collect_story_data()
                with open(path, "w", encoding="utf-8") as f:
                    json.dump(story_data, f, ensure_ascii=False, indent=2)
            except Exception as e:
                self._show_error(f"导出失败: {str(e)}")

    def _load_story_data(self, data):
        """加载剧情数据到界面"""
        self.ui.story_treeview.clear()
        self.ui.respond_json.setText(json.dumps(data, ensure_ascii=False, indent=2))
        self.update_story_treeview(data)  # 更新树视图
        pass

    def _collect_story_data(self) -> Dict:
        """从界面收集剧情数据"""
        from jsonfinder import jsonfinder
        for _, __, obj in jsonfinder(self.ui.respond_json.toPlainText(), json_only=True):
            if isinstance(obj, list):  # 确保我们提取到的是JSON数组
                return obj
 

    def _show_error(self, message: str):
        """显示错误信息"""
        self.ui.ai_create_story.setEnabled(True)
        self.ui.ai_create_story.stop_animation()
        self.ui.request_modify.setEnabled(True)
        self.ui.request_modify.stop_animation()
        QMessageBox.critical(None, "错误", message)

    def get_status_output(self) -> Dict[str, str]:
        """获取要发送到状态监视器的数据"""
        return {
            self.current_config["status_field"]: self._get_current_story_description()
        }

    def _get_current_story_description(self) -> str:
        """获取当前剧情描述（需根据实际数据结构实现）"""
        return "示例剧情描述"

    def create_story_node(self):
        """调用创建类生成剧情节点"""
        api_config = self.get_api_config(self.ui.story_create_api_provider.currentText())
        model = self.ui.story_create_model.currentText()
        prompt = self.ui.user_input.text()
        self.creator= MainStoryCreater(api_config)
        self.creator.request_completed.connect(self.update_story_treeview)  # 更新UI
        self.creator.error_occurred.connect(self._show_error)
        self.creator.send_request(prompt, model)
        self.ui.ai_create_story.setEnabled(False)
        self.ui.request_modify.setEnabled(False)
        pass

    def modify_story_node(self):
        """调用创建类生成剧情节点"""
        api_config = self.get_api_config(self.ui.story_create_api_provider.currentText())
        model = self.ui.story_create_model.currentText()
        prompt = self.ui.user_input.text()
        pervious_result = self.ui.respond_json.toPlainText()
        self.creator= MainStoryCreater(api_config)
        self.creator.request_completed.connect(self.update_story_treeview)  # 更新UI
        self.creator.error_occurred.connect(self._show_error)
        self.creator.send_request(prompt, model,pervious_result= pervious_result)
        self.ui.ai_create_story.setEnabled(False)
        self.ui.request_modify.setEnabled(False)
        pass

    def update_story_treeview(self, story_nodes: list):
        """更新剧情树视图"""
        # 获取story_treeview控件
        tree = self.ui.story_treeview
        
        # 清除现有内容
        tree.clear()
        
        # 设置树形视图的列数和标题
        tree.setColumnCount(2)
        tree.setHeaderLabels(["节点ID", "故事内容"])
        
        # 自动调整列宽
        tree.header().setSectionResizeMode(0, QHeaderView.ResizeToContents)  # ID列自适应
        tree.header().setSectionResizeMode(1, QHeaderView.Stretch)  # 内容列自动拉伸
        
        # 创建顶级节点
        root_item = QTreeWidgetItem(tree, ["故事主线", "完整故事节点结构"])
        root_item.setExpanded(True)  # 默认展开根节点
        root_item.setFont(0, QFont("Arial", 10, QFont.Bold))
        
        # 填充数据
        for node in story_nodes:
            # 创建节点
            item = QTreeWidgetItem(root_item)
            item.setText(0, node['node_id'])
            item.setText(1, node['content'])
            
            # 设置节点属性
            item.setExpanded(False)  # 默认收起所有子节点
            item.setToolTip(0, f"节点ID: {node['node_id']}")
            item.setToolTip(1, node['content'])
            
            # 添加展开/收起指示器（小三角形）
            item.setChildIndicatorPolicy(QTreeWidgetItem.ShowIndicator)
        self.ui.respond_json.setText(json.dumps(story_nodes, ensure_ascii=False, indent=2))
        self.ui.ai_create_story.setEnabled(True)
        self.ui.ai_create_story.stop_animation()
        self.ui.request_modify.setEnabled(True)
        self.ui.request_modify.stop_animation()
    
    def analyze_story_progress(self, chat_history: Dict,nodes=None):
        """调用分析类分析剧情进度"""
        if type(chat_history) is not dict:
            json.dumps(nodes, ensure_ascii=False)
        if not nodes:
            from jsonfinder import jsonfinder
            for _, __, obj in jsonfinder(self.ui.respond_json.toPlainText(), json_only=True):
                if isinstance(obj, list):  # 确保我们提取到的是JSON数组
                    nodes=obj
        if not nodes:
            print("nodes???")
            return False
        if self.income_round % int(self.ui.update_rounds.value()) == 0:
            api_config = self.get_api_config(self.ui.story_update_api_provider.currentText())
            model = self.ui.story_update_model.currentText()
            length = self.ui.story_update_story_lenth.value()
            self.analysier = Analysier(api_config)
            self.analysier.request_completed.connect(self.update_last_node_analysis)
            self.analysier.send_request(model, nodes, chat_history, length)
            return True
        return False
    
    def update_last_node_analysis(self,text):
        self.last_node_analysis=text


    def refine_story_node(self, node_id: str, refinement: str):
        """调用整理类细化剧情节点"""
        pass

    def save_settings(self):
        """保存当前配置到 INI 文件"""
        if not os.path.exists("config.ini"):
            with open("config.ini", 'w') as f:
                print('created')
                pass  # 创建空文件
        settings = QSettings("config.ini", QSettings.IniFormat)
        
        # 保存主线创建设置
        settings.setValue("create_provider", self.ui.story_create_api_provider.currentText())
        settings.setValue("create_model", self.ui.story_create_model.currentText())
        
        # 保存主线节点设置
        settings.setValue("update_provider", self.ui.story_update_api_provider.currentText())
        settings.setValue("update_model", self.ui.story_update_model.currentText())
        settings.setValue("analysis_length", self.ui.story_update_story_lenth.value())
        settings.setValue("update_rounds", self.ui.update_rounds.value())
        
        # 保存挂载位置设置
        if self.ui.story_hint_current.isChecked():
            mount_position = "current"
        elif self.ui.story_hint_system.isChecked():
            mount_position = "system"
        else:
            mount_position = "status"
        settings.setValue("mount_position", mount_position)
        settings.setValue("status_var", self.ui.story_hint_var_text.text())
        
        # 保存用户输入和响应（可选）
        settings.setValue("user_input", self.ui.user_input.text())
        settings.setValue("respond_json", self.ui.respond_json.toPlainText())
        
        # 保存当前剧情树数据
        tree_data = self._collect_story_data()
        if tree_data:
            settings.setValue("story_data", json.dumps(tree_data))
    
    def _load_settings(self):
        """从 INI 文件加载配置"""
        settings = QSettings("config.ini", QSettings.IniFormat)
        
        # 加载主线创建设置
        provider = settings.value("create_provider", "baidu", type=str)
        if provider in self.model_map:
            self.ui.story_create_api_provider.setCurrentText(provider)
            self._on_create_provider_changed(self.ui.story_create_api_provider.currentIndex())
        
        model = settings.value("create_model", "", type=str)
        if model and self.ui.story_create_model.findText(model) >= 0:
            self.ui.story_create_model.setCurrentText(model)
        
        # 加载主线节点设置
        provider = settings.value("update_provider", "baidu", type=str)
        if provider in self.model_map:
            self.ui.story_update_api_provider.setCurrentText(provider)
            self._on_update_provider_changed(self.ui.story_update_api_provider.currentIndex())
        
        model = settings.value("update_model", "", type=str)
        if model and self.ui.story_update_model.findText(model) >= 0:
            self.ui.story_update_model.setCurrentText(model)
        
        self.ui.story_update_story_lenth.setValue(settings.value("analysis_length", 300, type=int))
        self.ui.update_rounds.setValue(settings.value("update_rounds", 5, type=int))
        
        # 加载挂载位置设置
        mount_position = settings.value("mount_position", "system", type=str)
        if mount_position == "current":
            self.ui.story_hint_current.setChecked(True)
        elif mount_position == "status":
            self.ui.story_hint_status_manager.setChecked(True)
        else:  # 默认
            self.ui.story_hint_system.setChecked(True)
        self.ui.story_hint_var_text.setText(settings.value("status_var", "主线节点", type=str))
        
        # 加载用户输入和响应
        self.ui.user_input.setText(settings.value("user_input", "", type=str))
        self.ui.respond_json.setPlainText(settings.value("respond_json", "", type=str))
        
        # 加载剧情树数据
        story_data = settings.value("story_data", "")
        if story_data:
            try:
                data = json.loads(story_data)
                self._load_story_data(data)
            except json.JSONDecodeError:
                pass

    def closeEvent(self, event):
        self.save_settings()
        event.accept()

class MainStoryCreaterInstruction:
    def mod_main_function():
        window =StoryManagerBackend()
        return {"ui":window,"name":"status_monitor_window"}
    def mod_configer():
        window =StoryManagerBackend()
        return window

if __name__ == "__main__":
    
    test_nodes=[{"node_id": "01",
"content": "飞机失事迫降原始森林，你和野外专家是仅有的幸存者。必须决定留在原地或进入森林。"},
{"node_id": "02",
"content": "在残骸中找到急救包、食物和信号枪。远处传来野兽嚎叫，需决定是否发射信号。"},
{"node_id": "03",
"content": "森林突然起雾，指南针失灵。专家发现地面有奇怪的爪印，暗示这不是普通森林。"},
{"node_id": "04",
"content": "你们发现被藤蔓覆盖的石碑，刻着未知文字。专家认出这是某个失落文明的警告符号。"},
{"node_id": "05",
"content": "夜幕降临，周围出现发光的眼睛。搭建的临时庇护所外传来抓挠声，必须决定守夜或立即转移。"},
{"node_id": "06",
"content": "次日发现一条人工开凿的小径，尽头是锈蚀的铁门。门缝里渗出冷风，伴有机械运转的嗡嗡声。"},
{"node_id": "07",
"content": "铁门后是废弃实验室，文件显示这里进行过生物实验。突然所有出口自动封锁，通风口排出绿色气体。"},
{"node_id": "08",
"content": "在控制室找到残缺地图，显示森林中央有发射塔。但启动电源会唤醒所有休眠中的实验体。"},
{"node_id": "09",
"content": "专家被变异藤蔓缠住，求你独自逃生。最后看到他把信号枪对准了燃料罐。"},
{"node_id": "10",
"content": "爆炸声后，你在浓烟中看到救援直升机。但驾驶员戴着和实验室里同样的标志..."}]

    test_chathistory = [
    {"role": "user", "content": "我们坠机了，怎么办？"},
    {"role": "assistant", "content": "我们需要先评估周围环境，寻找幸存者和资源。"},
    {"role": "user", "content": "我看到残骸附近有急救包和食物，我们应该先去拿吗？"},
    {"role": "assistant", "content": "是的，急救包和食物是首要任务。我们还需要决定是否发射信号求救。"},
    {"role": "user", "content": "我发射了信号，但远处传来野兽嚎叫，我们该怎么办？"},
    {"role": "assistant", "content": "我们需要保持警惕，可能需要搭建临时庇护所。"},
    {"role": "user", "content": "森林起雾了，指南针失灵了。我们该如何判断方向？"},
    {"role": "assistant", "content": "我们可以观察地形和太阳位置来判断方向，但要小心周围的爪印。"},
    {"role": "user", "content": "我们发现了一个被藤蔓覆盖的石碑，上面有奇怪的文字。"},
    {"role": "assistant", "content": "这可能是某个失落文明的警告符号，我们需要小心行事。"},
    {"role": "user", "content": "夜晚来了，周围有发光的眼睛，我们该怎么办？"},
    {"role": "assistant", "content": "我们需要守夜，保持警惕，确保安全。"},
    {"role": "user", "content": "次日我们发现了一条小径，通向锈蚀的铁门。"},
    {"role": "assistant", "content": "这可能是通往某个重要地点的线索，但要小心门缝里渗出的冷风。"},
    {"role": "user", "content": "铁门后是废弃实验室，文件显示这里进行过生物实验。"},
    {"role": "assistant", "content": "我们需要尽快找到出口，这里可能不安全。"},
    {"role": "user", "content": "控制室里有残缺地图，显示森林中央有发射塔，但启动电源会唤醒实验体。"},
    {"role": "assistant", "content": "我们需要权衡风险，是否启动电源。"},
    {"role": "user", "content": "专家被藤蔓缠住了，他让我独自逃生。"},
    {"role": "assistant", "content": "你必须逃生，但要记住专家的牺牲。"}]

    app = QApplication(sys.argv)
    
    window=MainStoryCreaterInstruction.mod_configer()
 
    # 显示窗口
    window.show()
    sys.exit(app.exec_())
