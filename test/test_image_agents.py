import os
import sys
import pytest
import time
from pathlib import Path
from unittest.mock import Mock, patch


from PyQt6.QtCore import QCoreApplication, QEventLoop, QTimer
from PyQt6.QtWidgets import QApplication

from utils.setting import APP_SETTINGS, APP_RUNTIME
from test.model_manager_to_main import init_settings_from_ini


# ============================================================
# Fixtures
# ============================================================

@pytest.fixture(scope="module")
def qapp():
    """QApplication 实例，图片生成需要事件循环"""
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    yield app


@pytest.fixture(scope="module")
def setup_config():
    """从 ini 加载配置"""
    loaded = init_settings_from_ini()
    if not loaded:
        pytest.skip("找不到 api_config.ini")
    return loaded


@pytest.fixture
def image_agent(qapp, setup_config):
    """创建 ImageAgent 实例"""
    from utils.text_to_image.image_agents import ImageAgent
    agent = ImageAgent()
    yield agent
    # cleanup
    agent.generator = None
    agent.generators.clear()


@pytest.fixture
def output_dir():
    """确保输出目录存在"""
    pics_dir = Path(APP_RUNTIME.paths.application_path) / "pics"
    pics_dir.mkdir(parents=True, exist_ok=True)
    return pics_dir


# ============================================================
# 基础测试
# ============================================================

class TestImageAgentBasic:
    """ImageAgent 基础功能测试"""

    def test_import(self):
        """能正常导入"""
        from utils.text_to_image.image_agents import ImageAgent
        assert ImageAgent is not None

    def test_init_no_params(self, qapp, setup_config):
        """无参初始化"""
        from utils.text_to_image.image_agents import ImageAgent
        agent = ImageAgent()

        assert agent is not None
        assert agent.generator is None
        assert agent.application_path == APP_RUNTIME.paths.application_path
        print(f"✓ 初始化成功，application_path: {agent.application_path}")

    def test_supported_providers(self, image_agent):
        """检查支持的供应商"""
        expected = ['novita', 'siliconflow', 'baidu']

        for provider in expected:
            assert provider in image_agent.SUPPORTED_PROVIDERS

        print(f"✓ 支持的供应商: {list(image_agent.SUPPORTED_PROVIDERS.keys())}")

    def test_get_api_key(self, image_agent, setup_config):
        """能从 APP_SETTINGS 获取 API Key"""
        for provider in image_agent.SUPPORTED_PROVIDERS:
            key = image_agent._get_api_key(provider)
            if provider in setup_config:
                assert key != "" or setup_config[provider].get("key", "") == ""
                print(f"✓ [{provider}] Key: {'*' * 8 if key else '(空)'}")

    def test_set_generator(self, image_agent, setup_config):
        """设置生成器"""
        # 选一个有配置的供应商
        available = [p for p in image_agent.SUPPORTED_PROVIDERS if p in setup_config]
        if not available:
            pytest.skip("没有可用的图片供应商配置")

        provider = available[0]
        image_agent.set_generator(provider)

        assert image_agent.generator is not None
        assert image_agent.generator_name == provider
        print(f"✓ 设置生成器: {provider}")

    def test_set_invalid_generator(self, image_agent):
        """设置不存在的生成器"""
        failure_received = []
        image_agent.failure.connect(lambda name, msg: failure_received.append((name, msg)))

        image_agent.set_generator("不存在的供应商")

        assert image_agent.generator is None
        assert len(failure_received) == 1
        print(f"✓ 正确处理无效供应商: {failure_received[0]}")


# ============================================================
# 模型列表测试
# ============================================================

class TestImageModelList:
    """图片模型列表测试"""

    def test_get_image_model_map(self, image_agent):
        """获取图片模型映射"""
        model_map = image_agent.get_image_model_map()

        assert isinstance(model_map, dict)
        print(f"✓ 图片模型映射: {list(model_map.keys())}")

        for provider, models in model_map.items():
            print(f"  [{provider}] {len(models)} 个模型")
            if models and not models[0].startswith('Fail'):
                print(f"    示例: {models[:2]}")

    def test_get_model_list_single(self, image_agent, setup_config):
        """获取单个供应商的模型列表"""
        available = [p for p in image_agent.SUPPORTED_PROVIDERS if p in setup_config]
        if not available:
            pytest.skip("没有可用配置")

        provider = available[0]
        models = image_agent.get_model_list(provider)

        assert isinstance(models, list)
        assert len(models) > 0
        print(f"✓ [{provider}] 模型列表: {models[:5]}...")

    def test_model_cache(self, image_agent, setup_config):
        """模型缓存机制"""
        available = [p for p in image_agent.SUPPORTED_PROVIDERS if p in setup_config]
        if not available:
            pytest.skip("没有可用配置")

        provider = available[0]

        # 第一次调用
        start = time.time()
        models1 = image_agent.get_model_list(provider)
        first_time = time.time() - start

        # 第二次调用（应该走缓存）
        start = time.time()
        models2 = image_agent.get_model_list(provider)
        second_time = time.time() - start

        assert models1 == models2
        assert second_time < first_time  # 缓存应该更快
        print(f"✓ 缓存生效: 首次 {first_time:.3f}s, 缓存 {second_time:.6f}s")


