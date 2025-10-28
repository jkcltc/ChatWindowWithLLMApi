import json
import os
from collections import defaultdict
from PyQt6.QtCore import pyqtSignal,QThread,Qt
from PyQt6.QtWidgets import (QWidget, QVBoxLayout, QHBoxLayout, QPushButton,
                             QLabel, QLineEdit, QFileDialog, QProgressBar,
                             QTabWidget, QTreeWidget, QTreeWidgetItem,QGroupBox,QHeaderView,QMessageBox)
from PyQt6.QtGui import QFont
class TokenAnalyzer:
    """Token分析逻辑类"""
    
    def __init__(self):
        self.reset()
    
    def reset(self):
        self.stats = defaultdict(lambda: {
            'count': 0,
            'total': 0,
            'min': float('inf'),
            'max': float('-inf'),
            'types': set()
        })
        self.message_count = 0
        self.total_tokens = 0
        self.token_fields = set()
        self.string_fields = set()
    
    def analyze(self, log_data):
        """分析聊天记录数据"""
        self.reset()
        
        if not isinstance(log_data, list):
            raise ValueError("日志数据必须是字典列表")
        
        for message in log_data:
            self.message_count += 1
            self._process_item(message, "")
        
        # 计算字符串字段的平均长度
        for field in self.string_fields:
            stats = self.stats[field]
            if stats['count'] > 0:
                stats['avg'] = stats['total'] / stats['count']
        
        return self.get_results()
    
    def _process_item(self, item, path):
        """递归处理数据项"""
        if isinstance(item, dict):
            for key, value in item.items():
                new_path = f"{path}.{key}" if path else key
                self._process_item(value, new_path)
        elif isinstance(item, list):
            for idx, value in enumerate(item):
                new_path = f"{path}[{idx}]"
                self._process_item(value, new_path)
        elif isinstance(item, (int, float)):
            self._update_numeric_stat(path, item)
            # 特别处理token相关字段
            if "token" in path.lower():
                self.token_fields.add(path)
                self.total_tokens += item
        elif isinstance(item, str):
            self.string_fields.add(path)
            self._update_string_stat(path, len(item))
        elif item is not None:
            # 处理其他数据类型
            type_name = type(item).__name__
            self.stats[path]['types'].add(type_name)
            self.stats[path]['count'] += 1
    
    def _update_numeric_stat(self, field, value):
        """更新数值类型字段的统计"""
        stats = self.stats[field]
        stats['count'] += 1
        stats['total'] += value
        stats['min'] = min(stats['min'], value)
        stats['max'] = max(stats['max'], value)
        stats['types'].add(type(value).__name__)
    
    def _update_string_stat(self, field, length):
        """更新字符串类型字段的统计"""
        stats = self.stats[field]
        stats['count'] += 1
        stats['total'] += length
        stats['min'] = min(stats['min'], length)
        stats['max'] = max(stats['max'], length)
        stats['types'].add('str')
    
    def get_results(self):
        """获取分析结果"""
        return {
            'message_count': self.message_count,
            'total_tokens': self.total_tokens,
            'stats': dict(self.stats),
            'token_fields': list(self.token_fields),
            'string_fields': list(self.string_fields)
        }


class AnalysisWorker(QThread):
    """文件分析工作线程"""
    progress = pyqtSignal(int)
    finished = pyqtSignal(dict)
    error = pyqtSignal(str)
    
    def __init__(self, files):
        super().__init__()
        self.files = files
    
    def run(self):
        total = len(self.files)
        analyzer = TokenAnalyzer()
        combined_results = {
            'files_analyzed': len(self.files),
            'message_count': 0,
            'total_tokens': 0,
            'stats': defaultdict(lambda: {
                'count': 0,
                'total': 0,
                'min': float('inf'),
                'max': float('-inf'),
                'types': set()
            }),
            'token_fields': set(),
            'string_fields': set()
        }
        
        for idx, file_path in enumerate(self.files):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    log_data = json.load(f)
                
                results = analyzer.analyze(log_data)
                
                # 合并统计信息
                combined_results['message_count'] += results['message_count']
                combined_results['total_tokens'] += results['total_tokens']
                
                for field, stats in results['stats'].items():
                    combined = combined_results['stats'][field]
                    combined['count'] += stats['count']
                    combined['total'] += stats['total']
                    combined['min'] = min(combined['min'], stats['min'])
                    combined['max'] = max(combined['max'], stats['max'])
                    combined['types'] |= stats['types']
                
                combined_results['token_fields'] |= set(results['token_fields'])
                combined_results['string_fields'] |= set(results['string_fields'])
                
                self.progress.emit(int((idx + 1) / total * 100))
            except Exception as e:
                self.error.emit(f"处理文件 {os.path.basename(file_path)} 时出错: {str(e)}")
                return
        
        # 将defaultdict转换为普通字典便于序列化
        combined_results['stats'] = dict(combined_results['stats'])
        combined_results['token_fields'] = list(combined_results['token_fields'])
        combined_results['string_fields'] = list(combined_results['string_fields'])
        
        self.finished.emit(combined_results)


