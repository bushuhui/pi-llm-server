#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
日志工具模块

提供结构化日志配置和日志记录器。
"""

import os
import sys
import logging
from logging.handlers import RotatingFileHandler
from datetime import datetime
from pathlib import Path
from typing import Optional


class JsonFormatter(logging.Formatter):
    """JSON 格式化器 - 可选使用"""

    def format(self, record: logging.LogRecord) -> str:
        """格式化为 JSON 格式"""
        import json

        log_data = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "level": record.levelname,
            "service": getattr(record, "service", "pi-llm-server"),
            "message": record.getMessage(),
        }

        # 添加可选字段
        if hasattr(record, "endpoint"):
            log_data["endpoint"] = record.endpoint
        if hasattr(record, "method"):
            log_data["method"] = record.method
        if hasattr(record, "status"):
            log_data["status"] = record.status
        if hasattr(record, "latency_ms"):
            log_data["latency_ms"] = record.latency_ms
        if hasattr(record, "client_ip"):
            log_data["client_ip"] = record.client_ip
        if hasattr(record, "model"):
            log_data["model"] = record.model
        if hasattr(record, "queue_wait_ms"):
            log_data["queue_wait_ms"] = record.queue_wait_ms

        # 添加错误信息
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, ensure_ascii=False)


def setup_logging(
    service_name: str = "pi-llm-server",
    log_level: str = "info",
    log_dir: Optional[str] = None,
    use_json: bool = False,
) -> logging.Logger:
    """
    配置日志系统

    Args:
        service_name: 服务名称
        log_level: 日志级别 (debug, info, warning, error)
        log_dir: 日志目录 (None 则不创建文件 handler)
        use_json: 是否使用 JSON 格式

    Returns:
        logging.Logger: 配置好的 logger
    """
    # 创建 logger
    logger = logging.getLogger(service_name)
    logger.setLevel(getattr(logging, log_level.upper()))

    # 清除已有的 handlers
    logger.handlers = []

    # 创建 formatter
    if use_json:
        formatter = JsonFormatter()
    else:
        formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S"
        )

    # 控制台 handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件 handler (可选)
    if log_dir:
        os.makedirs(log_dir, exist_ok=True)
        log_file = os.path.join(log_dir, f"{service_name}.log")

        # 旋转文件 handler (最大 10MB，保留 5 个文件)
        file_handler = RotatingFileHandler(
            log_file,
            maxBytes=10 * 1024 * 1024,  # 10MB
            backupCount=5,
            encoding="utf-8"
        )
        file_handler.setLevel(getattr(logging, log_level.upper()))
        file_handler.setFormatter(formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    获取 logger 实例

    Args:
        name: logger 名称 (默认使用模块名)

    Returns:
        logging.Logger: logger 实例
    """
    if name:
        return logging.getLogger(name)
    return logging.getLogger()


# 默认 logger 实例
default_logger: Optional[logging.Logger] = None


def init_default_logging(
    service_name: str = "pi-llm-server",
    log_level: str = "info",
    log_dir: Optional[str] = None,
) -> logging.Logger:
    """
    初始化默认日志

    Args:
        service_name: 服务名称
        log_level: 日志级别
        log_dir: 日志目录

    Returns:
        logging.Logger: 默认 logger
    """
    global default_logger
    default_logger = setup_logging(service_name, log_level, log_dir)
    return default_logger


def get_default_logger() -> logging.Logger:
    """获取默认 logger"""
    global default_logger
    if not default_logger:
        default_logger = setup_logging()
    return default_logger
