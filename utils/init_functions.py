import os,sys
def install_packages():
    import subprocess
    import tkinter as tk
    from tkinter import messagebox
    # 定义需要安装的模块
    packages = [
        "requests",
        "openai",
        "pyqt5",
        'beautifulsoup4',
        'lxml',
        'pygments',
        'markdown',
        'jsonfinder'
    ]

    # 过滤掉标准库模块
    packages_to_install = [pkg for pkg in packages if pkg not in sys.builtin_module_names]

    # 提示用户需要安装的模块，并询问是否继续
    root = tk.Tk()
    root.withdraw()  # 隐藏主窗口
    response = messagebox.askyesno("初始化", f"需要向程序库安装 {packages_to_install}，是否继续？")

    if not response:
        messagebox.showinfo("操作取消", "用户选择取消安装，程序将退出。")
        # 用户拒绝安装，终止程序
        sys.exit(0)

    # 使用 pip 安装模块
    for package in packages_to_install:
        try:
            print(f"正在安装 {package}...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", package, 
                                       "--index-url", "https://mirrors.aliyun.com/pypi/simple/"])
                print(f"{package} 安装成功！")
            except:
                subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        except subprocess.CalledProcessError as e:
            messagebox.showerror("错误", f"安装 {package} 时出错: {e}")
            print(f"安装 {package} 时出错: {e}")
    messagebox.showinfo("提示", "程序初始化完成！")

def delete_directory(dir_path):
    """递归删除目录及其所有内容（仅使用 os 模块）"""
    if not os.path.exists(dir_path):
        return
    
    # 先删除目录中的所有文件和子目录
    for entry in os.listdir(dir_path):
        full_path = os.path.join(dir_path, entry)
        
        if os.path.isdir(full_path) and not os.path.islink(full_path):
            # 递归删除子目录
            delete_directory(full_path)
        else:
            # 删除文件或符号链接
            try:
                os.remove(full_path)
            except:
                pass  # 忽略删除错误
    
    # 当目录为空时，删除该目录
    try:
        os.rmdir(dir_path)
    except:
        pass  # 忽略删除错误

