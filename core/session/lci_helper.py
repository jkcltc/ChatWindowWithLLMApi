from dataclasses import dataclass
from .session_model import ChatSession
from typing import TYPE_CHECKING
if TYPE_CHECKING:
    from config.settings import LciSettings


@dataclass(frozen=True)
class LciMetrics:
    """LCI (Long Context Integration) 触发判定所需的度量快照

    记录当前对话状态的关键指标，用于判断是否需要触发长上下文整合(LCI)。
    LCI 用于在对话过长时将上下文压缩，避免超出模型token限制。

    Attributes:
        full_chat_rounds: 当前对话总轮次（包含历史对话）
        full_chat_length: 当前对话总长度（字符数，包含历史对话）
        new_chat_rounds: 自上次LCI以来的新增对话轮次
        new_chat_length: 自上次LCI以来的新增对话长度（字符数）
    """
    full_chat_rounds: int
    full_chat_length: int
    new_chat_rounds: int
    new_chat_length: int

    @classmethod
    def from_session(cls, session: ChatSession) -> "LciMetrics":
        """从 ChatSession 采集当前对话的度量数据

        Args:
            session: 当前聊天会话对象，包含对话轮次和长度信息

        Returns:
            LciMetrics: 包含当前对话状态的度量快照
        """
        return cls(
            full_chat_rounds=session.chat_rounds,
            full_chat_length=session.chat_length,
            new_chat_rounds=session.new_chat_rounds,
            new_chat_length=session.new_chat_length,
        )


@dataclass(frozen=True)
class LciEvaluation:
    """LCI 判定结果（含中间步骤，方便日志和调试）

    根据 LciMetrics 和配置设置，评估是否触发长上下文整合(LCI)。
    采用两级触发机制：
    1. 基础触发条件：总对话长度或轮次超过阈值（表示对话已足够长）
    2. 增量触发条件：新增对话长度或轮次超过阈值（表示自上次LCI后积累了足够新内容）

    Attributes:
        metrics: 对话度量快照（LciMetrics）
        base_trigger_reached: 是否满足基础触发条件（总长度/轮次超过阈值）
        new_rounds_reached: 是否满足新增轮次触发条件
        new_length_reached: 是否满足新增长度触发条件
        triggered: 最终判定结果（base_trigger_reached and (new_rounds_reached or new_length_reached)）
    """
    metrics: LciMetrics
    base_trigger_reached: bool
    new_rounds_reached: bool
    new_length_reached: bool
    triggered: bool

    @classmethod
    def evaluate(cls, metrics: LciMetrics, settings:"LciSettings") -> "LciEvaluation":
        """根据度量数据和配置评估是否触发LCI

        触发逻辑：
        - 基础条件：总轮次 > max_segment_rounds 或 总长度 > max_total_length
        - 增量条件：新增轮次 > max_segment_rounds 或 新增长度 > max_segment_length
        - 最终触发：基础条件成立 且 (新增轮次条件成立 或 新增长度条件成立)

        Args:
            metrics: 对话度量快照（LciMetrics）
            settings: LCI配置对象，包含以下阈值：
                - max_segment_rounds: 单段最大对话轮次阈值
                - max_total_length: 对话总长度阈值
                - max_segment_length: 单段对话长度阈值

        Returns:
            LciEvaluation: 包含判定结果和中间状态的对象
        """
        base = (
            metrics.full_chat_rounds > settings.max_segment_rounds
            or metrics.full_chat_length > settings.max_total_length
        )
        rounds = metrics.new_chat_rounds > settings.max_segment_rounds
        length = metrics.new_chat_length > settings.max_segment_length

        triggered = base and (rounds or length)

        return cls(
            metrics=metrics,
            base_trigger_reached=base,
            new_rounds_reached=rounds,
            new_length_reached=length,
            triggered=triggered,
        )

    def format_log(self, settings) -> str:
        """格式化LCI评估结果为可读日志字符串

        用于调试和监控LCI触发情况，显示当前对话状态和触发条件检查结果。

        Args:
            settings: LCI配置对象，用于显示阈值对比

        Returns:
            str: 格式化的日志字符串，包含对话统计和触发条件状态
        """
        m = self.metrics
        return (
            f"[LCI]\n"
            f"当前对话总次数:{m.full_chat_rounds}\n"
            f"当前对话总长度:{m.full_chat_length}\n\n"
            f"新对话轮次:{m.new_chat_rounds}/{settings.max_segment_rounds}\n"
            f"新对话长度:{m.new_chat_length}/{settings.max_segment_length}\n\n"
            f"全长要求: {self.base_trigger_reached}\n"
            f"轮次要求: {self.new_rounds_reached}\n"
            f"长度要求: {self.new_length_reached}\n\n"
            f"触发LCI:{self.triggered}"
        )
