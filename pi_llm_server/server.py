"""
PI-LLM-Server FastAPI 应用定义
"""
import glob
import logging
import os
import shutil
import tempfile
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from pi_llm_server.config import ConfigManager
from pi_llm_server.queue_manager import QueueManager, ServiceQueueConfig, init_queue_manager
from pi_llm_server.health_monitor import HealthMonitor, init_health_monitor
from pi_llm_server.utils.exceptions import (
    AuthenticationError,
    ServiceUnavailableError,
    QueueFullError,
)

# 导入服务模块
from pi_llm_server.services import (
    init_embedding_service,
    init_reranker_service,
    init_asr_service,
    init_mineru_service,
    init_memory_service,
    get_embedding_service,
    get_reranker_service,
    get_asr_service,
    get_mineru_service,
    get_memory_service,
)

logger = logging.getLogger(__name__)


# ============ 全局变量 ============

config_manager: Optional[ConfigManager] = None
queue_manager: Optional[QueueManager] = None
health_monitor: Optional[HealthMonitor] = None


def _cleanup_service_temp_residuals():
    """清理 /tmp 下残留的 mineru_ 和 asr_ 临时目录（只删超过 1 小时的）"""
    tmp_dir = tempfile.gettempdir()
    now = time.time()
    max_age = 3600  # 1 小时

    for prefix in ("mineru_", "asr_"):
        pattern = os.path.join(tmp_dir, f"{prefix}*")
        for path in glob.glob(pattern):
            if not os.path.isdir(path):
                continue
            try:
                if now - os.path.getmtime(path) > max_age:
                    shutil.rmtree(path, ignore_errors=True)
                    logger.info(f"清理残留临时目录: {path}")
            except Exception as e:
                logger.warning(f"清理残留临时目录失败 {path}: {e}")


# ============ 生命周期管理 ============

@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    应用生命周期管理

    启动时初始化各组件，关闭时清理资源
    """
    # 启动：初始化各服务
    logger.info("=" * 60)
    logger.info("PI-LLM-Server 启动中...")
    logger.info("=" * 60)

    # 清理残留临时目录
    _cleanup_service_temp_residuals()

    # 初始化健康监控后台任务
    if health_monitor and config_manager.config.health_check.enabled:
        await health_monitor.start_background_check()

    # 等待服务准备完成
    import asyncio
    await asyncio.sleep(2)

    logger.info("=" * 60)
    logger.info("PI-LLM-Server 启动完成!")
    logger.info(f"API 文档：http://{config_manager.config.server.host}:{config_manager.config.server.port}/docs")
    logger.info("=" * 60)

    yield

    # 关闭：清理资源
    logger.info("PI-LLM-Server 停止中...")

    # 停止健康监控
    if health_monitor:
        await health_monitor.stop_background_check()

    # 关闭各服务 HTTP 客户端
    try:
        embedding_svc = get_embedding_service()
        await embedding_svc.close()
    except RuntimeError:
        pass

    try:
        reranker_svc = get_reranker_service()
        await reranker_svc.close()
    except RuntimeError:
        pass

    try:
        asr_svc = get_asr_service()
        await asr_svc.close()
    except RuntimeError:
        pass

    try:
        mineru_svc = get_mineru_service()
        await mineru_svc.close()
    except RuntimeError:
        pass

    try:
        memory_svc = get_memory_service()
        await memory_svc.close()
    except RuntimeError:
        pass

    logger.info("PI-LLM-Server 已停止")


# ============ FastAPI 应用 ============

from pi_llm_server import __version__

app = FastAPI(
    title="PI-LLM Server",
    description="统一 LLM 服务网关 - 集成 Embedding、ASR、Reranker、MinerU 服务",
    version=__version__,
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

# CORS 中间件
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ============ 中间件 ============

@app.middleware("http")
async def auth_middleware_wrapper(request: Request, call_next):
    """认证中间件"""
    if not config_manager or not config_manager.config.auth.enabled:
        return await call_next(request)

    # 白名单路径
    public_paths = {"/health", "/docs", "/redoc", "/openapi.json", "/"}
    if request.url.path in public_paths:
        return await call_next(request)

    # 获取 Token
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return JSONResponse(
            status_code=401,
            content={"error": "Unauthorized", "message": "Missing authentication token"},
        )

    # 提取 token
    if auth_header.startswith("Bearer "):
        token = auth_header[7:]
    else:
        token = auth_header

    # 验证 token
    if not config_manager.validate_token(token, request.url.path):
        return JSONResponse(
            status_code=401,
            content={"error": "Unauthorized", "message": "Invalid authentication token"},
        )

    request.state.token = token
    return await call_next(request)


# ============ 通用端点 ============

@app.get("/", tags=["root"])
async def root():
    """根路径"""
    return {
        "name": "PI-LLM Server",
        "version": __version__,
        "description": "统一 LLM 服务网关",
        "docs": "/docs",
        "health": "/health",
        "status": "/status",
        "models": "/v1/models",
    }


@app.get("/health", tags=["health"])
async def health_check():
    """
    健康检查
    """
    if not health_monitor:
        return {"status": "unknown", "message": "健康监控未初始化"}

    return health_monitor.get_aggregated_status()


@app.get("/status", tags=["health"])
async def status_detail():
    """
    详细状态（含子服务和队列）
    """
    status = {}

    # 服务健康状态
    if health_monitor:
        status["services"] = health_monitor.get_aggregated_status()

    # 队列状态
    if queue_manager:
        status["queue"] = queue_manager.get_status()

    return status


@app.get("/v1/models", tags=["models"])
async def list_models():
    """
    列出所有可用模型
    """
    models = []

    # 从各服务获取模型列表
    services = []
    for get_svc in [get_embedding_service, get_reranker_service, get_asr_service, get_mineru_service, get_memory_service]:
        try:
            services.append(get_svc())
        except RuntimeError:
            pass

    for svc in services:
        try:
            svc_models = await svc.get_models()
            models.extend(svc_models)
        except Exception as e:
            logger.warning(f"获取 {svc.__class__.__name__} 模型列表失败：{e}")

    return {
        "object": "list",
        "data": models,
    }


# ============ 注册各服务路由 ============

def register_services():
    """注册各子服务的路由"""
    services = []
    for name, get_svc in [
        ("embedding", get_embedding_service),
        ("reranker", get_reranker_service),
        ("asr", get_asr_service),
        ("mineru", get_mineru_service),
        ("memory", get_memory_service),
    ]:
        try:
            services.append((name, get_svc()))
        except RuntimeError:
            logger.warning(f"{name} 服务未初始化")

    for name, svc in services:
        app.include_router(svc.router)
        health_monitor.register_service(name, svc.health_check)
        logger.info(f"注册 {name} 服务路由")


# ============ 异常处理 ============

@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP 异常处理"""
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.detail},
    )


