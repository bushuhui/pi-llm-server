#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Reranker 服务模块

提供文档相关性排序服务，包括:
- /v1/rerank: 文档重排序
"""

import httpx
import logging
from typing import List, Optional, Any
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel, Field

from ..config import ServiceConfig

logger = logging.getLogger(__name__)


# ============ 请求/响应模型 ============

class RerankRequest(BaseModel):
    """Rerank 请求"""
    query: str = Field(..., description="查询文本")
    documents: List[str] = Field(..., description="文档列表")
    top_n: Optional[int] = Field(default=None, ge=1, le=100, description="返回前 N 个结果")
    model: Optional[str] = Field(default=None, description="模型 ID")


class RerankResult(BaseModel):
    """Rerank 结果"""
    index: int
    document: str
    relevance_score: float


class RerankResponse(BaseModel):
    """Rerank 响应"""
    model: str
    results: List[RerankResult]
    usage: Optional[dict] = None


# ============ 服务类 ============

class RerankerService:
    """Reranker 服务 (Client + Router)"""

    def __init__(self, config: ServiceConfig):
        """
        初始化 Reranker 服务

        Args:
            config: 服务配置
        """
        self.config = config
        self.base_url = config.base_url
        self.timeout = config.timeout_seconds
        self.max_retries = config.max_retries

        # HTTP 客户端
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout),
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20)
        )

        # Router
        self.router = APIRouter(tags=["reranker"])
        self._register_routes()

        # 服务信息
        self.models = config.models if hasattr(config, 'models') else []

    async def rerank(
        self,
        query: str,
        documents: List[str],
        top_n: Optional[int] = None,
        model: Optional[str] = None,
    ) -> dict:
        """
        调用 reranker 服务对文档进行相关性排序

        Args:
            query: 查询文本
            documents: 文档列表
            top_n: 返回前 N 个结果 (可选)
            model: 模型 ID (可选)

        Returns:
            dict: rerank 响应

        Raises:
            HTTPException: 请求失败时抛出
        """
        request_data = {
            "query": query,
            "documents": documents,
        }
        if top_n:
            request_data["top_n"] = top_n
        if model:
            request_data["model"] = model

        for attempt in range(self.max_retries):
            try:
                response = await self.client.post(
                    "/v1/rerank",
                    json=request_data,
                )
                response.raise_for_status()
                return response.json()
            except httpx.TimeoutException as e:
                logger.warning(f"Rerank 请求超时 (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt == self.max_retries - 1:
                    raise HTTPException(status_code=504, detail="Reranker 服务响应超时")
            except httpx.HTTPError as e:
                logger.error(f"Rerank 请求失败 (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt == self.max_retries - 1:
                    raise HTTPException(status_code=502, detail=f"Reranker 服务错误：{str(e)}")

        return None

    async def health_check(self) -> dict:
        """
        健康检查

        Returns:
            dict: 健康状态
        """
        try:
            response = await self.client.get("/health", timeout=5.0)
            if response.status_code == 200:
                return {"status": "healthy", "latency_ms": response.elapsed.total_seconds() * 1000}
            else:
                return {"status": "unhealthy", "status_code": response.status_code}
        except Exception as e:
            return {"status": "unhealthy", "error": str(e)}

    async def get_models(self) -> List[dict]:
        """
        获取可用模型列表

        Returns:
            List[dict]: 模型列表
        """
        try:
            response = await self.client.get("/v1/models", timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                # 添加服务信息
                models = data.get("data", [])
                for model in models:
                    model["service"] = "reranker"
                return models
            return []
        except Exception as e:
            logger.warning(f"获取模型列表失败：{e}")
            return []

    def _register_routes(self):
        """注册 FastAPI 路由"""

        @self.router.post("/v1/rerank", tags=["reranker"])
        async def rerank_endpoint(request: RerankRequest):
            """对文档进行相关性排序"""
            return await self.rerank(
                query=request.query,
                documents=request.documents,
                top_n=request.top_n,
                model=request.model,
            )

    async def close(self):
        """关闭 HTTP 客户端"""
        await self.client.aclose()


# ============ 全局实例 ============

reranker_service: Optional[RerankerService] = None


def init_reranker_service(config: ServiceConfig) -> RerankerService:
    """
    初始化 Reranker 服务

    Args:
        config: 服务配置

    Returns:
        RerankerService: 服务实例
    """
    global reranker_service
    reranker_service = RerankerService(config)
    logger.info(f"Reranker 服务初始化完成：{config.base_url}")
    return reranker_service


def get_reranker_service() -> RerankerService:
    """获取 Reranker 服务实例"""
    if not reranker_service:
        raise RuntimeError("Reranker 服务未初始化")
    return reranker_service
