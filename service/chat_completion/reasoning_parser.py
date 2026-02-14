"""
思维链（Chain of Thought）解析器 - 状态机实现

用于处理本地模型（如 Ollama、DeepSeek 本地部署）的思维链输出，
将 <think>...</think> 包裹的内容与正文分离。

相比原版的字符串查找方式，使用状态机可以更健壮地处理流式输出。
"""
from enum import Enum, auto
from typing import Optional, Callable, Dict, Any
from dataclasses import dataclass, field


class ReasoningState(Enum):
    """思维链解析状态"""
    NORMAL = auto()           # 正常输出状态
    THINKING = auto()         # 思维链内部状态
    THINK_START_PENDING = auto()   # 可能遇到 <think> 开头
    THINK_END_PENDING = auto()     # 可能遇到 </think> 结尾


@dataclass
class ParseResult:
    """解析结果"""
    content: str = ""           # 正文内容
    reasoning_content: str = "" # 思维链内容
    is_reasoning: bool = False  # 当前是否在思维链中
    state: ReasoningState = ReasoningState.NORMAL  # 当前状态


class ReasoningStateMachine:
    """
    思维链状态机解析器
    
    逐字符处理流式输出，实时分离思维链和正文内容。
    相比批量字符串处理，内存效率更高，适合流式场景。
    """
    
    # 标记定义
    THINK_START = "<think>"
    THINK_END = "</think>"
    
    def __init__(
        self, 
        think_start: str = "<think>", 
        think_end: str = "</think>",
        on_content: Optional[Callable[[str], None]] = None,
        on_reasoning: Optional[Callable[[str], None]] = None,
        on_state_change: Optional[Callable[[ReasoningState, ReasoningState], None]] = None
    ):
        """
        初始化状态机
        
        Args:
            think_start: 思维链开始标记
            think_end: 思维链结束标记
            on_content: 正文内容回调
            on_reasoning: 思维链内容回调  
            on_state_change: 状态变更回调 (old_state, new_state)
        """
        self.think_start = think_start
        self.think_end = think_end
        self.on_content = on_content
        self.on_reasoning = on_reasoning
        self.on_state_change = on_state_change
        
        # 状态
        self._state = ReasoningState.NORMAL
        self._buffer = ""  # 用于累积可能的标记字符
        self._pending_buffer = ""  # 待确认的内容
        
        # 累积内容（用于最终结果）
        self._full_content = ""
        self._full_reasoning = ""
        
        # 标记是否已看到开始标记（用于处理无开始标记但有结束标记的情况）
        self._has_seen_start = False
        
    @property
    def state(self) -> ReasoningState:
        return self._state
    
    @property
    def is_reasoning(self) -> bool:
        """当前是否处于思维链状态"""
        return self._state == ReasoningState.THINKING
    
    def reset(self):
        """重置状态机"""
        self._state = ReasoningState.NORMAL
        self._buffer = ""
        self._pending_buffer = ""
        self._full_content = ""
        self._full_reasoning = ""
        self._has_seen_start = False
    
    def process(self, text: str) -> ParseResult:
        """
        处理一段文本
        
        Args:
            text: 输入文本片段
            
        Returns:
            ParseResult: 解析结果
        """
        for char in text:
            self._process_char(char)
        
        return ParseResult(
            content=self._full_content,
            reasoning_content=self._full_reasoning,
            is_reasoning=self.is_reasoning,
            state=self._state
        )
    
    def _process_char(self, char: str):
        """处理单个字符"""
        if self._state == ReasoningState.NORMAL:
            self._process_in_normal(char)
        elif self._state == ReasoningState.THINK_START_PENDING:
            self._process_in_start_pending(char)
        elif self._state == ReasoningState.THINKING:
            self._process_in_thinking(char)
        elif self._state == ReasoningState.THINK_END_PENDING:
            self._process_in_end_pending(char)
    
    def _process_in_normal(self, char: str):
        """在正常状态下处理字符"""
        # 检查是否匹配 <think> 的开头
        if char == self.think_start[0]:
            self._state = ReasoningState.THINK_START_PENDING
            self._buffer = char
            self._pending_buffer = ""
        else:
            # 普通内容
            self._full_content += char
            if self.on_content:
                self.on_content(char)
    
    def _process_in_start_pending(self, char: str):
        """在可能的 think 开始标记中处理字符"""
        expected_char = self.think_start[len(self._buffer)]
        
        if char == expected_char:
            self._buffer += char
            
            # 完整匹配了开始标记
            if self._buffer == self.think_start:
                self._transition_to(ReasoningState.THINKING)
                self._buffer = ""
                self._has_seen_start = True
        else:
            # 不匹配，将缓冲区的内容和当前字符都作为普通内容输出
            pending = self._buffer + char
            self._full_content += pending
            if self.on_content:
                self.on_content(pending)
            self._buffer = ""
            self._state = ReasoningState.NORMAL
    
    def _process_in_thinking(self, char: str):
        """在思维链状态下处理字符"""
        # 检查是否匹配 </think> 的开头
        if char == self.think_end[0]:
            self._state = ReasoningState.THINK_END_PENDING
            self._buffer = char
        else:
            # 思维链内容
            self._full_reasoning += char
            if self.on_reasoning:
                self.on_reasoning(char)
    
    def _process_in_end_pending(self, char: str):
        """在可能的 think 结束标记中处理字符"""
        expected_char = self.think_end[len(self._buffer)]
        
        if char == expected_char:
            self._buffer += char
            
            # 完整匹配了结束标记
            if self._buffer == self.think_end:
                self._transition_to(ReasoningState.NORMAL)
                self._buffer = ""
        else:
            # 不匹配，将缓冲区内容作为思维链内容输出
            pending = self._buffer + char
            self._full_reasoning += pending
            if self.on_reasoning:
                self.on_reasoning(pending)
            self._buffer = ""
            self._state = ReasoningState.THINKING
    
    def _transition_to(self, new_state: ReasoningState):
        """状态转换"""
        old_state = self._state
        self._state = new_state
        
        if self.on_state_change:
            self.on_state_change(old_state, new_state)
    
    def finalize(self) -> ParseResult:
        """
        完成解析，处理可能剩余的缓冲区内容
        
        适用于流式结束时调用
        """
        # 如果还有未处理的缓冲区内容
        if self._buffer:
            if self._state in (ReasoningState.THINKING, ReasoningState.THINK_END_PENDING):
                self._full_reasoning += self._buffer
                if self.on_reasoning:
                    self.on_reasoning(self._buffer)
            else:
                self._full_content += self._buffer
                if self.on_content:
                    self.on_content(self._buffer)
            self._buffer = ""
        
        return ParseResult(
            content=self._full_content,
            reasoning_content=self._full_reasoning,
            is_reasoning=self.is_reasoning,
            state=self._state
        )


