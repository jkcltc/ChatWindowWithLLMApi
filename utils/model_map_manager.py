import json
import os
from pathlib import Path

import requests, urllib
import configparser
import threading
from typing import Optional, Dict, List, Tuple, Any
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

class ModelMapManager:
    _DEFAULT_FILE_PATH = Path("utils/global_presets/MODEL_MAP.json")
    
    def __init__(self, file_path: str = None):
        if file_path:
            self.file_path = Path(file_path)
        else:
            self.file_path = self._DEFAULT_FILE_PATH
    
    def get_model_map(self) -> dict:
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            
            if not self.file_path.exists():
                return self.get_default_model_map()
            
            with open(self.file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
                
        except (json.JSONDecodeError, OSError) as e:
            print(f"Error reading model map: {e}")
            return {}

    def save_model_map(self, model_map: dict):
        try:
            self.file_path.parent.mkdir(parents=True, exist_ok=True)
            
            with open(self.file_path, 'w', encoding='utf-8') as f:
                json.dump(model_map, f, indent=2, ensure_ascii=False)
                
        except (TypeError, OSError) as e:
            print(f"Error saving model map: {e}")

    def get_default_model_map(self) -> dict:
        return {
            "baidu": [
                "ernie-4.5-turbo-32k",
                "qwen3-0.6b",
            ],
            "deepseek": ["deepseek-chat", "deepseek-reasoner"],
            "tencent": ["deepseek-r1", "deepseek-v3"],
            "siliconflow": [
                'deepseek-ai/DeepSeek-V3',
                'deepseek-ai/DeepSeek-R1',
                'Pro/deepseek-ai/DeepSeek-R1',
                'SeedLLM/Seed-Rice-7B',
                'Qwen/QwQ-32B'
            ]
        }


class ModelListUpdater:
    _lock = threading.Lock()

    @staticmethod
    def _read_api_config(application_path=''):
        if application_path:
            config_path = os.path.join(application_path, "api_config.ini")
        else:
            script_dir = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(script_dir, "api_config.ini")
        
        if not os.path.exists(config_path):
            print(f"配置文件不存在: {config_path}")
            return {}

        config = configparser.ConfigParser()
        config.read(config_path, encoding='utf-8')
        
        api_configs = {}
        for section in config.sections():
            try:
                url = config.get(section, "url").strip()
                key = config.get(section, "key").strip()
                api_configs[section] = {"url": url, "key": key}
            except (configparser.NoOptionError, configparser.NoSectionError) as e:
                print(f"配置解析错误[{section}]: {str(e)}")
        
        return api_configs
    
    @staticmethod
    def _correct_url(url: str) -> str:
        parsed = urllib.parse.urlparse(url)
        path = parsed.path.rstrip('/')
        
        if not path.endswith('/models') and not path.endswith('/api/tags'):
            path += '/models'
        
        return urllib.parse.urlunparse((
            parsed.scheme or 'https',
            parsed.netloc,
            path,
            parsed.params,
            parsed.query,
            parsed.fragment
        ))

    @staticmethod
    def _update_platform_models(platform: str, platform_config: dict) -> List[str]:
        try:
            models = ModelListUpdater.get_model_list(platform_config)
            if models:
                models.sort()
                print(f"[{platform}] 获取到 {len(models)} 个模型")
                return models
            else:
                print(f"[{platform}] 响应数据为空")
                return []
        except Exception as e:
            print(f"[{platform}] 更新失败: {str(e)}")
            return []

    @staticmethod
    def is_ollama_alive(url='http://localhost:11434/'):
        try:
            corrected_url = urllib.parse.urljoin(url, 'api/tags')
            response = requests.get(corrected_url, timeout=5)
            return response.status_code == 200
        except requests.exceptions.RequestException:
            return False
    
    @staticmethod
    def get_model_list(platform):
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {platform["key"]}'
        }
        
        try:
            response = requests.get(platform["url"], headers=headers)
            response.raise_for_status()
            
            data = response.json()
            
            if 'data' in data:
                return [model['id'] for model in data['data']]
            else:
                print(f"返回数据中缺少'data'字段: {data}")
                return []
                
        except requests.exceptions.RequestException as e:
            print(f"请求失败: {e}")
            return []
        except json.JSONDecodeError:
            print("返回的不是有效JSON格式")
            return []

    @staticmethod
    def update(application_path='') -> Dict[str, List[str]]:
        ollama_alive = ModelListUpdater.is_ollama_alive()
        print(f"Ollama服务状态: {'存活' if ollama_alive else '未启动'}")
        return ModelListUpdater.update_model_map(
            update_ollama=ollama_alive,
            application_path=application_path
        )

    @staticmethod
    def update_model_map(update_ollama=False, application_path='') -> Dict[str, List[str]]:
        available_models = {}  
        
        api_configs = ModelListUpdater._read_api_config(application_path)
        if not api_configs:
            print("无有效API配置，跳过更新")
            return available_models
        
        if not update_ollama and "ollama" in api_configs:
            del api_configs["ollama"]
            print("跳过ollama更新")

        threads = []
        results = []
        
        for platform, config in api_configs.items():
            corrected_config = {
                "url": ModelListUpdater._correct_url(config["url"]),
                "key": config["key"]
            }
            
            def thread_func(plat, cfg):
                try:
                    models = ModelListUpdater.get_model_list(cfg)
                    if models:
                        models.sort()
                        results.append((plat, models))
                except Exception as e:
                    print(f"[{plat}] 更新失败: {str(e)}")
            
            thread = threading.Thread(target=thread_func, args=(platform, corrected_config))
            thread.start()
            threads.append(thread)
        
        for thread in threads:
            thread.join()
        
        for plat, models in results:
            available_models[plat] = models
            
        return available_models


