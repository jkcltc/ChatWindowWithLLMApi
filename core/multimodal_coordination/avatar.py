
from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
import os,json
from jsonfinder import jsonfinder
import copy
import time


from service.chat_completion import APIRequestHandler
from core.session.chat_history_manager import ChatHistoryTools
from service.text_to_image import ImageAgent



class ImageProcessor:
    """图像处理工具类"""
    @staticmethod
    def crop_and_scale(image_path, target_size=(256, 256), selection_rect=QRect()):
        """
        裁切并缩放图像：
        1. 载入图像
        2. 裁切为正方形（保留中心或用户选择的区域）
        3. 缩放至目标尺寸
        
        参数:
            image_path: 图像文件路径
            target_size: 目标尺寸
            selection_rect: 用户选择的裁剪区域 (QRect)，若为空则使用中心正方形裁切
        """
        pixmap = QPixmap(image_path)
        if pixmap.isNull():
            return QPixmap()
        
        # 如果提供了有效的选择区域
        if selection_rect and selection_rect.isValid() and not selection_rect.isNull():
            # 获取用户选择的矩形区域
            rect = selection_rect
            # 计算选择区域的中心点
            center = rect.center()
            
            # 获取该区域的宽高中较大值作为边长
            if rect.width() > rect.height():
                size = rect.width()
            else:
                size = rect.height()
            
            # 计算以中心点为中心的正方形区域
            square_rect = QRect(
                center.x() - size // 2,
                center.y() - size // 2,
                size,
                size
            )
            
            # 确保正方形在图像边界内
            square_rect = square_rect.intersected(QRect(0, 0, pixmap.width(), pixmap.height()))
            
            # 裁切正方形区域
            cropped = pixmap.copy(square_rect)
        
        # 如果没有提供选择区域，使用中心裁切
        else:
            # 获取较短边尺寸
            size = min(pixmap.width(), pixmap.height())
            
            # 裁切为正方形
            cropped = pixmap.copy(
                (pixmap.width() - size) // 2,
                (pixmap.height() - size) // 2,
                size, size
            )
        
        # 缩放至目标尺寸
        return cropped.scaled(
            target_size[0], target_size[1],
            Qt.AspectRatioMode.IgnoreAspectRatio, Qt.TransformationMode.SmoothTransformation
        )

class AvatarCreatorText:
    # 窗口名
    WINDOW_TITLE= '自定义头像'
    # 模式选择
    MODE_COMBO = ["手动选择", "AI生成"]
    
    # 按钮文本
    BUTTON_SELECT_IMAGE = "选择图片"
    BUTTON_GENERATE_AVATAR = "生成头像"
    BUTTON_CONFIRM_USE = "确认使用"
    
    # 提示文本
    TOOLTIP_SELECT_IMAGE = "从本地文件系统选择一张头像图片"
    TOOLTIP_PROVIDER_COMBO = "选择预设供应商"
    PLACEHOLDER_STYLE_EDIT = "输入风格描述..."
    TOOLTIP_STYLE_EDIT = "描述您希望生成的风格，例如'卡通风格'或'像素风格'"
    TOOLTIP_GENERATE_BUTTON = "根据描述生成头像图片"
    STATUS_WAITING_REQUEST = "等待请求发送..."
    
    # 标签文本
    LABEL_CHARACTER_SOURCE = "形象生成自"
    LABEL_SUMMARY_PROVIDER='文生图提示词模型'
    LABEL_PROVIDER = "供应商"
    LABEL_MODEL = "模型"
    LABEL_STYLE = "指定风格"
    LABEL_ORIGINAL_PREVIEW = "原始图片"
    LABEL_RESULT_PREVIEW = "处理结果"
    LABEL_SETTINGS = "设置"
    LABEL_CREATE_MODE = "创建模式"
    LABEL_ROLE = "角色"
    LABEL_PREVIEW_AREA = "预览区域"
    LABEL_ORIGINAL_IMAGE = "原始图像"
    LABEL_PROCESSED_IMAGE = "处理后图像"
    LABEL_CUT_SETTING = '对话数：'
    
    # 复选框文本
    CHECKBOX_INCLUDE_SYSPROMPT = "携带系统提示"
    
    # 下拉选项
    SOURCE_OPTIONS = ["完整对话", "选择的对话"]

    #图像生成要求
    IMAGE_GENERATE_SYSTEM_PROMPT='''
# 角色
你是一个专业的头像提示词(Prompt)艺术家。

# 任务
将用户的输入转化为一个丰富、具体、高质量的图像生成提示词。

# 思考步骤
1.  核心概念: 识别用户的核心主体和风格 (例如：“宇航员”, “猫耳女孩”)。
2.  丰富细节: 为核心概念添加具体的视觉元素：
    人物: 发型、眼睛颜色、表情、配饰。
    服装: 风格、材质。
3.  设定画风与构图:
    画风: 动漫、写实、3D渲染、水彩等。
    构图: 头像特写 (headshot), 上半身肖像 (upper body portrait)。
4.  组合与优化:
    正面提示词 (prompt): 组合以上所有元素，用逗号分隔,以 "masterpiece, best quality" 结尾。
    负面提示词 (negative_prompt): 排除常见错误。

# 输出格式
严格按照以下JSON格式输出，不要添加任何解释。
{"prompt":"","negative_prompt":""}

---
# 示例
用户输入: "一个赛博朋克风格的女孩"

输出举例:
{"prompt":" headshot of a cyberpunk girl, pink short hair, glowing blue eyes, confident smile, wearing a black leather jacket with neon patterns, intricate details, cinematic lighting, night city background,masterpiece, best quality",
"negative_prompt":"low quality, worst quality, blurry, deformed, bad anatomy, watermark, text, ugly, extra limbs"}
'''
    IMAGE_GENERATE_USER_PROMPT='''
聊天历史：
{chathistory}

风格要求：
**{style}**

根据聊天历史和要求的风格，生成{charactor}的形象描述。

返回json：
{{"prompt":"","negative_prompt":""}}
'''
    IMAGE_GENERATE_STATUS_SUCCESS='图像生成完成'
    IMAGE_GENERATE_STATUS_FAILURE='图像生成失败，失败原因 '
    IMAGE_GENERATE_STATUS_PROMPT ='图像生成中...正在生成图像描述'
    IMAGE_GENERATE_STATUS_IMAGE  ='图像生成中...正在等待图像生成'

    IRAG_USE_CHINESE='在本次回复中，你需要使用中文填充"prompt"字段中的内容。'

