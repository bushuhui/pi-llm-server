#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
pi-memory 代理服务模块

代理 pi-memory-server 的 REST API，包括:
- 记忆管理: /api/memory/* (search, store, delete, update, list, stats)
- 知识库:   /api/knowledge/* (search, index, stats)
"""

import httpx
import logging
from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, HTTPException, Query
from fastapi.responses import JSONResponse

from ..config import MemoryServiceConfig

logger = logging.getLogger(__name__)


class MemoryService:
    """pi-memory 代理服务 (Client + Router)"""

    def __init__(self, config: MemoryServiceConfig):
        self.config = config
        self.base_url = config.base_url
        self.timeout = config.timeout_seconds
        self.max_retries = config.max_retries
        self.api_key = config.api_key

        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
        )

        self.router = APIRouter(tags=["memory"])
        self._register_routes()

    async def _proxy_request(
        self,
        method: str,
        path: str,
        **kwargs,
    ) -> JSONResponse:
        """通用代理方法，处理重试和错误"""
        headers = {}
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"

        client_method = {
            "GET": self.client.get,
            "POST": self.client.post,
            "DELETE": self.client.delete,
            "PATCH": self.client.patch,
        }.get(method)

        if client_method is None:
            raise HTTPException(status_code=405, detail=f"Unsupported method: {method}")

        for attempt in range(self.max_retries):
            try:
                response = await client_method(path, headers=headers, **kwargs)
                response.raise_for_status()
                return JSONResponse(
                    status_code=200,
                    content=response.json(),
                )
            except httpx.TimeoutException as e:
                logger.warning(
                    f"pi-memory 请求超时 (attempt {attempt + 1}/{self.max_retries}): {method} {path} - {e}"
                )
                if attempt == self.max_retries - 1:
                    raise HTTPException(status_code=504, detail="pi-memory 服务响应超时")
            except httpx.HTTPStatusError as e:
                logger.error(
                    f"pi-memory 请求失败 (attempt {attempt + 1}/{self.max_retries}): "
                    f"{method} {path} - {e.response.status_code} {e.response.text[:500]}"
                )
                if attempt == self.max_retries - 1:
                    raise HTTPException(
                        status_code=e.response.status_code,
                        detail=f"pi-memory 服务错误: {e.response.status_code}",
                    )
            except httpx.HTTPError as e:
                logger.error(
                    f"pi-memory 连接失败 (attempt {attempt + 1}/{self.max_retries}): {e}"
                )
                if attempt == self.max_retries - 1:
                    raise HTTPException(status_code=502, detail="pi-memory 服务连接失败")

        return None

    async def health_check(self) -> dict:
        """健康检查"""
        try:
            response = await self.client.get("/health", timeout=5.0)
            if response.status_code == 200:
                return {"status": "healthy", "latency_ms": response.elapsed.total_seconds() * 1000}
            return {"status": "unknown", "status_code": response.status_code}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    async def get_models(self) -> list:
        """返回服务信息"""
        return [
            {"id": "memory/search", "service": "memory", "type": "memory"},
            {"id": "memory/knowledge", "service": "memory", "type": "knowledge"},
        ]

    def _register_routes(self):
        """注册 FastAPI 路由"""

        # ===== 记忆管理 =====

        @self.router.post("/memory/api/memory/search", tags=["memory"])
        async def memory_search(body: Dict[str, Any] = Body(...)):
            """混合检索记忆（Vector + BM25 + Rerank）"""
            return await self._proxy_request("POST", "/api/memory/search", json=body)

        @self.router.post("/memory/api/memory/store", tags=["memory"])
        async def memory_store(body: Dict[str, Any] = Body(...)):
            """存储新记忆"""
            return await self._proxy_request("POST", "/api/memory/store", json=body)

        @self.router.delete("/memory/api/memory/{memory_id}", tags=["memory"])
        async def memory_delete(memory_id: str):
            """删除指定记忆"""
            return await self._proxy_request("DELETE", f"/api/memory/{memory_id}")

        @self.router.patch("/memory/api/memory/{memory_id}", tags=["memory"])
        async def memory_update(memory_id: str, body: Dict[str, Any] = Body(...)):
            """更新记忆"""
            return await self._proxy_request("PATCH", f"/api/memory/{memory_id}", json=body)

        @self.router.get("/memory/api/memory/list", tags=["memory"])
        async def memory_list(
            limit: int = Query(default=20, ge=1, le=100),
            offset: int = Query(default=0, ge=0),
            scope: Optional[str] = None,
            category: Optional[str] = None,
        ):
            """列出记忆，支持分页和过滤"""
            params: Dict[str, Any] = {"limit": limit, "offset": offset}
            if scope:
                params["scope"] = scope
            if category:
                params["category"] = category
            return await self._proxy_request("GET", "/api/memory/list", params=params)

        @self.router.get("/memory/api/memory/stats", tags=["memory"])
        async def memory_stats():
            """记忆统计信息"""
            return await self._proxy_request("GET", "/api/memory/stats")

        # ===== 知识库 =====

        @self.router.post("/memory/api/knowledge/search", tags=["memory"])
        async def knowledge_search(body: Dict[str, Any] = Body(...)):
            """混合检索知识库（Vector + BM25 + RRF 融合 + Cross-Encoder Rerank）"""
            return await self._proxy_request("POST", "/api/knowledge/search", json=body)

        @self.router.post("/memory/api/knowledge/index", tags=["memory"])
        async def knowledge_index(body: Dict[str, Any] = Body(default_factory=dict)):
            """重建知识库索引（incremental: true=增量, false=全量）"""
            return await self._proxy_request("POST", "/api/knowledge/index", json=body)

        @self.router.get("/memory/api/knowledge/stats", tags=["memory"])
        async def knowledge_stats():
            """知识库统计信息"""
            return await self._proxy_request("GET", "/api/knowledge/stats")

    async def close(self):
        """关闭 HTTP 客户端"""
        await self.client.aclose()


# ============ 全局实例 ============

memory_service: Optional[MemoryService] = None


def init_memory_service(config: MemoryServiceConfig) -> MemoryService:
    """
    初始化 pi-memory 代理服务

    Args:
        config: 服务配置

    Returns:
        MemoryService: 服务实例
    """
    global memory_service
    memory_service = MemoryService(config)
    logger.info(f"pi-memory 代理服务初始化完成：{config.base_url}")
    return memory_service


def get_memory_service() -> MemoryService:
    """获取 pi-memory 服务实例"""
    if not memory_service:
        raise RuntimeError("pi-memory 服务未初始化")
    return memory_service
