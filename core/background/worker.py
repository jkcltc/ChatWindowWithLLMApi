from __future__ import annotations

import threading
from typing import Optional
from jsonfinder import jsonfinder

from config import APP_SETTINGS, APP_RUNTIME
from core.session.chat_history_manager import ChatHistoryTools
from service.chat_completion import APIRequestHandler
from service.text_to_image import ImageAgent

from .signals import BackgroundSignalBus


class BackgroundWorker:
    """背景生成工作器（Qt-free）。"""

    def __init__(self) -> None:
        self.signals = BackgroundSignalBus()
        self.request_sender: Optional[APIRequestHandler] = None
        self.creator: Optional[ImageAgent] = None
        self._watchdog: Optional[threading.Timer] = None

    # ========== 配置属性，统一从 APP_SETTINGS 读 ==========

    @property
    def application_path(self):
        return APP_RUNTIME.paths.application_path

    @property
    def background_cfg(self):
        """背景配置快捷访问"""
        return APP_SETTINGS.background

    @property
    def summary_provider(self):
        return self.background_cfg.summary_provider

    @property
    def summary_model(self):
        return self.background_cfg.summary_model

    @property
    def image_provider(self):
        return self.background_cfg.image_provider

    @property
    def image_model(self):
        return self.background_cfg.image_model

    @property
    def background_style(self):
        return self.background_cfg.style

    @property
    def required_length(self):
        return self.background_cfg.max_length

    def _get_api_config(self, provider: str) -> tuple:
        """从全局设置获取 API 配置"""
        return APP_SETTINGS.api.endpoints.get(provider, ("", ""))

    # ========== API 请求器生命周期 ==========

    def _init_api_requester(self):
        """用当前配置初始化 API 请求器"""
        url, key = self._get_api_config(self.summary_provider)
        self.signals.log.emit(f"BGW init API requester: provider={self.summary_provider}")
        self.request_sender = APIRequestHandler(api_config={
            "url": url,
            "key": key
        })
        self.request_sender.set_provider(
            provider=self.summary_provider,
            model=self.summary_model
        )
        self.request_sender.request_completed.connect(self._handle_image_prompt_receive)
        self.request_sender.error_occurred.connect(self._on_request_error)

    def _finish_api_requester(self):
        if self.request_sender is not None:
            try:
                self.request_sender.request_completed.disconnect(self._handle_image_prompt_receive)
            except Exception as e:
                self.signals.warning.emit(f"BGW Warning: _finish_api_requester Failed: {e}")
            self.request_sender = None

    # ========== 图像生成器生命周期 ==========

    def _init_image_agent(self):
        """用当前配置初始化图像生成器"""
        self.creator = ImageAgent()
        self.creator.set_generator(self.image_provider)
        self.creator.failure.connect(self._on_image_failure)
        self.creator.pull_success.connect(self._on_image_success)

    def _finish_image_agent(self):
        if self.creator is not None:
            try:
                self.creator.pull_success.disconnect(self._on_image_success)
            except Exception as e:
                self.signals.warning.emit(f"BGW Warning: _finish_image_agent Failed: {e}")
            self.creator = None
        self._cancel_watchdog()

    # ========== 主流程 ==========

    def generate(self, chathistory: list):
        """生成背景图 - 入口方法"""
        self.signals.log.emit("BGW generate start")
        self._finish_image_agent()
        self._finish_api_requester()
        try:
            self._request_image_prompt(chathistory)
        except Exception as e:
            self.signals.error.emit(f"back_ground_update: error code: {e}")

    def _request_image_prompt(self, chathistory: list):
        """第一步：请求LLM生成图像prompt"""
        self.signals.log.emit("BGW request image prompt")
        summary_prompt = self.background_cfg.preset.summary_prompt
        last_full_story = self._get_background_prompt_from_chathistory(chathistory)

        messages = [
            {"role": "system", "content": summary_prompt},
            {"role": "user", "content": last_full_story}
        ]

        try:
            self._init_api_requester()
        except Exception as e:
            self.signals.error.emit(f"APIRequestHandler init: {e}")
            return

        try:
            self.signals.log.emit(f"场景生成：prompt请求发送。\n发送内容长度:{len(last_full_story)}")
            self.request_sender.send_request(message=messages, model=self.summary_model)
        except Exception as e:
            self.signals.error.emit(f"back_ground_update_thread Error: {str(e)}")

    def _handle_image_prompt_receive(self, return_prompt: str):
        """第二步：收到prompt后，请求生成图像"""
        self._finish_api_requester()
        self.signals.log.emit(f"return_prompt received:{return_prompt}")
        self._generate_image(return_prompt)

    def _generate_image(self, return_prompt: str):
        """第三步：调用图像生成API"""
        param = {}
        for _, __, obj in jsonfinder(return_prompt, json_only=True):
            if isinstance(obj, dict):
                param = obj

        if 'prompt' not in param or 'negative_prompt' not in param:
            self.signals.error.emit(
                f"background_image: prompt extract failed, param extracted:{param}, return_prompt:{return_prompt}"
            )
            return


        param['width'] = 1280
        param['height'] = 720
        param['model'] = self.image_model

        try:
            self._init_image_agent()
        except Exception as e:
            self.signals.error.emit(f"background_image creater init Error: {str(e)}")
            return

        self._start_watchdog()
        try:
            self.signals.log.emit("BGW image create start")
            self.creator.create(params_dict=param)
        except Exception as e:
            self.signals.error.emit(f"background_image_create Error: {str(e)}")

    def _on_request_error(self, infos: str):
        self.signals.error.emit(f"request_sender: {infos}")
        self._finish_api_requester()

    def _on_image_success(self, image_path: str):
        self._cancel_watchdog()
        self.signals.poll_success.emit(image_path)

    def _on_image_failure(self, source: str, error: str):
        self.signals.error.emit(f"{source}: {error}")
        self._finish_image_agent()

    def _start_watchdog(self, timeout_s: int = 180):
        self._cancel_watchdog()
        self._watchdog = threading.Timer(timeout_s, self._on_watchdog_timeout)
        self._watchdog.daemon = True
        self._watchdog.start()

    def _cancel_watchdog(self):
        if self._watchdog is not None:
            self._watchdog.cancel()
            self._watchdog = None

    def _on_watchdog_timeout(self):
        self.signals.error.emit("background_image timeout: no success/failure signal")
        self._finish_image_agent()

    # ========== 辅助方法 ==========

    def _get_readable_story(self, chathistory: list) -> str:
        """从聊天记录提取指定长度的可读文本"""
        required_length = self.required_length
        total_chars = 0
        index = 1
        last_full_story = []

        for message in reversed(chathistory):
            if message["role"] != "system":
                content = message["content"]
                total_chars += len(content)
                index += 1
                
                if total_chars >= required_length:
                    last_full_story = chathistory[-index:]
                    break

        if total_chars < required_length:
            last_full_story = [msg for msg in chathistory if msg["role"] != "system"]
        return ChatHistoryTools.to_readable_str(last_full_story)

    def _get_last_full_story(self, chathistory: list) -> str:
        """从系统消息提取上次摘要"""
        for item in chathistory:
            if 'lci' in item['info']['id']:
                # lci = 上下文压缩
                return item['content']

    def _get_background_prompt_from_chathistory(self, chathistory: list) -> str:
        """组装发给LLM的完整prompt"""
        last_full_story = ''

        # 添加自迭代摘要结果
        summary_in_system = self._get_last_full_story(chathistory)
        if summary_in_system:
            last_full_story += (
                self.background_cfg.preset.system_prompt_hint + '\n'
                + summary_in_system + '\n'
            )

        # 添加场景内容
        last_full_story += (
            self.background_cfg.preset.scene_hint + '\n'
            + self._get_readable_story(chathistory) + '\n'
        )

        # 添加用户主请求
        last_full_story += self.background_cfg.preset.user_summary + '\n'

        # 添加风格要求
        if self.background_style:
            last_full_story += (
                self.background_cfg.preset.style_hint + '\n'
                + self.background_style + '\n\n'
            )

        # IRAG 特殊处理
        if 'irag' in self.image_model.lower():
            last_full_story += self.background_cfg.preset.IRAG_USE_CHINESE

        return last_full_story
