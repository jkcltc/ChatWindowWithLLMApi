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

        self.resize(900,600)
        
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
        
        # 加载初始文件列表
        self.load_file_list()
    
    def load_income_prompt(self,system_prompt):
        if self.is_modified:
            # 给用户保存更改的机会
            reply = QMessageBox.question(
                self,
                "未保存的更改",
                "您有未保存的更改。是否要保存后再继续操作？",
                QMessageBox.Save | QMessageBox.Discard | QMessageBox.Cancel
            )
            
            if reply == QMessageBox.Cancel:
                return  # 用户取消操作
            elif reply == QMessageBox.Save:
                self.save_current_config(show_window=False)
                # 保存后继续操作
        
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
        """当选择文件时加载内容"""
        selected_items = self.file_list.selectedItems()
        if not selected_items:
            return
        
        # 保存当前修改
        if self.is_modified:
            self.save_current_config()

        # 加载新文件
        file_name = selected_items[0].text()
        presets = self.file_manager.get_all_presets()
        for preset in presets:
            if preset["file_name"] == file_name:
                self.current_file = preset["file_path"]
                self.name_edit.setText(preset["name"])
                self.content_edit.setText(preset["content"])
                self.is_modified = False
                self.save_button.setEnabled(False)
                break
    
    def on_content_changed(self):
        """内容变化时标记为已修改"""
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
    
    def save_current_config(self,show_window=True):
        """保存当前配置文件"""
        if not self.current_file or not self.is_modified:
            return
        
        # 获取当前数据
        name = self.name_edit.text().strip()
        content = self.content_edit.toPlainText()
        
        if not name:
            QMessageBox.warning(self, "无效名称", "配置名称不能为空")
            return
        
        # 构建保存数据
        save_data = {
            "name": name,
            "content": content,
            "post_history": ""
        }
        
        # 检查是否需要重命名
        new_file_path = os.path.join(
            self.file_manager.folder_path, 
            f"{name}.json"
        )
        
        # 如果文件名已更改
        if new_file_path != self.current_file:
            # 删除旧文件
            if os.path.exists(self.current_file):
                os.remove(self.current_file)
            self.current_file = new_file_path
        
        # 保存文件
        if self.file_manager.save_preset(self.current_file, save_data):
            self.is_modified = False
            self.save_button.setEnabled(False)
            self.load_file_list()  # 刷新列表（如果名称改变）
            if show_window:
                QMessageBox.information(self, "保存成功", "配置文件已成功保存")
        else:
            QMessageBox.critical(self, "保存失败", "无法保存配置文件")
    
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

if __name__ == "__main__":
    app = QApplication([])
    window = SystemPromptUI()
    window.show()
    window.load_income_prompt('aaa')
    app.exec_()
