from typing import Dict, Any
from pydantic import BaseModel, ConfigDict

# ==================== 核心基类 ====================

class BaseSettings(BaseModel):
    """
    该类为所有配置类提供基础功能，自动获得属性更新（update 方法）和类型检查能力。
    继承自 BaseModel，适用于需要动态更新配置且保持类型安全的场景。
    Attributes:
        model_config (ConfigDict): 配置 Pydantic V2 的行为，包括属性赋值校验、忽略多余字段、允许任意类型。
    Methods:
        update(data: Dict[str, Any]) -> None:
            原地递归更新模型属性。对于嵌套的 BaseSettings 子模型，支持递归更新，确保对象内存地址不变。
            非嵌套字段直接赋值，触发 Pydantic 的类型校验。List 类型字段会被整体替换。
        to_dict() -> dict:
            返回模型的字典表示，兼容旧代码的 to_dict 调用方式，等价于 model_dump()。
    """

    # 配置 Pydantic V2 的行为
    model_config = ConfigDict(
        validate_assignment=True,  # 运行时修改属性也会触发校验 (setter 保护)
        extra='ignore',           # 忽略多余的字段 (防止旧版 JSON 导致崩溃)
        arbitrary_types_allowed=True
    )

    def update(self, data: Dict[str, Any]):
        """
        原地更新
        递归更新嵌套的 Pydantic 模型，确保对象内存地址（引用）不变。
        """
        if not isinstance(data, dict):
            return

        for key, value in data.items():
            if key not in type(self).model_fields:
                continue

            # 获取当前属性值
            current_val = getattr(self, key)

            # 如果是嵌套的 Model，且新值也是字典，则递归更新
            if isinstance(current_val, BaseSettings) and isinstance(value, dict):
                current_val.update(value)

            # 否则直接赋值，利用 validate_assignment 触发 Pydantic 的校验逻辑
            # 注意：List 类型会全量替换
            else:
                setattr(self, key, value)

    def to_dict(self) -> dict:
        """兼容旧代码的 to_dict 调用"""
        return self.model_dump()