@app.exception_handler(QueueFullError)
async def queue_full_exception_handler(request: Request, exc: QueueFullError):
    """队列满异常处理"""
    return JSONResponse(
        status_code=503,
        content=exc.to_dict(),
    )


@app.exception_handler(ServiceUnavailableError)
async def service_unavailable_exception_handler(request: Request, exc: ServiceUnavailableError):
    """服务不可用异常处理"""
    return JSONResponse(
        status_code=503,
        content=exc.to_dict(),
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """通用异常处理"""
    logger.error(f"未处理异常：{exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"error": "Internal server error", "message": str(exc)},
    )


# ============ 初始化 ============

def initialize_services(cfg: ConfigManager):
    """初始化各服务"""
    global config_manager, queue_manager, health_monitor

    config_manager = cfg

    # 初始化队列管理器
    queue_configs = {}
    for service_name in ["embedding", "reranker", "asr", "mineru"]:
        svc_cfg = cfg.get_service_config(service_name)
        if svc_cfg and svc_cfg.enabled:
            queue_cfg = cfg.get_queue_config(service_name)
            queue_configs[service_name] = ServiceQueueConfig(
                max_concurrent=queue_cfg.max_concurrent,
                max_size=queue_cfg.max_size,
                timeout_seconds=queue_cfg.timeout_seconds,
            )

    queue_manager = init_queue_manager(queue_configs)

    # 初始化健康监控器
    hc_cfg = cfg.config.health_check
    health_monitor = init_health_monitor(
        check_interval=hc_cfg.interval_seconds,
        timeout=hc_cfg.timeout_seconds,
        unhealthy_threshold=hc_cfg.unhealthy_threshold,
    )

    # 初始化各服务
    if cfg.get_service_config("embedding"):
        init_embedding_service(cfg.get_service_config("embedding"))

    if cfg.get_service_config("reranker"):
        init_reranker_service(cfg.get_service_config("reranker"))

    if cfg.get_service_config("asr"):
        init_asr_service(cfg.get_service_config("asr"))

    if cfg.get_service_config("mineru"):
        init_mineru_service(cfg.get_service_config("mineru"))

    if cfg.get_service_config("memory"):
        init_memory_service(cfg.get_service_config("memory"))

    # 注册服务路由
    register_services()
