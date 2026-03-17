#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
队列管理模块

实现差异化请求队列管理，支持按服务类型配置不同的并发策略。
- Embedding/Reranker: CPU 多核并行
- ASR/MinerU: GPU 顺序处理
"""

import asyncio
from typing import Dict, Callable, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


@dataclass
class ServiceQueueConfig:
    """服务队列配置"""
    max_concurrent: int = 1
    max_size: int = 100
    timeout_seconds: int = 300


@dataclass
class QueueStatus:
    """队列状态"""
    pending: int = 0
    processing: int = 0
    total_processed: int = 0
    total_rejected: int = 0
    last_processed_time: Optional[datetime] = None


class ServiceQueue:
    """单个服务的队列"""

    def __init__(self, config: ServiceQueueConfig):
        """
        初始化服务队列

        Args:
            config: 队列配置
        """
        self.config = config
        self.semaphore = asyncio.Semaphore(config.max_concurrent)
        self.queue = asyncio.Queue(maxsize=config.max_size)
        self.status = QueueStatus()
        self._lock = asyncio.Lock()

    async def acquire(self) -> bool:
        """
        获取处理权限

        Returns:
            bool: 是否成功获取权限
        """
        try:
            await asyncio.wait_for(self.semaphore.acquire(), timeout=0.1)
            return True
        except asyncio.TimeoutError:
            return False

    def release(self):
        """释放处理权限"""
        self.semaphore.release()

    async def process_with_queue(
        self,
        func: Callable,
        *args,
        timeout: Optional[int] = None,
        **kwargs
    ) -> Any:
        """
        在队列中执行函数

        Args:
            func: 要执行的函数
            *args: 函数参数
            timeout: 超时时间 (秒)，None 使用配置值
            **kwargs: 关键字参数

        Returns:
            Any: 函数执行结果

        Raises:
            asyncio.QueueFull: 队列满时抛出
            asyncio.TimeoutError: 超时时抛出
        """
        timeout = timeout or self.config.timeout_seconds

        # 检查队列是否已满
        if self.queue.full():
            self.status.total_rejected += 1
            raise asyncio.QueueFull(f"队列已满 (max_size={self.config.max_size})")

        # 获取处理权限
        acquired = await self.acquire()
        if not acquired:
            # 排队等待
            self.status.pending += 1
            await self.semaphore.acquire()
            self.status.pending -= 1

        try:
            self.status.processing += 1

            # 执行函数
            if asyncio.iscoroutinefunction(func):
                result = await asyncio.wait_for(
                    func(*args, **kwargs),
                    timeout=timeout
                )
            else:
                result = await asyncio.get_event_loop().run_in_executor(
                    None, lambda: func(*args, **kwargs)
                )

            self.status.processing -= 1
            self.status.total_processed += 1
            self.status.last_processed_time = datetime.now()

            return result

        except asyncio.TimeoutError:
            logger.warning(f"请求超时 (timeout={timeout}s)")
            raise
        except Exception as e:
            logger.error(f"执行出错：{e}")
            raise
        finally:
            self.release()

    def get_status(self) -> Dict:
        """获取队列状态"""
        return {
            "pending": self.status.pending,
            "processing": self.status.processing,
            "max_concurrent": self.config.max_concurrent,
            "max_size": self.config.max_size,
            "total_processed": self.status.total_processed,
            "total_rejected": self.status.total_rejected,
        }


class QueueManager:
    """队列管理器 - 管理多个服务的队列"""

    def __init__(self):
        """初始化队列管理器"""
        self.queues: Dict[str, ServiceQueue] = {}
        self._lock = asyncio.Lock()

    def add_queue(self, service_name: str, config: ServiceQueueConfig):
        """
        添加服务队列

        Args:
            service_name: 服务名称
            config: 队列配置
        """
        self.queues[service_name] = ServiceQueue(config)
        logger.info(f"添加 {service_name} 队列：max_concurrent={config.max_concurrent}, "
                    f"max_size={config.max_size}, timeout={config.timeout_seconds}s")

    def get_queue(self, service_name: str) -> Optional[ServiceQueue]:
        """
        获取服务队列

        Args:
            service_name: 服务名称

        Returns:
            Optional[ServiceQueue]: 服务队列，不存在则返回 None
        """
        return self.queues.get(service_name)

    async def process_request(
        self,
        service_name: str,
        func: Callable,
        *args,
        timeout: Optional[int] = None,
        **kwargs
    ) -> Any:
        """
        在指定服务的队列中处理请求

        Args:
            service_name: 服务名称
            func: 要执行的函数
            *args: 函数参数
            timeout: 超时时间 (秒)
            **kwargs: 关键字参数

        Returns:
            Any: 函数执行结果

        Raises:
            ValueError: 服务队列不存在
            asyncio.QueueFull: 队列满
            asyncio.TimeoutError: 超时
        """
        queue = self.get_queue(service_name)
        if not queue:
            raise ValueError(f"服务队列不存在：{service_name}")

        return await queue.process_with_queue(func, *args, timeout=timeout, **kwargs)

    def get_status(self) -> Dict:
        """获取所有队列状态"""
        return {
            name: queue.get_status()
            for name, queue in self.queues.items()
        }

    def get_aggregated_status(self) -> Dict:
        """获取聚合状态"""
        total_pending = sum(q.status.pending for q in self.queues.values())
        total_processing = sum(q.status.processing for q in self.queues.values())
        return {
            "pending": total_pending,
            "processing": total_processing,
        }


# 全局队列管理器实例
_queue_manager: Optional[QueueManager] = None


def init_queue_manager(service_configs: Dict[str, ServiceQueueConfig]) -> QueueManager:
    """
    初始化全局队列管理器

    Args:
        service_configs: 服务队列配置字典

    Returns:
        QueueManager: 队列管理器实例
    """
    global _queue_manager
    _queue_manager = QueueManager()

    for service_name, config in service_configs.items():
        _queue_manager.add_queue(service_name, config)

    return _queue_manager


def get_queue_manager() -> Optional[QueueManager]:
    """获取全局队列管理器实例"""
    return _queue_manager
