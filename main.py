import sys,ctypes
import atexit
import threading
import sys
import traceback
import logging

def inspect_lingering_threads():
    """检查退出时的线程 - 检查dummy"""
    def safe_log(msg):
        try:
            logging.getLogger('exiting').info(msg)
        except:
            print(msg, file=sys.stderr)

    safe_log("\n" + "="*50)
    safe_log("程序退出，正在检查残留线程...")

    # 获取所有活着的线程
    active_threads = threading.enumerate()
    # 过滤掉当前线程（通常是 MainThread，但如果是 sys.exit 被其他线程调用，则是那个线程）
    others = [t for t in active_threads if t != threading.current_thread()]

    if not others:
        safe_log("没有残留线程，干净退出。")
    else:
        safe_log(f"发现 {len(others)} 个残留线程：")

        # 获取所有线程的当前堆栈帧
        frames = sys._current_frames()

        for t in others:
            safe_log(f"\n--- 线程名: {t.name} (ID: {t.ident}) ---")
            safe_log(f"   状态: {'Daemon' if t.daemon else 'Normal'}, Alive: {t.is_alive()}")

            if t.ident in frames:
                safe_log("   调用堆栈:")

                stack_list = traceback.format_stack(frames[t.ident])
                safe_log("".join(stack_list))
            else:
                safe_log("   (无法获取堆栈)")

    safe_log("="*50 + "\n")

# 在 main 的最开始注册
atexit.register(inspect_lingering_threads)

if sys.platform == 'win32':
    appid = 'CWLA 0.26.1'
    ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(appid)
else:
    # 孩子们 鼠鼠不想跑linux和mac测试
    sys.exit(1)
from ui.CWLA_main import start
start()