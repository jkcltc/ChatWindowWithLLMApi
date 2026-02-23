"""
SSE (Server-Sent Events) 流式解析器

将流式响应解析逻辑从主请求处理器中剥离，实现单一职责。
"""
import json
from typing import Iterator, Dict, Any, Optional, Callable
from dataclasses import dataclass
from enum import Enum


def decode_content(content: bytes) -> str:
    """解码响应内容"""
    if not content:
        return ""
    
    # 尝试 UTF-8
    try:
        return content.decode('utf-8')
    except UnicodeDecodeError:
        pass
    # 尝试 UTF-8 带 BOM
    try:
        return content.decode('utf-8-sig')
    except UnicodeDecodeError:
        pass
    # 尝试 GBK
    try:
        return content.decode('gbk')
    except UnicodeDecodeError:
        pass

    try:
        return content.decode('gb18030')
    except UnicodeDecodeError:
        pass
    
    # 最终回退
    return content.decode('utf-8', errors='replace')

class DeltaType(Enum):
    """Delta 消息类型"""
    CONTENT = "content"
    REASONING = "reasoning"
    TOOL_CALL = "tool_call"
    DONE = "done"
    ERROR = "error"
    USAGE = "usage"


@dataclass
class DeltaObject:
    """
    表示 LLM 流式响应中的一个增量片段
    """
    content: Optional[str] = None
    reasoning_content: Optional[str] = None
    tool_calls: Optional[list] = None
    finish_reason: Optional[str] = None
    delta_type: DeltaType = DeltaType.CONTENT
    raw_data: Optional[Dict] = None
    usage: Optional[Dict] = None 
    
    @classmethod
    def from_openai_delta(cls, delta_data: Dict[str, Any]) -> "DeltaObject":
        """从 OpenAI 格式的 delta 数据创建 DeltaObject"""
        # 提取内容
        content = delta_data.get('content') or ""
        
        # 提取思维链（支持多种字段名）
        reasoning = delta_data.get('reasoning_content') or delta_data.get('reasoning') or ""
        
        # 提取工具调用
        tool_calls = None
        if 'tool_calls' in delta_data:
            tool_calls = cls._parse_tool_calls(delta_data['tool_calls'])
        
        # 确定类型
        delta_type = DeltaType.CONTENT
        if tool_calls:
            delta_type = DeltaType.TOOL_CALL
        elif reasoning and not content:
            delta_type = DeltaType.REASONING
            
        return cls(
            content=content,
            reasoning_content=reasoning,
            tool_calls=tool_calls,
            raw_data=delta_data,
            delta_type=delta_type
        )
    
    @staticmethod
    def _parse_tool_calls(tool_calls_data: list) -> Optional[list]:
        """解析工具调用数据"""
        if not tool_calls_data:
            return None
        
        tool_calls = []
        for tc in tool_calls_data:
            tool_call = {
                'index': tc.get('index', 0),
                'id': tc.get('id', ''),
                'type': tc.get('type', 'function'),
                'function': {
                    'name': tc.get('function', {}).get('name', ''),
                    'arguments': tc.get('function', {}).get('arguments', '')
                }
            }
            tool_calls.append(tool_call)
        
        return tool_calls
    
    def is_empty(self) -> bool:
        """检查此 delta 是否为空（无有效内容）"""
        if self.delta_type == DeltaType.USAGE and self.usage:
            return False
        if self.delta_type == DeltaType.DONE:
            return False

        return not (self.content or self.reasoning_content or self.tool_calls)


@dataclass  
class SSEEvent:
    """
    表示一个完整的 SSE 事件（包含多个 delta 的完整消息）
    """
    event_id: Optional[str] = None
    event_type: Optional[str] = None
    data: Optional[Dict[str, Any]] = None
    choices: Optional[list] = None
    model: Optional[str] = None
    usage: Optional[Dict] = None
    
    @classmethod
    def from_json(cls, json_data: Dict[str, Any]) -> "SSEEvent":
        """从 JSON 数据创建 SSEEvent"""
        choices = json_data.get('choices', [])
        
        return cls(
            event_id=json_data.get('id'),
            event_type=json_data.get('object'),
            data=json_data,
            choices=choices,
            model=json_data.get('model'),
            usage=json_data.get('usage')
        )
    
    def get_first_delta(self) -> Optional[DeltaObject]:
        """获取第一个 choice 的 delta"""
        
        # 1. 如果根本没有 choices（传统的最后一条带 usage 的 chunk）
        if not self.choices:
            if self.usage:
                return DeltaObject(
                    delta_type=DeltaType.USAGE,
                    usage=self.usage,
                    raw_data=self.data
                )
            return None

        # 2. 正常解析 choice 的内容
        choice = self.choices[0]
        delta_data = choice.get('delta', {})

        delta = DeltaObject.from_openai_delta(delta_data)
        delta.finish_reason = choice.get('finish_reason')
        
        # 3. chunk 附带了 usage,挂载到 delta 上
        if self.usage:
            delta.usage = self.usage

        return delta

    
    def get_finish_reason(self) -> Optional[str]:
        """获取完成原因"""
        if self.choices:
            return self.choices[0].get('finish_reason')
        return None


