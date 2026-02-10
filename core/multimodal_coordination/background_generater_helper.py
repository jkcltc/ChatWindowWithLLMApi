# background_generater_helper.py
from dataclasses import dataclass
from typing import TYPE_CHECKING
from core.session.session_model import ChatSession

if TYPE_CHECKING:
    from config.settings import BackgroundSettings


@dataclass(frozen=True)
class BggMetrics:
    """BGG (Background Generator) 触发判定所需的度量快照

    记录当前对话状态的关键指标，用于判断是否需要触发背景信息生成(BGG)。
    BGG 用于在对话过程中动态生成或更新角色背景信息，以保持角色一致性。

    Attributes:
        full_chat_rounds: 当前对话总轮次（包含历史对话）
        full_chat_length: 当前对话总长度（字符数，包含历史对话）
        new_background_rounds: 自上次背景更新以来的新增对话轮次
    """
    full_chat_rounds: int
    full_chat_length: int
    new_background_rounds: int

    @classmethod
    def from_session(cls, session: ChatSession) -> "BggMetrics":
        """从 ChatSession 采集当前对话的度量数据

        Args:
            session: 当前聊天会话对象，包含对话轮次和长度信息

        Returns:
            BggMetrics: 包含当前对话状态的度量快照
        """
        return cls(
            full_chat_rounds=session.chat_rounds,
            full_chat_length=session.chat_length,
            new_background_rounds=session.new_background_rounds,
        )


@dataclass(frozen=True)
class BggEvaluation:
    """BGG 判定结果（含中间步骤，方便日志和调试）

    根据 BggMetrics 和配置设置，评估是否触发背景信息生成(BGG)。
    采用两级触发机制：
    1. 基础触发条件：总对话长度或轮次超过阈值（表示对话已足够长）
    2. 增量触发条件：新增对话轮次超过阈值（表示自上次背景更新后积累了足够新内容）

    Attributes:
        metrics: 对话度量快照（BggMetrics）
        base_trigger_reached: 是否满足基础触发条件（总长度/轮次超过阈值）
        new_rounds_reached: 是否满足新增轮次触发条件
        triggered: 最终判定结果（base_trigger_reached and new_rounds_reached）
    """
    metrics: BggMetrics
    base_trigger_reached: bool
    new_rounds_reached: bool
    triggered: bool

    @classmethod
    def evaluate(cls, metrics: BggMetrics, settings: "BackgroundSettings") -> "BggEvaluation":
        """根据度量数据和配置评估是否触发BGG

        触发逻辑：
        - 基础条件：总轮次 > max_rounds 或 总长度 > max_length
        - 增量条件：新增轮次 > max_rounds
        - 最终触发：基础条件成立 且 新增轮次条件成立

        Args:
            metrics: 对话度量快照（BggMetrics）
            settings: 背景生成配置对象，包含以下阈值：
                - max_rounds: 最大对话轮次阈值（同时用于基础和增量条件）
                - max_length: 对话总长度阈值

        Returns:
            BggEvaluation: 包含判定结果和中间状态的对象
        """
        base_trigger = (
            metrics.full_chat_rounds > settings.max_rounds
            or metrics.full_chat_length > settings.max_length
        )
        new_rounds_trigger = metrics.new_background_rounds > settings.max_rounds
        
        triggered = base_trigger and new_rounds_trigger

        return cls(
            metrics=metrics,
            base_trigger_reached=base_trigger,
            new_rounds_reached=new_rounds_trigger,
            triggered=triggered,
        )

    def format_log(self, settings: "BackgroundSettings") -> str:
        """格式化BGG评估结果为可读日志字符串

        用于调试和监控BGG触发情况，显示当前对话状态和触发条件检查结果。

        Args:
            settings: 背景生成配置对象，用于显示阈值对比

        Returns:
            str: 格式化的日志字符串，包含对话统计和触发条件状态
        """
        m = self.metrics
        return (
            f"[BGG]\n"
            f"当前对话总次数:{m.full_chat_rounds}\n"
            f"当前对话总长度:{m.full_chat_length}\n\n"
            f"新对话轮次:{m.new_background_rounds}/{settings.max_rounds}\n\n"
            f"全长要求: {self.base_trigger_reached}\n"
            f"轮次要求: {self.new_rounds_reached}\n\n"
            f"触发背景更新:{self.triggered}"
        )