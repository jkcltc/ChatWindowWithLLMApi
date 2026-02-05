from PyQt6.QtWidgets import *
from PyQt6.QtCore import *
from PyQt6.QtGui import *
import json,re

class VariableItemWidget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.init_ui()
        self.setup_animation()

    def init_ui(self):
        # 创建控件
        self.variable_name_edit = QLineEdit()
        self.variable_name_edit.setPlaceholderText("变量名")
        self.variable_value_edit = QLineEdit()
        self.variable_value_edit.setPlaceholderText("变量值")
        self.ai_checkbox = QCheckBox("启用AI自动更新")
        self.cycle_checkbox = QCheckBox("启用循环加减")
        self.cycle_step_edit = QLineEdit()
        self.cycle_step_edit.setPlaceholderText("步长")
        self.cycle_step_edit.setFixedWidth(80)
        self.cycle_step_edit.setEnabled(False)

        # 布局
        layout = QHBoxLayout()
        layout.addWidget(self.variable_name_edit)
        layout.addWidget(self.variable_value_edit)
        layout.addWidget(self.ai_checkbox)
        layout.addWidget(self.cycle_checkbox)
        layout.addWidget(self.cycle_step_edit)
        self.setLayout(layout)

        # 创建高光覆盖层
        self.highlight_overlay = QWidget(self)
        self.highlight_overlay.setStyleSheet("background-color: rgba(173, 216, 230, 50);")
        self.highlight_overlay.hide()
        self.highlight_overlay.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents)
        
        # 添加透明度效果
        self.opacity_effect = QGraphicsOpacityEffect(self.highlight_overlay)
        self.opacity_effect.setOpacity(1.0)
        self.highlight_overlay.setGraphicsEffect(self.opacity_effect)

        # 信号连接
        self.cycle_checkbox.stateChanged.connect(self.toggle_cycle_step)

    def setup_animation(self):
        # 创建动画组
        self.animation_group = QSequentialAnimationGroup(self)

        # 宽度展开动画
        self.width_animation = QPropertyAnimation(self.highlight_overlay, b"geometry")
        self.width_animation.setDuration(400)
        self.width_animation.setEasingCurve(QEasingCurve.Type.OutCubic)

        # 修改后的淡出动画（使用opacity效果）
        self.fade_animation = QPropertyAnimation(self.opacity_effect, b"opacity")
        self.fade_animation.setDuration(450)  # 延长淡出时间
        self.fade_animation.setStartValue(1.0)
        self.fade_animation.setEndValue(0.0)
        self.fade_animation.setEasingCurve(QEasingCurve.Type.OutQuad)

        self.animation_group.addAnimation(self.width_animation)
        self.animation_group.addAnimation(self.fade_animation)
        self.animation_group.finished.connect(self.on_animation_finished)

    def toggle_cycle_step(self, state):
        self.cycle_step_edit.setEnabled(state == Qt.CheckState.Checked)

    def perform_cycle_step(self):
        try:
            step = float(self.cycle_step_edit.text())
        except ValueError:
            return

        current_value = self.variable_value_edit.text()
        if '%' in current_value:
            try:
                value = float(current_value.strip('%'))
                new_value = value + step
                self.variable_value_edit.setText(f"{new_value}%")
            except:
                return
        else:
            try:
                value = float(current_value)
                new_value = value + step
                self.variable_value_edit.setText(str(new_value))
            except:
                return

    def set_variable_value(self, value):
        """设置变量值并触发高光动画"""
        self.variable_value_edit.setText(value)
        self.start_highlight_animation()

    def start_highlight_animation(self):
        """启动高光动画（增加初始化设置）"""
        # 重置覆盖层状态
        self.highlight_overlay.setGeometry(0, 0, 0, self.height())
        self.opacity_effect.setOpacity(1.0)  # 确保每次动画前重置透明度
        self.highlight_overlay.show()
        self.highlight_overlay.raise_()

        # 设置动画参数
        end_width = self.width()
        self.width_animation.setStartValue(QRect(0, 0, 0, self.height()))
        self.width_animation.setEndValue(QRect(0, 0, end_width, self.height()))
        
        self.animation_group.start()

    def on_animation_finished(self):
        """动画完成后完全隐藏覆盖层"""
        self.highlight_overlay.hide()
        self.opacity_effect.setOpacity(1.0)  # 重置透明度以备下次使用

        
class StatusMonitorWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.init_ui()
        self.name_ai = None

    def init_ui(self):
        self.setWindowTitle("角色状态")
        self.setMinimumSize(800, 400)

        # 创建控件
        self.list_widget = QListWidget()
        self.add_btn = QPushButton("添加变量")
        self.del_btn = QPushButton("删除选中变量")
        
        # 布局
        main_layout = QVBoxLayout()
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.add_btn)
        btn_layout.addWidget(self.del_btn)
        
        main_layout.addLayout(btn_layout)
        main_layout.addWidget(self.list_widget)

        self.name_ai_label=QLabel("挂载角色名称")
        main_layout.addWidget(self.name_ai_label)
        self.name_ai_textedit=QLineEdit()
        self.name_ai_textedit.textChanged.connect(lambda text: setattr(self, 'name_ai', text))
        self.name_ai_textedit.textChanged.connect(self._update_names)
        main_layout.addWidget(self.name_ai_textedit)
        self.setLayout(main_layout)

        # 信号连接
        self.add_btn.clicked.connect(self.add_item)
        self.del_btn.clicked.connect(self.del_item)

    def _update_names(self):
        self.name_ai=self.name_ai_textedit.text()
        if self.name_ai and self.name_ai!='':
            self.setWindowTitle(self.name_ai+'的状态')
        else:
            self.setWindowTitle('角色状态')

    def add_item(self):
        item = QListWidgetItem()
        widget = VariableItemWidget()
        item.setSizeHint(widget.sizeHint())
        self.list_widget.addItem(item)
        self.list_widget.setItemWidget(item, widget)

    def del_item(self):
        current_row = self.list_widget.currentRow()
        if current_row >= 0:
            self.list_widget.takeItem(current_row)

    # 方法1: 获取所有变量
    def get_all_variables(self):
        variables = {}
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            widget = self.list_widget.itemWidget(item)
            name = widget.variable_name_edit.text()
            value = widget.variable_value_edit.text()
            variables[name] = value
        return variables

    # 方法2: 获取AI自动更新变量
    def get_ai_variables(self,use_str=False):
        variables = {}
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            widget = self.list_widget.itemWidget(item)
            if widget.ai_checkbox.isChecked():
                name = widget.variable_name_edit.text()
                value = widget.variable_value_edit.text()
                variables[name] = value
        if use_str:
            if variables != {}:
                ai_update_text = ''
                for key, value in variables.items():  # Fixed: use .items() for dictionary iteration
                    ai_update_text += f'{key}={value},\n'
                variables = '在回复的同时更新变量组，只更新下述内容，保持下述格式：\n变量组开始\n{' + ai_update_text + '}变量组结束\n'
            else:
                variables = ''
        
        return variables

    # 方法3: 更新AI变量
    def update_ai_variables(self, variables):
        cleaned_vars = self.parse_variables(variables)
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            widget = self.list_widget.itemWidget(item)
            if widget.ai_checkbox.isChecked():
                name = widget.variable_name_edit.text()
                if name in cleaned_vars:
                    widget.set_variable_value(str(cleaned_vars[name]))
    
    def parse_variables(self,input_data):
        """
        清洗和解析变量输入数据，将其转换为标准的字典格式
        
        参数:
            input_data: 可能是以下格式的数据:
                - 字典(dict)
                - JSON字符串(str)
                - str(dict)出来的字符串
                - 包含中文字符冒号的字符串
                - 包含在「变量组开始」和「变量组结束」中的键值对文本
        
        返回:
            解析后的字典，格式为 {变量名: 变量值}
            如果解析失败返回空字典 {}
        """
        # 如果输入已经是字典，直接返回
        if isinstance(input_data, dict):
            return input_data.copy()

        # 非字典类型尝试转换为字符串
        if not isinstance(input_data, str):
            try:
                input_data = str(input_data)
            except:
                return {}

        # 预处理：替换中文标点及全角符号
        input_data = input_data.replace('：', ':').replace('＝', '=').replace(',', '').strip()

        # 尝试1：解析为JSON
        try:
            return json.loads(input_data)
        except:
            pass

        # 尝试2：处理单引号包裹的类字典字符串
        if re.match(r'^\{.*\}$', input_data):
            try:
                # 单引号转双引号并移除可能存在的u前缀
                sanitized = re.sub(r"'\s*:\s*u'", '": "', input_data) \
                            .replace("'", '"') \
                            .replace("u\"", "\"")
                return json.loads(sanitized)
            except:
                pass

        # 尝试3：提取「变量组开始」和「变量组结束」之间的内容
        pattern = r'(?:变量组开始|VariablesStart)[\n\s]*({?.*?})?[\n\s]*(?:变量组结束|VariablesEnd)'
        match = re.search(pattern, input_data, re.DOTALL | re.IGNORECASE)
        if match:
            # 提取花括号内容或直接取匹配组内容
            target_text = match.group(1) or match.group(0)
            
            # 移除所有花括号和方括号
            target_text = re.sub(r'[{}[\]]', '', target_text)
            
            # 键值对解析（支持多分隔符和嵌套符号）
            data = {}
            for line in target_text.split('\n'):
                line = line.strip()
                if not line or line.startswith(('#', '//')):  # 跳过注释行
                    continue

                # 支持用=、:、->等符号作为分隔符
                if any(sym in line for sym in ('=', ':', '->')):
                    # 使用正则提取键值对（包含处理转义字符的逻辑）
                    match = re.match(
                        r'^[\'"]?(?P<key>[^=:]+?)[\'"]?\s*[=:]\s*[\'"]?(?P<value>.+?)[\'"]?$', 
                        line
                    )
                    if match:
                        key = match.group('key').strip()
                        value = match.group('value').strip().strip('"').strip("'")
                        data[key] = value
            if data:
                return data

        # 最终尝试：自由格式键值对解析
        data = {}
        for line in input_data.split('\n'):
            line = line.partition('#')[0].partition('//')[0].strip()  # 移除行内注释
            if not line:
                continue

            # 增强型分隔符识别（支持包含空格的键值）
            if '=' in line:
                key, _, value = line.partition('=')
            elif ':' in line:
                key, _, value = line.partition(':')
            else:
                continue

            key = key.strip()
            value = value.strip().strip('"').strip("'")
            if key:
                data[key] = value

        return data if data else {}
    
    # 方法4: 执行循环加减
    def perform_cycle_step(self):
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            widget = self.list_widget.itemWidget(item)
            if widget.cycle_checkbox.isChecked():
                widget.perform_cycle_step()

    # 方法5: 获取最简字符串
    def get_simplified_variables(self, ai_only=False):
        variables = {}
        for i in range(self.list_widget.count()):
            item = self.list_widget.item(i)
            widget = self.list_widget.itemWidget(item)
            if ai_only and not widget.ai_checkbox.isChecked():
                continue
                
            name = widget.variable_name_edit.text()
            value = widget.variable_value_edit.text()
            addon = widget.cycle_step_edit.text()
            try:
                num = float(addon)
                addon = f"+{addon}" if num > 0 else addon
            except Exception as e:
                pass
            if widget.cycle_step_edit.text()!='':
                addon = '('+addon+')'
            else:
                addon = ''
            # 处理百分比
            if '%' in value:
                try:
                    num = float(value.strip('%'))
                    num = f"{int(num)}%" if num.is_integer() else f"{num}%"
                    variables[name]= num+addon
                except:
                    variables[name] = str(value)+addon
            else:
                try:
                    num = float(value)
                    num = str(int(num)) if num.is_integer() else str(num)
                    variables[name] = num +addon
                except:
                    variables[name] = str(value)+addon
        
        variables = str(variables).replace("'", '').replace("\n", '').replace(" ", '')
        if self.name_ai:
            variables=str(self.name_ai)+':'+variables
        variables='[system/story teller|'+variables+"]\n"
        return variables

