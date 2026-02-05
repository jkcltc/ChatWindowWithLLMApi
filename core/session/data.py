from typing import List, Dict, Any ,Optional ,Callable,Union
from dataclasses import dataclass ,field
@dataclass
class ChatCompletionPack:
    """
    用于在不同组件间传递对话请求所需的完整上下文包。
    """
    chathistory: List[Dict[str, Any]]

    model: str

    provider: Any = None# actually utils.setting.data -> ProviderConfig(BaseSettings)

    tool_list: List[str] = field(default_factory=list)
    """function_manager.selected_tools=>list"""

    optional:dict = field(default_factory={
        "temp_style":'',
        'web_search_result':'',
        'enforce_lower_repeat_text':'',
    })

    mod: Optional[List[Callable]] = field(default_factory=list) 

    @property
    def sysrule(self):
        if self.chathistory[0]['role']=='system':
            return self.chathistory[0]['content']
        else:
            return ''
