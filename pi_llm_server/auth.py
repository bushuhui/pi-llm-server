#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
认证管理模块

实现 Bearer Token 认证中间件，支持 Token 验证和权限控制。
"""

from typing import Optional, List, Set
from fastapi import Request, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse


class AuthManager:
    """认证管理器"""

    # 无需认证的路径白名单
    PUBLIC_PATHS: Set[str] = {
        "/health",
        "/docs",
        "/redoc",
        "/openapi.json",
        "/",
    }

    def __init__(self, tokens: List[str], enabled: bool = True):
        """
        初始化认证管理器

        Args:
            tokens: 有效 token 列表
            enabled: 是否启用认证
        """
        self.tokens = set(tokens) if tokens else set()
        self.enabled = enabled
        self.security = HTTPBearer(auto_error=False)

    def is_public_path(self, path: str) -> bool:
        """
        检查路径是否在白名单中

        Args:
            path: 请求路径

        Returns:
            bool: 是否为公开路径
        """
        # 精确匹配
        if path in self.PUBLIC_PATHS:
            return True

        # 前缀匹配 (如 /docs?xyz=123)
        for public_path in self.PUBLIC_PATHS:
            if path.startswith(public_path):
                return True

        return False

    def validate_token(self, token: str) -> bool:
        """
        验证 token 是否有效

        Args:
            token: token 字符串

        Returns:
            bool: token 是否有效
        """
        if not self.enabled:
            return True
        return token in self.tokens

    async def get_token_from_request(self, request: Request) -> Optional[str]:
        """
        从请求中提取 token

        Args:
            request: HTTP 请求

        Returns:
            Optional[str]: token 字符串，如果不存在则返回 None
        """
        auth_header = request.headers.get("Authorization")
        if not auth_header:
            return None

        # 支持 Bearer Token 格式
        if auth_header.startswith("Bearer "):
            return auth_header[7:]

        # 支持直接传入 token (兼容旧版本)
        return auth_header

    async def __call__(self, request: Request, call_next):
        """
        认证中间件

        Args:
            request: HTTP 请求
            call_next: 下一个处理函数

        Returns:
            Response: HTTP 响应
        """
        # 检查是否在白名单中
        if self.is_public_path(request.url.path):
            return await call_next(request)

        # 获取 token
        token = await self.get_token_from_request(request)

        if not token:
            return JSONResponse(
                status_code=401,
                content={"error": "Unauthorized", "message": "Missing authentication token"}
            )

        # 验证 token
        if not self.validate_token(token):
            return JSONResponse(
                status_code=401,
                content={"error": "Unauthorized", "message": "Invalid authentication token"}
            )

        # 将 token 信息添加到请求状态中 (可选，供后续使用)
        request.state.token = token

        return await call_next(request)


def create_auth_middleware(tokens: List[str], enabled: bool = True) -> AuthManager:
    """
    创建认证中间件

    Args:
        tokens: 有效 token 列表
        enabled: 是否启用认证

    Returns:
        AuthManager: 认证中间件实例
    """
    return AuthManager(tokens=tokens, enabled=enabled)


# 简单的认证装饰器 (可选使用)
def require_auth(request: Request, auth_manager: AuthManager) -> bool:
    """
    同步认证检查 (用于非异步场景)

    Args:
        request: HTTP 请求
        auth_manager: 认证管理器

    Returns:
        bool: 是否通过认证

    Raises:
        HTTPException: 认证失败时抛出
    """
    if auth_manager.is_public_path(request.url.path):
        return True

    token = request.headers.get("Authorization")
    if not token:
        raise HTTPException(status_code=401, detail="Missing authentication token")

    if token.startswith("Bearer "):
        token = token[7:]

    if not auth_manager.validate_token(token):
        raise HTTPException(status_code=401, detail="Invalid authentication token")

    return True
