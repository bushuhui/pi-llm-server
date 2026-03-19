"""
服务模块测试
"""
import pytest
from pi_llm_server.config import ServiceConfig
from pi_llm_server.services import (
    EmbeddingService,
    ASRService,
    RerankerService,
    MinerUService,
)


class TestEmbeddingService:
    """Embedding 服务测试"""

    def test_service_creation(self):
        """测试服务创建"""
        config = ServiceConfig(
            base_url="http://localhost:8091",
            timeout_seconds=60,
            max_retries=3,
        )
        service = EmbeddingService(config=config)
        assert service.base_url == "http://localhost:8091"
        assert service.timeout == 60


class TestASRService:
    """ASR 服务测试"""

    def test_service_creation(self):
        """测试服务创建"""
        config = ServiceConfig(
            base_url="http://localhost:8092",
            timeout_seconds=300,
            max_retries=2,
        )
        service = ASRService(config=config)
        assert service.base_url == "http://localhost:8092"
        assert service.timeout == 300


class TestRerankerService:
    """Reranker 服务测试"""

    def test_service_creation(self):
        """测试服务创建"""
        config = ServiceConfig(
            base_url="http://localhost:8093",
            timeout_seconds=120,
            max_retries=3,
        )
        service = RerankerService(config=config)
        assert service.base_url == "http://localhost:8093"
        assert service.timeout == 120


class TestMinerUService:
    """MinerU 服务测试"""

    def test_service_creation(self):
        """测试服务创建"""
        config = ServiceConfig(
            base_url="http://localhost:8094",
            timeout_seconds=600,
            max_retries=1,
        )
        service = MinerUService(config=config)
        assert service.base_url == "http://localhost:8094"
        assert service.timeout == 600
