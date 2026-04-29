"""
服务模块 - 各子服务的 Client+Router 实现

每个服务模块导出:
- 一个 Service 类 (包含 HTTP 客户端和路由)
- 一个 init_xxx_service() 初始化函数
- 一个 get_xxx_service() 获取函数
"""

from .embedding import EmbeddingService, init_embedding_service, get_embedding_service
from .reranker import RerankerService, init_reranker_service, get_reranker_service
from .asr import ASRService, init_asr_service, get_asr_service
from .mineru import MinerUService, init_mineru_service, get_mineru_service
from .memory import MemoryService, init_memory_service, get_memory_service

__all__ = [
    "EmbeddingService",
    "init_embedding_service",
    "get_embedding_service",
    "RerankerService",
    "init_reranker_service",
    "get_reranker_service",
    "ASRService",
    "init_asr_service",
    "get_asr_service",
    "MinerUService",
    "init_mineru_service",
    "get_mineru_service",
    "MemoryService",
    "init_memory_service",
    "get_memory_service",
]
