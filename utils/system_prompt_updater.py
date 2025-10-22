import os
import json
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *

class FileManager:
    """文件管理类，负责JSON文件的读取和保存"""
    def __init__(self, folder_path="system_prompt_presets"):
        self.folder_path = folder_path
        if not os.path.exists(folder_path):
            os.makedirs(folder_path)
    
    def get_all_presets(self):
        """获取所有预设文件信息"""
        presets = []
        for filename in os.listdir(self.folder_path):
            if filename.endswith(".json"):
                file_path = os.path.join(self.folder_path, filename)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        presets.append({
                            "file_path": file_path,
                            "file_name": filename,
                            "name": data.get("name", ""),
                            "content": data.get("content", ""),
                            "post_history": data.get("post_history", "")
                        })
                except Exception as e:
                    print(f"Error reading {file_path}: {str(e)}")
        return presets
    
    def save_preset(self, file_path, data):
        """保存预设到文件"""
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=4, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Error saving {file_path}: {str(e)}")
            return False
    
    def create_new_preset(self, file_name, data):
        """创建新预设"""
        if not file_name.endswith(".json"):
            file_name += ".json"
        file_path = os.path.join(self.folder_path, file_name)
        return self.save_preset(file_path, data)
    
    def delete_preset(self, file_path):
        """删除预设文件"""
        try:
            os.remove(file_path)
            return True
        except Exception as e:
            print(f"Error deleting {file_path}: {str(e)}")
            return False

