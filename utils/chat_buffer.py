from dataclasses import dataclass
from typing import Literal, Optional
@dataclass
class ChatBuffer:
    _content: str = ''
    reasoning: str = ''
    _tool: str = ''
    renewed: bool = False
    id: str = ''
    model: str = 'AI_init'
    role: Literal['user', 'assistant', 'tool'] = 'assistant'
    status: Optional[dict] = None

    @property
    def tool(self) -> str:
        return self._tool

    @tool.setter
    def tool(self, text: str):
        self._tool = text
        if text:
            self.content = ''
    
    @property
    def content(self) -> str:
        return self._content
    
    @content.setter
    def content(self, text: str):
        self._content = text
        if text:
            self.reasoning = ''
    
    def reset(self):
        self.content = ''
        self.reasoning = ''
        self._tool = ''
        self.renewed = False
        self.id = ''
        self.model = 'AI_ph'
        self.role = 'assistant'
        self.status = None