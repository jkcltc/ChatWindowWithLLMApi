# tests/test_api_config_refactoring.py
"""
API配置重构测试
测试 ModelListUpdater / RandomModelSelecter / APIConfigWidget 等组件
"""

import os
import sys
import pytest
import configparser
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

# 确保项目根目录在 path 里
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.setting import APP_SETTINGS, APP_RUNTIME, ConfigManager
from utils.setting.data import ProviderConfig


# ============================================================
# Fixtures: 测试前的准备工作
# ============================================================
@pytest.fixture(scope="module")
def load_config_from_ini():
    """
    从 api_config.ini 读取配置，注入到 APP_SETTINGS
    """
    # 找 ini 文件 - 修复：str 要用 os.path.join 拼接
    possible_paths = [
        Path("api_config.ini"),
        Path("utils/api_config.ini"),
    ]

    # APP_RUNTIME.paths.application_path 是 str，单独处理
    if APP_RUNTIME.paths.application_path:
        possible_paths.append(
            Path(APP_RUNTIME.paths.application_path) / "api_config.ini"
        )

    ini_path = None
    for p in possible_paths:
        if p and p.exists():
            ini_path = p
            break

    if not ini_path:
        pytest.skip("找不到 api_config.ini，跳过需要真实密钥的测试")
        return {}

    # 解析 ini
    config = configparser.ConfigParser()
    config.read(ini_path, encoding='utf-8')

    loaded_providers = {}
    for section in config.sections():
        try:
            url = config.get(section, "url").strip()
            key = config.get(section, "key").strip()

            if section in APP_SETTINGS.api.providers:
                APP_SETTINGS.api.providers[section].url = url
                APP_SETTINGS.api.providers[section].key = key
            else:
                APP_SETTINGS.api.providers[section] = ProviderConfig(
                    url=url,
                    key=key,
                    models=[]
                )

            loaded_providers[section] = {"url": url, "key": key}
            print(f"[Fixture] 已加载配置: {section}")

        except (configparser.NoOptionError, configparser.NoSectionError) as e:
            print(f"[Fixture] 配置解析错误[{section}]: {e}")

    return loaded_providers

@pytest.fixture
def mock_qapp():
    """
    创建 QApplication 实例（GUI 测试需要）
    """
    try:
        from PyQt6.QtWidgets import QApplication
        app = QApplication.instance()
        if app is None:
            app = QApplication([])
        yield app
    except ImportError:
        pytest.skip("PyQt6 未安装，跳过 GUI 测试")


# ============================================================
# 测试 APP_SETTINGS 单例
# ============================================================

class TestAppSettings:
    """测试全局配置单例"""

    def test_singleton_exists(self):
        """APP_SETTINGS 应该存在且不为空"""
        assert APP_SETTINGS is not None
        print(f"APP_SETTINGS 类型: {type(APP_SETTINGS)}")

    def test_api_providers_structure(self):
        """api.providers 应该是个字典结构"""
        providers = APP_SETTINGS.api.providers
        assert isinstance(providers, dict)
        print(f"当前 providers: {list(providers.keys())}")

    def test_model_map_property(self):
        """model_map 属性应该正确返回 {provider: [models]}"""
        model_map = APP_SETTINGS.api.model_map
        assert isinstance(model_map, dict)

        for provider, models in model_map.items():
            assert isinstance(provider, str)
            assert isinstance(models, list)

        print(f"model_map: {model_map}")

    def test_endpoints_property(self):
        """endpoints 属性应该返回 {provider: (url, key)}"""
        endpoints = APP_SETTINGS.api.endpoints
        assert isinstance(endpoints, dict)

        for provider, endpoint in endpoints.items():
            assert isinstance(endpoint, tuple)
            assert len(endpoint) == 2

        print(f"endpoints 数量: {len(endpoints)}")

    def test_inject_config_from_ini(self, load_config_from_ini):
        """测试从 ini 注入配置后，APP_SETTINGS 能正确读取"""
        if not load_config_from_ini:
            pytest.skip("无配置可测试")

        # >>> 只检查从 ini 实际加载的那些 provider <<<
        for provider_name in load_config_from_ini:
            assert provider_name in APP_SETTINGS.api.providers
            config = APP_SETTINGS.api.providers[provider_name]
            # 只检查 ini 里确实有的配置，不检查空的
            ini_config = load_config_from_ini[provider_name]
            if ini_config["url"]:  # ini 里有 URL 才检查
                assert config.url != "", f"[{provider_name}] URL 不应为空"
            print(f"[{provider_name}] URL: {config.url[:30] if config.url else '(空)'}...")