# ============================================================
# 实际生图测试
# ============================================================

class TestImageGeneration:
    """实际图片生成测试 - 会消耗 API 额度"""

    @pytest.fixture
    def wait_for_signal(self, qapp):
        """等待信号的辅助函数"""
        def _wait(signal, timeout=60000):
            loop = QEventLoop()
            result = {"received": False, "data": None}

            def on_signal(*args):
                result["received"] = True
                result["data"] = args
                loop.quit()

            signal.connect(on_signal)
            QTimer.singleShot(timeout, loop.quit)
            loop.exec()

            return result

        return _wait

    @pytest.mark.slow
    def test_generate_with_siliconflow(self, image_agent, setup_config, output_dir, wait_for_signal):
        """使用 SiliconFlow 生成图片"""
        if 'siliconflow' not in setup_config:
            pytest.skip("没有 siliconflow 配置")

        image_agent.set_generator('siliconflow')
        assert image_agent.generator is not None

        # 获取可用模型
        models = image_agent.get_model_list('siliconflow')
        if not models or models[0].startswith('Fail'):
            pytest.skip("无法获取模型列表")

        # 选第一个模型
        test_model = models[0]
        print(f"使用模型: {test_model}")

        params = {
            "prompt": "a cute cat, high quality, 4k",
            "negative_prompt": "low quality, blurry",
            "model": test_model,
            "width": 512,
            "height": 512,
            "steps": 20,
        }

        # 发起请求
        image_agent.create(params)

        # 等待结果
        result = wait_for_signal(image_agent.pull_success, timeout=120000)

        if result["received"]:
            image_path = result["data"][0]
            assert os.path.exists(image_path)
            print(f"✓ 图片生成成功: {image_path}")
            print(f"  文件大小: {os.path.getsize(image_path)} bytes")
        else:
            # 检查是否有错误
            pytest.fail("生成超时或失败")

    @pytest.mark.slow
    def test_generate_with_novita(self, image_agent, setup_config, output_dir, wait_for_signal):
        """使用 Novita 生成图片"""
        if 'novita' not in setup_config:
            pytest.skip("没有 novita 配置")

        image_agent.set_generator('novita')
        assert image_agent.generator is not None

        models = image_agent.get_model_list('novita')
        if not models or models[0].startswith('Fail'):
            pytest.skip("无法获取模型列表")

        test_model = models[0]
        print(f"使用模型: {test_model}")

        params = {
            "prompt": "a beautiful landscape, sunset, mountains",
            "negative_prompt": "ugly, deformed",
            "model": test_model,
            "width": 512,
            "height": 512,
        }

        image_agent.create(params)
        result = wait_for_signal(image_agent.pull_success, timeout=120000)

        if result["received"]:
            image_path = result["data"][0]
            assert os.path.exists(image_path)
            print(f"✓ 图片生成成功: {image_path}")
        else:
            pytest.fail("生成超时或失败")

    @pytest.mark.slow
    def test_generate_with_baidu(self, image_agent, setup_config, output_dir, wait_for_signal):
        """使用百度生成图片"""
        if 'baidu' not in setup_config:
            pytest.skip("没有 baidu 配置")

        image_agent.set_generator('baidu')
        assert image_agent.generator is not None

        models = image_agent.get_model_list('baidu')
        if not models or models[0].startswith('Fail'):
            pytest.skip("无法获取模型列表")

        test_model = models[0]
        print(f"使用模型: {test_model}")

        params = {
            "prompt": "一只可爱的熊猫在吃竹子",
            "model": test_model,
            "width": 512,
            "height": 512,
        }

        image_agent.create(params)
        result = wait_for_signal(image_agent.pull_success, timeout=120000)

        if result["received"]:
            image_path = result["data"][0]
            assert os.path.exists(image_path)
            print(f"✓ 图片生成成功: {image_path}")
        else:
            pytest.fail("生成超时或失败")


# ============================================================
# 错误处理测试
# ============================================================

class TestImageAgentErrors:
    """错误处理测试"""

    def test_invalid_api_key(self, qapp, setup_config):
        """无效 API Key 处理"""
        from utils.text_to_image.image_agents import ImageAgent

        # 临时设置一个无效的 key
        original_key = None
        provider = 'siliconflow'

        if provider in APP_SETTINGS.api.providers:
            original_key = APP_SETTINGS.api.providers[provider].key
            APP_SETTINGS.api.providers[provider].key = "invalid_key_12345"

        try:
            agent = ImageAgent()
            agent.set_generator(provider)

            # 尝试获取模型列表，应该失败或返回错误
            models = agent.get_model_list(provider)
            print(f"无效 Key 返回: {models}")
            # 不一定会失败，有些 API 获取模型列表不需要 key

        finally:
            # 恢复原来的 key
            if original_key is not None:
                APP_SETTINGS.api.providers[provider].key = original_key

    def test_create_without_generator(self, image_agent):
        """未设置生成器时调用 create"""
        # 不应该崩溃
        image_agent.create({"prompt": "test"})
        print("✓ 未设置生成器时调用 create 不会崩溃")


# ============================================================
# 运行配置
# ============================================================

if __name__ == "__main__":
    pytest.main([
        __file__,
        "-v",
        "-s",
        "--tb=short"
    ])