class APIConfigDialogUpdateModelThread(QThread):
    started_signal = pyqtSignal()
    finished_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)
    def __init__(self,application_path):
        super().__init__()
        self.application_path=application_path
        self.finished_signal.connect(self.deleteLater)

    def run(self) -> None:
        try:
            self.started_signal.emit()
            available_models = ModelListUpdater.update(self.application_path)
            self.finished_signal.emit(available_models)
        except Exception as e:
            self.error_signal.emit(str(e))

class APIConfigWidget(QWidget):
    """
    API配置管理窗口，用于管理各类API供应商的连接配置（URL、密钥）及模型选择。
    支持预设API供应商、自定义API添加/删除、模型库更新、配置保存等功能。
    """
    # 配置更新时发射，携带最新配置数据（dict格式）
    configUpdated = pyqtSignal(dict)
    # 初始化完成时发射，携带可用模型数据（dict格式）
    initializationCompleted = pyqtSignal(dict)
    # 告知主窗口保存完成
    notificationRequested=pyqtSignal(str,str) #message,level

    def __init__(self, parent: Optional[QWidget] = None, application_path=''):
        super().__init__(parent)
        # 预设API供应商列表（无需手动添加的内置供应商）
        self.preset_apis = ["baidu", "deepseek", "siliconflow", "tencent", "novita", "ollama"]
        # 自定义API供应商列表（用户手动添加的供应商）
        self.custom_apis = []
        # 应用程序路径（用于加载/保存配置文件）
        self.application_path = application_path
        # 存储各API对应的UI组件：(URL输入框, 密钥输入框, 模型列表, 搜索框)
        self.api_widgets: Dict[str, Tuple[QLineEdit, QLineEdit, QListWidget, QLineEdit]] = {}
        # 存储各API可用模型列表：{api_name: [model1, model2, ...]}
        self.available_models: Dict[str, List[str]] = {}
        # 用于延迟保存配置的定时器（避免频繁触发保存）
        self.api_timers = {}
        # 更新按钮动画相关组件
        self.update_btn_overlay = None
        self.animation_group = None
        # 保存按钮动画相关组件
        self.save_btn_overlay = None
        self.save_animation_group = None
        self.save_in_progress = False  # 标记保存流程是否在进行中
        # 初始化状态标志（避免初始化阶段触发不必要的配置更新）
        self.initializing = True

        # 初始化模型映射管理器（用于保存/加载模型选择状态）
        if application_path:
            model_map_path = os.path.join(application_path, ModelMapManager._DEFAULT_FILE_PATH)
            self.model_map_manager = ModelMapManager(model_map_path)
        else:
            self.model_map_manager = ModelMapManager()
        
        # 初始化UI、动画及配置
        self._initialize_ui()
        self._setup_update_button_animation()
        self._setup_save_button_animation()
        self.load_config()
        self.adjustSize()
        
        # 设置窗口位置和大小（居中显示，占屏幕30%宽、80%高）
        screen_geometry = QApplication.primaryScreen().availableGeometry()
        width = int(screen_geometry.width() * 0.3)
        height = int(screen_geometry.height() * 0.8)
        left = (screen_geometry.width() - width) // 2
        top = (screen_geometry.height() - height) // 2
        self.setGeometry(left, top, width, height)
        self.setWindowTitle("API 配置管理")

        # 初始化完成，发射信号并更新状态
        self.initializationCompleted.emit(self.available_models)
        self.initializing = False

    def _initialize_ui(self) -> None:
        """初始化主界面布局，包含标题、标签页容器和底部按钮区"""
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        # 标题标签
        title_label = QLabel("API 配置管理")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        
        # 标签页容器（左侧显示标签，用于切换不同API供应商）
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.West)  # 标签在左侧
        self.tab_widget.setDocumentMode(True)  # 启用文档模式（视觉优化）
        self.tab_widget.setElideMode(Qt.ElideNone)  # 不省略标签文本
        main_layout.addWidget(self.tab_widget, 1)  # 占主要空间
        
        # 底部按钮布局
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        button_layout.addStretch(1)  # 左侧留白
        
        # 添加自定义API按钮
        self.add_custom_btn = QPushButton("+ 添加自定义API供应商")
        self.add_custom_btn.setFixedHeight(40)
        self.add_custom_btn.clicked.connect(self.add_custom_api)
        button_layout.addWidget(self.add_custom_btn)
        
        # 更新模型库按钮
        self.update_btn = QPushButton("更新模型库")
        self.update_btn.setFixedHeight(40)
        self.update_btn.clicked.connect(self.on_update_models)
        button_layout.addWidget(self.update_btn)
        
        # 保存并关闭按钮
        self.save_btn = QPushButton("保存并关闭")
        self.save_btn.setFixedHeight(40)
        self.save_btn.clicked.connect(self.on_save_and_close)
        button_layout.addWidget(self.save_btn)
        
        main_layout.addLayout(button_layout)
        
        # 状态提示标签（显示保存结果、更新状态等）
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        main_layout.addWidget(self.status_label)

        # 初始化预设API的标签页
        self._setup_preset_apis()

    def _setup_preset_apis(self) -> None:
        """为预设API供应商创建标签页"""
        for api_name in self.preset_apis:
            self._create_api_tab(api_name, is_custom=False)

    def _create_api_tab(self, api_name: str, is_custom: bool = True) -> None:
        """
        为指定API供应商创建标签页内容（包含配置区和模型选择区）
        
        参数:
            api_name: API供应商名称
            is_custom: 是否为自定义供应商（自定义供应商显示删除按钮）
        """
        tab_content = QWidget()
        tab_content.setObjectName(api_name)  # 用API名称作为标识
        main_tab_layout = QVBoxLayout(tab_content)
        main_tab_layout.setContentsMargins(15, 15, 15, 15)
        main_tab_layout.setSpacing(15)
        
        # 1. API配置区域（URL和密钥输入）
        config_group = QGroupBox("API 配置")
        config_layout = QFormLayout()
        config_layout.setSpacing(12)
        config_layout.setContentsMargins(15, 15, 15, 15)
        
        # URL输入框（带清除按钮）
        url_entry = QLineEdit()
        url_entry.setPlaceholderText("请输入API端点URL...")
        url_entry.setClearButtonEnabled(True)
        
        # 密钥输入框（密码模式，带清除按钮）
        key_entry = QLineEdit()
        key_entry.setPlaceholderText("请输入认证密钥...")
        key_entry.setEchoMode(QLineEdit.Password)  # 隐藏输入内容
        key_entry.setClearButtonEnabled(True)
        
        # 输入变化时触发配置更新（延迟保存）
        url_entry.textChanged.connect(lambda text, api=api_name: self._on_config_edited(api))
        key_entry.textChanged.connect(lambda text, api=api_name: self._on_config_edited(api))
        
        config_layout.addRow("API URL:", url_entry)
        config_layout.addRow("API 密钥:", key_entry)
        
        # 自定义API添加删除按钮
        if is_custom:
            del_btn = QPushButton("删除此供应商")
            del_btn.setStyleSheet("QPushButton { color: #ff4444; }")  # 红色文本
            del_btn.clicked.connect(lambda: self.remove_custom_api(api_name))
            config_layout.addRow(del_btn)
            
        config_group.setLayout(config_layout)
        main_tab_layout.addWidget(config_group)
        
        # 2. 模型选择区域（模型列表和搜索）
        model_group = QGroupBox("模型选择")
        model_layout = QVBoxLayout(model_group)
        model_layout.setContentsMargins(15, 15, 15, 15)
        
        # 模型搜索框
        search_layout = QHBoxLayout()
        search_label = QLabel("搜索:")
        search_edit = QLineEdit()
        search_edit.setPlaceholderText("输入模型名称...")
        # 搜索文本变化时过滤模型列表
        search_edit.textChanged.connect(lambda text, api=api_name: self.filter_models(api, text))
        search_layout.addWidget(search_label)
        search_layout.addWidget(search_edit)
        model_layout.addLayout(search_layout)
        
        # 模型说明标签
        model_desc = QLabel("可用模型列表 (点击-添加/取消选用):")
        model_layout.addWidget(model_desc)
        
        # 模型列表（支持多选）
        model_list_widget = QListWidget()
        model_list_widget.setSelectionMode(QListWidget.MultiSelection)  # 允许多选
        model_list_widget.setAlternatingRowColors(True)  # 交替行颜色（视觉优化）
        model_layout.addWidget(model_list_widget)
        
        # 手动添加模型按钮
        add_model_btn = QPushButton("手动添加")
        add_model_btn.clicked.connect(lambda: self.add_manual_model(api_name))
        model_layout.addWidget(add_model_btn)
        
        # 模型选择变化时触发配置更新
        model_list_widget.itemSelectionChanged.connect(
            lambda api=api_name: self._on_config_edited(api)
        )
        
        main_tab_layout.addWidget(model_group, 5)  # 模型区域占较大空间
        self.tab_widget.addTab(tab_content, api_name)  # 添加到标签页容器
        # 存储当前API的UI组件（用于后续操作）
        self.api_widgets[api_name] = (url_entry, key_entry, model_list_widget, search_edit)
        
        # 记录自定义API
        if is_custom and api_name not in self.custom_apis:
            self.custom_apis.append(api_name)

    def add_manual_model(self, api_name: str):
        """
        手动为指定API供应商添加模型
        
        参数:
            api_name: 目标API供应商名称
        """
        # 弹出输入框获取模型名称
        model_name, ok = QInputDialog.getText(
            self, "添加模型", f"请输入要添加到{api_name}的模型名称:"
        )
        
        if ok and model_name:
            model_name = model_name.strip()
            if not model_name:
                QMessageBox.warning(self, "输入错误", "模型名称不能为空")
                return
                
            if api_name not in self.api_widgets:
                return
                
            # 获取模型列表控件
            _, _, list_widget, _ = self.api_widgets[api_name]
            
            # 检查模型是否已存在
            for i in range(list_widget.count()):
                item = list_widget.item(i)
                if item and item.text() == model_name:
                    QMessageBox.information(self, "已存在", f"模型 '{model_name}' 已在列表中")
                    return
                    
            # 添加新模型到列表和可用模型记录
            list_widget.addItem(model_name)
            if api_name not in self.available_models:
                self.available_models[api_name] = []
            self.available_models[api_name].append(model_name)
            self.available_models[api_name] = sorted(list(set(self.available_models[api_name])))  # 去重排序
            
            # 选中新添加的模型并滚动到可见位置
            for i in range(list_widget.count()):
                item = list_widget.item(i)
                if item and item.text() == model_name:
                    item.setSelected(True)
                    list_widget.scrollToItem(item)
                    break
                    
            self.status_label.setText(f"已添加模型: {model_name}")
            QTimer.singleShot(2000, lambda: self.status_label.setText(""))  # 2秒后清空提示
            
            # 触发配置更新
            self._on_config_edited(api_name)

    def _on_config_edited(self, api_name: str) -> None:
        """
        配置（URL、密钥、模型选择）变化时触发，延迟1秒保存（避免频繁操作）
        
        参数:
            api_name: 发生变化的API供应商名称
        """
        # 初始化阶段不触发保存
        if self.initializing:
            return
            
        # 为每个API维护一个定时器，延迟保存
        if api_name not in self.api_timers:
            timer = QTimer(self)
            timer.setSingleShot(True)  # 只触发一次
            timer.setInterval(1000)  # 延迟1秒
            timer.timeout.connect(lambda: self._validate_and_save(show_message=False))
            self.api_timers[api_name] = timer
        else:
            timer = self.api_timers[api_name]
        
        # 重置定时器（重新计时）
        if timer.isActive():
            timer.stop()
        timer.start()

    def _setup_update_button_animation(self):
        """初始化更新模型库按钮的动画（用于显示更新中状态）"""
        # 动画覆盖层（显示在按钮上方）
        self.update_btn_overlay = QWidget(self.update_btn)
        self.update_btn_overlay.setStyleSheet("background-color: rgba(173, 216, 230, 80);")  # 浅蓝色半透明
        self.update_btn_overlay.hide()
        self.update_btn_overlay.setAttribute(Qt.WA_TransparentForMouseEvents)  # 不响应鼠标事件
        
        # 透明度效果（用于淡出动画）
        self.opacity_effect = QGraphicsOpacityEffect(self.update_btn_overlay)
        self.opacity_effect.setOpacity(1.0)
        self.update_btn_overlay.setGraphicsEffect(self.opacity_effect)
        
        # 动画组（顺序执行宽度动画、淡出动画、重置动画）
        self.animation_group = QSequentialAnimationGroup(self)
        self.animation_group.setLoopCount(-1)  # 无限循环
        
        # 宽度动画（从0到按钮宽度，显示进度感）
        self.width_animation = QPropertyAnimation(self.update_btn_overlay, b"geometry")
        self.width_animation.setDuration(1500)  # 1.5秒
        self.width_animation.setEasingCurve(QEasingCurve.OutCubic)  # 缓动曲线
        
        # 淡出动画（透明度从1到0）
        self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_animation.setDuration(600)  # 0.6秒
        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.setEasingCurve(QEasingCurve.OutQuad)
        
        # 重置动画（恢复初始状态，准备下一次循环）
        self.reset_animation = QSequentialAnimationGroup()
        self.reset_opacity_anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.reset_opacity_anim.setDuration(0)  # 立即完成
        self.reset_opacity_anim.setStartValue(0.0)
        self.reset_opacity_anim.setEndValue(1.0)
        
        self.reset_geometry_anim = QPropertyAnimation(self.update_btn_overlay, b"geometry")
        self.reset_geometry_anim.setDuration(0)
        
        self.reset_animation.addAnimation(self.reset_opacity_anim)
        self.reset_animation.addAnimation(self.reset_geometry_anim)
        
        # 组合动画
        self.animation_group.addAnimation(self.width_animation)
        self.animation_group.addAnimation(self.fade_animation)
        self.animation_group.addAnimation(self.reset_animation)

    def _setup_save_button_animation(self):
        """初始化保存按钮的动画（用于显示保存中状态）"""
        # 动画覆盖层
        self.save_btn_overlay = QWidget(self.save_btn)
        self.save_btn_overlay.setStyleSheet("background-color: rgba(143, 188, 143, 80);")  # 浅绿色半透明
        self.save_btn_overlay.hide()
        self.save_btn_overlay.setAttribute(Qt.WA_TransparentForMouseEvents)
        
        # 透明度效果
        self.save_opacity_effect = QGraphicsOpacityEffect(self.save_btn_overlay)
        self.save_opacity_effect.setOpacity(1.0)
        self.save_btn_overlay.setGraphicsEffect(self.save_opacity_effect)
        
        # 动画组（只执行一次）
        self.save_animation_group = QSequentialAnimationGroup(self)
        self.save_animation_group.setLoopCount(1)
        
        # 宽度动画
        self.save_width_animation = QPropertyAnimation(self.save_btn_overlay, b"geometry")
        self.save_width_animation.setDuration(1500)
        self.save_width_animation.setEasingCurve(QEasingCurve.OutCubic)
        
        # 淡出动画
        self.save_fade_animation = QPropertyAnimation(self.save_opacity_effect, b"opacity")
        self.save_fade_animation.setDuration(600)
        self.save_fade_animation.setStartValue(1.0)
        self.save_fade_animation.setEndValue(0.0)
        self.save_fade_animation.setEasingCurve(QEasingCurve.OutQuad)
        
        # 动画完成后关闭窗口
        self.save_animation_group.finished.connect(self._on_save_animation_finished)
        
        self.save_animation_group.addAnimation(self.save_width_animation)
        self.save_animation_group.addAnimation(self.save_fade_animation)

    def start_update_animation(self):
        """启动更新按钮动画（更新模型库时）"""
        self.update_btn.setEnabled(False)  # 禁用按钮
        self.update_btn_overlay.setGeometry(0, 0, 0, self.update_btn.height())
        self.update_btn_overlay.show()
        self.update_btn_overlay.raise_()  # 显示在最上层
        
        # 设置动画参数（从0宽度到按钮宽度）
        end_width = self.update_btn.width()
        self.width_animation.setStartValue(QRect(0, 0, 0, self.update_btn.height()))
        self.width_animation.setEndValue(QRect(0, 0, end_width, self.update_btn.height()))
        self.reset_geometry_anim.setEndValue(QRect(0, 0, 0, self.update_btn.height()))
        self.animation_group.start()

    def stop_update_animation(self):
        """停止更新按钮动画（更新完成/出错时）"""
        self.update_btn.setEnabled(True)  # 恢复按钮可用
        if self.animation_group and self.animation_group.state() == QAbstractAnimation.Running:
            self.animation_group.stop()
        if self.update_btn_overlay:
            self.update_btn_overlay.hide()

    def start_save_animation(self):
        """启动保存按钮动画（保存配置时）"""
        self.save_in_progress = True
        self.save_btn.setFixedSize(self.save_btn.size())  # 固定按钮大小（避免动画中变形）
        self.save_btn.setText("取消")  # 按钮文本改为"取消"
        self.save_btn.setEnabled(True)
        self.save_btn_overlay.setGeometry(0, 0, 0, self.save_btn.height())
        self.save_btn_overlay.show()
        self.save_btn_overlay.raise_()
        
        # 设置动画参数
        end_width = self.save_btn.width()
        self.save_width_animation.setStartValue(QRect(0, 0, 0, self.save_btn.height()))
        self.save_width_animation.setEndValue(QRect(0, 0, end_width, self.save_btn.height()))
        self.save_animation_group.start()

    def stop_save_animation(self):
        """停止保存按钮动画（取消保存时）"""
        self.save_in_progress = False
        self.save_btn.setText("保存并关闭")  # 恢复文本
        if self.save_animation_group and self.save_animation_group.state() == QAbstractAnimation.Running:
            self.save_animation_group.stop()
        if self.save_btn_overlay:
            self.save_btn_overlay.hide()

    def on_update_models(self) -> None:
        """触发模型库更新（通过线程执行，避免界面卡顿）"""
        self.status_label.setText("正在更新模型库...")
        # 创建更新线程
        self.update_thread = APIConfigDialogUpdateModelThread(
            application_path=self.application_path, 
        )
        self.update_thread.started_signal.connect(
            lambda: self.status_label.setText("正在更新模型库..."))
        self.update_thread.finished_signal.connect(self._on_models_updated)  # 更新完成回调
        self.update_thread.error_signal.connect(  # 错误处理
            lambda msg: [self.status_label.setText(f"更新出错: {msg}"), self.stop_update_animation()])
        
        # 启动线程执行更新
        self.update_thread.start()
        self.start_update_animation()  # 显示更新动画

    def _on_models_updated(self, available_models: Dict[str, List[str]]) -> None:
        """
        模型库更新完成后的回调，合并手动添加的模型并更新UI
        
        参数:
            available_models: 新获取的可用模型列表
        """
        self.stop_update_animation()
        
        # 保留手动添加的模型（不在新更新列表中的模型）
        for api_name, models in self.available_models.items():
            if api_name in available_models:
                for model in models:
                    if model not in available_models[api_name]:
                        available_models[api_name].append(model)
                available_models[api_name] = sorted(list(set(available_models[api_name])))  # 去重排序
            else:
                available_models[api_name] = models  # 保留整个API的模型
        
        # 更新可用模型并刷新UI
        self.available_models = available_models
        selected_models_map = self.model_map_manager.get_model_map()
        self._populate_model_ui(available_models, selected_models_map)
        
        # 显示更新结果
        total_models = sum(len(models) for models in available_models.values())
        self.status_label.setText(f"模型库更新完成！共加载 {total_models} 个可用模型")

    def on_save_and_close(self):
        """处理保存并关闭逻辑（支持取消保存）"""
        if self.save_in_progress:
            # 正在保存时点击则取消
            self.stop_save_animation()
            self.status_label.setText("保存已取消")
            QTimer.singleShot(2000, lambda: self.status_label.setText(""))
            return
        
        # 执行保存并启动动画
        self.status_label.setText("正在保存配置...")
        self.start_save_animation()

    def _on_save_animation_finished(self):
        """保存动画完成后关闭窗口"""
        config=self._validate_and_save(show_message=True)
        self.save_btn_overlay.hide()
        self.save_in_progress = False
        self.notificationRequested.emit(f'模型列表更新完成。数量:{sum(map(len, config.values()))}','success')
        self.close()

    def add_custom_api(self) -> None:
        """添加自定义API供应商（通过输入框获取名称）"""
        name, ok = QInputDialog.getText(
            self, "添加自定义API供应商", "请输入供应商名称:", text="custom_api"
        )
        
        if ok and name:
            name = name.strip()
            if not name:
                QMessageBox.warning(self, "输入错误", "供应商名称不能为空")
                return
                
            if name in self.api_widgets:
                QMessageBox.warning(self, "名称冲突", "该供应商名称已存在")
                return
                
            # 创建标签页并保存配置
            self._create_api_tab(name, is_custom=True)
            self._validate_and_save(show_message=True)
            self.status_label.setText(f"已添加自定义供应商: {name}")
            QTimer.singleShot(2000, lambda: self.status_label.setText(""))

    def remove_custom_api(self, api_name: str) -> None:
        """
        删除自定义API供应商（包含配置和模型数据）
        
        参数:
            api_name: 要删除的API供应商名称
        """
        if api_name not in self.custom_apis:
            return
            
        # 确认删除
        reply = QMessageBox.question(
            self, "确认删除", 
            f"确定要删除'{api_name}'的配置吗?\n此操作不可恢复。",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                # 移除标签页
                widget = self.tab_widget.findChild(QWidget, api_name)
                if widget:
                    index = self.tab_widget.indexOf(widget)
                    if index != -1:
                        self.tab_widget.removeTab(index)
                        widget.deleteLater()
                
                # 清理数据
                if api_name in self.custom_apis:
                    self.custom_apis.remove(api_name)
                if api_name in self.api_widgets:
                    del self.api_widgets[api_name]
                if api_name in self.api_timers:
                    self.api_timers[api_name].stop()
                    del self.api_timers[api_name]
                if api_name in self.available_models:
                    del self.available_models[api_name]
                
                # 更新模型映射（移除该API的模型选择）
                current_map = self.model_map_manager.get_model_map()
                if api_name in current_map:
                    del current_map[api_name]
                    self.model_map_manager.save_model_map(current_map)
                
                # 保存配置并提示
                self._validate_and_save()
                self.status_label.setText(f"已删除供应商: {api_name}")
                QTimer.singleShot(2000, lambda: self.status_label.setText(""))
                
            except Exception as e:
                QMessageBox.critical(self, "删除错误", f"删除时发生错误: {str(e)}")

    def load_config(self) -> None:
        """从配置文件加载API配置（URL、密钥）和模型选择状态"""
        selected_models_map = self.model_map_manager.get_model_map()
        config_path = os.path.join(self.application_path, "api_config.ini")
        
        # 配置文件不存在时，用模型映射初始化
        if not os.path.exists(config_path):
            self.available_models = selected_models_map
            self._populate_model_ui(selected_models_map)
            return
            
        config = configparser.ConfigParser()
        try:
            config.read(config_path, encoding='utf-8')
            
            # 加载预设API配置
            for section in config.sections():
                if section in self.preset_apis and section in self.api_widgets:
                    url_entry, key_entry, _, search_edit = self.api_widgets[section]
                    # 阻塞信号（避免加载时触发保存）
                    url_entry.blockSignals(True)
                    key_entry.blockSignals(True)
                    search_edit.blockSignals(True)
                    url_entry.setText(config.get(section, "url", fallback=""))
                    key_entry.setText(config.get(section, "key", fallback=""))
                    # 恢复信号
                    url_entry.blockSignals(False)
                    key_entry.blockSignals(False)
                    search_edit.blockSignals(False)
                
                # 加载自定义API配置（自动创建标签页）
                elif section not in self.preset_apis and section not in self.api_widgets:
                    self._create_api_tab(section, is_custom=True)
                    if section in self.api_widgets:
                        url_entry, key_entry, _, search_edit = self.api_widgets[section]
                        url_entry.blockSignals(True)
                        key_entry.blockSignals(True)
                        search_edit.blockSignals(True)
                        url_entry.setText(config.get(section, "url", fallback=""))
                        key_entry.setText(config.get(section, "key", fallback=""))
                        url_entry.blockSignals(False)
                        key_entry.blockSignals(False)
                        search_edit.blockSignals(False)
            
            # 初始化可用模型并更新UI
            if not self.available_models:
                self.available_models = selected_models_map
            self._populate_model_ui(self.available_models, selected_models_map)

        except configparser.Error as e:
            QMessageBox.warning(self, "配置加载错误", f"配置文件格式错误:\n{str(e)}")

    def _populate_model_ui(self, available_models: Dict[str, List[str]], selected_models_map: Dict[str, List[str]] = None):
        """
        根据可用模型列表更新UI中的模型列表，并恢复选中状态
        
        参数:
            available_models: 可用模型列表
            selected_models_map: 已选择的模型列表（用于恢复选中状态）
        """
        selected_models_map = selected_models_map or {}
        for api_name, models in available_models.items():
            if api_name in self.api_widgets:
                _, _, list_widget, search_edit = self.api_widgets[api_name]
                # 断开信号（避免更新UI时触发保存）
                list_widget.itemSelectionChanged.disconnect()
                search_edit.blockSignals(True)
                try:
                    list_widget.clear()
                    # 添加模型到列表
                    for model in models:
                        list_widget.addItem(model)
                    # 恢复选中状态
                    if api_name in selected_models_map:
                        self._select_models(api_name, selected_models_map[api_name])
                finally:
                    # 恢复信号连接
                    list_widget.itemSelectionChanged.connect(
                        lambda api=api_name: self._on_config_edited(api)
                    )
                    search_edit.blockSignals(False)

    def _select_models(self, api_name: str, model_names: List[str]) -> None:
        """
        选中指定API供应商的目标模型
        
        参数:
            api_name: API供应商名称
            model_names: 需要选中的模型名称列表
        """
        if api_name not in self.api_widgets:
            return
            
        _, _, list_widget, _ = self.api_widgets[api_name]
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            if item and item.text() in model_names:
                item.setSelected(True)

    def _validate_and_save(self, show_message: bool = True) -> bool:
        """
        验证并保存当前配置（URL、密钥、模型选择）到文件
        
        参数:
            show_message: 是否显示保存结果提示
            
        返回:
            bool: 保存成功返回True，失败返回False
        """
        config = configparser.ConfigParser()
        config_data = {}  # 用于发射信号的配置数据
        selected_models_map = {}  # 模型选择状态（用于保存）
        
        # 收集各API的配置
        for api_name, widgets in self.api_widgets.items():
            url_entry, key_entry, list_widget, _ = widgets
            url = url_entry.text().strip()
            key = key_entry.text().strip()
            selected_models = [item.text() for item in list_widget.selectedItems()]
            
            # 保存到配置文件
            if not config.has_section(api_name):
                config.add_section(api_name)
            config.set(api_name, "url", url)
            config.set(api_name, "key", key)
            
            # 整理配置数据
            config_data[api_name] = {
                "url": url,
                "key": key,
                "models": selected_models
            }
            
            # 记录选中的模型
            if selected_models:
                selected_models_map[api_name] = selected_models

        try:
            # 保存配置文件
            config_path = os.path.join(self.application_path, "api_config.ini")
            with open(config_path, "w", encoding='utf-8') as f:
                config.write(f)
                
            # 保存模型选择状态
            self.model_map_manager.save_model_map(selected_models_map)
            
            # 显示提示（初始化阶段不显示）
            if not self.initializing and show_message:
                self.status_label.setText("配置已成功保存")
                QTimer.singleShot(3000, lambda: self.status_label.setText(""))  # 3秒后清空
                
            # 发射配置更新信号
            self.configUpdated.emit(config_data)
            return config_data
            
        except IOError as e:
            QMessageBox.critical(self, "保存失败", f"文件写入失败:\n{str(e)}")
            return False
        except Exception as e:
            QMessageBox.critical(self, "未知错误", f"保存时发生意外错误:\n{str(e)}")
            return False

    def filter_models(self, api_name: str, search_text: str) -> None:
        """
        根据搜索文本过滤模型列表，按匹配度排序
        
        参数:
            api_name: 目标API供应商名称
            search_text: 搜索文本
        """
        if api_name not in self.api_widgets:
            return
            
        _, _, list_widget, _ = self.api_widgets[api_name]
        
        # 保存当前选中的模型（过滤后恢复）
        selected_items = [item.text() for item in list_widget.selectedItems()]
        
        # 计算所有模型与搜索文本的匹配度
        items = []
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            text = item.text()
            score = self._calculate_match_score(text, search_text.lower())  # 匹配度得分
            items.append((score, text, item))
        
        # 按匹配度降序排序（得分高的在前）
        items.sort(key=lambda x: x[0], reverse=True)
        
        # 断开信号（避免排序时触发保存）
        list_widget.itemSelectionChanged.disconnect()
        try:
            # 清空并重新添加模型（按新顺序）
            list_widget.clear()
            for score, text, original_item in items:
                item = QListWidgetItem(text)
                list_widget.addItem(item)
                # 恢复选中状态
                if text in selected_items:
                    item.setSelected(True)
        finally:
            # 恢复信号连接
            list_widget.itemSelectionChanged.connect(
                lambda api=api_name: self._on_config_edited(api)
            )
        
        # 滚动到顶部
        if list_widget.count() > 0:
            list_widget.scrollToTop()

    def _calculate_match_score(self, text: str, search_text: str) -> int:
        """
        计算模型名称与搜索文本的匹配度得分（用于排序）
        
        参数:
            text: 模型名称
            search_text: 搜索文本（小写）
            
        返回:
            int: 匹配度得分（越高匹配度越好）
        """
        if not search_text:
            return 0  # 搜索为空时，所有模型得分相同（保持原顺序）
            
        text_lower = text.lower()
        
        # 完全匹配（最高优先级）
        if text_lower == search_text:
            return 100
        # 开头匹配（高优先级）
        if text_lower.startswith(search_text):
            return 90
        # 包含搜索文本（中等优先级，位置越靠前得分越高）
        if search_text in text_lower:
            return 80 - text_lower.find(search_text)
        # 单词开头匹配（低优先级）
        words = text_lower.split()
        for word in words:
            if word.startswith(search_text):
                return 50
        # 不匹配（最低优先级）
        return 0
    
if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QApplication
    app = QApplication(sys.argv)
    window = APIConfigWidget(application_path=r"C:\Users\kcji\Desktop\te\ChatWindowWithLLMApi")
    window.configUpdated.connect(print)
    with open(r'C:\Users\kcji\Desktop\te\ChatWindowWithLLMApi\theme\ds-r1-0528.qss',encoding='utf-8')as e:
        window.setStyleSheet(e.read())
    window.show()
    sys.exit(app.exec_())