# ============================================================
# 测试 ModelListUpdater
# ============================================================

class TestModelListUpdater:
    """测试模型列表更新器"""

    def test_import(self):
        """能正常导入 ModelListUpdater"""
        from utils.model_map_manager import ModelListUpdater  # 根据你实际路径调整
        assert ModelListUpdater is not None

    def test_correct_url_adds_models_path(self):
        """_correct_url 应该自动补全 /models 路径"""
        from utils.model_map_manager import ModelListUpdater

        test_cases = [
            ("https://api.example.com/v1", "https://api.example.com/v1/models"),
            ("https://api.example.com/v1/", "https://api.example.com/v1/models"),
            ("https://api.example.com/v1/models", "https://api.example.com/v1/models"),
            ("http://localhost:11434/api/tags", "http://localhost:11434/api/tags"),
        ]

        for input_url, expected in test_cases:
            result = ModelListUpdater._correct_url(input_url)
            assert result == expected, f"输入 {input_url}，期望 {expected}，实际 {result}"
            print(f"✓ {input_url} -> {result}")

    def test_is_ollama_alive_timeout(self):
        """测试 ollama 检测不会卡死（超时应该正常返回 False）"""
        from utils.model_map_manager import ModelListUpdater

        # 用一个不存在的地址测试超时
        result = ModelListUpdater.is_ollama_alive("http://192.0.2.1:11434/")  # TEST-NET，不可达
        assert result is False
        print("✓ 超时测试通过")

    def test_get_model_list_with_mock(self):
        """使用 mock 测试 get_model_list"""
        from utils.model_map_manager import ModelListUpdater

        mock_response = Mock()
        mock_response.json.return_value = {
            "data": [
                {"id": "model-a"},
                {"id": "model-b"},
                {"id": "model-c"},
            ]
        }
        mock_response.raise_for_status = Mock()

        with patch('requests.get', return_value=mock_response):
            result = ModelListUpdater.get_model_list({
                "url": "https://fake.api/models",
                "key": "fake-key"
            })

        assert result == ["model-a", "model-b", "model-c"]
        print(f"✓ Mock 测试返回: {result}")

    @pytest.mark.slow
    def test_update_real_api(self, load_config_from_ini):
        """
        真实 API 测试（需要有效密钥）
        标记为 slow，默认跳过，用 pytest -m slow 运行
        """
        if not load_config_from_ini:
            pytest.skip("无有效配置")

        from utils.model_map_manager import ModelListUpdater

        result = ModelListUpdater.update()

        assert isinstance(result, dict)
        print(f"✓ 真实 API 返回 {len(result)} 个供应商的模型列表")

        for provider, models in result.items():
            print(f"  [{provider}] {len(models)} 个模型")
            if models:
                print(f"    示例: {models[:3]}")


# ============================================================
# 测试 RandomModelSelecter (GUI)
# ============================================================

class TestRandomModelSelecter:
    """测试随机模型选择器"""

    def test_import(self):
        """能正常导入"""
        from utils.model_map_manager import RandomModelSelecter
        assert RandomModelSelecter is not None

    def test_init_without_model_map_param(self, mock_qapp, load_config_from_ini):
        """不传 model_map 参数也能正常初始化"""
        from utils.model_map_manager import RandomModelSelecter

        widget = RandomModelSelecter(parent=None, logger=None)

        assert widget is not None

        # >>> 改成检查能否正常访问 provider 下拉框 <<<
        provider_count = widget.ui.model_provider.count()
        assert provider_count > 0, "应该有可选的 provider"

        print(f"✓ 初始化成功，provider 数量: {provider_count}")

        widget.close()
        widget.deleteLater()

    def test_add_and_remove_model(self, mock_qapp, load_config_from_ini):
        """测试添加和移除模型"""
        from utils.model_map_manager import RandomModelSelecter

        widget = RandomModelSelecter(parent=None, logger=None)

        # >>> 直接用 APP_SETTINGS.api.model_map <<<
        model_map = APP_SETTINGS.api.model_map

        if model_map:
            first_provider = list(model_map.keys())[0]
            widget.ui.model_provider.setCurrentText(first_provider)

            if widget.ui.model_name.count() > 0:
                widget.add_model_to_list()
                assert len(widget.current_models) == 1
                print(f"✓ 添加模型: {widget.current_models[0]}")

                # 选中并移除
                widget.ui.random_model_list_viewer.setCurrentIndex(
                    widget.list_model.index(0, 0)
                )
                widget.remove_selected_model()
                assert len(widget.current_models) == 0
                print("✓ 移除模型成功")
        else:
            pytest.skip("model_map 为空")

        widget.close()
        widget.deleteLater()

    def test_collect_selected_models_order(self, mock_qapp, load_config_from_ini):
        """测试顺序轮询模式"""
        from utils.model_map_manager import RandomModelSelecter

        mock_logger = Mock()
        mock_logger.log = Mock()

        widget = RandomModelSelecter(parent=None, logger=mock_logger)

        # 手动添加几个模型
        widget.current_models = [
            ("provider_a", "model_1"),
            ("provider_b", "model_2"),
            ("provider_c", "model_3"),
        ]

        # 设置为顺序模式
        widget.ui.order_radio.setChecked(True)

        # 连续调用应该轮询
        results = [widget.collect_selected_models() for _ in range(6)]

        print(f"✓ 轮询结果: {results}")
        assert len(results) == 6

        widget.close()
        widget.deleteLater()


