import sys,threading,openai,os,configparser,json
from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
from theme_manager import ThemeSelector
MODEL_MAP={#临时测试用
  "baidu": [
    "deepseek-r1-distill-qwen-7b",
    "qwen3-8b"
  ],
  "deepseek": [
    "deepseek-chat",
    "deepseek-reasoner"
  ],
  "siliconflow": [
    "deepseek-ai/DeepSeek-V3",
    "Qwen/Qwen2-7B-Instruct",
    "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B"
  ]
}

class ConvergenceDialogueOptiUI(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        # 移除窗口标题和几何尺寸设置，因为现在是部件而不是主窗口
        
        # 创建滚动区域
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        content_widget = QWidget()
        scroll.setWidget(content_widget)
        
        # 主容器布局（用于放置滚动区域）
        main_container = QVBoxLayout(self)
        main_container.addWidget(scroll)
        main_container.setContentsMargins(0, 0, 0, 0)  # 移除外边距
        
        # 内容布局（在滚动区域内）
        main_layout = QVBoxLayout(content_widget)
        main_layout.setSpacing(15)
        
        # 添加标题和流程图引导（保持不变）
        title_label = QLabel("汇流对话优化")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        
        guide_label = QLabel(
            "工作流说明: 请按顺序使用各层功能。从请求并发层开始，逐层处理数据，最终获得优化结果。\n"
            "↓ 表示流程方向，每层处理后将结果传递给下一层"
        )
        guide_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(guide_label)
        
        # 以下部分保持不变...
        top_layout = QHBoxLayout()
        self.layer_spin = QSpinBox()
        self.layer_spin.setRange(2, 5)
        self.layer_spin.setValue(4)
        self.layer_spin.setPrefix("流程层数: ")
        self.layer_spin.valueChanged.connect(self.update_layer_visibility)
        
        top_layout.addWidget(self.layer_spin)
        top_layout.addStretch(1)

        self.settings_btn = QPushButton("设置")
        top_layout.addStretch(1)
        top_layout.addWidget(self.settings_btn)

        self.layer_container = QVBoxLayout()
        self.layer_container.setSpacing(30)
        
        self.create_layer1()
        self.create_layer2()
        self.create_layer3()
        self.create_layer4()
        self.create_layer5()
        
        main_layout.addLayout(top_layout)
        main_layout.addLayout(self.layer_container)
        main_layout.addStretch(1)
        
        self.update_layer_visibility()
        self.add_flow_arrows()
    
    def add_flow_arrows(self):
        # 移除当前所有箭头
        for i in reversed(range(self.layer_container.count())):
            item = self.layer_container.itemAt(i)
            if item.widget() and item.widget().property("flow_arrow"):
                self.layer_container.removeWidget(item.widget())
        
        # 添加新箭头（仅在可见层之间）
        visible_layers = []
        for i in range(self.layer_container.count()):
            item = self.layer_container.itemAt(i)
            if isinstance(item.widget(), QGroupBox) and item.widget().isVisible():
                visible_layers.append(item.widget())
        
        for i in range(len(visible_layers) - 1):
            arrow_label = QLabel("↓")  # 使用简单文本箭头
            arrow_label.setAlignment(Qt.AlignCenter)
            arrow_label.setProperty("flow_arrow", True)  # 标记为流程箭头
            
            # 在层和箭头之间添加间距
            next_layer_index = self.layer_container.indexOf(visible_layers[i+1])
            self.layer_container.insertWidget(
                next_layer_index, 
                arrow_label
            )
    
    def create_layer1(self):
        """创建请求并发层 - 修改为水平布局"""
        self.layer1 = QGroupBox("1. 请求并发层")
        layout = QVBoxLayout()
        
        # 并发设置
        concurrent_layout = QHBoxLayout()
        concurrent_layout.addWidget(QLabel("并发数量:"))
        
        self.concurrent_spin = QSpinBox()
        self.concurrent_spin.setRange(1, 10)
        self.concurrent_spin.setValue(3)
        self.concurrent_spin.valueChanged.connect(self.update_model_groups)
        concurrent_layout.addWidget(self.concurrent_spin)
        concurrent_layout.addStretch(1)
        
        # 水平布局的模型容器
        models_container = QWidget()
        models_layout = QHBoxLayout(models_container)
        models_layout.setSpacing(8)
        
        self.model_groups = []
        
        # 初始模型组
        for i in range(3):
            group = self.create_model_group(i+1)
            models_layout.addWidget(group)
            self.model_groups.append(group)
        
        layout.addLayout(concurrent_layout)
        layout.addWidget(models_container)
        
        # 添加流程说明
        self.layer1_guide = QLabel("↑ 同时请求多个AI模型，获取不同结果")
        self.layer1_guide.setAlignment(Qt.AlignRight)
        layout.addWidget(self.layer1_guide)
        
        self.layer1.setLayout(layout)
        self.layer_container.addWidget(self.layer1)
    
    def create_model_group(self, index):
        """创建单个模型组"""
        group = QGroupBox(f"模型 {index}")
        group_layout = QVBoxLayout()
        
        # 供应商选择
        vendor_layout = QHBoxLayout()
        vendor_layout.addWidget(QLabel("供应商:"))
        
        vendor_combo = QComboBox()
        vendor_combo.addItems(MODEL_MAP.keys())
        vendor_layout.addWidget(vendor_combo)
        vendor_layout.addStretch(1)
        
        # 模型选择
        model_layout = QHBoxLayout()
        model_layout.addWidget(QLabel("模型:"))
        
        model_combo = QComboBox()
        model_combo.addItems(MODEL_MAP[vendor_combo.currentText()])
        model_layout.addWidget(model_combo)
        model_layout.addStretch(1)
        
        # 响应显示
        response_text = QTextEdit()
        response_text.setReadOnly(True)
        response_text.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        response_text.setPlaceholderText("模型响应将显示在这里...")
        
        group_layout.addLayout(vendor_layout)
        group_layout.addLayout(model_layout)
        group_layout.addWidget(response_text)
        
        # 存储组件的引用
        group.setProperty("vendor", vendor_combo)
        group.setProperty("model", model_combo)
        group.setProperty("response", response_text)
        def update_models():
            """当供应商变化时更新模型列表"""
            vendor = vendor_combo.currentText()
            current_model = model_combo.currentText()
            
            # 获取新的模型列表
            model_combo.clear()
            model_combo.addItems(MODEL_MAP.get(vendor, []))
            
            # 尝试保持之前的模型选择（如果在新列表中）
            if current_model in MODEL_MAP.get(vendor, []):
                model_combo.setCurrentText(current_model)
        
        # 连接供应商变化信号
        vendor_combo.currentIndexChanged.connect(update_models)
        group.setLayout(group_layout)
        return group
    
    def create_layer2(self):
        """创建评价层"""
        self.layer2 = QGroupBox("2. 评价层")
        layout = QVBoxLayout()
        
        # 评分显示
        self.score_text = QTextEdit()
        self.score_text.setReadOnly(True)
        self.score_text.setMinimumHeight(120)
        self.score_text.setPlaceholderText("模型评价分数将显示在这里...")
        
        layout.addWidget(self.score_text)
        
        # 添加流程说明
        self.layer2_guide = QLabel("↑ 对多个模型的响应进行质量评价和评分")
        self.layer2_guide.setAlignment(Qt.AlignRight)
        layout.addWidget(self.layer2_guide)
        
        self.layer2.setLayout(layout)
        self.layer_container.addWidget(self.layer2)
    
    def create_layer3(self):
        """创建汇总层"""
        self.layer3 = QGroupBox("3. 汇总层")
        layout = QVBoxLayout()
        
        # 汇总结果显示
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setMinimumHeight(120)
        self.summary_text.setPlaceholderText("汇总结果将显示在这里...")
        
        layout.addWidget(self.summary_text)
        
        # 添加流程说明
        self.layer3_guide = QLabel("↑ 综合多个模型的响应生成最终结果")
        self.layer3_guide.setAlignment(Qt.AlignRight)
        layout.addWidget(self.layer3_guide)
        
        self.layer3.setLayout(layout)
        self.layer_container.addWidget(self.layer3)
    
    def create_layer4(self):
        """创建风格层"""
        self.layer4 = QGroupBox("4. 风格层")
        layout = QVBoxLayout()
        
        # 风格选择
        style_layout = QHBoxLayout()
        
        # 风格化结果显示
        self.style_text = QTextEdit()
        self.style_text.setReadOnly(True)
        self.style_text.setMinimumHeight(150)
        self.style_text.setPlaceholderText("风格化处理结果将显示在这里...")
        
        layout.addLayout(style_layout)
        layout.addWidget(self.style_text)
        
        # 添加流程说明
        self.layer4_guide = QLabel("↑ 调整最终结果的语气和表达风格")
        self.layer4_guide.setAlignment(Qt.AlignRight)
        layout.addWidget(self.layer4_guide)
        
        self.layer4.setLayout(layout)
        self.layer_container.addWidget(self.layer4)
    
    def create_layer5(self):
        """创建补正层"""
        self.layer5 = QGroupBox("5. 补正层")
        layout = QVBoxLayout()
        
        # 补正结果显示
        self.correction_text = QTextEdit()
        self.correction_text.setReadOnly(True)
        self.correction_text.setMinimumHeight(150)
        self.correction_text.setPlaceholderText("补正结果将显示在这里...")
        
        layout.addWidget(self.correction_text)
        
        # 添加最终流程说明
        self.layer5_guide = QLabel("↑ 最终优化和修正，得到最终结果")
        self.layer5_guide.setAlignment(Qt.AlignRight)
        layout.addWidget(self.layer5_guide)
        
        # 完成标记
        self.finish_label = QLabel("✓ 流程完成")
        self.finish_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(self.finish_label)
        
        self.layer5.setLayout(layout)
        self.layer_container.addWidget(self.layer5)
    
    def update_layer_visibility(self):
        """根据选择的层数更新各层的可见性"""
        layers = self.layer_spin.value()
        
        # 更新层标题以反映可见性
        self.layer1.setTitle(f"1. 请求并发层")
        
        # 2层模式：请求层 -> 风格层
        # 3层模式：请求层 -> 汇总层 -> 风格层
        # 4层模式：请求层 -> 评价层 -> 汇总层 -> 风格层
        # 5层模式：请求层 -> 评价层 -> 汇总层 -> 风格层 -> 补正层
        
        # 第一层始终显示
        self.layer1.setVisible(True)
        
        # 第二层在>=4层时显示
        self.layer2.setVisible(layers >= 4)
        
        # 第三层在>=3层时显示（汇总层优先于评价层）
        self.layer3.setVisible(layers >= 3)
        
        # 第四层始终显示
        self.layer4.setVisible(True)
        
        # 第五层在>=5层时显示
        self.layer5.setVisible(layers >= 5)
        
        # 更新层序号标题
        step = 2  # 从第2步开始计数（第1步是请求层）
        
        if layers >= 4:  # 显示评价层
            self.layer2.setTitle(f"{step}. 评价层")
            step += 1
        
        if layers >= 3:  # 显示汇总层
            self.layer3.setTitle(f"{step}. 汇总层")
            step += 1
        
        # 风格层是当前流程的最后一步或倒数第二步
        if layers < 5:
            # 当总层数小于5时，风格层是最后一步
            self.layer4.setTitle(f"{step}. 风格层")
        else:
            # 当有补正层时，风格层是倒数第二步
            self.layer4.setTitle(f"{step}. 风格层")
            step += 1
        
        if layers >= 5:  # 显示补正层
            self.layer5.setTitle(f"{step}. 补正层")
    
    def update_model_groups(self, count):
        """根据并发数量更新模型组的数量 - 修复并优化布局"""
        # 获取当前模型组容器
        models_container = self.layer1.layout().itemAt(1).widget()
        models_layout = models_container.layout()
        
        current_count = len(self.model_groups)
        
        if count > current_count:
            # 添加新的模型组
            for i in range(current_count, count):
                group = self.create_model_group(i+1)
                models_layout.addWidget(group)
                self.model_groups.append(group)
        elif count < current_count:
            # 移除多余的模型组
            for i in range(count, current_count):
                group = self.model_groups.pop()
                group.setParent(None)
                group.deleteLater()
        
        # 调整布局间距
        models_layout.setSpacing(15)

    def get_model_selections(self):
        """获取所有模型组的选择信息"""
        selections = []
        
        for group in self.model_groups:
            vendor_combo = group.property("vendor")
            model_combo = group.property("model")
            
            vendor = vendor_combo.currentText()
            model = model_combo.currentText()
            
            selections.append({
                "vendor": vendor,
                "model": model,
                "group": group  # 如果需要直接访问组对象
            })
        
        return selections

class ConvergenceSettingsWindow(QWidget):
    PRESETS_PATH = "utils/global_presets/convergence_presets.json"
    
    def __init__(self, processor, parent=None):
        super().__init__(parent)
        self.processor = processor
        self.setWindowTitle("汇流对话优化设置")
        self.resize(800, 600)
        
        # 创建主布局
        main_layout = QHBoxLayout()
        main_layout.setSpacing(10)
        self.setLayout(main_layout)
        
        # 创建左侧的选项卡控件
        self.tab_widget = QTabWidget()
        self.tab_widget.setTabPosition(QTabWidget.West)  # 选项卡放在左侧
        
        # 为每层创建设置页
        self.create_evaluation_tab()
        self.create_summary_tab()
        self.create_style_tab()
        self.create_correction_tab()
        
        main_layout.addWidget(self.tab_widget, 3)
        
        # 创建右侧的按钮区域
        button_area = QVBoxLayout()
        button_area.setAlignment(Qt.AlignTop)
        button_area.setSpacing(20)
        
        # 保存按钮
        save_button = QPushButton("保存设置")
        save_button.setMinimumHeight(40)
        save_button.clicked.connect(self.save_settings)
        
        # 取消按钮
        cancel_button = QPushButton("取消")
        cancel_button.setMinimumHeight(40)
        cancel_button.clicked.connect(self.close)
        
        # 导入按钮
        import_button = QPushButton("导入预设")
        import_button.setMinimumHeight(40)
        import_button.clicked.connect(self.import_presets)
        
        # 导出按钮
        export_button = QPushButton("导出预设")
        export_button.setMinimumHeight(40)
        export_button.clicked.connect(self.export_presets)
        
        button_area.addWidget(save_button)
        button_area.addWidget(cancel_button)
        button_area.addWidget(import_button)
        button_area.addWidget(export_button)
        button_area.addStretch(1)
        
        main_layout.addLayout(button_area, 1)
        
        # 初始化界面数据
        self.load_presets_to_ui()
    
    def create_evaluation_tab(self):
        """创建评价层设置页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)
        
        # 前缀设置
        prefix_group = QGroupBox("评价前缀")
        prefix_layout = QVBoxLayout()
        self.evaluation_prefix = QTextEdit()
        self.evaluation_prefix.setPlaceholderText("输入评价请求的前缀内容...")
        prefix_layout.addWidget(self.evaluation_prefix)
        prefix_group.setLayout(prefix_layout)
        
        # 后缀设置
        suffix_group = QGroupBox("评价后缀")
        suffix_layout = QVBoxLayout()
        self.evaluation_suffix = QTextEdit()
        self.evaluation_suffix.setPlaceholderText("输入评价请求的后缀内容...")
        suffix_layout.addWidget(self.evaluation_suffix)
        suffix_group.setLayout(suffix_layout)
        
        # 处理模型选择
        model_group = QGroupBox("处理模型选择")
        model_layout = QVBoxLayout()
        
        provider_layout = QHBoxLayout()
        provider_layout.addWidget(QLabel("供应商:"))
        self.evaluation_provider = QComboBox()
        self.evaluation_provider.addItems(MODEL_MAP.keys())
        provider_layout.addWidget(self.evaluation_provider)
        model_layout.addLayout(provider_layout)
        
        model_layout.addWidget(QLabel("模型:"))
        self.evaluation_model = QComboBox()
        self.evaluation_model.addItems(MODEL_MAP[self.evaluation_provider.currentText()])
        model_layout.addWidget(self.evaluation_model)
        
        # 更新模型列表当供应商变化
        self.evaluation_provider.currentTextChanged.connect(
            lambda: self.update_model_combo(
                self.evaluation_provider.currentText(), 
                self.evaluation_model
            )
        )
        
        model_group.setLayout(model_layout)
        
        layout.addWidget(prefix_group)
        layout.addWidget(suffix_group)
        layout.addWidget(model_group)
        layout.addStretch(1)
        
        self.tab_widget.addTab(tab, "评价层")
    
    def create_summary_tab(self):
        """创建汇总层设置页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)
        
        # 前缀设置
        prefix_group = QGroupBox("汇总前缀")
        prefix_layout = QVBoxLayout()
        self.summary_prefix = QTextEdit()
        self.summary_prefix.setPlaceholderText("输入汇总请求的前缀内容...")
        prefix_layout.addWidget(self.summary_prefix)
        prefix_group.setLayout(prefix_layout)
        
        # 后缀设置
        suffix_group = QGroupBox("汇总后缀")
        suffix_layout = QVBoxLayout()
        self.summary_suffix = QTextEdit()
        self.summary_suffix.setPlaceholderText("输入汇总请求的后缀内容...")
        suffix_layout.addWidget(self.summary_suffix)
        suffix_group.setLayout(suffix_layout)
        
        # 处理模型选择
        model_group = QGroupBox("处理模型选择")
        model_layout = QVBoxLayout()
        
        provider_layout = QHBoxLayout()
        provider_layout.addWidget(QLabel("供应商:"))
        self.summary_provider = QComboBox()
        self.summary_provider.addItems(MODEL_MAP.keys())
        provider_layout.addWidget(self.summary_provider)
        model_layout.addLayout(provider_layout)
        
        model_layout.addWidget(QLabel("模型:"))
        self.summary_model = QComboBox()
        self.summary_model.addItems(MODEL_MAP[self.summary_provider.currentText()])
        model_layout.addWidget(self.summary_model)
        
        # 更新模型列表当供应商变化
        self.summary_provider.currentTextChanged.connect(
            lambda: self.update_model_combo(
                self.summary_provider.currentText(), 
                self.summary_model
            )
        )
        
        model_group.setLayout(model_layout)
        
        layout.addWidget(prefix_group)
        layout.addWidget(suffix_group)
        layout.addWidget(model_group)
        layout.addStretch(1)
        
        self.tab_widget.addTab(tab, "汇总层")
    
    def create_style_tab(self):
        """创建风格层设置页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)
        
        # 前缀设置
        prefix_group = QGroupBox("风格要求")
        prefix_layout = QVBoxLayout()
        self.style_prefix = QTextEdit()
        self.style_prefix.setPlaceholderText("输入风格调整请求的前缀内容...")
        prefix_layout.addWidget(self.style_prefix)
        prefix_group.setLayout(prefix_layout)
        
        # 后缀设置
        suffix_group = QGroupBox("变量库")
        suffix_layout = QVBoxLayout()
        self.style_suffix = QTextEdit()
        self.style_suffix.setPlaceholderText("输入风格调整请求的变量...")
        suffix_layout.addWidget(self.style_suffix)
        suffix_group.setLayout(suffix_layout)
        
        # 处理模型选择
        model_group = QGroupBox("处理模型选择")
        model_layout = QVBoxLayout()
        
        provider_layout = QHBoxLayout()
        provider_layout.addWidget(QLabel("供应商:"))
        self.style_provider = QComboBox()
        self.style_provider.addItems(MODEL_MAP.keys())
        provider_layout.addWidget(self.style_provider)
        model_layout.addLayout(provider_layout)
        
        model_layout.addWidget(QLabel("模型:"))
        self.style_model = QComboBox()
        self.style_model.addItems(MODEL_MAP[self.style_provider.currentText()])
        model_layout.addWidget(self.style_model)
        
        # 更新模型列表当供应商变化
        self.style_provider.currentTextChanged.connect(
            lambda: self.update_model_combo(
                self.style_provider.currentText(), 
                self.style_model
            )
        )
        
        model_group.setLayout(model_layout)
        
        # 变量解释
        var_group = QGroupBox("可用变量")
        var_layout = QVBoxLayout()
        var_layout.addWidget(QLabel("#user# - 当前用户标识"))
        var_layout.addWidget(QLabel("#style# - 指定的风格"))
        var_layout.addWidget(QLabel("#pervious_content# - 上一步的结果"))
        var_layout.addWidget(QLabel("注: 变量在流程执行时会被实际内容替换"))
        var_group.setLayout(var_layout)
        
        layout.addWidget(prefix_group)
        layout.addWidget(suffix_group)
        layout.addWidget(model_group)
        layout.addWidget(var_group)
        layout.addStretch(1)
        
        self.tab_widget.addTab(tab, "风格层")
    
    def create_correction_tab(self):
        """创建补正层设置页"""
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setSpacing(15)
        
        # 前缀设置
        prefix_group = QGroupBox("补正前缀")
        prefix_layout = QVBoxLayout()
        self.correction_prefix = QTextEdit()
        self.correction_prefix.setPlaceholderText("输入补正请求的前缀内容...")
        prefix_layout.addWidget(self.correction_prefix)
        prefix_group.setLayout(prefix_layout)
        
        # 后缀设置
        suffix_group = QGroupBox("补正后缀")
        suffix_layout = QVBoxLayout()
        self.correction_suffix = QTextEdit()
        self.correction_suffix.setPlaceholderText("输入补正请求的后缀内容...")
        suffix_layout.addWidget(self.correction_suffix)
        suffix_group.setLayout(suffix_layout)
        
        # 处理模型选择
        model_group = QGroupBox("处理模型选择")
        model_layout = QVBoxLayout()
        
        provider_layout = QHBoxLayout()
        provider_layout.addWidget(QLabel("供应商:"))
        self.correction_provider = QComboBox()
        self.correction_provider.addItems(MODEL_MAP.keys())
        provider_layout.addWidget(self.correction_provider)
        model_layout.addLayout(provider_layout)
        
        model_layout.addWidget(QLabel("模型:"))
        self.correction_model = QComboBox()
        self.correction_model.addItems(MODEL_MAP[self.correction_provider.currentText()])
        model_layout.addWidget(self.correction_model)
        
        # 更新模型列表当供应商变化
        self.correction_provider.currentTextChanged.connect(
            lambda: self.update_model_combo(
                self.correction_provider.currentText(), 
                self.correction_model
            )
        )
        
        model_group.setLayout(model_layout)
        
        # 变量解释
        var_group = QGroupBox("可用变量")
        var_layout = QVBoxLayout()
        var_layout.addWidget(QLabel("#mod_functions# - 使用的补正函数"))
        var_layout.addWidget(QLabel("#previous_content# - 上一步的结果"))
        var_layout.addWidget(QLabel("注: 变量在流程执行时会被实际内容替换"))
        var_group.setLayout(var_layout)
        
        layout.addWidget(prefix_group)
        layout.addWidget(suffix_group)
        layout.addWidget(model_group)
        layout.addWidget(var_group)
        layout.addStretch(1)
        
        self.tab_widget.addTab(tab, "补正层")
    
    def update_model_combo(self, provider, combo_box):
        """更新模型下拉框的选项"""
        combo_box.clear()
        combo_box.addItems(MODEL_MAP.get(provider, []))
    
    def load_presets_to_ui(self):
        """将处理器的预设加载到UI控件"""
        presets = self.processor.presets
        
        # 评价层
        if "evaluation" in presets:
            eval_preset = presets["evaluation"]
            self.evaluation_prefix.setPlainText(eval_preset["prefix"])
            self.evaluation_suffix.setPlainText(eval_preset["suffix"])
            self.evaluation_provider.setCurrentText(eval_preset.get("process_provider", ""))
            self.update_model_combo(eval_preset.get("process_provider", ""), self.evaluation_model)
            self.evaluation_model.setCurrentText(eval_preset.get("process_model", ""))
        
        # 汇总层
        if "summary" in presets:
            summary_preset = presets["summary"]
            self.summary_prefix.setPlainText(summary_preset["prefix"])
            self.summary_suffix.setPlainText(summary_preset["suffix"])
            self.summary_provider.setCurrentText(summary_preset.get("process_provider", ""))
            self.update_model_combo(summary_preset.get("process_provider", ""), self.summary_model)
            self.summary_model.setCurrentText(summary_preset.get("process_model", ""))
        
        # 风格层
        if "style" in presets:
            style_preset = presets["style"]
            self.style_prefix.setPlainText(style_preset["prefix"])
            self.style_suffix.setPlainText(style_preset["suffix"])
            self.style_provider.setCurrentText(style_preset.get("process_provider", ""))
            self.update_model_combo(style_preset.get("process_provider", ""), self.style_model)
            self.style_model.setCurrentText(style_preset.get("process_model", ""))
        
        # 补正层
        if "correction" in presets:
            correction_preset = presets["correction"]
            self.correction_prefix.setPlainText(correction_preset["prefix"])
            self.correction_suffix.setPlainText(correction_preset["suffix"])
            self.correction_provider.setCurrentText(correction_preset.get("process_provider", ""))
            self.update_model_combo(correction_preset.get("process_provider", ""), self.correction_model)
            self.correction_model.setCurrentText(correction_preset.get("process_model", ""))
    
    def save_settings(self):
        """保存设置到处理器"""
        # 评价层
        self.processor.update_preset(
            "evaluation",
            self.evaluation_prefix.toPlainText(),
            self.evaluation_suffix.toPlainText(),
            self.evaluation_provider.currentText(),
            self.evaluation_model.currentText()
        )
        
        # 汇总层
        self.processor.update_preset(
            "summary",
            self.summary_prefix.toPlainText(),
            self.summary_suffix.toPlainText(),
            self.summary_provider.currentText(),
            self.summary_model.currentText()
        )
        
        # 风格层
        self.processor.update_preset(
            "style",
            self.style_prefix.toPlainText(),
            self.style_suffix.toPlainText(),
            self.style_provider.currentText(),
            self.style_model.currentText()
        )
        
        # 补正层
        self.processor.update_preset(
            "correction",
            self.correction_prefix.toPlainText(),
            self.correction_suffix.toPlainText(),
            self.correction_provider.currentText(),
            self.correction_model.currentText()
        )
        
        # 保存到文件
        self.processor.save_presets()
        self.close()
    
    def import_presets(self):
        """导入预设文件"""
        file_path, _ = QFileDialog.getOpenFileName(
            self, "导入预设文件", "", "JSON Files (*.json)"
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                imported_presets = json.load(f)
                
                # 更新处理器的预设
                self.processor.presets.update(imported_presets)
                self.load_presets_to_ui()
        except Exception as e:
            print(f"导入预设失败: {e}")
    
    def export_presets(self):
        """导出预设到文件"""
        file_path, _ = QFileDialog.getSaveFileName(
            self, "导出预设文件", "convergence_presets.json", "JSON Files (*.json)"
        )
        
        if not file_path:
            return
        
        try:
            with open(file_path, 'w', encoding='utf-8') as f:
                json.dump(self.processor.presets, f, ensure_ascii=False, indent=4)
        except Exception as e:
            print(f"导出预设失败: {e}")

class TestLib:
    def __init__(self):
        self.chathistory = [
    # 唐朝局部世界观：长安西市胡商聚集区的丝绸店背景
    {
        "role": "system",
        "content": '''当前场景设定在唐朝长安城西市的'波斯彩帛行'。店铺仅有：1) 胡商店主阿里木（大食人）2) 汉族顾客老王。
        你的语言、动机和认知必须完美契合这一设定：用词精准、背景一致。在互动中，自然推动对话——通过提问、分享观点或激发情绪来延续交流、推动关系变化，但严格限制在用户输入框架内。响应逻辑连贯：无缝衔接上下文，符合场景氛围和关系状态，杜绝任何设定外元素干扰；仅基于用户提供的直接内容和角色核心设定发展叙事，不添加未提及或者未发生的事件、物品或细节。情感表达饱满有层次，语言艺术追求精炼无冗余、用词富有表现力，并展现出角色独特风格，规避俗套模式；在用户身份未明确时，采用中性互动方式。总之，你的每次响应都应像一部微小说，真实而动人，且绝对忠实于输入语境。'''
    },
    {
        "role": "user",
        "content": "（老王掂量着丝绸）阿里木掌柜，这匹红底金纹的料子怎卖？"
    },
    {
        "role": "assistant",
        "content": "（擦着琉璃算盘）三百文一丈！撒马尔罕织工三月才出一匹，您摸摸这金线——"
    },
    {
        "role": "user",
        "content": "昨儿见波斯舶卸货有匹蓝宝石的，怎没摆出来？"
    },
    {
        "role": "assistant",
        "content": "（掀开布帘指后院）刚熏香防虫呢！您要现裁，我喊伙计取......"
    },
    {
        "role": "user",
        "content": "都说贞观年间长安繁盛，米价才五文一斗，当真如此？"
    }
]
        
class GodVarStock:
    def __init__(self,godclass=None):
        if godclass:
            self.stock=godclass
        else:
            self.stock=TestLib()

class ConcurrentorTools:
    @staticmethod
    def get_default_apis(testpath=True):
        current_path = os.path.abspath(__file__)
        if testpath:
            parent_dir = os.path.dirname(os.path.dirname(current_path))
            config_path = os.path.join(parent_dir, "api_config.ini")
        else:
            config_path="api_config.ini"
        
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

class APIRequestHandler(QObject):
    # 定义信号用于跨线程通信
    response_received = pyqtSignal(str)  # 接收到部分响应
    request_completed = pyqtSignal(str)  # 请求完成
    error_occurred = pyqtSignal(str)  # 发生错误
    
    def __init__(self, api_config, parent=None):
        """
        初始化API请求处理器
        :param api_config: API配置信息
        :param parent: 父对象
        """
        super().__init__(parent)
        self.api_config = api_config
        self.client = None
        self.current_thread = None
        self.full_response = ""  # 用于存储完整响应

    def send_request(self, message, model):
        """
        发送API请求（线程安全方式）
        :param message: 提示词
        :param model: 使用的模型
        """
        threading.Thread(
            target=self._send_request_thread,
            args=(message, model)
        ).start()
    
    def special_block_handler(self,content,                      #incoming content                     #function to call
                                  starter='<think>', 
                                  ender='</think>',
                                  extra_params=None             #extra params to fullfill
                                  ):
        """处理自定义块内容"""
        if starter in content :
            content = content.split(starter)[1]
            if ender in content:
                return {"starter":True,"ender":True}
            if extra_params:
                if hasattr(self, extra_params):
                    setattr(self, extra_params, content)

            return {"starter":True,"ender":False}
        return {"starter":False,"ender":False}


    def _send_request_thread(self, messages, model):

        
        def handle_response(content,temp_response):
            if hasattr(content, "content") and content.content:
                special_block_handler_result=self.special_block_handler(temp_response,
                                      starter='<think>', ender='</think>',
                                      extra_params='think_response'
                                      )
                if special_block_handler_result["starter"] and special_block_handler_result["ender"]:#如果思考链结束
                    self.full_response+= content.content
                    self.full_response.replace('</think>\n\n', '')
                elif not (special_block_handler_result["starter"]):#如果没有思考链
                    self.full_response += content.content
                print(content.content, end='', flush=True)
                        # 处理思考链内容
            if hasattr(content, "reasoning_content") and content.reasoning_content:
                self.think_response += content.reasoning_content
                print(content.reasoning_content, end='', flush=True)
        #try:
        client = openai.Client(
            api_key=self.api_config['key'],  # 替换为实际的 API 密钥
            base_url=self.api_config['url']  # 替换为实际的 API 基础 URL
        )
        try: 
            print('AI回复(流式):',type(messages))
            self.response = client.chat.completions.create(
                    model=model,
                    messages=messages,
                    #response_format={
                    #    'type': 'json_object'
                    #},
                    stream=True,  # 启用流式响应
                )
            self.full_response = ""
            self.think_response = "### AI 思考链\n---\n"
            temp_response = ""
            print('请求已经发到API')


            for event in self.response:
                if not hasattr(event, "choices") or not event.choices:
                    print("无效的响应事件:", event)
                    continue

                content = getattr(event.choices[0], "delta", None)
                if not content:
                    print("无效的内容:", event.choices[0])
                    continue
                if hasattr(content, "content") and content.content:
                    temp_response += content.content
                    handle_response(content,temp_response)
                if hasattr(content, "reasoning_content") and content.reasoning_content:
                    self.think_response += content.reasoning_content
                    print(content.reasoning_content, end='', flush=True)
            print("下一步是发送信号")
            self.request_completed.emit(self.full_response)
        except Exception as e:
            print("汇流优化API请求错误:", str(e))
            self.error_occurred.emit(f"API请求错误: {str(e)}")

class ConcurrentorSender(QObject):
    request_finished = pyqtSignal(dict)
    
    def __init__(self, slot, api_provider, model,params):
        super().__init__()
        self.slot = slot
        self.api_provider = api_provider
        self.model = model
        self.params=params
    
    def run(self):
        default_apis=ConcurrentorTools.get_default_apis()
        api_config={
            "url": default_apis[self.api_provider]["url"],
            "key": default_apis[self.api_provider]["key"]
        }

        self.requester=APIRequestHandler(api_config)
        self.requester.request_completed.connect(self.handle_request_completed)
        self.requester.send_request(self.params['messages'], self.model)

    def handle_request_completed(self,message):
        self.request_finished.emit({"slot": self.slot, "message": message})

class RatingSender(QObject):
    # 定义一个信号用于返回评价结果列表
    rating_finished = pyqtSignal(list)
    
    def run(self, messages, settings):
        """
        执行评价请求
        :param messages: 字符串列表，包含需要评价的各个模型生成结果 [message_1, message_2, ..., message_n]
        :param settings: 设置字典，包含评价所需参数
        """
        # 构建评价提示词
        content = settings["prefix"]
        
        # 添加每个模型生成结果
        for i, message in enumerate(messages, 1):
            content += f"\n\n--- 结果id: {i} ---\n{message}"
        
        # 添加后缀
        content += settings["suffix"]
        
        # 创建完整的消息结构
        full_messages = [
            {"role": "user", "content": content}
        ]
        
        # 获取API配置
        api_provider = settings["process_provider"]
        model = settings["process_model"]
        
        default_apis = ConcurrentorTools.get_default_apis()
        api_config = {
            "url": default_apis[api_provider]["url"],
            "key": default_apis[api_provider]["key"]
        }
        
        # 创建API请求处理器
        self.requester = APIRequestHandler(api_config)
        # 连接完成信号
        self.requester.request_completed.connect(self._handle_rating_response)
        # 发送请求
        print(full_messages)
        self.requester.send_request(full_messages, model)
    
    def _handle_rating_response(self, response_text):
        """
        处理评价API的响应
        :param response_text: API返回的文本响应
        """
        try:
            # 查找并提取JSON内容
            json_results = []
            from jsonfinder import jsonfinder
            for _, __, obj in jsonfinder(response_text, json_only=True):
                if isinstance(obj, list):  # 确保我们提取到的是JSON数组
                    json_results = obj
                    break
            
            # 验证结果格式
            if not json_results:
                raise ValueError("未找到有效的JSON结果")
            
            # 确保每个元素都包含text和rating字段
            valid_results = []
            for item in json_results:
                if not isinstance(item, dict):
                    continue
                if "text_id" in item and "rating" in item:
                    valid_results.append({
                        "text_id": item["text_id"],
                        "rating": item["rating"]
                    })
            
            # 发送评分结果
            self.rating_finished.emit(valid_results)
            
        except Exception as e:
            print(f"评分解析错误: {str(e)}")
            self.rating_finished.emit([])

class SummarySender(QObject):
    # 定义信号用于返回汇总结果
    summary_finished = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.requester = None
        
    def run(self, messages, ratings, summary_settings, params):
        """
        执行汇总请求
        :param messages: 待汇总的消息列表 [message_1, message_2, ...]
        :param ratings: 评分列表 [{"text_id": int, "rating": int}, ...]
        :param summary_settings: 汇总层设置
        :param params: 额外参数，包含用户当前消息等上下文信息
        """
        try:
            # 构建提示词
            content = summary_settings["prefix"]
            
            # 如果没有评分信息（来自并发层），添加特别提示
            if not ratings:
                content += "（以下回复没有评分信息，请自行判断保留优质回答）：\n"
            
            # 添加每个模型生成结果及评分（如果有）
            for i, msg in enumerate(messages):
                # 找到对应的评分（如果存在）
                rating_info = next((r for r in ratings if r["text_id"] == i+1), None)
                rating_value = rating_info["rating"] if rating_info else "未评分"
                
                content += f"\n\n--- 结果 {i+1} | 评分: {rating_value} ---\n{msg}"
            
            # 添加后缀
            content += summary_settings["suffix"]
            
            # 添加上下文信息（如果有）
            if "current_message" in params:
                content = content.replace("{{user}}", params["current_message"])
            
            # 创建完整的消息结构
            full_messages = [
                {"role": "user", "content": content}
            ]
            
            # 获取API配置
            api_provider = summary_settings["process_provider"]
            model = summary_settings["process_model"]
            
            default_apis = ConcurrentorTools.get_default_apis()
            api_config = {
                "url": default_apis[api_provider]["url"],
                "key": default_apis[api_provider]["key"]
            }
            
            # 创建API请求处理器
            self.requester = APIRequestHandler(api_config)
            self.requester.request_completed.connect(self._handle_summary_response)
            self.requester.send_request(full_messages, model)
        
        except Exception as e:
            print(f"创建汇总请求时出错: {str(e)}")
            self.summary_finished.emit(f"汇总出错: {str(e)}")
    
    def _handle_summary_response(self, response_text):
        """
        处理汇总API的响应
        :param response_text: API返回的汇总文本
        """
        # 直接返回汇总结果，无需额外处理
        self.summary_finished.emit(response_text)

class RequestDispatcher(QObject):
    """请求分发中转类，处理各层请求的分发"""
    layer_completed = pyqtSignal(dict, str)  # 数据, 完成的层名称
    
    def __init__(self, processor):
        super().__init__()
        self.processor = processor
        self.current_layer = None
        self.current_result = {}
    
    def dispatch_request(self, layer_name, params):
        """分派请求到指定层"""
        self.current_layer = layer_name
        
        if layer_name == "concurrent":
            self._dispatch_concurrent(params)
        elif layer_name == "evaluation":
            self._dispatch_evaluation()
        elif layer_name == "summary":
            self._dispatch_summary(params)
        elif layer_name == "style":
            self._dispatch_style(params)
        elif layer_name == "correction":
            self._dispatch_correction()
    
    def _dispatch_concurrent(self, params):
        """分派并发请求"""
        self.processor.start_concurrent_requests(params)
    
    def _dispatch_evaluation(self):
        """分派评价层请求"""
        messages = []
        for slot in sorted(self.processor.model_responses.keys()):
            message = self.processor.model_responses.get(slot)
            if message:  # 只包含非空消息
                messages.append(message)
        
        if not messages:
            print("所有模型返回空响应，无法进行评价")
            self.layer_completed.emit({"error": "所有模型返回空响应"}, "evaluation")
            return
        
        # 其余代码保持不变...
        eval_settings = self.processor.presets["evaluation"]
        self.rating_sender = RatingSender()
        self.rating_sender.rating_finished.connect(
            lambda ratings: self._handle_evaluation_result(ratings)
        )
        self.rating_sender.run(messages, eval_settings)
    
    def _handle_evaluation_result(self, ratings):
        """处理评价层返回结果"""
        self.layer_completed.emit({
            "rating": ratings,
            "messages": [msg for msg in self.processor.model_responses.values() if msg]
        }, "evaluation")
    
    def _dispatch_summary(self, params):
        """分派汇总层请求"""
        # 添加调试信息
        print(f"分派汇总请求，参数类型: {type(params)}")
        
        # 如果params为None，尝试从处理器获取有效的workflow_params
        if params is None:
            # 尝试从处理器获取工作流参数
            workflow_params = getattr(self.processor, "workflow_params", None)
            print(f"使用处理器的工作流参数: {workflow_params}")
            params = workflow_params
        
        summary_settings = self.processor.presets["summary"]
        messages = self.current_result.get("messages", [])
        ratings = self.current_result.get("rating", [])
        
        if not messages:
            print("没有有效消息进行汇总")
            self.layer_completed.emit({"error": "没有有效消息"}, "summary")
            return
        
        self.summary_sender = SummarySender()
        self.summary_sender.summary_finished.connect(
            lambda summary: self.layer_completed.emit({"summary": summary}, "summary")
        )
        
        # 确保传入有效的params，即使为空字典
        self.summary_sender.run(messages, ratings, summary_settings, params or {})
    
    def _dispatch_style(self, params):
        """分派风格层请求"""
        # 尝试获取汇总层的结果，但如果没有（层数可能跳过汇总层），则直接使用并发层的响应
        summary = self.current_result.get("summary", "")
        concurrent_messages = self.current_result.get("messages", [])
        
        # 如果没有任何输入内容，报错
        if not summary and not concurrent_messages:
            print("没有有效的输入内容进行风格化处理")
            self.layer_completed.emit({"error": "没有输入内容"}, "style")
            return
        
        # 如果没有汇总结果，使用并发层的响应（将它们合并）
        previous_content = summary
        if not previous_content and concurrent_messages:
            # 用分隔线合并所有并发层的响应
            separator = "\n\n" + "-"*40 + "\n\n"
            previous_content = separator.join(concurrent_messages)
        
        style_settings = self.processor.presets["style"]
        
        # 创建并启动风格转换
        self.style_sender = StyleSender()
        self.style_sender.style_finished.connect(
            lambda styled: self.layer_completed.emit({"styled_text": styled}, "style")
        )
        self.style_sender.run(previous_content, style_settings, params or {})
    
    def _dispatch_correction(self):
        """分派补正层请求"""
        # 从风格层获取的数据
        styled_text = self.current_result.get("styled_text", "")
        
        if not styled_text:
            print("没有风格化文本进行补正")
            self.layer_completed.emit({"error": "没有风格化文本"}, "correction")
            return
        
        correction_settings = self.processor.presets["correction"]
        self.correction_sender = CorrectionSender()
        self.correction_sender.correction_finished.connect(
            lambda corrected: self.layer_completed.emit({"corrected_text": corrected}, "correction")
        )
        self.correction_sender.run(styled_text, correction_settings)
    
    def set_current_result(self, result):
        """更新当前处理的中间结果"""
        self.current_result = result

class StyleSender(QObject):
    # 定义信号用于返回风格化后的文本
    style_finished = pyqtSignal(str)
    
    def __init__(self):
        super().__init__()
        self.requester = None
        
    def run(self, previous_content, style_settings, params):
        """
        执行风格转换请求
        :param previous_content: 上一步的结果文本（通常是汇总层的输出）
        :param style_settings: 风格层设置（包含前缀、后缀和模型信息）
        :param params: 额外参数（包含用户消息、对话历史等上下文）
        """
        chathistory=params.get("messages", "")
        user=params.get("user", "用户")
        message=''
        if type(chathistory)==list:
            for item in chathistory:
                if item["role"]=="user":
                    message+=user+':\n'+item["content"]
                elif item["role"]=="assistant":
                    message+="AI(you)"+':\n'+item["content"]
                elif item["role"]=="system":
                    message+="背景设定"+':\n'+item["content"]


        try:
            # 构建提示词
            content = style_settings["prefix"]
            
            # 替换提示词中的变量
            content = content.replace("#chathistory#", message)
            content = content.replace("#user#", user)
            content = content.replace("#style#", params.get("style", ""))
            content = content.replace("#pervious_content#", previous_content)
            
            # 添加后缀内容
            content += style_settings["suffix"]
            
            # 创建完整的消息结构
            full_messages = [
                {"role": "user", "content": content}
            ]
            
            # 获取API配置
            api_provider = style_settings["process_provider"]
            model = style_settings["process_model"]
            
            # 从全局获取API配置
            default_apis = ConcurrentorTools.get_default_apis()
            api_config = {
                "url": default_apis[api_provider]["url"],
                "key": default_apis[api_provider]["key"]
            }
            
            # 创建API请求处理器
            print(full_messages[0]("content"))
            self.requester = APIRequestHandler(api_config)
            self.requester.request_completed.connect(self._handle_style_response)
            self.requester.send_request(full_messages, model)
        
        except Exception as e:
            print(f"创建风格转换请求时出错: {str(e)}")
            self.style_finished.emit(f"风格转换出错: {str(e)}")
    
    def _handle_style_response(self, response_text):
        """
        处理风格转换API的响应
        :param response_text: API返回的风格化文本
        """
        # 直接返回风格化后的结果
        self.style_finished.emit(response_text)

class ConvergenceDialogueOptiProcessor(QWidget):
    PRESETS_PATH = "utils/global_presets/convergence_presets.json"
    
    def __init__(self):
        super().__init__()
        self.ui = ConvergenceDialogueOptiUI()
        self.dispatcher = RequestDispatcher(self)
        self.init_ui()
        self.connect_signals()
        self.active_requests = 0
        self.presets = {
            "evaluation": {"prefix": "请根据要求对模型响应进行评分。要求：越贴近日常交流，越让人觉得自己在和活生生的人对话时，分数越高。对话内容：\n", "suffix": '\n返回j格式[{"text_id":a,"rating":xx},{"text_id":b,"rating":xx}]', "process_provider": "deepseek", "process_model": "deepseek-chat"},
            "summary": {"prefix": "请总结以下多个模型响应的核心观点，可以抛弃评价较低的回复和观点:\n", "suffix": "\n\n要求: 生成简短的清晰总结。", "process_provider": "deepseek", "process_model": "deepseek-reasoner"},
            "style": {"prefix": "先前的对话是：#chathistory#\n现在根据内容指导，回复#user#。```内容指导\n#pervious_content#```\n要求：回复风格为非常暴躁#style#", "suffix": "style:自然", "process_provider": "deepseek", "process_model": "deepseek-reasoner"},
            "correction": {"prefix": "根据要求评估并返回响应的结果:\n#mod_functions#", "suffix": "回复时使用json", "process_provider": "deepseek", "process_model": "deepseek-reasoner"}
        }
        
        self.model_responses = {}  # 存储模型响应 {slot: response_text}
        self.load_presets()
    
    def init_ui(self):
        layout = QVBoxLayout()
        layout.addWidget(self.ui)
        self.setLayout(layout)
        self.setWindowTitle("汇流对话优化")
        self.resize(1000, 800)
    
    def connect_signals(self):
        self.ui.settings_btn.clicked.connect(self.open_settings)
        self.dispatcher.layer_completed.connect(self.handle_layer_completed)
    
    def start_workflow(self, params):
        """启动整个工作流"""
        # 1. 发送并发请求
        self.workflow_params = params
        self.dispatcher.dispatch_request("concurrent", params)
    
    def start_concurrent_requests(self, params):
        """启动并发请求"""
        # 重置计数器
        self.active_requests = 0
        self.model_responses = {}
        self.thread_keeper = []
        
        
        # 清除之前的响应
        for group in self.ui.model_groups:
            text_edit = group.property("response")
            text_edit.clear()
        
        # 遍历所有模型组并发送请求
        for slot, group in enumerate(self.ui.model_groups):
            vendor_combo = group.property("vendor")
            model_combo = group.property("model")
            
            vendor = vendor_combo.currentText()
            model = model_combo.currentText()
            
            if not vendor or not model:
                continue
            
            # 禁用界面控件
            vendor_combo.setEnabled(False)
            model_combo.setEnabled(False)
            self.ui.concurrent_spin.setEnabled(False)
            self.active_requests += 1
            
            # 创建并启动请求线程
            sender = ConcurrentorSender(slot, vendor, model, params)
            sender.request_finished.connect(self.on_request_finished)
            sender.run()
            self.thread_keeper.append(sender)
    
    def on_request_finished(self, result):
        """处理单个并发请求完成"""
        slot = result["slot"]
        message = result["message"]
        
        # 找到对应的模型组
        group = self.ui.model_groups[slot]
        text_edit = group.property("response")
        
        # 存储响应
        self.model_responses[slot] = message
        
        # 更新UI
        text_edit.setPlainText(message)
        
        # 减少活跃请求计数
        self.active_requests -= 1
        
        if self.active_requests == 0:
            # 所有请求完成，重新启用控件
            for group in self.ui.model_groups:
                vendor_combo = group.property("vendor")
                model_combo = group.property("model")
                
                vendor_combo.setEnabled(True)
                model_combo.setEnabled(True)
            
            self.ui.concurrent_spin.setEnabled(True)
            
            # 通知分派器并发层完成
            self.dispatcher.layer_completed.emit({
                "messages": [msg for msg in self.model_responses.values() if msg]
            }, "concurrent")
    
    def handle_layer_completed(self, result, layer_name):
        """处理某一层处理完成"""
        # 更新当前层结果
        self.dispatcher.set_current_result(result)
        layer_count = self.ui.layer_spin.value()
        
        # 根据完成的层，执行下一层处理
        if layer_name == "concurrent":
            # 并发层完成后，根据层数决定下一步
            if layer_count >= 4:  # 4层时执行评价层
                self.dispatcher.dispatch_request("evaluation", None)
            elif layer_count >= 3:  # 3层时直接执行总结层
                self.dispatcher.dispatch_request("summary", {
                    "messages": result.get("messages", [])
                })
            else: 
                self.dispatcher.dispatch_request("style", {
                    "messages": result.get("messages", []),
                    **self.workflow_params
                })
        
        elif layer_name == "evaluation":
            # 更新评价层UI
            self._update_rating_ui(result)
            
            # 传递评价结果给汇总层
            self.dispatcher.dispatch_request("summary", {
                "messages": self.model_responses.values(),
                "rating": result.get("rating", []),
                **self.workflow_params
            })
        
        elif layer_name == "summary":
            # 更新汇总层UI
            self._update_summary_ui(result)
            
            # 传递汇总结果给风格层
            self.dispatcher.dispatch_request("style", {
                "summary": result.get("summary", ""),
                **self.workflow_params
            })
        
        elif layer_name == "style":
            # 更新风格层UI
            self._update_style_ui(result)
            
            # 检查是否需要补正层
            if layer_count >= 5:
                self.dispatcher.dispatch_request("correction", {
                    "styled_text": result.get("styled_text", "")
                })
            else:
                # 如果不需要补正层，流程结束
                self.dispatcher.layer_completed.emit(
                    {"final_result": result.get("styled_text", "")}, "end"
                )
        
        elif layer_name == "correction":
            # 更新补正层UI
            self._update_correction_ui(result)
            
            # 流程结束
            self.dispatcher.layer_completed.emit(
                {"final_result": result.get("corrected_text", "")}, "end"
            )

    
    def _update_rating_ui(self, result):
        """更新评价层UI"""
        if "error" in result:
            self.ui.score_text.setPlainText(result["error"])
            return
        
        ratings = result.get("rating", [])
        rating_text = ""
        
        for result in ratings:
            text_id = result.get('text_id', '未知')
            rating = result.get('rating', 0)
            rating_text += f"文本ID: {text_id}  评分: {rating}\n"
        
        self.ui.score_text.setPlainText(rating_text)
    
    def _update_summary_ui(self, result):
        """更新汇总层UI"""
        if "error" in result:
            self.ui.summary_text.setPlainText(result["error"])
            return
        
        summary = result.get("summary", "")
        self.ui.summary_text.setPlainText(summary)
    
    def _update_style_ui(self, result):
        """更新风格层UI"""
        if "error" in result:
            self.ui.style_text.setPlainText(result["error"])
            return
        
        styled_text = result.get("styled_text", "")
        self.ui.style_text.setPlainText(styled_text)
    
    def _update_correction_ui(self, result):
        """更新补正层UI"""
        if "error" in result:
            self.ui.correction_text.setPlainText(result["error"])
            return
        
        corrected_text = result.get("corrected_text", "")
        self.ui.correction_text.setPlainText(corrected_text)
    
    # 以下是原有的方法，仅做部分调整
    def update_preset(self, layer_name, prefix, suffix, process_provider='', process_model=''):
        if layer_name in self.presets:
            self.presets[layer_name] = {
                "prefix": prefix, "suffix": suffix,
                "process_provider": process_provider, "process_model": process_model
            }
            return True
        return False
    
    def get_preset(self, layer_name):
        return self.presets.get(layer_name, {"prefix": "", "suffix": "", "process_provider": "", "process_model": ""})
    
    def load_presets(self):
        try:
            if os.path.exists(self.PRESETS_PATH):
                with open(self.PRESETS_PATH, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    for layer, preset in data.items():
                        if layer in self.presets:
                            self.presets[layer] = preset
        except Exception as e:
            print(f"加载预设时出错: {e}")
    
    def save_presets(self):
        try:
            os.makedirs(os.path.dirname(self.PRESETS_PATH), exist_ok=True)
            with open(self.PRESETS_PATH, 'w', encoding='utf-8') as f:
                json.dump(self.presets, f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            print(f"保存预设时出错: {e}")
            return False
    
    def open_settings(self):
        if not getattr(self, "settings_window", None):
            self.settings_window = ConvergenceSettingsWindow(self)
        self.settings_window.show()
        self.settings_window.raise_()

if __name__ != "__main__":
    app = QApplication([])
    def printer(value):
        print(value)
    sender = RatingSender()
    sender.rating_finished.connect(printer)
    settings = {
        "prefix": "请根据以下模型响应进行评分:\n",
        "suffix": '\n返回json,[{"text_id":a,"rating":xx},{"text_id":b,"rating":xx}]',
        "process_provider": "deepseek",
        "process_model": "deepseek-chat"
    }
    model_outputs = [
    "后端测试，给这一段打60分",
    "后端测试，给这一段打85分",
    "后端测试，给这一段打0分",
    "后端测试，在打分之前重复一下给你发送的内容"
]
    sender.run(model_outputs, settings)
    app.exec_()

if __name__ == "__main__":
    app = QApplication([])
    processor = ConvergenceDialogueOptiProcessor()
    processor.show()
    params={
        "messages":TestLib().chathistory
    }
    
    # 模拟外部调用启动请求（通常在UI中有触发按钮）
    def trigger_requests():
        processor.start_workflow(params)
    
    # 添加启动按钮以便测试
    btn = QPushButton("开始并发请求")
    btn.clicked.connect(trigger_requests)
    processor.layout().insertWidget(0, btn)
    
    app.exec_()
