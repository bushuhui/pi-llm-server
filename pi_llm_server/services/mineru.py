#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MinerU PDF 解析服务模块

提供 PDF 文件解析服务，包括:
- /v1/ocr/parser: PDF/OCR 解析 (前端网关路由)
- /file_parse: PDF/OCR 解析 (后端 MinerU API 实际路径)
"""

import asyncio
import httpx
import logging
import os
import shutil
import subprocess
import tempfile
from typing import Optional, List
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from ..config import ServiceConfig

logger = logging.getLogger(__name__)


# ============ 常量 ============

# 流式传输块大小（64KB）
CHUNK_SIZE = 64 * 1024

# 支持的文档类型
SUPPORTED_DOCUMENT_TYPES = {
    # PDF 格式
    ".pdf": "application/pdf",
    # 图片格式
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
    ".png": "image/png",
    # Office 文档（需要转换为 PDF）
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".doc": "application/msword",
    ".pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
    ".ppt": "application/vnd.ms-powerpoint",
    ".xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
    ".xls": "application/vnd.ms-excel",
}

# 需要转换为 PDF 的文件类型
OFFICE_DOCUMENT_TYPES = {".docx", ".doc", ".pptx", ".ppt", ".xlsx", ".xls"}


def get_file_extension(filename: str) -> str:
    """获取文件扩展名（小写）"""
    _, ext = os.path.splitext(filename)
    return ext.lower()


def is_supported_file(filename: str) -> bool:
    """检查文件类型是否支持"""
    ext = get_file_extension(filename)
    return ext in SUPPORTED_DOCUMENT_TYPES


def needs_pdf_conversion(filename: str) -> bool:
    """检查文件是否需要转换为 PDF"""
    ext = get_file_extension(filename)
    return ext in OFFICE_DOCUMENT_TYPES


async def _save_upload_to_disk(file: UploadFile, dest_path: str) -> int:
    """
    将上传文件流式写入磁盘临时文件，避免完整内容驻留内存

    Args:
        file: FastAPI UploadFile 对象
        dest_path: 目标磁盘路径

    Returns:
        int: 写入的字节总数
    """
    total = 0
    with open(dest_path, "wb") as out_f:
        while True:
            chunk = await file.read(CHUNK_SIZE)
            if not chunk:
                break
            out_f.write(chunk)
            total += len(chunk)
    return total


def _convert_to_pdf_sync(
    input_path: str, output_dir: str, original_filename: str, timeout_seconds: int = 600
) -> str:
    """
    同步：使用 libreoffice 将 Office 文档转换为 PDF（基于文件路径，不持有 bytes 副本）

    Args:
        input_path: 输入文件路径
        output_dir: 输出目录
        original_filename: 原始文件名（用于推算输出 PDF 名）
        timeout_seconds: libreoffice 转换超时（默认 600 秒）

    Returns:
        str: 生成的 PDF 文件路径

    Raises:
        HTTPException: 转换失败时抛出
    """
    # 为每次转换创建独立的临时用户目录，避免 libreoffice 多实例锁冲突
    user_dir = os.path.join(output_dir, "lo_user_profile")
    os.makedirs(user_dir, exist_ok=True)

    proc = subprocess.Popen(
        [
            "libreoffice",
            "--headless",
            "--norestore",
            "--nologo",
            "--nofirststartwizard",
            f"-env:UserInstallation=file://{user_dir}",
            "--convert-to", "pdf",
            "--outdir", output_dir,
            input_path,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=output_dir,
    )

    try:
        stdout, stderr = proc.communicate(timeout=timeout_seconds)
    except subprocess.TimeoutExpired:
        try:
            proc.kill()
            proc.wait(timeout=5)
        except Exception:
            pass
        logger.error(f"libreoffice 转换超时（文件：{original_filename}）")
        raise HTTPException(status_code=504, detail="Office 文档转换超时")

    if proc.returncode != 0:
        err_msg = stderr.decode("utf-8", errors="replace")[:500]
        logger.error(f"libreoffice 转换失败：{err_msg}")
        raise HTTPException(status_code=500, detail=f"Office 文档转换失败：{err_msg}")

    # libreoffice 输出文件名基于 input_path 的文件名，不是 original_filename
    pdf_filename = os.path.splitext(os.path.basename(input_path))[0] + ".pdf"
    pdf_path = os.path.join(output_dir, pdf_filename)
    if not os.path.exists(pdf_path):
        # 兜底：扫描 output_dir 下所有 pdf 文件
        pdf_files = [f for f in os.listdir(output_dir) if f.endswith(".pdf")]
        if pdf_files:
            pdf_path = os.path.join(output_dir, sorted(pdf_files)[0])
        else:
            logger.error(f"PDF 文件未生成：{pdf_path}")
            raise HTTPException(
                status_code=500,
                detail="Office 文档转换失败：未生成 PDF 文件",
            )

    return pdf_path


async def convert_to_pdf_file(
    input_path: str, output_dir: str, original_filename: str, timeout_seconds: int = 600
) -> str:
    """
    异步包装：在线程中执行 libreoffice 转换，避免阻塞事件循环

    Args:
        input_path: 输入文件路径
        output_dir: 输出目录
        original_filename: 原始文件名
        timeout_seconds: libreoffice 转换超时（默认 600 秒）

    Returns:
        str: 生成的 PDF 文件路径
    """
    try:
        return await asyncio.to_thread(
            _convert_to_pdf_sync, input_path, output_dir, original_filename, timeout_seconds
        )
    except FileNotFoundError:
        logger.error("未找到 libreoffice，请安装：sudo apt-get install libreoffice")
        raise HTTPException(
            status_code=500,
            detail="服务器未安装 libreoffice，无法转换 Office 文档",
        )


def _check_pdf_encrypted(pdf_path: str) -> bool:
    """检测 PDF 是否加密（密码保护）"""
    try:
        from pypdf import PdfReader
        reader = PdfReader(pdf_path)
        return reader.is_encrypted
    except Exception:
        # PDF 损坏或无法读取时，返回 False，让 MinerU 自行报错
        return False


def _get_pdf_page_count(pdf_path: str) -> int:
    """获取 PDF 总页数，异常时返回 0"""
    try:
        from pypdf import PdfReader
        reader = PdfReader(pdf_path)
        return len(reader.pages)
    except Exception:
        return 0


def _split_pdf_into_chunks(pdf_path: str, output_dir: str, pages_per_chunk: int) -> List[str]:
    """
    将 PDF 按页数拆分为多个片段

    Args:
        pdf_path: 输入 PDF 路径
        output_dir: 片段输出目录
        pages_per_chunk: 每个片段的最大页数

    Returns:
        List[str]: 片段文件路径列表。若总页数 <= pages_per_chunk 或拆分失败，返回原路径。
    """
    from pypdf import PdfReader, PdfWriter

    try:
        reader = PdfReader(pdf_path)
        total_pages = len(reader.pages)

        if total_pages <= pages_per_chunk:
            return [pdf_path]

        chunk_paths = []
        for start in range(0, total_pages, pages_per_chunk):
            end = min(start + pages_per_chunk, total_pages)
            writer = PdfWriter()
            for i in range(start, end):
                writer.add_page(reader.pages[i])
            chunk_path = os.path.join(output_dir, f"chunk_{start}_{end}.pdf")
            with open(chunk_path, "wb") as f:
                writer.write(f)
            chunk_paths.append(chunk_path)

        return chunk_paths
    except Exception as e:
        logger.warning(f"PDF 拆分失败，回退到单文件处理：{e}")
        return [pdf_path]


def _merge_mineru_zip_results(zip_paths: List[str], output_zip_path: str, output_stem: str) -> None:
    """
    合并多个 MinerU ZIP 结果为一个 ZIP

    每个输入 ZIP 结构：
        {stem}/{stem}.md
        {stem}/images/{hash}.jpg

    输出 ZIP 结构：
        {output_stem}/{output_stem}.md
        {output_stem}/images/{hash}.jpg

    Args:
        zip_paths: 输入 ZIP 文件路径列表
        output_zip_path: 输出 ZIP 文件路径
        output_stem: 输出 ZIP 中的顶层目录名和 markdown 文件名（不含扩展名）
    """
    import zipfile

    merged_md_parts = []
    images = {}  # basename -> bytes，利用 SHA256 哈希天然去重

    for zip_path in zip_paths:
        with zipfile.ZipFile(zip_path, "r") as zf:
            # 提取 markdown 内容
            md_files = [n for n in zf.namelist() if n.endswith(".md")]
            for md_file in md_files:
                content = zf.read(md_file).decode("utf-8", errors="replace")
                merged_md_parts.append(content)

            # 提取图片（去重）
            for name in zf.namelist():
                if "/images/" in name:
                    img_name = os.path.basename(name)
                    if img_name not in images:
                        images[img_name] = zf.read(name)

    with zipfile.ZipFile(output_zip_path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr(f"{output_stem}/{output_stem}.md", "\n\n".join(merged_md_parts))
        for img_name, data in images.items():
            zf.writestr(f"{output_stem}/images/{img_name}", data)


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

    async def _download_mineru_result(
        self,
        pdf_path: str,
        upload_filename: str,
        data: dict,
        output_path: str,
    ) -> None:
        """
        调用 MinerU 解析并将完整 ZIP 结果下载到文件

        Args:
            pdf_path: 上传的 PDF 文件路径
            upload_filename: 上传文件名
            data: 请求表单数据
            output_path: 结果 ZIP 保存路径

        Raises:
            HTTPException: 请求失败时抛出
        """
        client = self.client
        timeout_s = self.timeout
        max_retries = self.max_retries
        last_exc: Optional[Exception] = None

        for attempt in range(max_retries):
            try:
                with open(pdf_path, "rb") as f:
                    files = {"files": (upload_filename, f, "application/pdf")}
                    logger.info(
                        f"发送 PDF 解析请求 (attempt {attempt + 1}/{max_retries})..."
                    )
                    async with client.stream(
                        "POST", "/file_parse",
                        files=files,
                        data=data,
                        timeout=timeout_s,
                    ) as response:
                        response.raise_for_status()
                        with open(output_path, "wb") as out_f:
                            async for chunk in response.aiter_bytes(CHUNK_SIZE):
                                out_f.write(chunk)
                        return
            except httpx.TimeoutException as e:
                last_exc = e
                logger.warning(
                    f"MinerU 解析请求超时 (attempt {attempt + 1}/{max_retries}): {e}"
                )
            except httpx.HTTPStatusError as e:
                last_exc = e
                try:
                    body = (await e.response.aread()).decode("utf-8", "replace")[:500]
                except Exception:
                    body = "N/A"
                logger.error(
                    f"MinerU 解析请求失败 (attempt {attempt + 1}/{max_retries}): {e}"
                )
                logger.error(f"响应内容：{body}")
            except httpx.HTTPError as e:
                last_exc = e
                logger.error(
                    f"MinerU 解析请求失败 (attempt {attempt + 1}/{max_retries}): {e}"
                )

        if isinstance(last_exc, httpx.TimeoutException):
            raise HTTPException(status_code=504, detail="MinerU 服务响应超时")
        if isinstance(last_exc, httpx.HTTPStatusError):
            raise HTTPException(
                status_code=last_exc.response.status_code,
                detail=f"MinerU 服务错误：{str(last_exc)}",
            )
        raise HTTPException(
            status_code=502,
            detail=f"MinerU 服务错误：{str(last_exc)}",
        )

    async def parse_pdf_stream(
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
    ) -> StreamingResponse:
        """
        流式解析文档：上传文件流式落盘 → 流式上传到 MinerU → 后端响应流式回写客户端。
        全程不持有完整文件副本，避免 OOM。

        Args:
            file: 上传的文件（支持 PDF、jpg、png、docx、doc、pptx、ppt、xlsx、xls）
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
            StreamingResponse: 流式 ZIP 响应

        Raises:
            HTTPException: 请求失败时抛出
        """
        file_filename = file.filename or "document.pdf"
        file_ext = get_file_extension(file_filename)

        # 检查文件类型是否支持
        if not is_supported_file(file_filename):
            raise HTTPException(
                status_code=400,
                detail=(
                    f"不支持的文件类型：{file_ext}。"
                    f"支持的类型：{', '.join(SUPPORTED_DOCUMENT_TYPES.keys())}"
                ),
            )

        # 临时目录由 generator 的 finally 负责清理
        temp_dir = tempfile.mkdtemp(prefix="mineru_")

        try:
            # 1. 上传文件流式落盘
            safe_ext = file_ext if file_ext else ".bin"
            input_path = os.path.join(temp_dir, f"input{safe_ext}")
            size = await _save_upload_to_disk(file, input_path)
            logger.info(f"上传文件已落盘：{file_filename} ({size} bytes)")

            # 2. Office 文档转换为 PDF
            libreoffice_timeout = self.mineru_config.get("libreoffice_timeout", 600)
            if needs_pdf_conversion(file_filename):
                pdf_path = await convert_to_pdf_file(
                    input_path, temp_dir, file_filename, timeout_seconds=libreoffice_timeout
                )
                upload_filename = os.path.splitext(file_filename)[0] + ".pdf"
                logger.info(f"文件已转换为 PDF: {upload_filename}")
            else:
                pdf_path = input_path
                upload_filename = file_filename

            # 3. 加密 PDF 检测
            if _check_pdf_encrypted(pdf_path):
                shutil.rmtree(temp_dir, ignore_errors=True)
                raise HTTPException(status_code=400, detail="PDF 文件已加密，无法解析")

            # 4. 准备请求参数
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

            client = self.client
            timeout_s = self.timeout
            max_retries = self.max_retries

            # 5. 判断是否需分批处理
            batch_page_size = self.mineru_config.get("batch_page_size", 50)
            batch_size_threshold_mb = self.mineru_config.get(
                "batch_size_threshold_mb", 50
            )
            batch_size_threshold = batch_size_threshold_mb * 1024 * 1024
            pdf_size = os.path.getsize(pdf_path)
            total_pages = _get_pdf_page_count(pdf_path)
            needs_batch = total_pages > batch_page_size or pdf_size > batch_size_threshold

            if needs_batch:
                logger.info(
                    f"大文件触发分批处理：页数={total_pages}，大小={pdf_size} bytes，"
                    f"阈值={batch_page_size}页/{batch_size_threshold_mb}MB"
                )

            async def generate():
                try:
                    if needs_batch:
                        # 大文件：拆分 → 分批解析 → 合并结果
                        chunk_paths = await asyncio.to_thread(
                            _split_pdf_into_chunks,
                            pdf_path,
                            temp_dir,
                            batch_page_size,
                        )

                        result_zips = []
                        for i, chunk_path in enumerate(chunk_paths):
                            result_zip = os.path.join(temp_dir, f"result_{i}.zip")
                            await self._download_mineru_result(
                                chunk_path,
                                f"chunk_{i}.pdf",
                                data,
                                result_zip,
                            )
                            result_zips.append(result_zip)

                        merged_zip = os.path.join(temp_dir, "merged.zip")
                        await asyncio.to_thread(
                            _merge_mineru_zip_results,
                            result_zips,
                            merged_zip,
                            "result",
                        )

                        with open(merged_zip, "rb") as f:
                            while True:
                                chunk = f.read(CHUNK_SIZE)
                                if not chunk:
                                    break
                                yield chunk
                    else:
                        # 小文件：直接流式转发
                        last_exc: Optional[Exception] = None
                        for attempt in range(max_retries):
                            try:
                                with open(pdf_path, "rb") as f:
                                    files = {
                                        "files": (upload_filename, f, "application/pdf")
                                    }
                                    logger.info(
                                        f"发送 PDF 解析请求 (attempt {attempt + 1}/{max_retries})..."
                                    )
                                    logger.info(
                                        f"文件：{upload_filename}, 后端：{backend}, 超时：{timeout_s}s"
                                    )
                                    async with client.stream(
                                        "POST", "/file_parse",
                                        files=files,
                                        data=data,
                                    ) as response:
                                        response.raise_for_status()
                                        async for chunk in response.aiter_bytes(CHUNK_SIZE):
                                            yield chunk
                                        return
                            except httpx.TimeoutException as e:
                                last_exc = e
                                logger.warning(
                                    f"MinerU 解析请求超时 (attempt {attempt + 1}/{max_retries}): {e}"
                                )
                            except httpx.HTTPStatusError as e:
                                last_exc = e
                                try:
                                    body = (await e.response.aread()).decode(
                                        "utf-8", "replace"
                                    )[:500]
                                except Exception:
                                    body = "N/A"
                                logger.error(
                                    f"MinerU 解析请求失败 (attempt {attempt + 1}/{max_retries}): {e}"
                                )
                                logger.error(f"响应内容：{body}")
                            except httpx.HTTPError as e:
                                last_exc = e
                                logger.error(
                                    f"MinerU 解析请求失败 (attempt {attempt + 1}/{max_retries}): {e}"
                                )

                        # 重试耗尽：抛 HTTPException
                        if isinstance(last_exc, httpx.TimeoutException):
                            raise HTTPException(status_code=504, detail="MinerU 服务响应超时")
                        if isinstance(last_exc, httpx.HTTPStatusError):
                            raise HTTPException(
                                status_code=last_exc.response.status_code,
                                detail=f"MinerU 服务错误：{str(last_exc)}",
                            )
                        raise HTTPException(
                            status_code=502,
                            detail=f"MinerU 服务错误：{str(last_exc)}",
                        )
                finally:
                    shutil.rmtree(temp_dir, ignore_errors=True)

            return StreamingResponse(
                generate(),
                media_type="application/zip",
                headers={"Content-Disposition": "attachment; filename=result.zip"},
            )

        except Exception:
            # 流式 generator 启动前的异常路径：直接清理临时目录
            shutil.rmtree(temp_dir, ignore_errors=True)
            raise

    async def health_check(self) -> dict:
        """
        健康检查

        Returns:
            dict: 健康状态
        """
        # MinerU 没有 /health 端点，检查 /openapi.json
        try:
            response = await self.client.get("/openapi.json", timeout=5.0)
            if response.status_code == 200:
                return {"status": "healthy", "latency_ms": response.elapsed.total_seconds() * 1000}
            else:
                return {"status": "unknown", "status_code": response.status_code}
        except Exception as e:
            # 连接失败时返回 unhealthy
            return {"status": "unhealthy", "error": str(e)}

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
            files: UploadFile = File(..., description="文档文件（支持 PDF、jpg、png、docx、doc、pptx、ppt、xlsx、xls）"),
            backend: Optional[str] = Form(default="pipeline", description="解析后端"),
            parse_method: Optional[str] = Form(default="auto", description="解析方法"),
            lang_list: Optional[str] = Form(default="ch", description="语言"),
            formula_enable: Optional[bool] = Form(default=True, description="公式解析"),
            table_enable: Optional[bool] = Form(default=True, description="表格解析"),
            return_md: Optional[bool] = Form(default=True, description="返回 markdown"),
            return_images: Optional[bool] = Form(default=True, description="返回图片"),
        ):
            """解析文档文件为 Markdown 和图片（支持 PDF、图片、Office 文档）"""
            return await self.parse_pdf_stream(
                file=files,
                backend=backend,
                parse_method=parse_method,
                lang_list=lang_list,
                formula_enable=formula_enable,
                table_enable=table_enable,
                return_md=return_md,
                return_images=return_images,
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
