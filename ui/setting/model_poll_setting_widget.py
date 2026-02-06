import random
from PyQt6.QtWidgets import (
    QWidget,QLabel,QGridLayout,
    QGroupBox,QPushButton,QSizePolicy,
    QComboBox,QMessageBox,QRadioButton,
    QListView,QAbstractItemView
)
from PyQt6.QtCore import (
    QCoreApplication,QMetaObject
)
from PyQt6.QtGui import QStandardItem,QStandardItemModel

from config.settings import LLMUsagePack,ApiConfig,ModelPollSettings

#随机分发模型请求
class Ui_random_model_selecter(object):
    def setupUi(self, random_model_selecter):
        random_model_selecter.setObjectName("random_model_selecter")
        random_model_selecter.resize(408, 305)
        self.gridLayout_5 = QGridLayout(random_model_selecter)
        self.gridLayout_5.setObjectName("gridLayout_5")
        self.groupBox = QGroupBox(random_model_selecter)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(1)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.groupBox.sizePolicy().hasHeightForWidth())
        self.groupBox.setSizePolicy(sizePolicy)
        self.groupBox.setObjectName("groupBox")
        self.gridLayout_4 = QGridLayout(self.groupBox)
        self.gridLayout_4.setObjectName("gridLayout_4")
        self.order_radio = QRadioButton(self.groupBox)
        self.order_radio.setChecked(True)
        self.order_radio.setObjectName("order_radio")
        self.gridLayout_4.addWidget(self.order_radio, 0, 0, 1, 1)
        self.random_radio = QRadioButton(self.groupBox)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Minimum, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(1)
        sizePolicy.setHeightForWidth(self.random_radio.sizePolicy().hasHeightForWidth())
        self.random_radio.setSizePolicy(sizePolicy)
        self.random_radio.setObjectName("random_radio")
        self.gridLayout_4.addWidget(self.random_radio, 1, 0, 1, 1)
        self.gridLayout_5.addWidget(self.groupBox, 1, 0, 1, 1)
        self.groupBox_add_model = QGroupBox(random_model_selecter)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(1)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.groupBox_add_model.sizePolicy().hasHeightForWidth())
        self.groupBox_add_model.setSizePolicy(sizePolicy)
        self.groupBox_add_model.setObjectName("groupBox_add_model")
        self.gridLayout_2 = QGridLayout(self.groupBox_add_model)
        self.gridLayout_2.setObjectName("gridLayout_2")
        self.groupBox_model_config = QGroupBox(self.groupBox_add_model)
        self.groupBox_model_config.setObjectName("groupBox_model_config")
        self.gridLayout = QGridLayout(self.groupBox_model_config)
        self.gridLayout.setObjectName("gridLayout")
        self.model_name_label = QLabel(self.groupBox_model_config)
        self.model_name_label.setObjectName("model_name_label")
        self.gridLayout.addWidget(self.model_name_label, 2, 0, 1, 1)
        self.model_name = QComboBox(self.groupBox_model_config)
        self.model_name.setObjectName("model_name")
        self.gridLayout.addWidget(self.model_name, 3, 0, 1, 1)
        self.model_provider_label = QLabel(self.groupBox_model_config)
        self.model_provider_label.setObjectName("model_provider_label")
        self.gridLayout.addWidget(self.model_provider_label, 0, 0, 1, 1)
        self.model_provider = QComboBox(self.groupBox_model_config)
        self.model_provider.setObjectName("model_provider")
        self.gridLayout.addWidget(self.model_provider, 1, 0, 1, 1)
        self.gridLayout_2.addWidget(self.groupBox_model_config, 0, 0, 1, 1)
        self.add_model_to_list = QPushButton(self.groupBox_add_model)
        self.add_model_to_list.setObjectName("add_model_to_list")
        self.gridLayout_2.addWidget(self.add_model_to_list, 1, 0, 1, 1)
        self.gridLayout_5.addWidget(self.groupBox_add_model, 0, 0, 1, 1)
        self.label = QLabel(random_model_selecter)
        self.label.setText("")
        self.label.setObjectName("label")
        self.gridLayout_5.addWidget(self.label, 3, 1, 1, 1)
        self.confirm_button = QPushButton(random_model_selecter)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        sizePolicy.setHorizontalStretch(0)
        sizePolicy.setVerticalStretch(0)
        sizePolicy.setHeightForWidth(self.confirm_button.sizePolicy().hasHeightForWidth())
        self.confirm_button.setSizePolicy(sizePolicy)
        self.confirm_button.setObjectName("confirm_button")
        self.gridLayout_5.addWidget(self.confirm_button, 3, 2, 1, 1)
        self.groupBox_view_model = QGroupBox(random_model_selecter)
        sizePolicy = QSizePolicy(QSizePolicy.Policy.Preferred, QSizePolicy.Policy.Preferred)
        sizePolicy.setHorizontalStretch(2)
        sizePolicy.setVerticalStretch(1)
        sizePolicy.setHeightForWidth(self.groupBox_view_model.sizePolicy().hasHeightForWidth())
        self.groupBox_view_model.setSizePolicy(sizePolicy)
        self.groupBox_view_model.setObjectName("groupBox_view_model")
        self.gridLayout_3 = QGridLayout(self.groupBox_view_model)
        self.gridLayout_3.setObjectName("gridLayout_3")
        self.random_model_list_viewer = QListView(self.groupBox_view_model)
        self.random_model_list_viewer.setObjectName("random_model_list_viewer")
        self.gridLayout_3.addWidget(self.random_model_list_viewer, 0, 0, 1, 1)
        self.remove_model = QPushButton(self.groupBox_view_model)
        self.remove_model.setObjectName("remove_model")
        self.gridLayout_3.addWidget(self.remove_model, 1, 0, 1, 1)
        self.gridLayout_5.addWidget(self.groupBox_view_model, 0, 1, 2, 2)

        self.retranslateUi(random_model_selecter)
        QMetaObject.connectSlotsByName(random_model_selecter)

    def retranslateUi(self, random_model_selecter):
        _translate = QCoreApplication.translate
        random_model_selecter.setWindowTitle(_translate("random_model_selecter", "设置轮换/随机模型"))
        self.groupBox.setTitle(_translate("random_model_selecter", "使用模型"))
        self.order_radio.setText(_translate("random_model_selecter", "顺序输出"))
        self.random_radio.setText(_translate("random_model_selecter", "随机选择"))
        self.groupBox_add_model.setTitle(_translate("random_model_selecter", "添加模型"))
        self.groupBox_model_config.setTitle(_translate("random_model_selecter", ""))
        self.model_name_label.setText(_translate("random_model_selecter", "名称"))
        self.model_provider_label.setText(_translate("random_model_selecter", "提供商"))
        self.add_model_to_list.setText(_translate("random_model_selecter", "添加"))
        self.confirm_button.setText(_translate("random_model_selecter", "完成"))
        self.groupBox_view_model.setTitle(_translate("random_model_selecter", "模型库-使用的模型将在其中选择"))
        self.remove_model.setText(_translate("random_model_selecter", "移除选中项"))


