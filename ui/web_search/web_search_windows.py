# websearch/ui/web_search_windows.py
from __future__ import annotations
import os
from typing import List

from PyQt6.QtWidgets import (
    QWidget, QVBoxLayout, QLabel, QComboBox, QLineEdit,
    QCheckBox, QPushButton, QListWidget, QListWidgetItem,
    QSizePolicy
)
from PyQt6.QtCore import Qt, QSize
from PyQt6.QtGui import QIntValidator, QDesktopServices
from PyQt6.QtCore import QUrl

from service.web_search.models import WebResult
from config import APP_SETTINGS  # UI 可以依赖全局设置

class WebSearchSettingWindows:
    def __init__(self):
        self.search_settings_widget = QWidget()
        self.search_settings_widget.setWindowTitle("搜索设置")

        self.search_results_widget = QWidget()
        self.search_results_widget.setWindowTitle("搜索结果")

        self._build_settings_ui()
        self._build_results_ui()

    @property
    def model_map(self):
        return APP_SETTINGS.api.model_map

    def _build_settings_ui(self):
        layout = QVBoxLayout(self.search_settings_widget)

        layout.addWidget(QLabel("搜索引擎"))
        self.engine_combo = QComboBox()
        self.engine_combo.addItems(["baidu", "bing"])
        self.engine_combo.setCurrentText(APP_SETTINGS.web_search.search_engine)
        layout.addWidget(self.engine_combo)

        layout.addWidget(QLabel("返回结果数"))
        self.result_num_edit = QLineEdit()
        self.result_num_edit.setValidator(QIntValidator())
        self.result_num_edit.setText(str(APP_SETTINGS.web_search.search_results_num))
        layout.addWidget(self.result_num_edit)

        self.rag_checkbox = QCheckBox("使用RAG过滤")
        self.rag_checkbox.setChecked(APP_SETTINGS.web_search.use_llm_reformat)
        layout.addWidget(self.rag_checkbox)

        self.rag_provider_label = QLabel("RAG 过滤器模型提供商")
        self.rag_provider_combo = QComboBox()
        self.rag_provider_combo.addItems(list(self.model_map.keys()))
        layout.addWidget(self.rag_provider_label)
        layout.addWidget(self.rag_provider_combo)

        self.rag_model_label = QLabel("RAG过滤模型")
        self.rag_model_combo = QComboBox()
        layout.addWidget(self.rag_model_label)
        layout.addWidget(self.rag_model_combo)

        def refresh_models():
            provider = self.rag_provider_combo.currentText()
            self.rag_model_combo.clear()
            self.rag_model_combo.addItems(self.model_map.get(provider, []))

        self.rag_provider_combo.currentTextChanged.connect(refresh_models)
        refresh_models()

        def toggle_rag(checked: bool):
            self.rag_provider_label.setVisible(checked)
            self.rag_provider_combo.setVisible(checked)
            self.rag_model_label.setVisible(checked)
            self.rag_model_combo.setVisible(checked)

        self.rag_checkbox.stateChanged.connect(lambda s: toggle_rag(s == Qt.CheckState.Checked))
        toggle_rag(self.rag_checkbox.isChecked())

        confirm_btn = QPushButton("确定")
        confirm_btn.clicked.connect(self.save_settings)
        layout.addWidget(confirm_btn)

    def save_settings(self):
        APP_SETTINGS.web_search.search_engine = self.engine_combo.currentText()
        APP_SETTINGS.web_search.search_results_num = int(self.result_num_edit.text() or "5")
        APP_SETTINGS.web_search.use_llm_reformat = self.rag_checkbox.isChecked()

        # 如果你有 LLMUsagePack：这里按你的结构写回 provider/model
        # APP_SETTINGS.web_search.reformat_config.provider = self.rag_provider_combo.currentText()
        # APP_SETTINGS.web_search.reformat_config.model = self.rag_model_combo.currentText()

        self.search_settings_widget.hide()

    def _build_results_ui(self):
        layout = QVBoxLayout(self.search_results_widget)
        self.results_list = QListWidget()
        layout.addWidget(self.results_list)

    def set_results(self, results: List[WebResult]):
        self.results_list.clear()

        button_style = """
            QPushButton {
                background: white;
                color: #404040;
                border: 1px solid #e0e0e0;
                border-radius: 3px;
                padding: 6px 10px;
                text-align: left;
                font-size: 13px;
                margin: 1px;
                min-width: 240px;
            }
            QPushButton:hover { background: #f8f8f8; border-color: #c0c0c0; }
            QPushButton:pressed { background: #f0f0f0; }
        """

        for r in results:
            rank = r.hit.rank
            title = r.hit.title
            url = r.hit.url

            btn = QPushButton(f"{rank}. {title}")
            btn.setStyleSheet(button_style)
            btn.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            btn.setFixedHeight(32)
            btn.setIconSize(QSize(16, 16))
            btn.clicked.connect(lambda _, u=url: QDesktopServices.openUrl(QUrl(u)))

            item = QListWidgetItem()
            item.setSizeHint(QSize(0, 34))
            self.results_list.addItem(item)
            self.results_list.setItemWidget(item, btn)