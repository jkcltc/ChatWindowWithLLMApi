import sys
from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget, QVBoxLayout, QHBoxLayout,
                             QGroupBox, QLabel, QSpinBox, QComboBox, QTextEdit, QPushButton, 
                             QSizePolicy, QFrame)
from PyQt5.QtCore import Qt
from PyQt5.QtGui import QFont, QPixmap
from theme_manager import ThemeSelector
MODEL_MAP={
  "baidu": [
    "ernie-4.5-turbo-32k",
    "deepseek-r1",
    "deepseek-v3",
    "ernie-4.5-8k-preview",
    "ernie-4.0-8k",
    "ernie-3.5-8k",
    "ernie-speed-pro-128k",
    "ernie-4.0-turbo-8k",
    "qwq-32b",
    "ernie-4.5-turbo-vl-32k",
    "aquilachat-7b",
    "bloomz-7b",
    "chatglm2-6b-32k",
    "codellama-7b-instruct",
    "deepseek-r1-distill-llama-70b",
    "deepseek-r1-distill-llama-8b",
    "deepseek-r1-distill-qianfan-70b",
    "deepseek-r1-distill-qianfan-8b",
    "deepseek-r1-distill-qianfan-llama-70b",
    "deepseek-r1-distill-qianfan-llama-8b",
    "deepseek-r1-distill-qwen-1.5b",
    "deepseek-r1-distill-qwen-14b",
    "deepseek-r1-distill-qwen-32b",
    "deepseek-r1-distill-qwen-7b",
    "deepseek-v3-241226",
    "deepseek-vl2",
    "deepseek-vl2-small",
    "enrie-irag-edit",
    "ernie-3.5-128k",
    "ernie-3.5-128k-preview",
    "ernie-3.5-8k-0613",
    "ernie-3.5-8k-0701",
    "ernie-3.5-8k-preview",
    "ernie-4.0-8k-0613",
    "ernie-4.0-8k-latest",
    "ernie-4.0-8k-preview",
    "ernie-4.0-turbo-128k",
    "ernie-4.0-turbo-8k-0628",
    "ernie-4.0-turbo-8k-0927",
    "ernie-4.0-turbo-8k-latest",
    "ernie-4.0-turbo-8k-preview",
    "ernie-4.5-8k-preview",
    "ernie-4.5-turbo-128k",
    "ernie-x1-32k",
    "ernie-x1-32k-preview",
    "ernie-x1-turbo-32k",
    "gemma-7b-it",
    "glm-4-32b-0414",
    "glm-z1-32b-0414",
    "glm-z1-rumination-32b-0414",
    "internvl2.5-38b-mpo",
    "llama-2-13b-chat",
    "llama-2-70b-chat",
    "llama-2-7b-chat",
    "llama-4-maverick-17b-128e-instruct",
    "llama-4-scout-17b-16e-instruct",
    "meta-llama-3-70b",
    "meta-llama-3-8b",
    "mixtral-8x7b-instruct",
    "qianfan-70b",
    "qianfan-8b",
    "qianfan-agent-lite-8k",
    "qianfan-agent-speed-32k",
    "qianfan-agent-speed-8k",
    "qianfan-bloomz-7b-compressed",
    "qianfan-chinese-llama-2-13b",
    "qianfan-chinese-llama-2-70b",
    "qianfan-chinese-llama-2-7b",
    "qianfan-llama-vl-8b",
    "qianfan-sug-8k",
    "qwen2.5-7b-instruct",
    "qwen2.5-vl-32b-instruct",
    "qwen2.5-vl-7b-instruct",
    "sqlcoder-7b",
    "xuanyuan-70b-chat-4bit",
    "ernie-speed-128k",
    "ernie-speed-8k",
    "ernie-lite-8k",
    "ernie-lite-pro-128k",
    "qwen3-235b-a22b",
    "qwen3-30b-a3b",
    "qwen3-32b",
    "qwen3-14b",
    "qwen3-8b",
    "qwen3-4b",
    "qwen3-1.7b",
    "qwen3-0.6b",
    "deepseek-r1-250528",
    "ernie-4.5-turbo-vl-32k-preview",
    "ernie-char-8k",
    "ernie-char-fiction-8k",
    "ernie-irag-edit",
    "ernie-novel-8k",
    "ernie-tiny-8k",
    "flux.1-schnell",
    "internvl3-14b",
    "internvl3-1b",
    "internvl3-38b",
    "irag-1.0",
    "qianfan-agent-intent-32k",
    "qianfan-check-vl",
    "qianfan-composition",
    "qianfan-multpicocr",
    "search-deepseek-v3",
    "wan-2.1-i2v-14b-480p",
    "yi-34b-chat"
  ],
  "deepseek": [
    "deepseek-chat",
    "deepseek-reasoner"
  ],
  "tencent": [
    "deepseek-r1",
    "deepseek-v3",
    "deepseek-prover-v2",
    "deepseek-v3-0324"
  ],
  "siliconflow": [
    "deepseek-ai/DeepSeek-V3",
    "deepseek-ai/DeepSeek-R1",
    "Pro/deepseek-ai/DeepSeek-R1",
    "Pro/deepseek-ai/DeepSeek-V3",
    "THUDM/chatglm3-6b",
    "THUDM/glm-4-9b-chat",
    "Qwen/Qwen2-7B-Instruct",
    "Qwen/Qwen2-1.5B-Instruct",
    "internlm/internlm2_5-7b-chat",
    "BAAI/bge-large-en-v1.5",
    "BAAI/bge-large-zh-v1.5",
    "Pro/Qwen/Qwen2-7B-Instruct",
    "Pro/Qwen/Qwen2-1.5B-Instruct",
    "Pro/THUDM/glm-4-9b-chat",
    "meta-llama/Meta-Llama-3.1-8B-Instruct",
    "Pro/meta-llama/Meta-Llama-3.1-8B-Instruct",
    "meta-llama/Meta-Llama-3.1-70B-Instruct",
    "netease-youdao/bce-embedding-base_v1",
    "BAAI/bge-m3",
    "internlm/internlm2_5-20b-chat",
    "netease-youdao/bce-reranker-base_v1",
    "BAAI/bge-reranker-v2-m3",
    "deepseek-ai/DeepSeek-V2.5",
    "Qwen/Qwen2.5-72B-Instruct",
    "Qwen/Qwen2.5-7B-Instruct",
    "Qwen/Qwen2.5-14B-Instruct",
    "Qwen/Qwen2.5-32B-Instruct",
    "Qwen/Qwen2.5-Coder-7B-Instruct",
    "TeleAI/TeleChat2",
    "Pro/Qwen/Qwen2.5-7B-Instruct",
    "Qwen/Qwen2.5-72B-Instruct-128K",
    "Qwen/Qwen2-VL-72B-Instruct",
    "OpenGVLab/InternVL2-26B",
    "Pro/BAAI/bge-m3",
    "Pro/OpenGVLab/InternVL2-8B",
    "Pro/Qwen/Qwen2-VL-7B-Instruct",
    "LoRA/Qwen/Qwen2.5-7B-Instruct",
    "Pro/Qwen/Qwen2.5-Coder-7B-Instruct",
    "LoRA/Qwen/Qwen2.5-72B-Instruct",
    "Qwen/Qwen2.5-Coder-32B-Instruct",
    "Pro/BAAI/bge-reranker-v2-m3",
    "Qwen/QwQ-32B-Preview",
    "AIDC-AI/Marco-o1",
    "LoRA/Qwen/Qwen2.5-14B-Instruct",
    "LoRA/Qwen/Qwen2.5-32B-Instruct",
    "meta-llama/Llama-3.3-70B-Instruct",
    "LoRA/meta-llama/Meta-Llama-3.1-8B-Instruct",
    "deepseek-ai/deepseek-vl2",
    "Qwen/QVQ-72B-Preview",
    "Pro/deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B",
    "Pro/deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
    "Pro/deepseek-ai/DeepSeek-R1-Distill-Llama-8B",
    "deepseek-ai/DeepSeek-R1-Distill-Qwen-14B",
    "deepseek-ai/DeepSeek-R1-Distill-Qwen-32B",
    "deepseek-ai/DeepSeek-R1-Distill-Llama-70B",
    "deepseek-ai/DeepSeek-R1-Distill-Qwen-1.5B",
    "deepseek-ai/DeepSeek-R1-Distill-Qwen-7B",
    "deepseek-ai/DeepSeek-R1-Distill-Llama-8B",
    "SeedLLM/Seed-Rice-7B",
    "Qwen/QwQ-32B",
    "Pro/Qwen/Qwen2.5-VL-7B-Instruct",
    "Pro/deepseek-ai/DeepSeek-R1-0120",
    "Pro/deepseek-ai/DeepSeek-V3-1226",
    "Qwen/Qwen2.5-VL-32B-Instruct",
    "Qwen/Qwen2.5-VL-72B-Instruct",
    "Qwen/Qwen3-14B",
    "Qwen/Qwen3-235B-A22B",
    "Qwen/Qwen3-30B-A3B",
    "Qwen/Qwen3-32B",
    "Qwen/Qwen3-8B",
    "THUDM/GLM-4-32B-0414",
    "THUDM/GLM-4-9B-0414",
    "THUDM/GLM-Z1-32B-0414",
    "THUDM/GLM-Z1-9B-0414",
    "THUDM/GLM-Z1-Rumination-32B-0414",
    "Tongyi-Zhiwen/QwenLong-L1-32B",
    "deepseek-ai/DeepSeek-R1-0528-Qwen3-8B"
  ],
  "ollama": [
    "deepseek-r1:1.5b",
    "deepseek-r1:14b",
    "deepseek-r1:70b",
    "deepseek-r1:8b",
    "gemma3:27b",
    "mistral:latest",
    "qwen3:14b",
    "qwen3:30b-a3b",
    "qwen3:32b",
    "qwen3:4b",
    "qwq:latest"
  ]
}
class AIWorkflowUI(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("AI 工作流处理系统")
        self.setGeometry(100, 100, 1200, 900)  # 增加窗口尺寸以适应水平布局
        
        # 主控件和布局
        main_widget = QWidget()
        self.setCentralWidget(main_widget)
        main_layout = QVBoxLayout(main_widget)
        main_layout.setSpacing(20)
        
        # 添加标题和流程图引导
        title_label = QLabel("AI 工作流处理流程图")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        main_layout.addWidget(title_label)
        
        # 流程图说明
        guide_label = QLabel(
            "工作流说明: 请按顺序使用各层功能。从请求并发层开始，逐层处理数据，最终获得优化结果。\n"
            "↓ 表示流程方向，每层处理后将结果传递给下一层"
        )
        guide_label.setAlignment(Qt.AlignCenter)
        guide_label.setStyleSheet("background-color: #f0f8ff; padding: 10px; border-radius: 5px;")
        main_layout.addWidget(guide_label)
        
        # 顶部控制区域
        top_layout = QHBoxLayout()
        self.layer_spin = QSpinBox()
        self.layer_spin.setRange(2, 5)
        self.layer_spin.setValue(4)
        self.layer_spin.setPrefix("流程层数: ")
        self.layer_spin.valueChanged.connect(self.update_layer_visibility)
        
        top_layout.addWidget(self.layer_spin)
        top_layout.addStretch(1)
        
        # 流程层容器
        self.layer_container = QVBoxLayout()
        self.layer_container.setSpacing(30)
        
        # 创建各层控件
        self.create_layer1()  # 请求并发层
        self.create_layer2()  # 评价层
        self.create_layer3()  # 汇总层
        self.create_layer4()  # 风格层
        self.create_layer5()  # 补正层
        
        # 添加到主布局
        main_layout.addLayout(top_layout)
        main_layout.addLayout(self.layer_container)
        main_layout.addStretch(1)
        
        # 初始可见性设置
        self.update_layer_visibility()
        
        # 添加流程箭头
        self.add_flow_arrows()
    
    def add_flow_arrows(self):
        """在层之间添加箭头表示流程方向"""
        arrows = []
        for i in range(4):  # 最多4个箭头
            arrow_label = QLabel()
            arrow_label.setPixmap(QPixmap("").scaled(30, 30))  # 实际使用时替换为箭头图片
            arrow_label.setText("↓")  # 使用文本箭头作为替代
            arrow_label.setAlignment(Qt.AlignCenter)
            arrow_label.setStyleSheet("font-size: 24px; color: #888;")
            arrows.append(arrow_label)
        
        # 在层之间插入箭头
        for i, widget in enumerate(self.layer_container.parent().children()):
            if isinstance(widget, QGroupBox):
                index = self.layer_container.indexOf(widget)
                if index > 0 and i <= len(arrows):
                    self.layer_container.insertWidget(index, arrows[i-1])
    
    def create_layer1(self):
        """创建请求并发层 - 修改为水平布局"""
        self.layer1 = QGroupBox("1. 请求并发层")
        self.layer1.setStyleSheet("QGroupBox { font-weight: bold; }")
        layout = QVBoxLayout()
        
        # 并发设置
        concurrent_layout = QHBoxLayout()
        concurrent_layout.addWidget(QLabel("并发数量:"))
        
        self.concurrent_spin = QSpinBox()
        self.concurrent_spin.setRange(1, 10)
        self.concurrent_spin.setValue(3)
        self.concurrent_spin.valueChanged.connect(self.update_model_groups)  # 修复信号绑定
        concurrent_layout.addWidget(self.concurrent_spin)
        concurrent_layout.addStretch(1)
        
        # 水平布局的模型容器
        models_container = QWidget()
        models_layout = QHBoxLayout(models_container)
        models_layout.setSpacing(15)
        
        self.model_groups = []
        
        # 初始模型组
        for i in range(3):
            group = self.create_model_group(i+1)
            models_layout.addWidget(group)
            self.model_groups.append(group)
        
        layout.addLayout(concurrent_layout)
        layout.addWidget(models_container)
        
        # 添加流程说明
        layer1_guide = QLabel("↑ 同时请求多个AI模型，获取不同结果")
        layer1_guide.setAlignment(Qt.AlignRight)
        layer1_guide.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(layer1_guide)
        
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
        vendor_combo
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
        response_text.setMinimumHeight(150)
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
        self.layer2.setStyleSheet("QGroupBox { font-weight: bold; }")
        layout = QVBoxLayout()
        
        # 评分显示
        self.score_text = QTextEdit()
        self.score_text.setReadOnly(True)
        self.score_text.setMinimumHeight(120)
        self.score_text.setPlaceholderText("模型评价分数将显示在这里...")
        
        layout.addWidget(self.score_text)
        
        # 添加流程说明
        layer2_guide = QLabel("↑ 对多个模型的响应进行质量评价和评分")
        layer2_guide.setAlignment(Qt.AlignRight)
        layer2_guide.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(layer2_guide)
        
        self.layer2.setLayout(layout)
        self.layer_container.addWidget(self.layer2)
    
    def create_layer3(self):
        """创建汇总层"""
        self.layer3 = QGroupBox("3. 汇总层")
        self.layer3.setStyleSheet("QGroupBox { font-weight: bold; }")
        layout = QVBoxLayout()
        
        # 汇总结果显示
        self.summary_text = QTextEdit()
        self.summary_text.setReadOnly(True)
        self.summary_text.setMinimumHeight(120)
        self.summary_text.setPlaceholderText("汇总结果将显示在这里...")
        
        layout.addWidget(self.summary_text)
        
        # 添加流程说明
        layer3_guide = QLabel("↑ 综合多个模型的响应生成最终结果")
        layer3_guide.setAlignment(Qt.AlignRight)
        layer3_guide.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(layer3_guide)
        
        self.layer3.setLayout(layout)
        self.layer_container.addWidget(self.layer3)
    
    def create_layer4(self):
        """创建风格层"""
        self.layer4 = QGroupBox("4. 风格层")
        self.layer4.setStyleSheet("QGroupBox { font-weight: bold; }")
        layout = QVBoxLayout()
        
        # 风格选择
        style_layout = QHBoxLayout()
        style_layout.addWidget(QLabel("输出风格:"))
        
        self.style_combo = QComboBox()
        self.style_combo.addItems(["正式", "简洁", "专业", "幽默", "学术"])
        style_layout.addWidget(self.style_combo)
        style_layout.addStretch(1)
        
        # 风格化结果显示
        self.style_text = QTextEdit()
        self.style_text.setReadOnly(True)
        self.style_text.setMinimumHeight(150)
        self.style_text.setPlaceholderText("风格化处理结果将显示在这里...")
        
        layout.addLayout(style_layout)
        layout.addWidget(self.style_text)
        
        # 添加流程说明
        layer4_guide = QLabel("↑ 调整最终结果的语气和表达风格")
        layer4_guide.setAlignment(Qt.AlignRight)
        layer4_guide.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(layer4_guide)
        
        self.layer4.setLayout(layout)
        self.layer_container.addWidget(self.layer4)
    
    def create_layer5(self):
        """创建补正层"""
        self.layer5 = QGroupBox("5. 补正层")
        self.layer5.setStyleSheet("QGroupBox { font-weight: bold; }")
        layout = QVBoxLayout()
        
        # 补正结果显示
        self.correction_text = QTextEdit()
        self.correction_text.setReadOnly(True)
        self.correction_text.setMinimumHeight(150)
        self.correction_text.setPlaceholderText("补正结果将显示在这里...")
        
        layout.addWidget(self.correction_text)
        
        # 添加最终流程说明
        layer5_guide = QLabel("↑ 最终优化和修正，得到最终结果")
        layer5_guide.setAlignment(Qt.AlignRight)
        layer5_guide.setStyleSheet("color: #666; font-style: italic;")
        layout.addWidget(layer5_guide)
        
        # 完成标记
        finish_label = QLabel("✓ 流程完成")
        finish_label.setAlignment(Qt.AlignCenter)
        finish_label.setStyleSheet("font-weight: bold; color: green; font-size: 14px; padding-top: 10px;")
        layout.addWidget(finish_label)
        
        self.layer5.setLayout(layout)
        self.layer_container.addWidget(self.layer5)
    
    def update_layer_visibility(self):
        """根据选择的层数更新各层的可见性"""
        layers = self.layer_spin.value()
        
        # 更新层标题以反映可见性
        self.layer1.setTitle(f"1. 请求并发层")
        if layers >= 3:
            self.layer2.setTitle(f"2. 评价层")
        if layers >= 4:
            self.layer3.setTitle(f"3. 汇总层")
        self.layer4.setTitle(f"{layers}. 风格层" if layers < 5 else "4. 风格层")
        if layers >= 5:
            self.layer5.setTitle("5. 补正层")
        
        # 第一层和第四层始终显示
        self.layer1.setVisible(True)
        self.layer4.setVisible(True)
        
        # 第二层在>=3层时显示
        self.layer2.setVisible(layers >= 3)
        
        # 第三层在>=4层时显示
        self.layer3.setVisible(layers >= 4)
        
        # 第五层在>=5层时显示
        self.layer5.setVisible(layers >= 5)
    
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

if __name__ == "__main__":
    import sys
    from PyQt5.QtWidgets import QMainWindow, QTextEdit
    
    class MainWindow(QMainWindow):
        def __init__(self):
            super().__init__()
            self.setWindowTitle("主应用窗口")
            self.setGeometry(100, 100, 800, 600)
            
            # 创建中央部件
            central_widget = QTextEdit()
            central_widget.setPlaceholderText("这里是主应用内容区域...")
            self.setCentralWidget(central_widget)
            
            # 添加主题选择按钮
            theme_button = QPushButton("更换主题", self)
            theme_button.move(20, 20)
            theme_button.clicked.connect(self.open_theme_selector)
        
        def open_theme_selector(self):
            selector = ThemeSelector(self,init_path=r'C:\Users\Administrator\Desktop\chatApi\ChatWindowWithLLMApi')
            selector.show()
    
    app = QApplication(sys.argv)
    wifndow = MainWindow()
    wifndow.show()

if __name__ == "__main__":

    window = AIWorkflowUI()
    window.show()
    sys.exit(app.exec_())