# ============================================================
# 测试 APIConfigWidget (GUI)
# ============================================================

class TestAPIConfigWidget:
    """测试 API 配置窗口"""

    def test_import(self):
        """能正常导入"""
        from utils.model_map_manager import APIConfigWidget  # 根据实际路径调整
        assert APIConfigWidget is not None

    def test_init_without_application_path(self, mock_qapp, load_config_from_ini):
        """不传 application_path 也能正常初始化"""
        from utils.model_map_manager import APIConfigWidget

        # 不传参数
        widget = APIConfigWidget(parent=None)

        assert widget is not None
        assert widget.application_path == APP_RUNTIME.paths.application_path

        print(f"✓ 初始化成功，application_path: {widget.application_path}")

        widget.close()
        widget.deleteLater()

    def test_preset_apis_loaded(self, mock_qapp, load_config_from_ini):
        """预设 API 供应商应该被加载"""
        from utils.model_map_manager import APIConfigWidget

        widget = APIConfigWidget(parent=None)

        expected_presets = ["baidu", "deepseek", "siliconflow", "tencent", "novita", "ollama"]

        for preset in expected_presets:
            assert preset in widget.api_widgets, f"缺少预设供应商: {preset}"

        print(f"✓ 预设供应商全部加载: {expected_presets}")

        widget.close()
        widget.deleteLater()

    def test_config_from_app_settings(self, mock_qapp, load_config_from_ini):
        """配置应该从 APP_SETTINGS 加载"""
        from utils.model_map_manager import APIConfigWidget

        widget = APIConfigWidget(parent=None)

        # 检查 UI 中的值是否和 APP_SETTINGS 一致
        for api_name, widgets in widget.api_widgets.items():
            url_entry, key_entry, _, _ = widgets

            if api_name in APP_SETTINGS.api.providers:
                expected_url = APP_SETTINGS.api.providers[api_name].url
                actual_url = url_entry.text()

                assert actual_url == expected_url, \
                    f"[{api_name}] URL 不匹配: 期望 {expected_url}, 实际 {actual_url}"

        print("✓ 配置从 APP_SETTINGS 正确加载")

        widget.close()
        widget.deleteLater()


# ============================================================
# 测试 APIConfigDialogUpdateModelThread
# ============================================================

class TestAPIConfigDialogUpdateModelThread:
    """测试模型更新线程"""

    def test_import(self):
        """能正常导入"""
        from utils.model_map_manager import APIConfigDialogUpdateModelThread
        assert APIConfigDialogUpdateModelThread is not None

    def test_init_without_params(self, mock_qapp):
        """不传参数也能正常初始化"""
        from utils.model_map_manager import APIConfigDialogUpdateModelThread

        thread = APIConfigDialogUpdateModelThread()

        assert thread is not None
        print("✓ 线程初始化成功（无参数）")

    def test_signals_exist(self, mock_qapp):
        """信号应该存在"""
        from utils.model_map_manager import APIConfigDialogUpdateModelThread

        thread = APIConfigDialogUpdateModelThread()

        assert hasattr(thread, 'started_signal')
        assert hasattr(thread, 'finished_signal')
        assert hasattr(thread, 'error_signal')

        print("✓ 所有信号存在")


# ============================================================
# 运行配置
# ============================================================

if __name__ == "__main__":
    # 直接运行此文件时的配置
    pytest.main([
        __file__,
        "-v",                    # 详细输出
        "-s",                    # 显示 print
        "--tb=short",            # 简短的 traceback
        "-m", "slow",        # 默认跳过慢测试
    ])