class SystemPromptUI(QWidget):
    update_system_prompt = pyqtSignal(str)
    
    def __init__(self,folder_path="system_prompt_presets"):
        super().__init__()
        

        self.setWindowTitle('system prompt')
        # 初始化文件管理器
        self.file_manager = FileManager(folder_path)

        screen_geometry = QApplication.primaryScreen().availableGeometry()
        
        width = int(screen_geometry.width() * 0.8)
        height = int(screen_geometry.height() * 0.8)
        
        left = (screen_geometry.width() - width) // 2
        top = (screen_geometry.height() - height) // 2
        
        self.setGeometry(left, top, width, height)

        # 当前选中的文件
        self.current_file = None
        
        # 主布局
        self.main_layout = QHBoxLayout(self)  # 直接设置布局到自身
        
        # 使用分割器
        self.splitter = QSplitter(Qt.Horizontal)
        self.main_layout.addWidget(self.splitter)
        
        # 左侧文件列表
        self.left_widget = QWidget()
        self.left_layout = QVBoxLayout(self.left_widget)
        
        self.file_list_label = QLabel("预设列表(感谢silly tavern)")
        self.left_layout.addWidget(self.file_list_label)
        
        self.file_list = QListWidget()
        self.file_list.itemSelectionChanged.connect(self.on_file_selected)
        self.left_layout.addWidget(self.file_list)
        
        # 右侧编辑区
        self.right_widget = QWidget()
        self.right_layout = QVBoxLayout(self.right_widget)
        
        # 文件名编辑
        self.name_layout = QHBoxLayout()
        self.name_label = QLabel("配置名称:")
        self.name_edit = QLineEdit()
        self.name_edit.textChanged.connect(self.on_content_changed)
        self.name_layout.addWidget(self.name_label)
        self.name_layout.addWidget(self.name_edit)
        self.right_layout.addLayout(self.name_layout)
        
        # 内容编辑
        self.content_label = QLabel("配置内容:")
        self.right_layout.addWidget(self.content_label)
        
        self.content_edit = QTextEdit()
        self.content_edit.textChanged.connect(self.on_content_changed)
        self.right_layout.addWidget(self.content_edit)
        
        info_layout=QHBoxLayout()

        name_user_label=QLabel(r'用户代称{{user}}=')
        self.name_user_edit=QLineEdit()

        info_layout.addWidget(name_user_label)
        info_layout.addWidget(self.name_user_edit)

        name_ai_label=QLabel(r'AI代称{{char}}=')
        self.name_ai_edit=QLineEdit()

        info_layout.addWidget(name_ai_label)
        info_layout.addWidget(self.name_ai_edit)

        self.right_layout.addLayout(info_layout)

        # 按钮区域
        self.button_layout = QHBoxLayout()
        
        self.new_button = QPushButton("新建配置")
        self.new_button.clicked.connect(self.create_new_config)
        self.button_layout.addWidget(self.new_button)
        
        self.delete_button = QPushButton("删除配置")
        self.delete_button.clicked.connect(self.delete_current_config)
        self.button_layout.addWidget(self.delete_button)
        
        self.save_button = QPushButton("保存更改")
        self.save_button.clicked.connect(self.save_current_config)
        self.save_button.setEnabled(False)
        self.button_layout.addWidget(self.save_button)
        
        # 添加发送内容按钮
        self.send_button = QPushButton("覆盖系统提示")
        self.send_button.clicked.connect(self.send_current_content)
        self.button_layout.addWidget(self.send_button)
        
        self.right_layout.addLayout(self.button_layout)
        
        # 添加左右部件到分割器
        self.splitter.addWidget(self.left_widget)
        self.splitter.addWidget(self.right_widget)
        self.splitter.setSizes([200, 700])
        
        # 状态变量
        self.is_modified = False

        # 内部变量
        self.default_current_filename='当前对话'
        self.ignore_changes = False
        
        # 加载初始文件列表
        self.load_file_list()
    
    def load_income_prompt(self,system_prompt,name={}):
        if self.is_modified and system_prompt != self.content_edit.toPlainText():
            # 给用户保存更改的机会
            reply = QMessageBox.question(
                self,
                "未保存的更改",
                "您有未保存的更改。是否要保存后再继续操作？",
                QMessageBox.Save | QMessageBox.Discard 
            )
            
            if reply == QMessageBox.Save:
                self.save_current_config(show_window=False)
                # 保存后继续操作
        if name:
            self.name_user_edit.setText(name['user'])
            self.name_ai_edit.setText(name['assistant'])
        
        # 查找现有的名为"当前对话.json"的文件
        existing_config = None
        filename = f"{self.default_current_filename}.json"
        file_path = os.path.join(self.file_manager.folder_path, filename)
        
        presets = self.file_manager.get_all_presets()
        for preset in presets:
            if preset["file_name"] == filename:
                existing_config = preset
                break
        
        # 如果是新创建或内容更新
        if not existing_config or existing_config["content"] != system_prompt:
            # 创建/更新配置
            self.create_new_config(self.default_current_filename, True, default_content=system_prompt)
        
        # 确保选中该文件
        found_index = -1
        for i in range(self.file_list.count()):
            if self.file_list.item(i).text() == filename:
                found_index = i
                break
        
        if found_index != -1:
            self.file_list.setCurrentRow(found_index)

    def load_file_list(self):
        """加载文件列表"""
        self.file_list.clear()
        presets = self.file_manager.get_all_presets()
        for preset in presets:
            self.file_list.addItem(preset["file_name"])
    
    def on_file_selected(self):
        """当选择文件时加载内容（修复循环保存问题）"""
        selected_items = self.file_list.selectedItems()
        if not selected_items:
            return  # 无选中项直接返回
        
        # 保存当前修改（如果有）
        if self.is_modified:
            # 阻塞列表信号，防止保存时刷新列表触发重复选择事件
            self.file_list.blockSignals(True)
            try:
                self.save_current_config(show_window=False)  # 不弹窗提示
            finally:
                self.file_list.blockSignals(False)  # 确保信号恢复
        
        # 重新获取选中项（可能因保存后列表刷新导致索引变化）
        selected_items = self.file_list.selectedItems()
        if not selected_items:
            return
        
        # 加载新选中的文件
        file_name = selected_items[0].text()
        presets = self.file_manager.get_all_presets()
        for preset in presets:
            if preset["file_name"] == file_name:
                self.current_file = preset["file_path"]
                
                # 临时忽略内容变化信号（避免程序加载触发修改标记）
                self.ignore_changes = True
                self.name_edit.setText(preset["name"])
                self.content_edit.setText(preset["content"])
                self.ignore_changes = False  # 恢复信号响应
                
                self.is_modified = False
                self.save_button.setEnabled(False)
                break

    def on_content_changed(self):
        """内容变化时标记为已修改（仅响应用户手动修改）"""
        if self.ignore_changes:  # 新增：程序自动修改时忽略
            return
        self.is_modified = True
        self.save_button.setEnabled(True)
    
    def create_new_config(self, name=None, ok=None, default_content='', select_new=True):
        """创建新配置文件"""
        if not name and not ok:
            name, ok = QInputDialog.getText(
                self, "新建配置", "请输入配置名称:"
            )

        if ok and name:
            # 检查文件名是否有效
            if not name.endswith(".json"):
                name += ".json"
            
            # 检查是否已存在
            file_path = os.path.join(self.file_manager.folder_path, name)
            #if os.path.exists(file_path):
            #    QMessageBox.warning(self, "文件已存在", "该文件名已存在，请使用其他名称")
            #    return
            
            # 创建新配置
            new_config = {
                "name": name.replace(".json", ""),
                "content": default_content,
                "post_history": ""
            }
            
            if self.file_manager.create_new_preset(name, new_config):
                if select_new:
                    self.load_file_list()
                    # 选择新创建的文件
                    for i in range(self.file_list.count()):
                        if self.file_list.item(i).text() == name:
                            self.file_list.setCurrentRow(i)
                            break
            else:
                QMessageBox.critical(self, "创建失败", "无法创建新配置文件")
    
    def delete_current_config(self):
        """删除当前选中的配置文件"""
        selected_items = self.file_list.selectedItems()
        if not selected_items:
            return
        
        file_name = selected_items[0].text()
        reply = QMessageBox.question(
            self, "确认删除",
            f"确定要删除配置文件 '{file_name}' 吗?",
            QMessageBox.Yes | QMessageBox.No
        )
        
        if reply == QMessageBox.Yes:
            presets = self.file_manager.get_all_presets()
            for preset in presets:
                if preset["file_name"] == file_name:
                    if self.file_manager.delete_preset(preset["file_path"]):
                        self.file_list.takeItem(self.file_list.currentRow())
                        self.current_file = None
                        self.name_edit.clear()
                        self.content_edit.clear()
                    else:
                        QMessageBox.critical(self, "删除失败", "无法删除配置文件")
                    break
    
    def save_current_config(self, show_window=True):
        """保存当前配置文件（优化列表刷新逻辑）"""
        if not self.current_file or not self.is_modified:
            return False  # 无修改则不保存
        
        # 获取当前数据
        name = self.name_edit.text().strip()
        content = self.content_edit.toPlainText()
        
        if not name:
            if show_window:
                QMessageBox.warning(self, "无效名称", "配置名称不能为空")
            return False
        
        # 构建保存数据
        save_data = {
            "name": name,
            "content": content,
            "post_history": ""
        }
        
        # 检查是否需要重命名
        new_file_name = f"{name}.json"
        new_file_path = os.path.join(self.file_manager.folder_path, new_file_name)
        old_file_name = os.path.basename(self.current_file)
        
        # 文件名变更时删除旧文件
        file_renamed = new_file_path != self.current_file
        if file_renamed and os.path.exists(self.current_file):
            os.remove(self.current_file)
        self.current_file = new_file_path
        
        # 保存文件
        if self.file_manager.save_preset(self.current_file, save_data):
            self.is_modified = False
            self.save_button.setEnabled(False)
            
            # 仅在文件名变更或列表项变化时刷新列表
            if file_renamed or old_file_name not in [self.file_list.item(i).text() for i in range(self.file_list.count())]:
                # 刷新列表前记录新文件名，用于恢复选中
                current_selected_name = new_file_name
                # 阻塞信号防止刷新时触发选择事件
                self.file_list.blockSignals(True)
                self.load_file_list()  # 刷新列表
                self.file_list.blockSignals(False)
                
                # 恢复选中状态（定位新文件名）
                for i in range(self.file_list.count()):
                    if self.file_list.item(i).text() == current_selected_name:
                        self.file_list.setCurrentRow(i)
                        break
            
            if show_window:
                QMessageBox.information(self, "保存成功", "配置文件已成功保存")
            return True
        else:
            if show_window:
                QMessageBox.critical(self, "保存失败", "无法保存配置文件")
            return False    
    def send_current_content(self):
        """发送当前内容"""
        # 保存当前状态以便恢复
        was_modified = self.is_modified
        old_file = self.current_file
        
        try:
            # 阻塞文件列表的信号，避免触发on_file_selected
            self.file_list.blockSignals(True)
            
            content = self.content_edit.toPlainText().strip()
            
            # 创建新配置
            self.create_new_config(self.default_current_filename, True, default_content=content)
            
            # 手动设置当前文件为新创建的配置
            new_file_path = os.path.join(
                self.file_manager.folder_path, 
                f"{self.default_current_filename}.json"
            )
            self.current_file = new_file_path
            self.is_modified = False
            self.save_button.setEnabled(False)
            
            # 发送内容信号
            self.update_system_prompt.emit(content)
            QMessageBox.information(self, "发送成功", "配置内容已发送")
        
        finally:
            # 恢复文件列表信号
            self.file_list.blockSignals(False)
            
            # 恢复原始状态
            self.is_modified = was_modified
            self.current_file = old_file

