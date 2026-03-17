#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
健康监控模块

实现子服务健康检查、状态聚合和后台轮询。
"""

import asyncio
import logging
from typing import Dict, Optional, List, Any
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ServiceStatus:
    """服务状态"""
    status: str = "unknown"  # healthy, unhealthy, unknown
    latency_ms: Optional[float] = None
    status_code: Optional[int] = None
    error: Optional[str] = None
    last_check: Optional[datetime] = None
    consecutive_failures: int = 0


@dataclass
class HealthStatus:
    """整体健康状态"""
    status: str = "unknown"
    timestamp: str = ""
    services: Dict[str, ServiceStatus] = field(default_factory=dict)
    queue: Dict[str, Any] = field(default_factory=dict)


class HealthMonitor:
    """健康监控器"""

    def __init__(
        self,
        check_interval: int = 30,
        timeout: int = 10,
        unhealthy_threshold: int = 3,
    ):
        """
        初始化健康监控器

        Args:
            check_interval: 健康检查间隔 (秒)
            timeout: 单次检查超时 (秒)
            unhealthy_threshold: 连续失败次数判定为不健康
        """
        self.check_interval = check_interval
        self.timeout = timeout
        self.unhealthy_threshold = unhealthy_threshold

        # 服务健康检查函数
        self.health_check_funcs: Dict[str, callable] = {}

        # 服务状态
        self.services_status: Dict[str, ServiceStatus] = {}

        # 后台任务
        self._background_task: Optional[asyncio.Task] = None
        self._running = False

    def register_service(self, name: str, health_check_func: callable):
        """
        注册服务健康检查函数

        Args:
            name: 服务名称
            health_check_func: 健康检查函数 (async)
        """
        self.health_check_funcs[name] = health_check_func
        self.services_status[name] = ServiceStatus()
        logger.info(f"注册健康检查服务：{name}")

    async def check_service(self, name: str) -> ServiceStatus:
        """
        检查单个服务健康状态

        Args:
            name: 服务名称

        Returns:
            ServiceStatus: 服务状态
        """
        if name not in self.health_check_funcs:
            return ServiceStatus(status="unknown", error="服务未注册")

        status = self.services_status.get(name, ServiceStatus())
        start_time = datetime.now()

        try:
            # 调用健康检查函数
            health_check = self.health_check_funcs[name]
            if asyncio.iscoroutinefunction(health_check):
                result = await asyncio.wait_for(health_check(), timeout=self.timeout)
            else:
                result = health_check()

            # 更新状态
            latency_ms = (datetime.now() - start_time).total_seconds() * 1000

            if isinstance(result, dict):
                status.status = result.get("status", "unknown")
                status.latency_ms = result.get("latency_ms", latency_ms)
                status.status_code = result.get("status_code")
                status.error = result.get("error")
            else:
                # 布尔值返回
                status.status = "healthy" if result else "unhealthy"
                status.latency_ms = latency_ms

            # 重置失败计数
            if status.status == "healthy":
                status.consecutive_failures = 0

        except asyncio.TimeoutError:
            status.status = "unhealthy"
            status.error = f"健康检查超时 (>{self.timeout}s)"
            status.consecutive_failures += 1
            logger.warning(f"{name} 健康检查超时")

        except Exception as e:
            status.status = "unhealthy"
            status.error = str(e)
            status.consecutive_failures += 1
            logger.warning(f"{name} 健康检查失败：{e}")

        # 更新检查时间
        status.last_check = datetime.now()
        self.services_status[name] = status

        return status

    async def check_all_services(self) -> Dict[str, ServiceStatus]:
        """
        检查所有服务健康状态

        Returns:
            Dict[str, ServiceStatus]: 所有服务状态
        """
        tasks = [self.check_service(name) for name in self.health_check_funcs.keys()]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        return {
            name: (result if isinstance(result, ServiceStatus) else ServiceStatus(
                status="unhealthy", error=str(result) if result else "Unknown error"
            ))
            for name, result in zip(self.health_check_funcs.keys(), results)
        }

    def get_aggregated_status(self) -> dict:
        """
        获取聚合状态

        Returns:
            dict: 聚合状态
        """
        # 计算整体状态
        statuses = list(self.services_status.values())

        if not statuses:
            overall_status = "unknown"
        elif all(s.status == "healthy" for s in statuses):
            overall_status = "healthy"
        elif all(s.status in ("unhealthy", "unknown") for s in statuses):
            overall_status = "unhealthy"
        else:
            overall_status = "degraded"

        return {
            "status": overall_status,
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "services": {
                name: {
                    "status": status.status,
                    "latency_ms": status.latency_ms,
                    "error": status.error,
                    "last_check": status.last_check.isoformat() if status.last_check else None,
                }
                for name, status in self.services_status.items()
            },
        }

    async def start_background_check(self):
        """启动后台健康检查"""
        if self._running:
            logger.warning("健康检查已在运行")
            return

        self._running = True
        self._background_task = asyncio.create_task(self._background_check_loop())
        logger.info(f"启动后台健康检查 (interval={self.check_interval}s)")

    async def stop_background_check(self):
        """停止后台健康检查"""
        self._running = False
        if self._background_task:
            self._background_task.cancel()
            try:
                await self._background_task
            except asyncio.CancelledError:
                pass
        logger.info("停止后台健康检查")

    async def _background_check_loop(self):
        """后台健康检查循环"""
        while self._running:
            try:
                await self.check_all_services()
                logger.debug(
                    f"健康检查完成："
                    f"{', '.join(f'{k}={v.status}' for k, v in self.services_status.items())}"
                )
            except Exception as e:
                logger.error(f"健康检查异常：{e}")

            await asyncio.sleep(self.check_interval)

    def get_status(self) -> HealthStatus:
        """获取完整健康状态"""
        return HealthStatus(
            status=self.get_aggregated_status()["status"],
            timestamp=datetime.utcnow().isoformat() + "Z",
            services=self.services_status,
        )


# 全局健康监控器实例
_health_monitor: Optional[HealthMonitor] = None


def init_health_monitor(
    check_interval: int = 30,
    timeout: int = 10,
    unhealthy_threshold: int = 3,
) -> HealthMonitor:
    """
    初始化全局健康监控器

    Args:
        check_interval: 健康检查间隔 (秒)
        timeout: 单次检查超时 (秒)
        unhealthy_threshold: 连续失败次数

    Returns:
        HealthMonitor: 健康监控器实例
    """
    global _health_monitor
    _health_monitor = HealthMonitor(
        check_interval=check_interval,
        timeout=timeout,
        unhealthy_threshold=unhealthy_threshold,
    )
    return _health_monitor


def get_health_monitor() -> Optional[HealthMonitor]:
    """获取全局健康监控器实例"""
    return _health_monitor