class AvatarImageGenerator(QObject):
    status_update=pyqtSignal(str)
    pull_success=pyqtSignal(str)#img path
    failure=pyqtSignal(str,str)
    def __init__(self,generator='',application_path='',model=''):
        super().__init__()
        self.generator_name=generator
        self.generator=ImageAgent()
        self.generator.set_generator(generator)
        self.generator.pull_success.connect(self.pull_success.emit)
        self.generator.pull_success.connect(lambda  _:self.status_update.emit(AvatarCreatorText.IMAGE_GENERATE_STATUS_SUCCESS))
        self.model=model
    
    def prepare_message(self,
                      target,
                      chathistory_list,
                      style='简约头像',
                      charactors={'user':'user','assistant':'assistant'},
                      msg_id='',
                      use_system_prompt=True,
                      cut_lenth=10
                      ):
        '''
        param: target 用于指定生成目标
        '''
        chathistory_list=copy.deepcopy(chathistory_list)
        if target in charactors:
            target=charactors[target]
        if not use_system_prompt:
            chathistory_list=chathistory_list[1:]
        if msg_id:
            for item in chathistory_list:
                if item['info']['id']==msg_id:
                    chathistory=item['content']
                    break
            else:
                chathistory=ChatHistoryTools.to_readable_str(chathistory_list[-2:])
                self.failure.emit('prepare_message',f'no id found:{msg_id}')
        else:
            chathistory_list=chathistory_list[-cut_lenth:]
            chathistory=ChatHistoryTools.to_readable_str(chathistory=chathistory_list,
                                                         names=charactors)
        
        system_message=AvatarCreatorText.IMAGE_GENERATE_SYSTEM_PROMPT
        user_message=AvatarCreatorText.IMAGE_GENERATE_USER_PROMPT.format(
            chathistory=chathistory,
            style=style,
            charactor=target
        )
        if 'irag' in self.model:
            user_message+=AvatarCreatorText.IRAG_USE_CHINESE

        self.message=[{'role':'system','content':system_message},
                 {'role':'user','content':user_message}]
        return self.message
        
    def send_image_workflow_request(self,api_config,summary_model):
        '''
        api_config={
            "url": default_apis[self.api_provider]["url"],
            "key": default_apis[self.api_provider]["key"]
        }
        '''
        self.request_handler=APIRequestHandler(api_config=api_config)
        self.request_handler.request_completed.connect(self.image_request_sender)
        self.status_update.emit(AvatarCreatorText.IMAGE_GENERATE_STATUS_PROMPT)
        self.request_handler.send_request(message=self.message,model=summary_model)

        
    def image_request_sender(self,json_return):
        if not hasattr(self,'message'):
            self.failure.emit('AvartarImageGenerator','Not init yet')
        self.status_update.emit(AvatarCreatorText.IMAGE_GENERATE_STATUS_IMAGE)
        for _, __, obj in jsonfinder(json_return):
            if isinstance(obj, dict):  # 确保我们提取到的是JSON数组
                param=obj
        param['model']=self.model
        self.generator.create(params_dict=param)