class SystemPromptComboBox(QWidget):
    update_system_prompt = pyqtSignal(str)
    request_open_editor = pyqtSignal()
    class _Entry:
        __slots__ = ("display_name", "mtime_ns", "size", "content_hash")
        def __init__(self, display_name="", mtime_ns=0, size=0, content_hash=None):
            self.display_name = display_name
            self.mtime_ns = mtime_ns
            self.size = size
            self.content_hash = content_hash  # 针对 content 相等匹配用

    def __init__(
        self,
        folder_path='system_prompt_presets',
        parent=None,
        include_placeholder=True,
        current_filename_base='当前对话',
        auto_emit_on_external_change=False,
    ):
        super().__init__(parent)
        self.folder_path = folder_path
        self.include_placeholder = include_placeholder
        self.current_filename_base = current_filename_base
        self.auto_emit_on_external_change = auto_emit_on_external_change
        self.special_current_display = "临时修改的系统提示"
        self.setContentsMargins(0, 0, 0, 0)

        # UI
        self.combo = QComboBox()
        self.combo.currentIndexChanged.connect(self._on_current_index_changed)
        self.combo.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        self.open_btn = QToolButton()
        self.open_btn.setText('+')
        self.open_btn.setToolTip('打开完整编辑器')
        self.open_btn.clicked.connect(lambda: self.request_open_editor.emit())
        self.open_btn.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)
        layout.addWidget(self.combo, 1)
        layout.addWidget(self.open_btn, 0)

        # 状态
        self.ignore_combo_signals = False
        self._reload_timer = QTimer(self)
        self._reload_timer.setSingleShot(True)
        self._reload_timer.setInterval(200)  # 适度增大，进一步合并频繁变更
        self._reload_timer.timeout.connect(self._do_reload)

        # 文件系统监听（仅监听目录 + 当前选中文件）
        self.watcher = QFileSystemWatcher(self)
        self.watcher.directoryChanged.connect(self._on_dir_changed)
        self.watcher.fileChanged.connect(self._on_file_changed)
        self._watched_dir = None
        self._watched_current_file = None

        # 缓存：path -> _Entry
        self._cache = {}
        # 快照：用于避免重复重建下拉框
        self._items_snapshot = []  # list[(display_name, file_path)]
        self._last_target_data = None  # 上次目标 selection data

        self.reload_presets(keep_current=False)

    def set_folder_path(self, folder_path):
        if self.folder_path == folder_path:
            return
        self.folder_path = folder_path
        self.reload_presets(keep_current=False)

    def schedule_reload(self, delay_ms=200):
        self._reload_timer.start(delay_ms)

    def _on_dir_changed(self, _):
        self.schedule_reload()

    def _on_file_changed(self, path):
        # 仅监听当前选中文件；发生变化时根据策略处理
        if self.auto_emit_on_external_change and path and path == self.combo.currentData():
            self._maybe_emit_current()
        # 无论是否发射，都做一次增量刷新（保留选择）
        self.schedule_reload()

    def _do_reload(self):
        self.reload_presets(keep_current=True)

    def _current_dialog_path(self):
        if not self.current_filename_base:
            return None
        return os.path.join(self.folder_path, f"{self.current_filename_base}.json")

    def _hash_text(self, text):
        import hashlib
        return hashlib.blake2b(text.encode('utf-8'), digest_size=16).hexdigest()

    def _read_json_min(self, file_path):
        # 读取 json 并返回 (display_name, content, ok)
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                data = json.load(f)
            display_name = data.get('name') or os.path.splitext(os.path.basename(file_path))[0]
            content = data.get('content', '')
            return display_name, content, True
        except Exception:
            return os.path.splitext(os.path.basename(file_path))[0], '', False

    def _stat(self, path):
        try:
            st = os.stat(path)
            return st.st_mtime_ns, st.st_size
        except Exception:
            return 0, 0

    def _scan_json_files(self):
        # 更快的目录扫描
        try:
            with os.scandir(self.folder_path) as it:
                return [entry.path for entry in it if entry.is_file() and entry.name.endswith('.json')]
        except FileNotFoundError:
            os.makedirs(self.folder_path, exist_ok=True)
            return []

    def reload_presets(self, keep_current=True):
        previous_data = self.combo.currentData() if keep_current else None

        # 确保目录存在
        if not os.path.isdir(self.folder_path):
            os.makedirs(self.folder_path, exist_ok=True)

        current_json_path = self._current_dialog_path()

        # 扫描文件列表
        all_file_paths = self._scan_json_files()

        # 当前对话内容与哈希（用于匹配来源）
        current_content = None
        current_hash = None
        if current_json_path and os.path.isfile(current_json_path):
            _, current_content, ok = self._read_json_min(current_json_path)
            if ok:
                current_hash = self._hash_text(current_content)

        # 更新缓存（仅对变更文件重读）
        for file_path in all_file_paths:
            mtime_ns, size = self._stat(file_path)
            entry = self._cache.get(file_path)
            if entry and entry.mtime_ns == mtime_ns and entry.size == size:
                continue  # 未变化
            display_name, content, ok = self._read_json_min(file_path)
            content_hash = self._hash_text(content) if ok else None
            self._cache[file_path] = self._Entry(display_name=display_name, mtime_ns=mtime_ns, size=size, content_hash=content_hash)

        # 清理已删除文件的缓存
        cache_keys = set(self._cache.keys())
        living = set(all_file_paths)
        for k in list(cache_keys - living):
            self._cache.pop(k, None)

        # 生成普通条目（排除“当前对话.json”）
        items = []
        for file_path in all_file_paths:
            if current_json_path and os.path.abspath(file_path) == os.path.abspath(current_json_path):
                continue
            entry = self._cache.get(file_path)
            display_name = entry.display_name if entry else os.path.splitext(os.path.basename(file_path))[0]
            items.append((display_name, file_path))

        # 排序
        items.sort(key=lambda x: x[0].casefold())

        # 尝试定位“当前对话”的来源（通过 content_hash）
        matched_path = None
        if current_hash is not None:
            for _, file_path in items:
                entry = self._cache.get(file_path)
                if entry and entry.content_hash == current_hash:
                    matched_path = file_path
                    break

        # 计算需要呈现的最终列表（含占位与临时项）
        final_items = []
        if self.include_placeholder:
            final_items.append(("选择系统提示…", None))

        added_special = False
        if current_json_path and os.path.isfile(current_json_path) and matched_path is None:
            final_items.append((self.special_current_display, current_json_path))
            added_special = True

        final_items.extend(items)

        # 如果列表未变化且目标选择未变化，避免重建 UI
        target_data = None
        if matched_path is not None:
            target_data = matched_path
        elif added_special:
            target_data = current_json_path
        elif keep_current and previous_data:
            target_data = previous_data

        same_list = (self._items_snapshot == final_items)
        same_target = (self._last_target_data == target_data)

        if not same_list:
            self.ignore_combo_signals = True
            self.combo.blockSignals(True)
            self.combo.clear()
            for display_name, file_path in final_items:
                self.combo.addItem(display_name, file_path)
            # 选择
            if target_data is not None:
                idx = self.combo.findData(target_data)
                if idx >= 0:
                    self.combo.setCurrentIndex(idx)
                else:
                    self.combo.setCurrentIndex(0 if self.include_placeholder else (0 if self.combo.count() > 0 else -1))
            else:
                self.combo.setCurrentIndex(0 if self.include_placeholder else (0 if self.combo.count() > 0 else -1))
            self.combo.blockSignals(False)
            self.ignore_combo_signals = False
            self._items_snapshot = list(final_items)
        else:
            # 列表未变，仅按需调整选择
            if target_data is not None and not same_target:
                idx = self.combo.findData(target_data)
                if idx >= 0 and idx != self.combo.currentIndex():
                    self.ignore_combo_signals = True
                    self.combo.blockSignals(True)
                    self.combo.setCurrentIndex(idx)
                    self.combo.blockSignals(False)
                    self.ignore_combo_signals = False

        self._last_target_data = target_data

        # 更新 watcher：仅监听目录 + 当前选中文件
        self._update_watchers(current_selected=self.combo.currentData())

        # 外部文件变化后，如果当前选中项被修改，自动再次发射
        if self.auto_emit_on_external_change:
            self._maybe_emit_current()

    def _update_watchers(self, current_selected):
        # 目录
        if self._watched_dir != self.folder_path:
            try:
                if self._watched_dir:
                    self.watcher.removePath(self._watched_dir)
            except Exception:
                pass
            try:
                self.watcher.addPath(self.folder_path)
                self._watched_dir = self.folder_path
            except Exception:
                self._watched_dir = None

        # 当前选中文件
        if self._watched_current_file and self._watched_current_file != current_selected:
            try:
                self.watcher.removePath(self._watched_current_file)
            except Exception:
                pass
            self._watched_current_file = None

        if current_selected and os.path.exists(current_selected) and self._watched_current_file != current_selected:
            try:
                self.watcher.addPath(current_selected)
                self._watched_current_file = current_selected
            except Exception:
                self._watched_current_file = None

    def _maybe_emit_current(self):
        if self.include_placeholder and self.combo.currentIndex() == 0:
            return
        file_path = self.combo.currentData()
        if not file_path or not os.path.exists(file_path):
            return
        # 只读取一次并发射
        try:
            _, content, ok = self._read_json_min(file_path)
            content = content if ok else ''
        except Exception:
            content = ''
        self.update_system_prompt.emit(content)

    def _on_current_index_changed(self, index):
        if self.ignore_combo_signals:
            return
        file_path = self.combo.itemData(index)
        # 更新仅监听当前选中文件
        self._update_watchers(current_selected=file_path)
        if not file_path:
            return
        try:
            _, content, ok = self._read_json_min(file_path)
            if not ok:
                raise ValueError("JSON 解析失败")
        except Exception as e:
            QMessageBox.warning(self, "读取失败", f"无法读取预设：\n{os.path.basename(file_path)}\n{e}")
            return
        self.update_system_prompt.emit(content)

    # 可选辅助方法
    def select_by_name(self, display_name):
        idx = self.combo.findText(display_name, Qt.MatchFixedString)
        if idx >= 0:
            self.combo.setCurrentIndex(idx)

    def select_by_filename(self, filename):
        file_path = os.path.join(self.folder_path, filename)
        idx = self.combo.findData(file_path)
        if idx >= 0:
            self.combo.setCurrentIndex(idx)

if __name__ == "__main__":
    app = QApplication([])
    window = SystemPromptUI()
    window.show()
    app.exec_()
