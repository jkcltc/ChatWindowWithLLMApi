from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *
import json,os

#函数管理器
class FunctionManager:
    def __init__(self):
        self.functions = {}  # 存储函数信息的字典结构
        self.function_library = FunctionLibrary()
        self.init_functions()  # 初始化时自动加载函数库

    def init_functions(self):
        """从函数库加载所有预定义函数"""
        # 遍历函数库中的所有预定义函数
        for func in self.function_library.functions:
            # 解析每个函数描述（支持多个描述）
            for desc in func["description"]:
                if desc["type"] == "function":
                    func_info = desc["function"]
                    # 注册函数到管理器
                    self.add_function(
                        name=func_info["name"],
                        function=func["definition"],
                        description=func_info["description"],
                        parameters=func_info["parameters"]
                    )

    def add_function(self, name, function, description, parameters):
        """
        添加新函数
        :param name: 函数名称（需与AI模型返回一致）
        :param function: 函数实现（可调用对象）
        :param description: 功能描述（用于模型理解）
        :param parameters: 参数规范（JSON Schema格式）
        """
        if name in self.functions:
            raise ValueError(f"Function '{name}' already exists")
            
        self.functions[name] = {
            'function': function,
            'description': description,
            'parameters': parameters
        }

    def remove_function(self, name):
        """删除指定函数"""
        if name not in self.functions:
            raise KeyError(f"Function '{name}' not found")
        del self.functions[name]

    def update_function(self, name, function=None, description=None, parameters=None):
        """
        更新现有函数
        :param name: 要更新的函数名称
        :param function: 新的函数实现（可选）
        :param description: 新的描述（可选）
        :param parameters: 新的参数规范（可选）
        """
        if name not in self.functions:
            raise KeyError(f"Function '{name}' not found")

        entry = self.functions[name]
        if function is not None:
            entry['function'] = function
        if description is not None:
            entry['description'] = description
        if parameters is not None:
            entry['parameters'] = parameters

    def get_function(self, name):
        """获取单个函数信息"""
        return self.functions.get(name)

    def get_functions_list(self):
        """获取符合OpenAI格式的函数列表"""
        return [{
            'name': name,
            'description': info['description'],
            'parameters': info['parameters']
        } for name, info in self.functions.items()]

    def call_function(self, function_call_dict):
        """
        适配流式函数调用格式
        :param function_call_dict: 包含完整函数调用信息的字典
        Example格式:
        {
            "id": "call_abc123",
            "type": "function",
            "function": {
                "name": "get_weather",
                "arguments": {"location": "Beijing"}
            }
        }
        """
        print(f"Function call dict: {function_call_dict}")
        # 参数校验
        if not isinstance(function_call_dict, dict):
            raise ValueError("Function call must be a dictionary")
        
        try:
            # 提取关键信息
            func_name = function_call_dict["function"]["name"]
            arguments = function_call_dict["function"]["arguments"]
            
            # 类型安全校验
            if not isinstance(arguments, dict):
                raise TypeError(f"Arguments should be dict, got {type(arguments)}")
            
            # 调用核心逻辑
            return self._execute_function(func_name, arguments)
        except KeyError as e:
            raise ValueError(f"Missing required field in function call: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Function call failed: {str(e)}") from e

    def _execute_function(self, name, arguments):
        """实际执行函数的内部方法"""
        func_info = self.functions.get(name)
        if not func_info:
            raise ValueError(f"Function '{name}' not found")

        try:
            # 参数类型二次校验
            if not isinstance(arguments, dict):
                arguments = json.loads(arguments) if isinstance(arguments, str) else {}
                
            return func_info['function'](**arguments)
        except json.JSONDecodeError:
            raise ValueError(f"Invalid JSON arguments for {name}")
        except TypeError as e:
            raise ValueError(f"Invalid arguments for {name}: {str(e)}")
        except Exception as e:
            raise RuntimeError(f"Runtime error in {name}: {str(e)}")

