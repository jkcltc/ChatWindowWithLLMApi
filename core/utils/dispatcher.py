from typing import Callable, Optional, Any
from functools import wraps
import traceback

class MainThreadDispatcher:
    """主线程调度"""
    
    _runner: Optional[Callable[[Callable], None]] = None

    @classmethod
    def register_runner(cls, runner: Callable[[Callable], None]) -> None:
        """供 GUI 层在程序启动时调用，注入主线程归并方法"""
        cls._runner = runner

    @classmethod
    def register_logger(cls, logger: Callable[[str], None]) -> None:
        """供 GUI 层在程序启动时调用，注入日志记录器"""
        cls._logger = logger

    @classmethod
    def run_in_main(cls, func: Callable) -> Callable[..., None]:
        """
        装饰器：强制目标函数在主线程排队执行。
        警告：被装饰的函数不能有返回值（即使有也会被丢弃）。
        最好在线程归并时使用，在session Manager里用很蠢
        """
        @wraps(func)
        def wrapper(*args, **kwargs) -> None:

            def task():
                try:
                    func(*args, **kwargs)
                except Exception as e:
                    er=traceback.format_exc()
                    if hasattr(cls, '_logger') and cls._logger is not None:
                        cls._logger(f"[MainThreadDispatcher] 跨线程执行 {func.__name__} 时崩溃: {e},\n{er}")
                    else:
                        print(f"[MainThreadDispatcher] 跨线程执行 {func.__name__} 时崩溃: {e},\n{er}")
                    
            
            if cls._runner is not None:
                # 如果注入了 GUI 调度器，交由 GUI 调度
                cls._runner(task)
            else:
                # 如果没有注入，直接就地执行
                task()
                
            return None
            
        return wrapper

run_in_main = MainThreadDispatcher.run_in_main