class TestWindow(QWidget):
    def __init__(self, tool_window):
        super().__init__()
        self.tool_window = tool_window
        self.init_ui()
        
    def init_ui(self):
        self.setWindowTitle("测试控制面板")
        self.setGeometry(100, 100, 600, 400)

        # 创建控件
        self.result_display = QTextEdit()
        self.result_display.setReadOnly(True)
        
        self.btn_get_all = QPushButton("获取所有变量")
        self.btn_get_ai = QPushButton("获取AI变量")
        self.btn_update_ai = QPushButton("更新AI变量")
        self.btn_cycle = QPushButton("执行循环加减")
        self.btn_get_simplified = QPushButton("获取简化变量")
        
        self.test_input = QLineEdit()
        self.test_input.setPlaceholderText("输入测试变量（格式：变量名=值）")
        self.add_test_btn = QPushButton("添加测试变量")

        # 布局
        main_layout = QVBoxLayout()
        
        # 测试操作区
        test_controls = QHBoxLayout()
        test_controls.addWidget(self.add_test_btn)
        test_controls.addWidget(self.test_input)
        
        # 功能按钮区
        btn_layout = QHBoxLayout()
        btn_layout.addWidget(self.btn_get_all)
        btn_layout.addWidget(self.btn_get_ai)
        btn_layout.addWidget(self.btn_update_ai)
        btn_layout.addWidget(self.btn_cycle)
        btn_layout.addWidget(self.btn_get_simplified)
        
        main_layout.addLayout(test_controls)
        main_layout.addLayout(btn_layout)
        main_layout.addWidget(self.result_display)
        
        self.setLayout(main_layout)

        # 连接信号
        self.btn_get_all.clicked.connect(self.show_all_variables)
        self.btn_get_ai.clicked.connect(self.show_ai_variables)
        self.btn_update_ai.clicked.connect(self.update_ai_vars)
        self.btn_cycle.clicked.connect(self.execute_cycle)
        self.btn_get_simplified.clicked.connect(self.show_simplified)
        self.add_test_btn.clicked.connect(self.add_test_variable)

    def display_result(self, data):
        """格式化显示字典数据"""
        self.result_display.setText(str(data))

    def show_all_variables(self):
        self.display_result(self.tool_window.get_all_variables())

    def show_ai_variables(self):
        self.display_result(self.tool_window.get_ai_variables())

    def update_ai_vars(self):
        # 示例更新数据（可根据需要扩展输入）
        update_data = {
            "temperature": "35.5",
            "humidity": "60%"
        }
        self.tool_window.update_ai_variables(update_data)
        self.result_display.append("\n已更新AI变量：")
        self.display_result(update_data)

    def execute_cycle(self):
        self.tool_window.perform_cycle_step()
        self.result_display.append("\n已执行循环加减，当前变量：")
        self.display_result(self.tool_window.get_all_variables())

    def show_simplified(self):
        simplified = self.tool_window.get_simplified_variables()
        self.display_result(simplified)

    def add_test_variable(self):
        """通过输入框添加测试变量"""
        text = self.test_input.text()
        if '=' in text:
            name, value = text.split('=', 1)
            self._add_variable(name.strip(), value.strip())
            self.test_input.clear()

    def _add_variable(self, name, value):
        """实际添加变量到工具窗口"""
        item = QListWidgetItem()
        widget = VariableItemWidget()
        widget.variable_name_edit.setText(name)
        widget.variable_value_edit.setText(value)
        # 随机设置部分复选框用于测试
        if name.startswith("ai_"):
            widget.ai_checkbox.setChecked(True)
        if name.startswith("cycle_"):
            widget.cycle_checkbox.setChecked(True)
            widget.cycle_step_edit.setText("5")
        item.setSizeHint(widget.sizeHint())
        self.tool_window.list_widget.addItem(item)
        self.tool_window.list_widget.setItemWidget(item, widget)

class StatusMonitorInstruction:
    def mod_main_function():
        return {"ui":StatusMonitorWindow,"name":"status_monitor_window"}
    def mod_configer():
        return QLabel("已集成在主UI")


if __name__ == '__main__':
    app = QApplication([])
    
    # 创建工具窗口
    tool_win = StatusMonitorWindow()
    tool_win.show()
    
    # 创建测试窗口
    test_win = TestWindow(tool_win)
    test_win.show()
    
    # 添加初始测试数据
    test_win._add_variable("temperature", "25.5")
    test_win._add_variable("ai_humidity", "60%")
    test_win._add_variable("cycle_pressure", "100")
    
    app.exec()