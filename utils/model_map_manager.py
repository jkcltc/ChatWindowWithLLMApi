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
    # 保持原有代码不变
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
    # 保持原有代码不变
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
        config.read(config_path)
        
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


class APIConfigDialogUpdateModelThread(QObject):
    # 保持原有代码不变
    started_signal = pyqtSignal()
    finished_signal = pyqtSignal(dict)
    error_signal = pyqtSignal(str)

    def run(self, application_path='') -> None:
        try:
            self.started_signal.emit()
            available_models = ModelListUpdater.update(application_path)
            self.finished_signal.emit(available_models)
        except Exception as e:
            self.error_signal.emit(str(e))


class APIConfigWidget(QWidget):
    configUpdated = pyqtSignal(dict)
    initializationCompleted = pyqtSignal(dict)

    def __init__(self, parent: Optional[QWidget] = None, application_path=''):
        super().__init__(parent)
        self.preset_apis = [
            "baidu", "deepseek", "siliconflow", "tencent", "novita", "ollama"
        ]
        self.custom_apis = []
        self.application_path = application_path
        self.api_widgets: Dict[str, Tuple[QLineEdit, QLineEdit, QListWidget]] = {}
        self.available_models: Dict[str, List[str]] = {}
        self.api_timers = {}
        self.update_btn_overlay = None
        self.update_animation_group = None
        # 新增保存按钮动画相关变量
        self.save_btn_overlay = None
        self.save_animation_group = None
        self.save_in_progress = False  # 标记保存流程是否在进行中
        
        # 添加初始化状态标志
        self.initializing = True  # 初始化阶段为True，完成后设为False

        if application_path:
            model_map_path = os.path.join(application_path, ModelMapManager._DEFAULT_FILE_PATH)
            self.model_map_manager = ModelMapManager(model_map_path)
        else:
            self.model_map_manager = ModelMapManager()
        
        self._initialize_ui()
        self._setup_update_button_animation()
        self._setup_save_button_animation()  # 初始化保存按钮动画
        self.load_config()
        self.adjustSize()
        
        screen_geometry = QApplication.primaryScreen().availableGeometry()
        width = int(screen_geometry.width() * 0.3)
        height = int(screen_geometry.height() * 0.8)
        left = (screen_geometry.width() - width) // 2
        top = (screen_geometry.height() - height) // 2
        self.setGeometry(left, top, width, height)
        self.setWindowTitle("API 配置管理")

        self.initializationCompleted.emit(self.available_models)
        # 初始化完成，更新状态标志
        self.initializing = False

    def _initialize_ui(self) -> None:
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(15, 15, 15, 15)
        main_layout.setSpacing(15)
        
        title_label = QLabel("API 配置管理")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.West)
        self.tab_widget.setDocumentMode(True)
        self.tab_widget.setElideMode(Qt.ElideNone)
        main_layout.addWidget(self.tab_widget, 1)
        
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)
        button_layout.addStretch(1)
        
        self.add_custom_btn = QPushButton("+ 添加自定义API供应商")
        self.add_custom_btn.setFixedHeight(40)
        self.add_custom_btn.clicked.connect(self.add_custom_api)
        button_layout.addWidget(self.add_custom_btn)
        
        self.update_btn = QPushButton("更新模型库")
        self.update_btn.setFixedHeight(40)
        self.update_btn.clicked.connect(self.on_update_models)
        button_layout.addWidget(self.update_btn)
        
        # 修改保存按钮文本和点击事件
        self.save_btn = QPushButton("保存并关闭")
        self.save_btn.setFixedHeight(40)
        self.save_btn.clicked.connect(self.on_save_and_close)  # 连接到新的处理函数
        button_layout.addWidget(self.save_btn)
        
        main_layout.addLayout(button_layout)
        
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setWordWrap(True)
        main_layout.addWidget(self.status_label)

        self._setup_preset_apis()

    def _setup_preset_apis(self) -> None:
        for api_name in self.preset_apis:
            self._create_api_tab(api_name, is_custom=False)

    def _create_api_tab(self, api_name: str, is_custom: bool = True) -> None:
        tab_content = QWidget()
        tab_content.setObjectName(api_name)
        main_tab_layout = QVBoxLayout(tab_content)
        main_tab_layout.setContentsMargins(15, 15, 15, 15)
        main_tab_layout.setSpacing(15)
        
        config_group = QGroupBox("API 配置")
        config_layout = QFormLayout()
        config_layout.setSpacing(12)
        config_layout.setContentsMargins(15, 15, 15, 15)
        
        url_entry = QLineEdit()
        url_entry.setPlaceholderText("请输入API端点URL...")
        url_entry.setClearButtonEnabled(True)
        
        key_entry = QLineEdit()
        key_entry.setPlaceholderText("请输入认证密钥...")
        key_entry.setEchoMode(QLineEdit.Password)
        key_entry.setClearButtonEnabled(True)
        
        # 连接信号（初始化时会被暂时阻塞）
        url_entry.textChanged.connect(lambda text, api=api_name: self._on_config_edited(api))
        key_entry.textChanged.connect(lambda text, api=api_name: self._on_config_edited(api))
        
        config_layout.addRow("API URL:", url_entry)
        config_layout.addRow("API 密钥:", key_entry)
        
        if is_custom:
            del_btn = QPushButton("删除此供应商")
            del_btn.setStyleSheet("QPushButton { color: #ff4444; }")
            del_btn.clicked.connect(lambda: self.remove_custom_api(api_name))
            config_layout.addRow(del_btn)
            
        config_group.setLayout(config_layout)
        main_tab_layout.addWidget(config_group)
        
        model_group = QGroupBox("模型选择")
        model_layout = QVBoxLayout(model_group)
        model_layout.setContentsMargins(15, 15, 15, 15)
        
        model_desc = QLabel("可用模型列表 (点击-添加/取消选用):")
        model_layout.addWidget(model_desc)
        
        model_list_widget = QListWidget()
        model_list_widget.setSelectionMode(QListWidget.MultiSelection)
        model_list_widget.setAlternatingRowColors(True)
        model_layout.addWidget(model_list_widget)
        
        # 添加"添加模型"按钮
        add_model_btn = QPushButton("手动添加")
        add_model_btn.clicked.connect(lambda: self.add_manual_model(api_name))
        model_layout.addWidget(add_model_btn)
        
        # 连接模型选择信号（初始化时会被暂时阻塞）
        model_list_widget.itemSelectionChanged.connect(
            lambda api=api_name: self._on_config_edited(api)
        )
        
        main_tab_layout.addWidget(model_group, 5)
        self.tab_widget.addTab(tab_content, api_name)
        self.api_widgets[api_name] = (url_entry, key_entry, model_list_widget)
        
        if is_custom and api_name not in self.custom_apis:
            self.custom_apis.append(api_name)

    def add_manual_model(self, api_name: str):
        """手动添加模型到指定API供应商的模型列表"""
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
            _, _, list_widget = self.api_widgets[api_name]
            
            # 检查模型是否已存在
            for i in range(list_widget.count()):
                item = list_widget.item(i)
                if item and item.text() == model_name:
                    QMessageBox.information(self, "已存在", f"模型 '{model_name}' 已在列表中")
                    return
                    
            # 添加新模型到列表
            list_widget.addItem(model_name)
            
            # 如果该API供应商不在available_models中，则创建一个条目
            if api_name not in self.available_models:
                self.available_models[api_name] = []
                
            # 将新模型添加到available_models
            self.available_models[api_name].append(model_name)
            # 去重并排序
            self.available_models[api_name] = sorted(list(set(self.available_models[api_name])))
            
            # 选中新添加的模型
            for i in range(list_widget.count()):
                item = list_widget.item(i)
                if item and item.text() == model_name:
                    item.setSelected(True)
                    # 滚动到新添加的项
                    list_widget.scrollToItem(item)
                    break
                    
            self.status_label.setText(f"已添加模型: {model_name}")
            QTimer.singleShot(2000, lambda: self.status_label.setText(""))
            
            # 触发配置保存
            self._on_config_edited(api_name)

    def _on_config_edited(self, api_name: str) -> None:
        if api_name not in self.api_timers:
            timer = QTimer(self)
            timer.setSingleShot(True)
            timer.setInterval(1000)
            timer.timeout.connect(lambda: self._validate_and_save(show_message=False))
            self.api_timers[api_name] = timer
        else:
            timer = self.api_timers[api_name]
        
        if timer.isActive():
            timer.stop()
        timer.start()

    def _setup_update_button_animation(self):
        self.update_btn_overlay = QWidget(self.update_btn)
        self.update_btn_overlay.setStyleSheet("background-color: rgba(173, 216, 230, 80);")
        self.update_btn_overlay.hide()
        self.update_btn_overlay.setAttribute(Qt.WA_TransparentForMouseEvents)
        
        self.opacity_effect = QGraphicsOpacityEffect(self.update_btn_overlay)
        self.opacity_effect.setOpacity(1.0)
        self.update_btn_overlay.setGraphicsEffect(self.opacity_effect)
        
        self.animation_group = QSequentialAnimationGroup(self)
        self.animation_group.setLoopCount(-1)
        
        self.width_animation = QPropertyAnimation(self.update_btn_overlay, b"geometry")
        self.width_animation.setDuration(1500)
        self.width_animation.setEasingCurve(QEasingCurve.OutCubic)
        
        self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_animation.setDuration(600)
        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.setEasingCurve(QEasingCurve.OutQuad)
        
        self.reset_animation = QSequentialAnimationGroup()
        self.reset_opacity_anim = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.reset_opacity_anim.setDuration(0)
        self.reset_opacity_anim.setStartValue(0.0)
        self.reset_opacity_anim.setEndValue(1.0)
        
        self.reset_geometry_anim = QPropertyAnimation(self.update_btn_overlay, b"geometry")
        self.reset_geometry_anim.setDuration(0)
        
        self.reset_animation.addAnimation(self.reset_opacity_anim)
        self.reset_animation.addAnimation(self.reset_geometry_anim)
        self.animation_group.addAnimation(self.width_animation)
        self.animation_group.addAnimation(self.fade_animation)
        self.animation_group.addAnimation(self.reset_animation)

    # 新增保存按钮动画设置
    def _setup_save_button_animation(self):
        self.save_btn_overlay = QWidget(self.save_btn)
        self.save_btn_overlay.setStyleSheet("background-color: rgba(143, 188, 143, 80);")  # 浅绿色背景
        self.save_btn_overlay.hide()
        self.save_btn_overlay.setAttribute(Qt.WA_TransparentForMouseEvents)
        
        self.save_opacity_effect = QGraphicsOpacityEffect(self.save_btn_overlay)
        self.save_opacity_effect.setOpacity(1.0)
        self.save_btn_overlay.setGraphicsEffect(self.save_opacity_effect)
        
        self.save_animation_group = QSequentialAnimationGroup(self)
        self.save_animation_group.setLoopCount(1)  # 只播放一次
        
        self.save_width_animation = QPropertyAnimation(self.save_btn_overlay, b"geometry")
        self.save_width_animation.setDuration(1500)
        self.save_width_animation.setEasingCurve(QEasingCurve.OutCubic)
        
        self.save_fade_animation = QPropertyAnimation(self.save_opacity_effect, b"opacity")
        self.save_fade_animation.setDuration(600)
        self.save_fade_animation.setStartValue(1.0)
        self.save_fade_animation.setEndValue(0.0)
        self.save_fade_animation.setEasingCurve(QEasingCurve.OutQuad)
        
        # 动画完成后触发关闭窗口
        self.save_animation_group.finished.connect(self._on_save_animation_finished)
        
        self.save_animation_group.addAnimation(self.save_width_animation)
        self.save_animation_group.addAnimation(self.save_fade_animation)

    def start_update_animation(self):
        self.update_btn.setEnabled(False)
        self.update_btn_overlay.setGeometry(0, 0, 0, self.update_btn.height())
        self.update_btn_overlay.show()
        self.update_btn_overlay.raise_()
        
        end_width = self.update_btn.width()
        self.width_animation.setStartValue(QRect(0, 0, 0, self.update_btn.height()))
        self.width_animation.setEndValue(QRect(0, 0, end_width, self.update_btn.height()))
        self.reset_geometry_anim.setEndValue(QRect(0, 0, 0, self.update_btn.height()))
        self.animation_group.start()

    def stop_update_animation(self):
        self.update_btn.setEnabled(True)
        if self.animation_group and self.animation_group.state() == QAbstractAnimation.Running:
            self.animation_group.stop()
        if self.update_btn_overlay:
            self.update_btn_overlay.hide()

    # 新增保存按钮动画启动方法
    def start_save_animation(self):
        self.save_in_progress = True
        self.save_btn.setFixedSize(self.save_btn.size())
        self.save_btn.setText("取消")  # 更改按钮文本为"取消"
        self.save_btn.setEnabled(True)  # 确保按钮可点击以取消
        self.save_btn_overlay.setGeometry(0, 0, 0, self.save_btn.height())
        self.save_btn_overlay.show()
        self.save_btn_overlay.raise_()
        
        end_width = self.save_btn.width()
        self.save_width_animation.setStartValue(QRect(0, 0, 0, self.save_btn.height()))
        self.save_width_animation.setEndValue(QRect(0, 0, end_width, self.save_btn.height()))
        self.save_animation_group.start()

    # 新增保存按钮动画停止方法
    def stop_save_animation(self):
        self.save_in_progress = False
        self.save_btn.setText("保存并关闭")  # 恢复按钮文本
        if self.save_animation_group and self.save_animation_group.state() == QAbstractAnimation.Running:
            self.save_animation_group.stop()
        if self.save_btn_overlay:
            self.save_btn_overlay.hide()

    def on_update_models(self) -> None:
        self.status_label.setText("正在更新模型库...")
        self.update_thread = APIConfigDialogUpdateModelThread()
        self.update_thread.started_signal.connect(
            lambda: self.status_label.setText("正在更新模型库..."))
        self.update_thread.finished_signal.connect(self._on_models_updated)
        self.update_thread.error_signal.connect(
            lambda msg: [self.status_label.setText(f"更新出错: {msg}"), self.stop_update_animation()])
        
        runner = threading.Thread(
            target=self.update_thread.run, 
            args=(self.application_path,)
        )
        runner.start()
        self.start_update_animation()

    def _on_models_updated(self, available_models: Dict[str, List[str]]) -> None:
        self.stop_update_animation()
        
        # 保留手动添加的模型
        for api_name, models in self.available_models.items():
            # 如果API在新更新的模型列表中
            if api_name in available_models:
                # 检查每个模型是否是手动添加的
                for model in models:
                    if model not in available_models[api_name]:
                        # 保留手动添加的模型
                        available_models[api_name].append(model)
                # 去重并排序
                available_models[api_name] = sorted(list(set(available_models[api_name])))
            else:
                # 如果API不在新更新的列表中，保留所有模型
                available_models[api_name] = models
        
        self.available_models = available_models
        selected_models_map = self.model_map_manager.get_model_map()
        self._populate_model_ui(available_models, selected_models_map)
        
        total_models = sum(len(models) for models in available_models.values())
        self.status_label.setText(f"模型库更新完成！共加载 {total_models} 个可用模型")

    # 新增保存并关闭的处理函数
    def on_save_and_close(self):
        if self.save_in_progress:
            # 如果正在保存流程中（按钮显示"取消"），则停止保存
            self.stop_save_animation()
            self.status_label.setText("保存已取消")
            QTimer.singleShot(2000, lambda: self.status_label.setText(""))
            return
        
        # 执行保存操作
        if self._validate_and_save(show_message=True):
            self.status_label.setText("正在保存配置...")
            self.start_save_animation()  # 启动保存动画

    # 新增动画完成后的处理函数
    def _on_save_animation_finished(self):
        self.save_btn_overlay.hide()
        self.save_in_progress = False
        self.close()  # 动画完成后关闭窗口

    def add_custom_api(self) -> None:
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
                
            self._create_api_tab(name, is_custom=True)
            self._validate_and_save(show_message=True)
            self.status_label.setText(f"已添加自定义供应商: {name}")
            QTimer.singleShot(2000, lambda: self.status_label.setText(""))

    def remove_custom_api(self, api_name: str) -> None:
        if api_name not in self.custom_apis:
            return
            
        reply = QMessageBox.question(
            self, "确认删除", 
            f"确定要删除'{api_name}'的配置吗?\n此操作不可恢复。",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            try:
                widget = self.tab_widget.findChild(QWidget, api_name)
                if widget:
                    index = self.tab_widget.indexOf(widget)
                    if index != -1:
                        self.tab_widget.removeTab(index)
                        widget.deleteLater()
                
                if api_name in self.custom_apis:
                    self.custom_apis.remove(api_name)
                    
                if api_name in self.api_widgets:
                    del self.api_widgets[api_name]
                
                if api_name in self.api_timers:
                    self.api_timers[api_name].stop()
                    del self.api_timers[api_name]
                
                if api_name in self.available_models:
                    del self.available_models[api_name]
                
                current_map = self.model_map_manager.get_model_map()
                if api_name in current_map:
                    del current_map[api_name]
                    self.model_map_manager.save_model_map(current_map)
                
                self._validate_and_save()
                self.status_label.setText(f"已删除供应商: {api_name}")
                QTimer.singleShot(2000, lambda: self.status_label.setText(""))
                
            except Exception as e:
                QMessageBox.critical(self, "删除错误", f"删除时发生错误: {str(e)}")

    def load_config(self) -> None:
        selected_models_map = self.model_map_manager.get_model_map()
        config_path = os.path.join(self.application_path, "api_config.ini")
        
        if not os.path.exists(config_path):
            self.available_models = selected_models_map
            self._populate_model_ui(selected_models_map)
            return
            
        config = configparser.ConfigParser()
        try:
            config.read(config_path)
            
            for section in config.sections():
                # 处理预设API
                if section in self.preset_apis and section in self.api_widgets:
                    url_entry, key_entry, _ = self.api_widgets[section]
                    # 阻塞信号，避免初始化时触发保存
                    url_entry.blockSignals(True)
                    key_entry.blockSignals(True)
                    url_entry.setText(config.get(section, "url", fallback=""))
                    key_entry.setText(config.get(section, "key", fallback=""))
                    # 恢复信号
                    url_entry.blockSignals(False)
                    key_entry.blockSignals(False)
                
                # 处理自定义API
                elif section not in self.preset_apis and section not in self.api_widgets:
                    self._create_api_tab(section, is_custom=True)
                    if section in self.api_widgets:
                        url_entry, key_entry, _ = self.api_widgets[section]
                        url_entry.blockSignals(True)
                        key_entry.blockSignals(True)
                        url_entry.setText(config.get(section, "url", fallback=""))
                        key_entry.setText(config.get(section, "key", fallback=""))
                        url_entry.blockSignals(False)
                        key_entry.blockSignals(False)
            
            if not self.available_models:
                self.available_models = selected_models_map
            self._populate_model_ui(self.available_models, selected_models_map)

        except configparser.Error as e:
            QMessageBox.warning(self, "配置加载错误", f"配置文件格式错误:\n{str(e)}")

    def _populate_model_ui(self, available_models: Dict[str, List[str]], selected_models_map: Dict[str, List[str]] = None):
        selected_models_map = selected_models_map or {}
        for api_name, models in available_models.items():
            if api_name in self.api_widgets:
                _, _, list_widget = self.api_widgets[api_name]
                # 断开选择信号，避免初始化时触发保存
                list_widget.itemSelectionChanged.disconnect()
                try:
                    list_widget.clear()
                    for model in models:
                        list_widget.addItem(model)
                    # 设置选中状态
                    if api_name in selected_models_map:
                        self._select_models(api_name, selected_models_map[api_name])
                finally:
                    # 恢复信号连接
                    list_widget.itemSelectionChanged.connect(
                        lambda api=api_name: self._on_config_edited(api)
                    )

    def _select_models(self, api_name: str, model_names: List[str]) -> None:
        if api_name not in self.api_widgets:
            return
            
        _, _, list_widget = self.api_widgets[api_name]
        for i in range(list_widget.count()):
            item = list_widget.item(i)
            if item and item.text() in model_names:
                item.setSelected(True)

    def _validate_and_save(self, show_message: bool = True) -> bool:
        """修改为返回布尔值表示保存是否成功"""
        config = configparser.ConfigParser()
        config_data = {}
        selected_models_map = {}
        
        for api_name, (url_entry, key_entry, list_widget) in self.api_widgets.items():
            url = url_entry.text().strip()
            key = key_entry.text().strip()
            selected_models = [item.text() for item in list_widget.selectedItems()]
            
            if not config.has_section(api_name):
                config.add_section(api_name)
            config.set(api_name, "url", url)
            config.set(api_name, "key", key)
            
            config_data[api_name] = {
                "url": url,
                "key": key,
                "models": selected_models
            }
            
            if selected_models:
                selected_models_map[api_name] = selected_models

        try:
            config_path = os.path.join(self.application_path, "api_config.ini")
            with open(config_path, "w", encoding='utf-8') as f:
                config.write(f)
                
            self.model_map_manager.save_model_map(selected_models_map)
            
            if not self.initializing and show_message:
                self.status_label.setText("配置已成功保存")
                QTimer.singleShot(3000, lambda: self.status_label.setText(""))
                
            self.configUpdated.emit(config_data)
            return True  # 保存成功
            
        except IOError as e:
            QMessageBox.critical(self, "保存失败", f"文件写入失败:\n{str(e)}")
            return False  # 保存失败
        except Exception as e:
            QMessageBox.critical(self, "未知错误", f"保存时发生意外错误:\n{str(e)}")
            return False  # 保存失败


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