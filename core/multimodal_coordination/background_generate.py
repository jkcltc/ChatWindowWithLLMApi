"""
兼容入口：背景生成模块已迁移至 core.background。
"""

from core.background.agent import BackgroundAgent
from core.background.worker import BackgroundWorker

__all__ = [
    "BackgroundAgent",
    "BackgroundWorker",
]