#函数选择器UI
class FunctionSelectorUI(QWidget):
    def __init__(self, function_manager, parent=None):
        super().__init__(parent)
        self.function_manager = function_manager  # 函数管理器实例
        self.selected_functions = []              # 存储选中函数名称的列表
        self.init_ui()
        self.refresh_functions()

    def init_ui(self):
        """初始化界面布局"""
        self.setWindowTitle('Function Selector')
        self.setMinimumSize(400, 300)

        # 主滚动区域
        self.scroll = QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QFrame.NoFrame)

        # 滚动区域内容容器
        self.content_widget = QWidget()
        self.layout = QVBoxLayout(self.content_widget)
        self.layout.setAlignment(Qt.AlignTop)
        
        self.scroll.setWidget(self.content_widget)

        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.addWidget(self.scroll)
        self.setLayout(main_layout)

    def refresh_functions(self):
        """刷新函数列表显示"""
        # 清空现有复选框
        while self.layout.count():
            item = self.layout.takeAt(0)
            if widget := item.widget():
                widget.deleteLater()
        
        # 添加新复选框
        functions = self.function_manager.get_functions_list()
        for func in functions:
            self._add_function_checkbox(func)

    def _add_function_checkbox(self, func):
        """添加单个函数复选框"""
        cb = QCheckBox(self._format_checkbox_text(func), self.content_widget)
        cb.setObjectName(func['name'])  # 使用函数名作为对象标识
        
        # 使用带参数的lambda保证正确捕获变量
        cb.toggled.connect(
            lambda checked, name=func['name']: 
            self._handle_checkbox_toggle(name, checked)
        )
        
        self.layout.addWidget(cb)

    def _format_checkbox_text(self, func):
        """格式化复选框显示文本"""
        return f"{func['name']}\n{func['description']}"

    def _handle_checkbox_toggle(self, name, checked):
        """处理复选框状态变化"""
        if checked and name not in self.selected_functions:
            self.selected_functions.append(name)
        elif not checked and name in self.selected_functions:
            self.selected_functions.remove(name)

    def get_selected_functions(self):
        """获取当前选中函数列表（按名称）"""
        return self.selected_functions.copy()

    def get_selected_function_details(self):
        """获取选中函数的详细信息"""
        return [
            self.function_manager.get_function(name)
            for name in self.selected_functions
        ]

#function库
class FunctionLibrary:
    def __init__(self):
        self.functions=[
            {
            "name": "open_file",
            "description": [
    {
        "type": "function",
        "function": {
            "name": "open_file",
            "description": "Open a file, can be a URL or a local file",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL/path to open",
                    }
                },
                "required": ["url"]
            },
        }
    },
],
            "definition": FunctionLibrary.open_file
        },

        {
            "name": "python_cmd",
            "description": [
    {
        "type": "function",
        "function": {
            "name": "python_cmd",
            "description": "A Python interpreter that will exec() the code you provide,and will return the content in the print(). Ensure the code is safe.",
            "parameters": {
                "type": "object",
                "properties": {
                    "code": {
                        "type": "string",
                        "description": "python code to exec(),do not use markdown",
                    }
                },
                "required": ["code"]
            },
        }
    },
],
            "definition": FunctionLibrary.python_cmd
        },
    {
            "name": "sys_time",
            "description": [
    {
        "type": "function",
        "function": {
            "name": "sys_time",
            "description": "get the current date and time",
            "parameters": {
                "type": "object",
                "properties": {
                    "type": {
                        "type": "string",
                        "description": "date or exact time",
                    }
                },
                "required": ["type"]
            },
        }
    },
],
            "definition": FunctionLibrary.get_current_time
        }
]


    @staticmethod
    def weather_test(**kwargs):
        """天气查询函数"""
        # 这里可以添加实际的天气查询逻辑
        return f"Weather is sunny. 0°C. Windy."

    @staticmethod
    def open_file(**kwargs):
        """打开网页函数"""
        url = kwargs.get("url", "")
        try:
            os.startfile(url)
            return f"Opened {url}"
        except Exception as e:
            return f"Failed to open {url}: {str(e)}"
    
    @staticmethod
    def python_cmd(**kwargs):
        """Python命令执行函数，捕获print输出"""
        import contextlib
        from io import StringIO
        code = kwargs.get("code", "")
        code = code.replace('```python', '').replace('```', '').replace('`', '')
        print(f"Executing code: {code}")
        output_buffer = StringIO()
        try:
            with contextlib.redirect_stdout(output_buffer):
                exec(code, {})  # 在独立环境中执行代码
            captured_output = output_buffer.getvalue().strip()
            if len(captured_output)>10000:
                return '部分执行'+captured_output[0:10000]+"\n部分执行\ntoo many output!\nthe rest is abandoned"
            if len(captured_output) == 0:
                return '执行成功，无输出内容'
            return f"执行成功，输出内容：\n{captured_output}"
        except Exception as e:
            return f"执行失败：{str(e)}"

    @staticmethod
    def get_current_time(**kwargs):
        """获取当前日期时间函数"""
        import datetime
        current_time = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        return f"当前时间：{current_time}"