class RandomModelSelecter(QWidget):
    def __init__(self, api_config: ApiConfig, poll_settings: ModelPollSettings, parent=None, logger=None):
        super().__init__(parent)
        self.ui = Ui_random_model_selecter()

        self.ui.setupUi(self)

        # 引用传入的 Pydantic 配置对象
        self.api_config = api_config
        self.poll_settings = poll_settings
        self.logger = logger

        # 运行时状态
        self.last_check = 0

        # 初始化流程
        self.init_list_view()
        self.init_providers()

        # 核心：加载数据和模式设置
        self.load_settings_to_ui()


        self.init_connections()

        

        # UI 初始刷新
        self.update_model_names()

    def init_providers(self):
        """初始化模型提供商下拉框"""
        self.ui.model_provider.clear()
        if self.api_config and self.api_config.providers:
            self.ui.model_provider.addItems(list(self.api_config.providers.keys()))

    def init_connections(self):
        """建立信号槽连接"""
        # 1. 下拉框与按钮
        self.ui.model_provider.currentTextChanged.connect(self.update_model_names)
        self.ui.add_model_to_list.clicked.connect(self.add_model_to_list)
        self.ui.remove_model.clicked.connect(self.remove_selected_model)
        self.ui.confirm_button.clicked.connect(self.hide)

        # 2. 模式切换 (顺序/随机) 绑定到配置对象
        self.ui.order_radio.toggled.connect(self._on_mode_changed)
        self.ui.random_radio.toggled.connect(self._on_mode_changed)

    def _on_mode_changed(self):
        """
        当单选框状态改变时，更新 poll_settings.mode
        """
        if self.ui.order_radio.isChecked():
            self.poll_settings.mode = 'order'
        else:
            self.poll_settings.mode = 'random'

    def init_list_view(self):
        """初始化列表视图"""
        self.list_model = QStandardItemModel()
        self.ui.random_model_list_viewer.setModel(self.list_model)
        self.ui.random_model_list_viewer.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.ui.random_model_list_viewer.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

    def update_model_names(self):
        """更新右侧具体的模型名称"""
        current_provider_key = self.ui.model_provider.currentText()
        self.ui.model_name.clear()

        if not current_provider_key:
            return

        provider_config = self.api_config.providers.get(current_provider_key)
        if provider_config and provider_config.models:
            self.ui.model_name.addItems(provider_config.models)
            self.ui.model_name.setCurrentIndex(0)

    def load_settings_to_ui(self):
        """
        将 poll_settings 中的数据（列表和模式）加载到 UI
        """
        # 1. 加载模型列表
        self.list_model.clear()
        if self.poll_settings.model_map:
            for pack in self.poll_settings.model_map:
                self._add_item_to_view(pack.provider, pack.model)

        # 2. 加载模式 (Order / Random)
        # 根据 poll_settings.mode 设置 UI 状态
        if self.poll_settings.mode == 'order':
            self.ui.order_radio.setChecked(True)
        else:
            # 默认为 random 或其他情况
            self.ui.random_radio.setChecked(True)

    def _add_item_to_view(self, provider: str, model: str):
        """仅向 UI 列表添加视觉项"""
        item_text = f"{provider} - {model}"
        item = QStandardItem(item_text)
        item.setData({"provider": provider, "model": model})
        self.list_model.appendRow(item)

    def add_model_to_list(self):
        """添加模型到配置对象和UI"""
        self.last_check = 0
        provider = self.ui.model_provider.currentText()
        model_name = self.ui.model_name.currentText()

        if not provider or not model_name:
            return

        # 查重
        for pack in self.poll_settings.model_map:
            if pack.provider == provider and pack.model == model_name:
                QMessageBox.warning(self, "警告", "该模型已存在于列表中！")
                return

        # 更新配置对象
        new_pack = LLMUsagePack(provider=provider, model=model_name)
        self.poll_settings.model_map.append(new_pack)

        # 更新UI
        self._add_item_to_view(provider, model_name)

        if self.logger:
            self.logger.log(f"[模型轮询] 添加: {provider}/{model_name}")

    def remove_selected_model(self):
        """移除模型"""
        selected_indexes = self.ui.random_model_list_viewer.selectedIndexes()
        if not selected_indexes:
            return

        for index in sorted(selected_indexes, key=lambda x: x.row(), reverse=True):
            row = index.row()
            if 0 <= row < len(self.poll_settings.model_map):
                removed = self.poll_settings.model_map.pop(row)
                if self.logger:
                    self.logger.log(f"[模型轮询] 移除: {removed.provider}/{removed.model}")
            self.list_model.removeRow(row)

        self.last_check = 0

    def get_next_model(self) -> LLMUsagePack | None:
        """
        运行时调用：获取下一个模型
        直接依据 poll_settings.mode 决定逻辑，不再依赖 UI 状态
        """
        if not self.poll_settings.model_map:
            if self.logger:
                self.logger.error("[模型轮询] 警告：列表为空，无法轮询！")
            return None

        models = self.poll_settings.model_map

        # 读取配置中的模式
        mode = self.poll_settings.mode

        if mode == 'order':
            self.last_check += 1
            selected_pack = models[self.last_check % len(models)]
            log_prefix = "顺序"
        else:
            # mode == 'random'
            selected_pack = random.choice(models)
            log_prefix = "随机"

        if self.logger:
            self.logger.log(f"[模型轮询][{log_prefix}] 切至: {selected_pack.provider} - {selected_pack.model}")

        return selected_pack

