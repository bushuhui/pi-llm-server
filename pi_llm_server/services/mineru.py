#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MinerU PDF 解析服务模块

提供 PDF 文件解析服务，包括:
- /v1/ocr/parser: PDF/OCR 解析
"""

import httpx
import logging
from typing import Optional, List, Union
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse, JSONResponse
from pydantic import BaseModel, Field

from ..config import ServiceConfig

logger = logging.getLogger(__name__)


# ============ 请求/响应模型 ============

class MinerURequest(BaseModel):
    """MinerU 解析请求 (JSON 方式)"""
    backend: Optional[str] = Field(default="pipeline", description="解析后端")
    parse_method: Optional[str] = Field(default="auto", description="解析方法")
    lang_list: Optional[str] = Field(default="ch", description="语言")
    formula_enable: Optional[bool] = Field(default=True, description="公式解析")
    table_enable: Optional[bool] = Field(default=True, description="表格解析")
    return_md: Optional[bool] = Field(default=True, description="返回 markdown")
    return_images: Optional[bool] = Field(default=True, description="返回图片")
    return_middle_json: Optional[bool] = Field(default=False, description="返回中间 JSON")
    start_page_id: Optional[int] = Field(default=0, description="起始页")
    end_page_id: Optional[int] = Field(default=99999, description="结束页")


# ============ 服务类 ============

class MinerUService:
    """MinerU 服务 (Client + Router)"""

    def __init__(self, config: ServiceConfig):
        """
        初始化 MinerU 服务

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
            limits=httpx.Limits(max_keepalive_connections=5, max_connections=10)
        )

        # Router
        self.router = APIRouter(tags=["mineru"])
        self._register_routes()

        # 服务配置
        self.mineru_config = config.config if hasattr(config, 'config') else {}

    async def parse_pdf(
        self,
        file: UploadFile,
        backend: Optional[str] = "pipeline",
        parse_method: Optional[str] = "auto",
        lang_list: Optional[str] = "ch",
        formula_enable: Optional[bool] = True,
        table_enable: Optional[bool] = True,
        return_md: Optional[bool] = True,
        return_images: Optional[bool] = True,
        return_middle_json: Optional[bool] = False,
        start_page_id: Optional[int] = 0,
        end_page_id: Optional[int] = 99999,
    ) -> bytes:
        """
        解析 PDF 文件

        Args:
            file: PDF 文件
            backend: 解析后端 (pipeline/hybrid-auto-engine/vlm-auto-engine)
            parse_method: 解析方法 (auto/txt/ocr)
            lang_list: 语言 (ch/en/korean/japan 等)
            formula_enable: 是否启用公式解析
            table_enable: 是否启用表格解析
            return_md: 是否返回 markdown
            return_images: 是否返回图片
            return_middle_json: 是否返回中间 JSON
            start_page_id: 起始页码
            end_page_id: 结束页码

        Returns:
            bytes: ZIP 文件内容

        Raises:
            HTTPException: 请求失败时抛出
        """
        # 读取文件内容
        file_content = await file.read()
        file_filename = file.filename or "document.pdf"

        # 准备请求参数
        files = {"files": (file_filename, file_content, "application/pdf")}
        data = {
            "backend": backend,
            "parse_method": parse_method,
            "lang_list": lang_list,
            "formula_enable": str(formula_enable).lower(),
            "table_enable": str(table_enable).lower(),
            "return_md": str(return_md).lower(),
            "return_images": str(return_images).lower(),
            "return_middle_json": str(return_middle_json).lower(),
            "start_page_id": str(start_page_id),
            "end_page_id": str(end_page_id),
            "response_format_zip": "true",  # 关键：以 zip 格式返回
        }

        for attempt in range(self.max_retries):
            try:
                logger.info(f"发送 PDF 解析请求 (attempt {attempt + 1}/{self.max_retries})...")
                logger.info(f"文件：{file_filename}, 后端：{backend}, 超时：{self.timeout}s")

                response = await self.client.post(
                    "/v1/ocr/parser",
                    files=files,
                    data=data,
                )
                response.raise_for_status()
                return response.content
            except httpx.TimeoutException as e:
                logger.warning(f"MinerU 解析请求超时 (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt == self.max_retries - 1:
                    raise HTTPException(status_code=504, detail="MinerU 服务响应超时")
            except httpx.HTTPStatusError as e:
                logger.error(f"MinerU 解析请求失败 (attempt {attempt + 1}/{self.max_retries}): {e}")
                logger.error(f"响应内容：{e.response.text[:500] if e.response.text else 'N/A'}")
                if attempt == self.max_retries - 1:
                    raise HTTPException(
                        status_code=e.response.status_code,
                        detail=f"MinerU 服务错误：{str(e)}",
                    )
            except httpx.HTTPError as e:
                logger.error(f"MinerU 解析请求失败 (attempt {attempt + 1}/{self.max_retries}): {e}")
                if attempt == self.max_retries - 1:
                    raise HTTPException(status_code=502, detail=f"MinerU 服务错误：{str(e)}")

        return None

    async def health_check(self) -> dict:
        """
        健康检查

        Returns:
            dict: 健康状态
        """
        # MinerU 可能没有 /health 端点，直接返回健康
        try:
            response = await self.client.get("/health", timeout=5.0)
            if response.status_code == 200:
                return {"status": "healthy", "latency_ms": response.elapsed.total_seconds() * 1000}
            else:
                return {"status": "unknown", "status_code": response.status_code}
        except Exception as e:
            # MinerU 没有健康端点时，返回 unknown 而非 unhealthy
            return {"status": "unknown", "note": "MinerU 服务未提供健康检查端点"}

    async def get_models(self) -> List[dict]:
        """
        获取可用模型列表

        Returns:
            List[dict]: 模型列表
        """
        # MinerU 返回后端类型作为"模型"
        backends = [
            {"id": "mineru/pipeline", "service": "mineru", "type": "pipeline"},
            {"id": "mineru/hybrid-auto-engine", "service": "mineru", "type": "hybrid"},
            {"id": "mineru/vlm-auto-engine", "service": "mineru", "type": "vlm"},
        ]
        return backends

    def _register_routes(self):
        """注册 FastAPI 路由"""

        @self.router.post("/v1/ocr/parser", tags=["mineru"])
        async def parser_endpoint(
            files: UploadFile = File(..., description="PDF 文件"),
            backend: Optional[str] = Form(default="pipeline", description="解析后端"),
            parse_method: Optional[str] = Form(default="auto", description="解析方法"),
            lang_list: Optional[str] = Form(default="ch", description="语言"),
            formula_enable: Optional[bool] = Form(default=True, description="公式解析"),
            table_enable: Optional[bool] = Form(default=True, description="表格解析"),
            return_md: Optional[bool] = Form(default=True, description="返回 markdown"),
            return_images: Optional[bool] = Form(default=True, description="返回图片"),
        ):
            """解析 PDF 文件为 Markdown 和图片"""
            zip_content = await self.parse_pdf(
                file=files,
                backend=backend,
                parse_method=parse_method,
                lang_list=lang_list,
                formula_enable=formula_enable,
                table_enable=table_enable,
                return_md=return_md,
                return_images=return_images,
            )
            return StreamingResponse(
                iter([zip_content]),
                media_type="application/zip",
                headers={"Content-Disposition": "attachment; filename=result.zip"},
            )

    async def close(self):
        """关闭 HTTP 客户端"""
        await self.client.aclose()


# ============ 全局实例 ============

mineru_service: Optional[MinerUService] = None


def init_mineru_service(config: ServiceConfig) -> MinerUService:
    """
    初始化 MinerU 服务

    Args:
        config: 服务配置

    Returns:
        MinerUService: 服务实例
    """
    global mineru_service
    mineru_service = MinerUService(config)
    logger.info(f"MinerU 服务初始化完成：{config.base_url}")
    return mineru_service


def get_mineru_service() -> MinerUService:
    """获取 MinerU 服务实例"""
    if not mineru_service:
        raise RuntimeError("MinerU 服务未初始化")
    return mineru_service
