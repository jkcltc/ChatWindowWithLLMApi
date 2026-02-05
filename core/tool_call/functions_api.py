from utils.tool_core import get_tool_registry
def user_tool(name=None, description=None, parameters=None, **meta):
    """装饰器：桥接到全局 ToolRegistry 单例。"""
    return get_tool_registry().tool(name=name, description=description, parameters=parameters, **meta)
