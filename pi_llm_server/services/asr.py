#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
ASR 语音识别服务模块

提供语音转文字服务，包括:
- /v1/audio/transcriptions: 语音识别 (form-data 方式)
- /v1/chat/completions: 语音识别 (audio_url 方式)
"""

import httpx
import logging
import os
import shutil
import tempfile
from typing import Optional, List, Union
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from ..config import ServiceConfig

logger = logging.getLogger(__name__)


# 流式传输块大小（64KB）
CHUNK_SIZE = 64 * 1024


# ============ 请求/响应模型 ============

class ChatCompletionMessage(BaseModel):
    """Chat 消息"""
    role: str
    content: Union[str, List[dict]]


class ChatCompletionRequest(BaseModel):
    """Chat Completion 请求"""
    model: str
    messages: List[ChatCompletionMessage]
    max_tokens: Optional[int] = Field(default=512, ge=1, le=4096)


class ChatCompletionResponse(BaseModel):
    """Chat Completion 响应"""
    id: str
    object: str
    created: int
    model: str
    choices: List[dict]
    usage: dict


class TranscriptionResponse(BaseModel):
    """语音转写响应"""
    text: str


# ============ 服务类 ============

class ASRService:
    """ASR 服务 (Client + Router)"""

    def __init__(self, config: ServiceConfig):
        """
        初始化 ASR 服务

        Args:
            config: 服务配置
        """
        self.config = config
        self.base_url = config.base_url
        self.timeout = config.timeout_seconds
        self.max_retries = config.max_retries

        # HTTP 客户端 (普通请求)
        self.client = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(self.timeout),
            limits=httpx.Limits(max_keepalive_connections=10, max_connections=20)
        )

        # HTTP 客户端 (长超时，用于长音频)
        self.client_long_timeout = httpx.AsyncClient(
            base_url=self.base_url,
            timeout=httpx.Timeout(max(self.timeout, 600)),
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        )

        # Router
        self.router = APIRouter(tags=["asr"])
        self._register_routes()

        # 服务信息
        self.models = config.models if hasattr(config, 'models') else []

    async def transcribe_audio(
        self,
        file: UploadFile,
        model: Optional[str] = None,
    ) -> str:
        """
        语音识别 - form-data 方式

        上传文件流式落盘，再以磁盘文件流式转发到后端，
        避免完整音频内容驻留内存。

        Args:
            file: 音频文件
            model: 模型 ID (可选)

        Returns:
            str: 转写文本

        Raises:
            HTTPException: 请求失败时抛出
        """
        file_filename = file.filename or "audio.wav"
        content_type = file.content_type or "audio/wav"

        # 临时目录用于流式落盘
        temp_dir = tempfile.mkdtemp(prefix="asr_")
        try:
            ext = os.path.splitext(file_filename)[1] or ".wav"
            input_path = os.path.join(temp_dir, f"input{ext}")

            # 流式写入磁盘临时文件
            with open(input_path, "wb") as out_f:
                while True:
                    chunk = await file.read(CHUNK_SIZE)
                    if not chunk:
                        break
                    out_f.write(chunk)

            data = {}
            if model:
                data["model"] = model

            for attempt in range(self.max_retries):
                try:
                    # 以磁盘文件句柄发起 multipart 上传，httpx 会按需读取
                    with open(input_path, "rb") as upload_f:
                        files = {"file": (file_filename, upload_f, content_type)}
                        response = await self.client_long_timeout.post(
                            "/v1/audio/transcriptions",
                            files=files,
                            data=data,
                        )
                        response.raise_for_status()
                        result = response.json()
                        return result.get("text", "")
                except httpx.TimeoutException as e:
                    logger.warning(
                        f"ASR 转录请求超时 (attempt {attempt + 1}/{self.max_retries}): {e}"
                    )
                    if attempt == self.max_retries - 1:
                        raise HTTPException(status_code=504, detail="ASR 服务响应超时")
                except httpx.HTTPError as e:
                    logger.error(
                        f"ASR 转录请求失败 (attempt {attempt + 1}/{self.max_retries}): {e}"
                    )
                    if attempt == self.max_retries - 1:
                        raise HTTPException(status_code=502, detail=f"ASR 服务错误：{str(e)}")

            return ""
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    async def chat_completion(
        self,
        messages: List[dict],
        model: str,
        max_tokens: int = 512,
    ) -> dict:
        """
        语音识别 - chat/completions 方式 (audio_url)

        Args:
            messages: 消息列表
            model: 模型 ID
            max_tokens: 最大生成长度

        Returns:
            dict: chat completion 响应

        Raises:
            HTTPException: 请求失败时抛出
        """
        request_data = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
        }

        for attempt in range(self.max_retries):
            try:
                response = await self.client.post(
                    "/v1/chat/completions",
                    json=request_data,
                )
                response.raise_for_status()
                return response.json()
            except httpx.TimeoutException as e:
                logger.warning(f"ASR chat 请求超时 (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt == self.max_retries - 1:
                    raise HTTPException(status_code=504, detail="ASR 服务响应超时")
            except httpx.HTTPError as e:
                logger.error(f"ASR chat 请求失败 (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt == self.max_retries - 1:
                    raise HTTPException(status_code=502, detail=f"ASR 服务错误：{str(e)}")

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
                    model["service"] = "asr"
                return models
            return []
        except Exception as e:
            logger.warning(f"获取模型列表失败：{e}")
            return []

    def _register_routes(self):
        """注册 FastAPI 路由"""

        @self.router.post("/v1/audio/transcriptions", tags=["asr"])
        async def transcriptions_endpoint(
            file: UploadFile = File(..., description="音频文件 (mp3/wav/ogg 等)"),
            model: str = Form(default="Qwen/Qwen3-ASR-1.7B", description="模型 ID"),
        ):
            """语音识别 - form-data 方式"""
            text = await self.transcribe_audio(file, model)
            return {"text": text}

        @self.router.post("/v1/chat/completions", tags=["asr"])
        async def chat_completions_endpoint(request: ChatCompletionRequest):
            """语音识别 - chat/completions 方式 (audio_url)"""
            return await self.chat_completion(
                messages=[m.dict() for m in request.messages],
                model=request.model,
                max_tokens=request.max_tokens,
            )

    async def close(self):
        """关闭 HTTP 客户端"""
        await self.client.aclose()
        await self.client_long_timeout.aclose()


# ============ 全局实例 ============

asr_service: Optional[ASRService] = None


def init_asr_service(config: ServiceConfig) -> ASRService:
    """
    初始化 ASR 服务

    Args:
        config: 服务配置

    Returns:
        ASRService: 服务实例
    """
    global asr_service
    asr_service = ASRService(config)
    logger.info(f"ASR 服务初始化完成：{config.base_url}")
    return asr_service


def get_asr_service() -> ASRService:
    """获取 ASR 服务实例"""
    if not asr_service:
        raise RuntimeError("ASR 服务未初始化")
    return asr_service
