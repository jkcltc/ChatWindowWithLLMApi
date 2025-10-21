import os,sys
import subprocess,importlib.util
import configparser

API_CONFIG_FILE = "api_config.ini"

DEFAULT_APIS = {
    "baidu": {
        "url": "https://qianfan.baidubce.com/v2",
        "key": "unknown"
    },
    "deepseek": {
        "url": "https://api.deepseek.com/v1",
        "key": "unknown"
    },
    "siliconflow": {
        "url": "https://api.siliconflow.cn/v1",
        "key": "unknown"
    },
    "tencent": {
        "url": "https://api.lkeap.cloud.tencent.com/v1",
        "key": "unknown"
    },
    "novita":{
        "url": "https://api.novita.ai/v3",
        "key": "unknown"
    }
}

def install_packages(package_map={}):
    # 统一包名和模块名的映射关系
    if not package_map:
        package_map = {
            "requests": "requests",
            "openai": "openai",
            "pyqt5": "PyQt5",  # 安装包名 vs 导入模块名
            "beautifulsoup4": "bs4",
            "lxml": "lxml",
            "pygments": "pygments",
            "markdown": "markdown",
            "jsonfinder": "jsonfinder",
            'edge-tts':'edge_tts'
        }
    
    # 检查是否有缺失包
    missing_packages = []
    for pkg, module in package_map.items():
        if importlib.util.find_spec(module) is None:
            missing_packages.append(pkg)
    
    if not missing_packages:
        return
    
    # 初始化GUI
    import tkinter as tk
    from tkinter import messagebox
    root = tk.Tk()
    root.withdraw()

    # 过滤标准库（实际不需要，但保留原逻辑）
    to_install = [pkg for pkg in missing_packages if pkg not in sys.builtin_module_names]
    
    # 用户确认
    prompt = f"需要安装以下依赖包:\n{', '.join(to_install)}\n\n是否继续？"
    if not messagebox.askyesno("初始化", prompt):
        messagebox.showinfo("操作取消", "用户取消安装，程序将退出")
        sys.exit(0)
    
    # 安装过程
    success = []
    failed = []
    for package in to_install:
        try:
            # 优先使用阿里云镜像
            cmd = [sys.executable, "-m", "pip", "install", package]
            try:
                subprocess.check_call(cmd + ["--index-url", "https://mirrors.aliyun.com/pypi/simple/"])
            except subprocess.CalledProcessError:
                subprocess.check_call(cmd)  # 回退到默认源
            success.append(package)
        except Exception as e:
            failed.append((package, str(e)))
    
    # 安装结果反馈
    result_msg = []
    if success:
        result_msg.append(f"成功安装: {', '.join(success)}")
    if failed:
        errors = '\n'.join([f"{pkg}: {err}" for pkg, err in failed])
        result_msg.append(f"安装失败:\n{errors}")
    
    messagebox.showinfo("安装结果", "\n\n".join(result_msg) if result_msg else "所有依赖已满足")
    
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

def clean_cache():
    """
    Recursively searches for and removes all '__pycache__' directories starting from the current directory.
    For each '__pycache__' directory found, prints its path and deletes it using the 'delete_directory' function.
    """
    for root, dirs, files in os.walk('.', topdown=True):
        if '__pycache__' in dirs:
            cache_dir = os.path.join(root, '__pycache__')
            print(f"Removing: {cache_dir}")
            delete_directory(cache_dir)
            dirs.remove('__pycache__')

#同步模型
def _create_default_config():
    """创建默认配置文件并返回默认API配置"""
    config = configparser.ConfigParser()
    for api_name, api_config in DEFAULT_APIS.items():
        config[api_name] = api_config
    
    try:
        with open(API_CONFIG_FILE, "w",encoding='utf-8') as configfile:
            config.write(configfile)
    except IOError as e:
        return {}
    
    return {k: [v["url"], v["key"]] for k, v in DEFAULT_APIS.items()}

def _read_existing_config():
    """读取已存在的配置文件"""
    config = configparser.ConfigParser()
    api_data = {}
    
    try:
        if not config.read(API_CONFIG_FILE,encoding='utf-8'):
            raise FileNotFoundError
        
        for api_name in config.sections():
            if config.has_section(api_name):
                url = config.get(api_name, "url", fallback="")
                key = config.get(api_name, "key", fallback="")
                api_data[api_name] = [url, key]
                DEFAULT_APIS[api_name]={'url':url,
                                        'key':key
                                        }       
            else:
                api_data[api_name] = [DEFAULT_APIS[api_name]["url"],[DEFAULT_APIS[api_name]["key"]]]
        return api_data
    except (configparser.Error, FileNotFoundError) as e:
        return _create_default_config()

def api_init():
    """
    初始化API配置
    返回格式：{"api_name": [url, key], ...}
    """
    if not os.path.exists(API_CONFIG_FILE):
        return _create_default_config()
    return _read_existing_config()



if __name__=='__main__':
    install_packages()