import time

from config import APP_SETTINGS

from core.context.base import ContextComponent
from core.context.model import Descriptor, PrePhase, ContextPayload

_pip_env_cache = None


class UserCharHandler(ContextComponent):
    """
    {{user}}/{{char}}/{{model}} 等模板替换 + name 字段注入。
    原 Preprocessor._handle_user_and_char
    """

    def descriptor(self) -> Descriptor:
        return Descriptor(
            name="user_char_handler",
            phase=PrePhase.DECORATE,
            depth=0,
            description="模板替换 + name 字段注入",
        )

    def process(self, payload: ContextPayload) -> ContextPayload:
        messages = payload.messages
        pack = payload.pack

        if not messages:
            return payload

        names_config = pack.chat_session.name

        ai_name = names_config.get('assistant')
        if not ai_name:
            ai_name = APP_SETTINGS.names.ai if APP_SETTINGS.names.ai else pack.model

        user_name = names_config.get('user')
        if not user_name:
            user_name = APP_SETTINGS.names.user if APP_SETTINGS.names.user else 'user'

        for item in messages:
            role = item.get('role')
            if APP_SETTINGS.names.character_enforce:
                if role == 'user':
                    item['name'] = user_name
                elif role == 'assistant':
                    item['name'] = ai_name

            if role == 'system':
                content = item.get('content', '')
                if '{{user}}' in content:
                    content = content.replace('{{user}}', user_name)
                if '{{char}}' in content:
                    content = content.replace('{{char}}', ai_name)
                if '{{model}}' in content:
                    content = content.replace('{{model}}', pack.model)
                if '{{time}}' in content:
                    content = content.replace('{{time}}', time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()))
                if '{{date}}' in content:
                    content = content.replace('{{date}}', time.strftime("%Y-%m-%d", time.localtime()))
                if '{{platform}}' in content:
                    import platform
                    sys_platform = platform.platform()
                    content = content.replace('{{platform}}', sys_platform)
                if '{{user_profile}}' in content:
                    import getpass
                    current_user = getpass.getuser()
                    content = content.replace('{{user_profile}}', current_user)
                if '{{pip_env}}' in content:
                    global _pip_env_cache
                    if _pip_env_cache is None:
                        import importlib.metadata
                        dists = importlib.metadata.distributions()
                        _pip_env_cache = "\n".join([f"{dist.metadata['Name']}=={dist.version}" for dist in dists])
                    content = content.replace('{{pip_env}}', _pip_env_cache)
                if '{{abandon_kvcache}}' in content:
                    import uuid
                    random_cache_breaker = str(uuid.uuid4())
                    content = content.replace('{{abandon_kvcache}}', random_cache_breaker)

                item['content'] = content

        payload.messages = messages
        return payload
