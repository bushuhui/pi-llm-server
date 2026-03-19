"""
配置模块测试
"""
import pytest
from pathlib import Path
from pi_llm_server.config import ConfigManager, Config, ServiceConfig


# 示例配置文件路径
EXAMPLE_CONFIG = Path(__file__).parent.parent / "examples" / "config.example.yaml"


class TestConfigManager:
    """配置管理器测试"""

    def test_config_load(self):
        """测试配置文件加载"""
        config = ConfigManager(str(EXAMPLE_CONFIG))
        assert config.server.port == 8090
        assert config.server.host == "0.0.0.0"
        assert config.server.workers == 4

    def test_auth_config(self):
        """测试认证配置"""
        config = ConfigManager(str(EXAMPLE_CONFIG))
        assert config.auth.enabled is True
        assert len(config.auth.tokens) > 0
        assert "sk-admin-token-001" in config.auth.tokens

    def test_queue_config(self):
        """测试队列配置"""
        config = ConfigManager(str(EXAMPLE_CONFIG))
        assert config.queue.enabled is True
        # 检查默认配置
        assert config.queue.default.max_concurrent == 1
        assert config.queue.default.max_size == 100

    def test_service_queue_config(self):
        """测试服务队列配置"""
        config = ConfigManager(str(EXAMPLE_CONFIG))
        # 检查 embedding 队列配置
        emb_queue = config.get_queue_config("embedding")
        assert emb_queue.max_concurrent == 4
        assert emb_queue.max_size == 200

        # 检查 asr 队列配置
        asr_queue = config.get_queue_config("asr")
        assert asr_queue.max_concurrent == 1
        assert asr_queue.max_size == 50

    def test_service_config(self):
        """测试服务配置"""
        config = ConfigManager(str(EXAMPLE_CONFIG))
        embedding_cfg = config.get_service_config("embedding")
        assert embedding_cfg is not None
        assert embedding_cfg.enabled is True
        assert embedding_cfg.base_url == "http://127.0.0.1:8091"

    def test_health_check_config(self):
        """测试健康检查配置"""
        config = ConfigManager(str(EXAMPLE_CONFIG))
        hc = config.health_check
        assert hc.enabled is True
        assert hc.interval_seconds == 30
        assert hc.timeout_seconds == 10
        assert hc.unhealthy_threshold == 3

    def test_get_enabled_services(self):
        """测试获取启用的服务列表"""
        config = ConfigManager(str(EXAMPLE_CONFIG))
        services = config.get_enabled_services()
        assert "embedding" in services
        assert "asr" in services
        assert "reranker" in services
        assert "mineru" in services

    def test_token_validation(self):
        """测试 Token 验证"""
        config = ConfigManager(str(EXAMPLE_CONFIG))
        # 有效 token
        assert config.validate_token("sk-admin-token-001", "/v1/embeddings")
        # 无效 token
        assert not config.validate_token("invalid-token", "/v1/embeddings")


class TestConfigModels:
    """配置模型测试"""

    def test_server_config(self):
        """测试服务器配置模型"""
        from pi_llm_server.config import ServerConfig
        cfg = ServerConfig()
        assert cfg.host == "0.0.0.0"
        assert cfg.port == 8090

    def test_service_config(self):
        """测试服务配置模型"""
        cfg = ServiceConfig(
            enabled=True,
            base_url="http://localhost:8000"
        )
        assert cfg.enabled is True
        assert cfg.base_url == "http://localhost:8000"
        assert cfg.timeout_seconds == 300
        assert cfg.max_retries == 3