class TokenAnalysisManager:
    """Token分析管理器，供UI调用"""
    
    def __init__(self):
        self.worker = None
    
    def analyze_dict(self, data_dict):
        """直接分析字典数据"""
        analyzer = TokenAnalyzer()
        return analyzer.analyze(data_dict)
    
    def analyze_file(self, file_path):
        """分析单个文件"""
        return self.analyze_files([file_path])
    
    def analyze_folder(self, folder_path):
        """分析整个文件夹的JSON文件"""
        json_files = []
        for file in os.listdir(folder_path):
            if file.endswith('.json'):
                json_files.append(os.path.join(folder_path, file))
        
        if not json_files:
            raise ValueError(f"文件夹 {folder_path} 中没有JSON文件")
        
        return self.analyze_files(json_files)
    
    def analyze_files(self, file_list):
        """使用工作线程分析文件列表"""
        if self.worker and self.worker.isRunning():
            self.worker.terminate()
            
        self.worker = AnalysisWorker(file_list)
        return self.worker


class TokenAnalysisWidget(QWidget):
    """聊天记录用量分析组件"""
    
    def __init__(self, parent=None):
        super().__init__(parent)
        self.manager = TokenAnalysisManager()
        self.current_data = None
        self.init_ui()
        
    def init_ui(self):
        """初始化用户界面"""
        self.setWindowTitle('聊天记录用量分析')
        self.setMinimumSize(900, 700)
        
        # 创建主布局
        main_layout = QVBoxLayout()
        main_layout.setSpacing(10)
        
        # 添加控制面板
        control_group = QGroupBox("控制面板")
        control_layout = QHBoxLayout()
        
        # 路径选择部分
        self.path_input = QLineEdit()
        self.path_input.setPlaceholderText("选择文件或文件夹路径，或直接粘贴JSON内容")
        self.path_input.setMinimumWidth(300)
        control_layout.addWidget(self.path_input)
        
        self.browse_file_btn = QPushButton("选择文件")
        self.browse_file_btn.clicked.connect(self.browse_file)
        control_layout.addWidget(self.browse_file_btn)
        
        self.browse_folder_btn = QPushButton("选择文件夹")
        self.browse_folder_btn.clicked.connect(self.browse_folder)
        control_layout.addWidget(self.browse_folder_btn)
        
        self.realtime_btn = QPushButton("分析实时数据")
        self.realtime_btn.clicked.connect(self.analyze_realtime)
        self.realtime_btn.setToolTip("分析通过set_data()方法传入的数据")
        control_layout.addWidget(self.realtime_btn)
        
        self.clear_btn = QPushButton("清空结果")
        self.clear_btn.clicked.connect(self.clear_results)
        control_layout.addWidget(self.clear_btn)
        
        control_group.setLayout(control_layout)
        main_layout.addWidget(control_group)
        
        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)
        
        # 分析状态标签
        self.status_label = QLabel("就绪")
        main_layout.addWidget(self.status_label)
        
        # 创建结果展示区域
        self.result_tabs = QTabWidget()
        
        # 摘要标签页
        self.summary_tab = QWidget()
        summary_layout = QVBoxLayout()
        self.summary_tree = QTreeWidget()
        self.summary_tree.setHeaderLabels(["项目", "值"])
        self.summary_tree.setColumnWidth(0, 200)
        self.summary_tree.header().setSectionResizeMode(1, QHeaderView.ResizeMode.Stretch)
        summary_layout.addWidget(self.summary_tree)
        self.summary_tab.setLayout(summary_layout)
        self.result_tabs.addTab(self.summary_tab, "摘要")
        
        # 字段统计标签页
        self.stats_tab = QWidget()
        stats_layout = QVBoxLayout()
        self.stats_tree = QTreeWidget()
        self.stats_tree.setHeaderLabels(["字段路径", "计数", "总和", "最小值", "最大值", "平均值", "类型"])
        stats_layout.addWidget(self.stats_tree)
        self.stats_tab.setLayout(stats_layout)
        self.result_tabs.addTab(self.stats_tab, "字段统计")
        
        # Token字段标签页
        self.token_fields_tab = QWidget()
        token_fields_layout = QVBoxLayout()
        self.token_fields_list = QTreeWidget()
        self.token_fields_list.setHeaderLabels(["Token字段路径"])
        token_fields_layout.addWidget(self.token_fields_list)
        self.token_fields_tab.setLayout(token_fields_layout)
        self.result_tabs.addTab(self.token_fields_tab, "Token字段")
        
        # 字符串字段标签页
        self.string_fields_tab = QWidget()
        string_fields_layout = QVBoxLayout()
        self.string_fields_list = QTreeWidget()
        self.string_fields_list.setHeaderLabels(["字符串字段路径"])
        string_fields_layout.addWidget(self.string_fields_list)
        self.string_fields_tab.setLayout(string_fields_layout)
        self.result_tabs.addTab(self.string_fields_tab, "字符串字段")
        
        main_layout.addWidget(self.result_tabs)
        self.setLayout(main_layout)
        
        # 初始化状态
        self.last_analyzed_path = ""
    
    def browse_file(self):
        """浏览文件对话框并立即开始分析"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "选择JSON文件", "", "JSON Files (*.json);;All Files (*)"
        )
        if file_path:
            self.path_input.setText(file_path)
            # 只有在选择新文件时才分析
            if file_path != self.last_analyzed_path:
                self.start_analysis(file_path)
    
    def browse_folder(self):
        """浏览文件夹对话框并立即开始分析"""
        folder_path = QFileDialog.getExistingDirectory(
            self, "选择包含JSON文件的文件夹"
        )
        if folder_path:
            self.path_input.setText(folder_path)
            # 只有在选择新文件夹时才分析
            if folder_path != self.last_analyzed_path:
                self.start_analysis(folder_path)
    
    def start_analysis(self, path):
        """开始分析指定的路径（文件或文件夹）"""
        self.status_label.setText(f"正在分析: {os.path.basename(path)}")
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        
        # 根据路径类型选择分析方式
        if os.path.isfile(path):
            self.worker = self.manager.analyze_file(path)
            self.last_analyzed_path = path
        elif os.path.isdir(path):
            self.worker = self.manager.analyze_folder(path)
            self.last_analyzed_path = path
        else:
            try:
                # 尝试解析为JSON数据
                data = json.loads(path)
                self.current_data = data
                self.analyze_current_data()
                return
            except json.JSONDecodeError:
                QMessageBox.warning(self, "无效输入", "请输入有效的文件路径、文件夹路径或JSON数据")
                return
        
        # 连接信号
        self.worker.progress.connect(self.progress_bar.setValue)
        self.worker.finished.connect(self.on_analysis_finished)
        self.worker.error.connect(self.on_analysis_error)
        self.worker.start()
    
    def analyze_realtime(self):
        """分析实时数据"""
        if self.current_data:
            self.status_label.setText("正在分析实时数据...")
            self.progress_bar.setVisible(True)
            self.progress_bar.setValue(0)
            # 在子线程中执行实时分析
            QThread.msleep(50)  # 短暂延迟确保进度条可见
            self.analyze_current_data()
        else:
            QMessageBox.information(self, "无数据", "请先设置数据")
    
    def analyze_current_data(self):
        """分析当前数据"""
        try:
            results = self.manager.analyze_dict(self.current_data)
            # 更新摘要统计项
            self.update_summary_results(results)
            # 显示完整结果
            self.display_results(results)
            self.progress_bar.setValue(100)
            self.status_label.setText("实时数据分析完成!")
        except Exception as e:
            QMessageBox.critical(self, "分析错误", f"分析数据时出错: {str(e)}")
            self.progress_bar.setVisible(False)
            self.status_label.setText(f"分析出错: {str(e)}")
    
    def set_data(self, data):
        """
        设置要分析的数据（外部调用）
        可接受类型：
        1. 文件路径 (str)
        2. 文件夹路径 (str)
        3. 字典 (聊天记录数据)
        """
        if isinstance(data, list):
            # 直接设置字典数据
            self.current_data = data
            self.path_input.setText("实时数据 - 准备分析")
            self.path_input.setEnabled(False)
            self.analyze_realtime()
        elif isinstance(data, str):
            # 检查是文件还是文件夹路径
            if os.path.isfile(data) or os.path.isdir(data):
                self.path_input.setText(data)
                # 立即开始分析
                self.start_analysis(data)
            else:
                # 尝试解析为JSON数据
                try:
                    data_dict = json.loads(data)
                    self.current_data = data_dict
                    self.path_input.setText("JSON字符串 - 准备分析")
                    self.path_input.setEnabled(False)
                    self.analyze_realtime()
                except json.JSONDecodeError:
                    self.last_analyzed_path=''
                    QMessageBox.warning(self, "无效输入", "输入的字符串既不是有效路径，也不是有效的JSON数据")
        else:
            QMessageBox.warning(self, "无效输入", "只接受文件路径、文件夹路径或聊天历史数据")
    
    def on_analysis_finished(self, results):
        """分析完成处理"""
        self.progress_bar.setVisible(False)
        # 更新摘要统计项
        self.update_summary_results(results)
        # 显示完整结果
        self.display_results(results)
        self.status_label.setText(f"分析完成! 已处理 {len(self.manager.worker.files)} 个文件")
    
    def on_analysis_error(self, error_msg):
        """分析错误处理"""
        self.progress_bar.setVisible(False)
        self.status_label.setText(f"错误: {error_msg}")
        QMessageBox.critical(self, "分析错误", error_msg)
    
    def update_summary_results(self, results):
        """更新摘要统计结果，添加content和reasoning_content总字数统计"""
        # 显示摘要
        self.summary_tree.clear()
        
        # 基础统计
        summary_items = [
            ("分析的文件数", results.get('files_analyzed', 1)),
            ("总消息数", results['message_count']),
            ("总Tokens", results['total_tokens']),
            ("Token字段数", len(results['token_fields'])),
            ("字符串字段数", len(results['string_fields']))
        ]
        
        # 特殊统计 - content和reasoning_content总字数
        total_content_len = 0
        total_reasoning_content_len = 0
        
        # 查找content字段
        content_fields = [f for f in results['stats'] if f.endswith('.content') or f == 'content']
        for field in content_fields:
            if 'total' in results['stats'][field]:
                total_content_len += results['stats'][field]['total']
        
        # 查找reasoning_content字段
        reasoning_fields = [f for f in results['stats'] if f.endswith('.reasoning_content') or f == 'reasoning_content']
        for field in reasoning_fields:
            if 'total' in results['stats'][field]:
                total_reasoning_content_len += results['stats'][field]['total']
        
        # 添加特殊统计到摘要
        summary_items.append(("总Content字数", total_content_len))
        summary_items.append(("总Reasoning Content字数", total_reasoning_content_len))
        
        # 添加到UI
        for label, value in summary_items:
            item = QTreeWidgetItem([str(label), str(value)])
            if label in ("总Content字数", "总Reasoning Content字数"):
                font = QFont()
                font.setBold(True)
                item.setFont(0, font)
                item.setFont(1, font)
            self.summary_tree.addTopLevelItem(item)
    
    def display_results(self, results):
        """显示完整分析结果"""
        # 显示字段统计
        self.stats_tree.clear()
        
        for field, stats in results['stats'].items():
            avg = stats.get('avg', stats['total'] / stats['count'] if stats['count'] else 0)
            
            item = QTreeWidgetItem([
                field,
                str(stats['count']),
                str(stats['total']),
                str(stats['min']),
                str(stats['max']),
                f"{avg:.2f}",
                ', '.join(stats['types'])
            ])
            
            # 高亮显示content和reasoning_content字段
            if field.endswith('.content') or field == 'content':
                for i in range(7):
                    item.setBackground(i, Qt.GlobalColor.yellow)
            elif field.endswith('.reasoning_content') or field == 'reasoning_content':
                for i in range(7):
                    item.setBackground(i, Qt.GlobalColor.cyan)
            
            self.stats_tree.addTopLevelItem(item)
        
        # 调整列宽
        for i in range(self.stats_tree.columnCount()):
            self.stats_tree.resizeColumnToContents(i)
        
        # 显示Token字段
        self.token_fields_list.clear()
        for field in results['token_fields']:
            item = QTreeWidgetItem([field])
            self.token_fields_list.addTopLevelItem(item)
        
        # 显示字符串字段
        self.string_fields_list.clear()
        for field in results['string_fields']:
            item = QTreeWidgetItem([field])
            self.string_fields_list.addTopLevelItem(item)
    
    def clear_results(self):
        """清空所有结果"""
        self.summary_tree.clear()
        self.stats_tree.clear()
        self.token_fields_list.clear()
        self.string_fields_list.clear()
        self.path_input.clear()
        self.progress_bar.setVisible(False)
        self.status_label.setText("就绪")
        self.current_data = None
        self.last_analyzed_path = ""
        
        # 重置manager状态
        self.manager = TokenAnalysisManager()
        
        # 更新路径输入框状态
        self.path_input.setEnabled(True)
        self.path_input.setPlaceholderText("选择文件或文件夹路径，或直接粘贴JSON内容")

if __name__ == "__main__":
    from PyQt6.QtWidgets import QApplication
    app = QApplication([])
    window = TokenAnalysisWidget()
    window.show()
    app.exec()