class SimpleReasoningParser:
    """
    简化的思维链解析器（批量处理版本）
    
    适用于非流式场景，一次性处理完整文本
    """
    
    @staticmethod
    def parse(
        text: str, 
        think_start: str = "<think>", 
        think_end: str = "</think>"
    ) -> ParseResult:
        """
        解析包含思维链的文本
        
        Args:
            text: 完整文本
            think_start: 思维链开始标记
            think_end: 思维链结束标记
            
        Returns:
            ParseResult: 解析结果
        """
        reasoning_content = ""
        content = ""
        is_reasoning = False
        
        # 情况1：有完整的开始和结束标记
        if think_start in text and think_end in text:
            start_pos = text.index(think_start)
            end_pos = text.index(think_end)
            
            # 提取思维链（去掉标记）
            reasoning_content = text[start_pos + len(think_start):end_pos]
            # 提取正文（结束标记之后）
            content = text[end_pos + len(think_end):]
            is_reasoning = False
            
        # 情况2：只有开始标记（正在思考中）
        elif think_start in text and think_end not in text:
            start_pos = text.index(think_start)
            reasoning_content = text[start_pos + len(think_start):]
            # 开始标记之前的内容是正文
            content = text[:start_pos]
            is_reasoning = True
            
        # 情况3：只有结束标记（某些模型不生成开始标记）
        elif think_end in text and think_start not in text:
            end_pos = text.index(think_end)
            # 将结束标记之前的内容视为思维链
            reasoning_content = text[:end_pos]
            content = text[end_pos + len(think_end):]
            is_reasoning = False
            
        # 情况4：没有任何标记
        else:
            content = text
            is_reasoning = False
        
        return ParseResult(
            content=content,
            reasoning_content=reasoning_content,
            is_reasoning=is_reasoning,
            state=ReasoningState.THINKING if is_reasoning else ReasoningState.NORMAL
        )


class StreamingReasoningParser:
    """
    流式思维链解析器（适配器）
    
    将状态机包装为更易用的流式处理接口
    """
    
    def __init__(
        self,
        think_start: str = "<think>",
        think_end: str = "</think>"
    ):
        self.state_machine = ReasoningStateMachine(
            think_start=think_start,
            think_end=think_end
        )
        
        # 用于流式回调的内容缓冲区
        self._content_chunks: list[str] = []
        self._reasoning_chunks: list[str] = []
        
        # 设置回调
        self.state_machine.on_content = self._on_content
        self.state_machine.on_reasoning = self._on_reasoning
    
    def _on_content(self, chunk: str):
        self._content_chunks.append(chunk)
    
    def _on_reasoning(self, chunk: str):
        self._reasoning_chunks.append(chunk)
    
    def feed(self, chunk: str) -> Dict[str, Any]:
        """
        喂入一个文本块
        
        Args:
            chunk: 新的文本片段
            
        Returns:
            包含本次解析结果的字典
        """
        # 清空缓冲区
        self._content_chunks.clear()
        self._reasoning_chunks.clear()
        
        # 处理
        result = self.state_machine.process(chunk)
        
        return {
            'content_delta': ''.join(self._content_chunks),
            'reasoning_delta': ''.join(self._reasoning_chunks),
            'is_reasoning': result.is_reasoning,
            'full_content': result.content,
            'full_reasoning': result.reasoning_content
        }
    
    def finalize(self) -> ParseResult:
        """完成解析"""
        return self.state_machine.finalize()
    
    def reset(self):
        """重置解析器"""
        self.state_machine.reset()
        self._content_chunks.clear()
        self._reasoning_chunks.clear()
    
    @property
    def is_reasoning(self) -> bool:
        return self.state_machine.is_reasoning


# 便捷函数
def parse_reasoning(text: str, **kwargs) -> ParseResult:
    """便捷函数：批量解析思维链文本"""
    return SimpleReasoningParser.parse(text, **kwargs)


def create_streaming_parser(**kwargs) -> StreamingReasoningParser:
    """便捷函数：创建流式解析器"""
    return StreamingReasoningParser(**kwargs)