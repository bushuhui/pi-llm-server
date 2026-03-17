#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
异常模块

定义统一的异常类型和错误处理。
"""

from typing import Optional, Any, Dict


class PIException(Exception):
    """PI-LLM-Server 基础异常类"""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        """
        初始化异常

        Args:
            message: 错误消息
            status_code: HTTP 状态码
            error_code: 错误代码 (可选)
            details: 详细错误信息 (可选)
        """
        super().__init__(message)
        self.message = message
        self.status_code = status_code
        self.error_code = error_code or self.__class__.__name__
        self.details = details or {}

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典格式"""
        return {
            "error": self.error_code,
            "message": self.message,
            "details": self.details,
        }


class AuthenticationError(PIException):
    """认证错误"""

    def __init__(
        self,
        message: str = "认证失败",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            status_code=401,
            error_code="AuthenticationError",
            details=details,
        )


class AuthorizationError(PIException):
    """授权错误"""

    def __init__(
        self,
        message: str = "没有权限访问该资源",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            status_code=403,
            error_code="AuthorizationError",
            details=details,
        )


class ServiceUnavailableError(PIException):
    """服务不可用错误"""

    def __init__(
        self,
        message: str = "服务暂时不可用",
        service_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        if service_name:
            message = f"{message}: {service_name}"
        super().__init__(
            message=message,
            status_code=503,
            error_code="ServiceUnavailable",
            details={"service": service_name, **(details or {})},
        )


class QueueFullError(PIException):
    """队列满错误"""

    def __init__(
        self,
        message: str = "服务繁忙，请稍后重试",
        service_name: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        if service_name:
            message = f"{message}: {service_name} 队列已满"
        super().__init__(
            message=message,
            status_code=503,
            error_code="QueueFull",
            details={"service": service_name, **(details or {})},
        )


class TimeoutError(PIException):
    """超时错误"""

    def __init__(
        self,
        message: str = "请求超时",
        service_name: Optional[str] = None,
        timeout_seconds: Optional[int] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        if service_name:
            message = f"{message}: {service_name} 响应超时"
        if timeout_seconds:
            details = {"timeout_seconds": timeout_seconds, **(details or {})}
        super().__init__(
            message=message,
            status_code=504,
            error_code="Timeout",
            details=details,
        )


class ValidationError(PIException):
    """参数校验错误"""

    def __init__(
        self,
        message: str = "参数校验失败",
        field: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        if field:
            message = f"{message}: {field}"
        super().__init__(
            message=message,
            status_code=400,
            error_code="ValidationError",
            details={"field": field, **(details or {})},
        )


class NotFoundError(PIException):
    """资源不存在错误"""

    def __init__(
        self,
        message: str = "资源不存在",
        resource: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        if resource:
            message = f"{message}: {resource}"
        super().__init__(
            message=message,
            status_code=404,
            error_code="NotFound",
            details={"resource": resource, **(details or {})},
        )


class InternalServerError(PIException):
    """服务器内部错误"""

    def __init__(
        self,
        message: str = "服务器内部错误",
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(
            message=message,
            status_code=500,
            error_code="InternalServerError",
            details=details,
        )
