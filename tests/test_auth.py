"""
认证模块测试
"""
import pytest
from pathlib import Path
from pi_llm_server.config import ConfigManager
from pi_llm_server.auth import AuthManager


EXAMPLE_CONFIG = Path(__file__).parent.parent / "examples" / "config.example.yaml"


class TestAuthManager:
    """认证管理器测试"""

    def test_auth_manager_creation(self):
        """测试认证管理器创建"""
        auth = AuthManager(tokens=[])
        assert auth.tokens == set()

    def test_auth_manager_with_tokens(self):
        """测试带 token 的认证管理器"""
        tokens = ["token1", "token2", "token3"]
        auth = AuthManager(tokens=tokens)
        assert len(auth.tokens) == 3
        assert "token1" in auth.tokens

    def test_validate_token(self):
        """测试 Token 验证"""
        tokens = ["valid-token-1", "valid-token-2"]
        auth = AuthManager(tokens=tokens)

        # 有效 token
        assert auth.validate_token("valid-token-1") is True
        assert auth.validate_token("valid-token-2") is True

        # 无效 token
        assert auth.validate_token("invalid-token") is False

    def test_load_from_config(self):
        """测试从配置文件加载"""
        config = ConfigManager(str(EXAMPLE_CONFIG))
        auth = AuthManager(tokens=config.get_auth_tokens())

        assert "sk-admin-token-001" in auth.tokens
        assert "sk-embedding-token-001" in auth.tokens
