#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
配置管理模块

负责加载、验证和管理 YAML 配置文件，提供类型安全的配置访问接口。
"""

import os
import yaml
from typing import Dict, List, Optional, Any, Union
from pydantic import BaseModel, Field, validator
from pathlib import Path


class ModelConfig(BaseModel):
    """模型配置"""
    id: str
    path: Optional[str] = None
    device: Optional[str] = "cpu"
    gpu_memory_utilization: Optional[float] = None
    max_model_len: Optional[int] = None
    launch_script: Optional[str] = None
    python_path: Optional[str] = None


class ServiceQueueConfig(BaseModel):
    """服务队列配置"""
    max_concurrent: int = Field(default=1, ge=1, le=10)
    max_size: int = Field(default=100, ge=1, le=1000)
    timeout_seconds: int = Field(default=300, ge=1, le=3600)


class QueueConfig(BaseModel):
    """请求队列配置"""
    enabled: bool = True
    default: ServiceQueueConfig = Field(default_factory=ServiceQueueConfig)
    services: Dict[str, ServiceQueueConfig] = Field(default_factory=dict)


class AuthConfig(BaseModel):
    """认证配置"""
    enabled: bool = True
    tokens: List[str] = Field(default_factory=list)

    @validator("tokens")
    def validate_tokens(cls, v):
        if not v:
            return []
        # 过滤空 token
        return [t.strip() for t in v if t.strip()]


class ServerConfig(BaseModel):
    """服务器配置"""
    host: str = "0.0.0.0"
    port: int = Field(default=8090, ge=1, le=65535)
    workers: int = Field(default=4, ge=1, le=16)
    log_level: str = "info"


class ServiceConfig(BaseModel):
    """子服务配置"""
    enabled: bool = True
    base_url: str
    timeout_seconds: int = Field(default=300, ge=1, le=3600)
    max_retries: int = Field(default=3, ge=0, le=10)
    models: List[ModelConfig] = Field(default_factory=list)
    launch_script: Optional[str] = None
    working_directory: Optional[str] = None
    python_path: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)


class ServicesConfig(BaseModel):
    """所有子服务配置"""
    embedding: Optional[ServiceConfig] = None
    asr: Optional[ServiceConfig] = None
    reranker: Optional[ServiceConfig] = None
    mineru: Optional[ServiceConfig] = None


class HealthCheckConfig(BaseModel):
    """健康检查配置"""
    enabled: bool = True
    interval_seconds: int = Field(default=30, ge=5, le=300)
    timeout_seconds: int = Field(default=10, ge=1, le=60)
    unhealthy_threshold: int = Field(default=3, ge=1, le=10)


class Config(BaseModel):
    """主配置类"""
    server: ServerConfig = Field(default_factory=ServerConfig)
    auth: AuthConfig = Field(default_factory=AuthConfig)
    queue: QueueConfig = Field(default_factory=QueueConfig)
    services: ServicesConfig = Field(default_factory=ServicesConfig)
    health_check: HealthCheckConfig = Field(default_factory=HealthCheckConfig)

    # 配置中心 - 所有服务配置的统一访问点
    _service_configs: Dict[str, ServiceConfig] = {}

    def get_service_config(self, service_name: str) -> Optional[ServiceConfig]:
        """获取指定服务的配置"""
        if not self._service_configs:
            self._build_service_configs()
        return self._service_configs.get(service_name)

    def get_queue_config(self, service_name: str) -> ServiceQueueConfig:
        """获取指定服务的队列配置"""
        if service_name in self.queue.services:
            return self.queue.services[service_name]
        return self.queue.default

    def get_enabled_services(self) -> List[str]:
        """获取所有启用的服务名称"""
        if not self._service_configs:
            self._build_service_configs()
        return [name for name, cfg in self._service_configs.items() if cfg.enabled]

    def _build_service_configs(self):
        """构建服务配置字典"""
        self._service_configs = {}
        if self.services.embedding:
            self._service_configs["embedding"] = self.services.embedding
        if self.services.asr:
            self._service_configs["asr"] = self.services.asr
        if self.services.reranker:
            self._service_configs["reranker"] = self.services.reranker
        if self.services.mineru:
            self._service_configs["mineru"] = self.services.mineru


class ConfigManager:
    """配置管理器"""

    def __init__(self, config_path: str):
        """
        初始化配置管理器

        Args:
            config_path: 配置文件路径
        """
        self.config_path = config_path
        self.config: Config = self._load_config()

    def _load_config(self) -> Config:
        """
        加载配置文件并验证

        Returns:
            Config: 验证后的配置对象
        """
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"配置文件不存在：{self.config_path}")

        with open(self.config_path, "r", encoding="utf-8") as f:
            raw_config = yaml.safe_load(f)

        return Config(**raw_config)

    def reload(self) -> Config:
        """重新加载配置文件"""
        self.config = self._load_config()
        return self.config

    def get_service_config(self, service_name: str) -> Optional[ServiceConfig]:
        """获取指定服务的配置"""
        return self.config.get_service_config(service_name)

    def get_queue_config(self, service_name: str) -> ServiceQueueConfig:
        """获取指定服务的队列配置"""
        return self.config.get_queue_config(service_name)

    def get_auth_tokens(self) -> List[str]:
        """获取所有有效 token"""
        return self.config.auth.tokens

    def validate_token(self, token: str, endpoint: str) -> bool:
        """
        验证 token 是否有效

        Args:
            token: token 字符串
            endpoint: 请求端点

        Returns:
            bool: token 是否有效
        """
        if not self.config.auth.enabled:
            return True
        return token in self.config.auth.tokens

    def get_enabled_services(self) -> List[str]:
        """获取所有启用的服务名称"""
        return self.config.get_enabled_services()

    @property
    def server(self) -> ServerConfig:
        """获取服务器配置"""
        return self.config.server

    @property
    def auth(self) -> AuthConfig:
        """获取认证配置"""
        return self.config.auth

    @property
    def queue(self) -> QueueConfig:
        """获取队列配置"""
        return self.config.queue

    @property
    def health_check(self) -> HealthCheckConfig:
        """获取健康检查配置"""
        return self.config.health_check


# 全局配置管理器实例
_config_manager: Optional[ConfigManager] = None


def init_config(config_path: str) -> ConfigManager:
    """
    初始化全局配置管理器

    Args:
        config_path: 配置文件路径

    Returns:
        ConfigManager: 配置管理器实例
    """
    global _config_manager
    _config_manager = ConfigManager(config_path)
    return _config_manager


def get_config_manager() -> Optional[ConfigManager]:
    """获取全局配置管理器实例"""
    return _config_manager


def get_config() -> Optional[Config]:
    """获取全局配置对象"""
    if _config_manager:
        return _config_manager.config
    return None