class SSEParser:
    """
    SSE 流式响应解析器
    
    将 HTTP 流式响应行解析为结构化的 SSEEvent 对象
    """
    
    def __init__(self, logger: Optional[Callable] = None):
        self.logger = logger
        self._buffer = ""
        self._current_event_id: Optional[str] = None
        self._current_event_type: Optional[str] = None
        
    def parse_lines(self, response_iterator: Iterator) -> Iterator[SSEEvent]:
        """
        解析 SSE 流式响应行
        
        Args:
            response_iterator: HTTP 响应的 iter_lines() 迭代器
                              可以是字节 (decode_unicode=False) 或字符串 (decode_unicode=True)
            
        Yields:
            SSEEvent: 解析后的事件对象
        """
        for line_data in response_iterator:
            if line_data is None:
                continue
                
            # 如果已经是字符串，直接使用；否则解码
            if isinstance(line_data, str):
                line = line_data
            else:
                line = decode_content(line_data)
            
            if not line:
                continue
                
            # 处理 SSE 格式
            if line.startswith('data:'):
                data_str = line[5:].lstrip()
                
                # 检查结束标记
                if data_str == '[DONE]':
                    yield SSEEvent(data={'done': True})
                    continue
                
                # 解析 JSON 数据
                try:
                    event_data = json.loads(data_str)
                    event = SSEEvent.from_json(event_data)
                    
                    # 更新事件元数据
                    if event.event_id:
                        self._current_event_id = event.event_id
                    
                    yield event
                    
                except json.JSONDecodeError as e:
                    if self.logger:
                        self.logger(f"SSE JSON 解析错误: {e}, data: {data_str[:100]}")
                    continue
                    
            elif line.startswith('id:'):
                self._current_event_id = line[3:].lstrip()
                
            elif line.startswith('event:'):
                self._current_event_type = line[6:].lstrip()
                
            elif line.startswith('retry:'):
                # 重试时间，可以忽略
                pass
    
    def parse_deltas(self, response_iterator: Iterator[bytes]) -> Iterator[DeltaObject]:
        """
        直接解析为 DeltaObject 流（更简洁的 API）
        
        Args:
            response_iterator: HTTP 响应的 iter_lines() 迭代器
            
        Yields:
            DeltaObject: 增量内容对象
        """
        for event in self.parse_lines(response_iterator):
            # 跳过 DONE 标记
            if event.data and event.data.get('done'):
                delta = DeltaObject(delta_type=DeltaType.DONE)
                yield delta
                continue
            
            delta = event.get_first_delta()
            if delta and not delta.is_empty():
                yield delta


class SimpleSSEParser:
    """
    简化的 SSE 解析器，用于快速集成
    
    不依赖复杂的状态管理，直接产出可用的 delta 数据
    """
    
    @staticmethod
    def parse_stream(response, logger: Optional[Callable] = None) -> Iterator[DeltaObject]:
        """
        从 requests 响应对象直接解析
        
        Args:
            response: requests Response 对象
            logger: 可选的日志函数
            
        Yields:
            DeltaObject: 增量内容
        """
        
        try:
            for line_bytes in response.iter_lines(decode_unicode=False):
                if not line_bytes:
                    continue
                line = decode_content(line_bytes)

                if line.startswith('data:'):
                    data_str = line[5:].lstrip()

                    if data_str == '[DONE]':
                        yield DeltaObject(delta_type=DeltaType.DONE)
                        break

                    try:
                        event_data = json.loads(data_str)
                        event = SSEEvent.from_json(event_data)
                        delta = event.get_first_delta()

                        if delta:
                            delta.raw_data = event_data
                            if not delta.is_empty():
                                yield delta

                    except json.JSONDecodeError:
                        if logger:
                            logger(f"JSON parse error: {data_str[:50]}...")
                        continue
        except (AttributeError, ValueError) as e:
            return
        
        except Exception as e:
            if logger:
                logger(f"Stream parse error: {e}")
            raise


# 便捷函数
def create_parser() -> SSEParser:
    """创建默认的 SSE 解析器实例"""
    return SSEParser()