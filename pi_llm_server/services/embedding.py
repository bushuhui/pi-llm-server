#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Embedding 服务模块

提供文本向量化服务，包括:
- /v1/embeddings: 生成 embedding 向量
- /v1/similarity: 计算文本相似度
"""

from __future__ import annotations

import httpx
import logging
from typing import Union, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from ..config import ServiceConfig

logger = logging.getLogger(__name__)


# ============ 请求/响应模型 ============

class EmbeddingRequest(BaseModel):
    """Embedding 请求"""
    input: Union[str, List[str]] = Field(..., description="输入文本或文本列表")
    model: Optional[str] = Field(default=None, description="模型 ID")
    encoding_format: Optional[str] = Field(default="float", description="编码格式：float | base64, 默认 float (OpenAI API 标准)")


class EmbeddingResponse(BaseModel):
    """Embedding 响应"""
    object: str = "list"
    data: List[dict]
    model: str
    usage: dict


class SimilarityRequest(BaseModel):
    """相似度计算请求"""
    text1: str = Field(..., description="第一个文本")
    text2: str = Field(..., description="第二个文本")


class SimilarityResponse(BaseModel):
    """相似度计算响应"""
    similarity: float


# ============ 服务类 ============

class EmbeddingService:
    """Embedding 服务 (Client + Router)"""

    def __init__(self, config: ServiceConfig):
        """
        初始化 Embedding 服务

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
        self.router = APIRouter(tags=["embedding"])
        self._register_routes()

        # 服务信息
        self.models = config.models if hasattr(config, 'models') else []

    async def create_embeddings(
        self,
        input_text: Union[str, List[str]],
        model: Optional[str] = None,
        encoding_format: Optional[str] = "float",
    ) -> dict:
        """
        调用 embedding 服务生成向量

        Args:
            input_text: 输入文本或文本列表
            model: 模型 ID (可选)
            encoding_format: 编码格式：float | base64 (可选，默认 float)

        Returns:
            dict: embedding 响应

        Raises:
            HTTPException: 请求失败时抛出
        """
        request_data = {"input": input_text}
        if model:
            request_data["model"] = model
        if encoding_format:
            request_data["encoding_format"] = encoding_format

        for attempt in range(self.max_retries):
            try:
                response = await self.client.post(
                    "/v1/embeddings",
                    json=request_data,
                )
                response.raise_for_status()
                return response.json()
            except httpx.TimeoutException as e:
                logger.warning(f"Embedding 请求超时 (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt == self.max_retries - 1:
                    raise HTTPException(status_code=504, detail="Embedding 服务响应超时")
            except httpx.HTTPError as e:
                logger.error(f"Embedding 请求失败 (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt == self.max_retries - 1:
                    raise HTTPException(status_code=502, detail=f"Embedding 服务错误：{str(e)}")

        return None

    async def calculate_similarity(self, text1: str, text2: str) -> float:
        """
        计算文本相似度

        Args:
            text1: 第一个文本
            text2: 第二个文本

        Returns:
            float: 相似度分数 (0-1)

        Raises:
            HTTPException: 请求失败时抛出
        """
        try:
            response = await self.client.post(
                "/v1/similarity",
                json={"text1": text1, "text2": text2},
            )
            response.raise_for_status()
            result = response.json()
            return result.get("similarity", 0.0)
        except httpx.TimeoutException as e:
            logger.warning(f"相似度计算超时：{e}")
            raise HTTPException(status_code=504, detail="相似度计算超时")
        except httpx.HTTPError as e:
            logger.error(f"相似度计算失败：{e}")
            raise HTTPException(status_code=502, detail=f"相似度计算失败：{str(e)}")

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
                    model["service"] = "embedding"
                return models
            return []
        except Exception as e:
            logger.warning(f"获取模型列表失败：{e}")
            return []

    def _register_routes(self):
        """注册 FastAPI 路由"""

        @self.router.post("/v1/embeddings", tags=["embedding"])
        async def embeddings_endpoint(request: EmbeddingRequest):
            """生成 embedding 向量"""
            return await self.create_embeddings(request.input, request.model)

        @self.router.post("/v1/similarity", tags=["embedding"])
        async def similarity_endpoint(request: SimilarityRequest):
            """计算两个文本的余弦相似度"""
            score = await self.calculate_similarity(request.text1, request.text2)
            return {"similarity": score}

    async def close(self):
        """关闭 HTTP 客户端"""
        await self.client.aclose()


# ============ 全局实例 ============

embedding_service: Optional[EmbeddingService] = None


def init_embedding_service(config: ServiceConfig) -> EmbeddingService:
    """
    初始化 Embedding 服务

    Args:
        config: 服务配置

    Returns:
        EmbeddingService: 服务实例
    """
    global embedding_service
    embedding_service = EmbeddingService(config)
    logger.info(f"Embedding 服务初始化完成：{config.base_url}")
    return embedding_service


def get_embedding_service() -> EmbeddingService:
    """获取 Embedding 服务实例"""
    if not embedding_service:
        raise RuntimeError("Embedding 服务未初始化")
    return embedding_service
