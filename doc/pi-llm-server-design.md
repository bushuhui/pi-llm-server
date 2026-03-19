# PI-LLM-Server 统一服务架构设计文档

## 1. 项目概述

### 1.1 背景

当前 LocalAI 目录下有 4 个独立的服务：
- **Embedding 服务** (端口 8091): 文本向量化，基于 SentenceTransformer + FastAPI
- **ASR 服务** (端口 8092): 语音识别，基于 vLLM + qwen-asr
- **Reranker 服务** (端口 8093): 文档相关性排序，基于 Transformers + FastAPI
- **MinerU 服务** (端口 8094): PDF 解析，基于 MinerU + FastAPI

每个服务独立运行，存在以下问题：
- 需要分别启动多个服务进程
- 无法统一管理配置和认证
- 没有统一的请求队列，无法控制并发
- 缺乏统一的状态和健康监控

### 1.2 目标

设计并实现一个统一的 LLM 服务网关 `pi-llm-server.py`，集成所有子服务，提供：
- **统一 API 入口**: 单个服务暴露所有功能
- **请求队列管理**: 顺序处理请求，避免资源竞争
- **OpenAI 兼容接口**: `/v1/models`, `/v1/chat/completions` 等
- **状态与健康监控**: 统一的健康检查和状态查询
- **集中配置管理**: 配置文件管理所有子服务参数
- **在线 API 文档**: FastAPI 自动生成的交互式文档

---

## 2. 架构设计

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                      Client Requests                            │
│                    (HTTP / OpenAI SDK)                          │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     PI-LLM-Server (FastAPI)                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              API Gateway / Router                        │   │
│  │  - /v1/models      - /v1/embeddings                      │   │
│  │  - /v1/rerank        - /v1/audio/transcriptions          │   │
│  │  - /v1/chat/completions  - /v1/ocr/parser                │   │
│  │  - /health           - /status                           │   │
│  └─────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Request Queue Manager                       │   │
│  │  - FIFO 队列，顺序处理请求                               │   │
│  │  - 支持优先级（可选）                                    │   │
│  │  - 限制并发数（保护 GPU 显存）                             │   │
│  └─────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Sub-Service Proxy Layer                     │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐   │   │
│  │  │Embedding │ │   ASR    │ │ Reranker │ │  MinerU  │   │   │
│  │  │  Client  │ │  Client  │ │  Client  │ │  Client  │   │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘   │   │
│  └─────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Config & Auth Manager                       │   │
│  │  - YAML 配置文件加载                                     │   │
│  │  - Token 认证管理                                        │   │
│  │  - 服务启动脚本管理                                      │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
          ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ Embedding Server│ │    ASR Server   │ │ Reranker Server │
│   (127.0.0.1:   │ │   (127.0.0.1:   │ │   (127.0.0.1:   │
│      8091)      │ │      8092)      │ │      8093)      │
└─────────────────┘ └─────────────────┘ └─────────────────┘
          │                   │                   │
          └───────────────────┼───────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  MinerU Server  │
                    │  (127.0.0.1:    │
                    │      8094)      │
                    └─────────────────┘
```

### 2.2 核心组件说明

| 组件 | 职责 | 实现方式 |
|------|------|----------|
| **API Gateway** | 路由分发、参数校验、响应格式化 | FastAPI Router + Pydantic |
| **Request Queue** | 请求排队、顺序执行、超时控制 | `asyncio.Queue` + 信号量 |
| **Sub-Service Proxy** | 调用子服务 HTTP API、错误重试、超时 | `httpx.AsyncClient` |
| **Config Manager** | 配置加载、热更新、默认值 | PyYAML + Pydantic Settings |
| **Auth Manager** | Token 验证、权限控制 | HTTP Bearer Token + 中间件 |
| **Health Monitor** | 子服务健康检查、状态聚合 | 定期轮询 + 缓存 |

---

## 3. API 设计

### 3.1 统一服务端口

| 服务 | 统一端口 | 原端口 | 说明 |
|------|----------|--------|------|
| PI-LLM-Server | **8090** | - | 统一入口 |
| └─ Embedding | - | 8091 | 子服务内部调用 |
| └─ ASR | - | 8092 | 子服务内部调用 |
| └─ Reranker | - | 8093 | 子服务内部调用 |
| └─ MinerU | - | 8094 | 子服务内部调用 |

### 3.2 API 端点设计

#### 3.2.1 通用端点

| 端点 | 方法 | 说明 | 认证 |
|------|------|------|------|
| `/health` | GET | 健康检查 | 否 |
| `/status` | GET | 详细状态（含子服务） | 是 |
| `/v1/models` | GET | 列出所有可用模型 | 可选 |
| `/docs` | GET | Swagger UI 文档 | 否 |
| `/redoc` | GET | ReDoc 文档 | 否 |

#### 3.2.2 Embedding 端点

| 端点 | 方法 | 说明 | 请求体 | 响应 |
|------|------|------|--------|------|
| `/v1/embeddings` | POST | 生成 embedding | `{"input": str\|list, "model": str}` | OpenAI 兼容格式 |
| `/v1/similarity` | POST | 计算相似度 | `{"text1": str, "text2": str}` | `{"similarity": float}` |

#### 3.2.3 Reranker 端点

| 端点 | 方法 | 说明 | 请求体 | 响应 |
|------|------|------|--------|------|
| `/v1/rerank` | POST | 文档重排序 | `{"query": str, "documents": list, "top_n": int}` | OpenAI 兼容格式 |

#### 3.2.4 ASR 端点

| 端点 | 方法 | 说明 | 请求体 | 响应 |
|------|------|------|--------|------|
| `/v1/audio/transcriptions` | POST | 语音转文字 (form-data) | `file: audio, model: str` | `{"text": str}` |
| `/v1/chat/completions` | POST | 语音识别 (audio_url) | OpenAI chat 格式 | OpenAI 兼容格式 |

#### 3.2.5 MinerU 端点

| 端点 | 方法 | 说明 | 请求体 | 响应 |
|------|------|------|--------|------|
| `/v1/ocr/parser` | POST | PDF/OCR 解析 | form-data: PDF 文件 + 参数 | ZIP 文件 |

### 3.3 请求/响应示例

#### `/v1/models` 响应

```json
{
  "object": "list",
  "data": [
    {
      "id": "unsloth/Qwen3-Embedding-0.6B",
      "object": "model",
      "owned_by": "local",
      "service": "embedding",
      "status": "healthy"
    },
    {
      "id": "Qwen/Qwen3-ASR-1.7B",
      "object": "model",
      "owned_by": "local",
      "service": "asr",
      "status": "healthy"
    },
    {
      "id": "Qwen/Qwen3-Reranker-0.6B",
      "object": "model",
      "owned_by": "local",
      "service": "reranker",
      "status": "healthy"
    },
    {
      "id": "mineru/pipeline",
      "object": "model",
      "owned_by": "local",
      "service": "mineru",
      "status": "healthy"
    }
  ]
}
```

#### `/health` 响应

```json
{
  "status": "healthy",
  "timestamp": "2026-03-16T10:30:00Z",
  "services": {
    "embedding": {"status": "healthy", "latency_ms": 15},
    "asr": {"status": "healthy", "latency_ms": 50},
    "reranker": {"status": "healthy", "latency_ms": 20},
    "mineru": {"status": "healthy", "latency_ms": 100}
  },
  "queue": {
    "pending": 0,
    "processing": 0
  }
}
```

---

## 4. 配置文件设计

### 4.1 配置文件结构 (config.yaml)

```yaml
# PI-LLM-Server 配置文件

# 服务基础配置
server:
  host: "0.0.0.0"
  port: 8090
  workers: 4
  log_level: "info"

# API 访问控制
auth:
  enabled: true
  tokens:
    - "sk-embedding-token-001"
    - "sk-asr-token-001"
    - "sk-reranker-token-001"
    - "sk-mineru-token-001"
    - "sk-admin-token-001"  # 管理员 token（可访问所有端点）


# 请求队列配置
queue:
  enabled: true
  # 全局默认配置
  default:
    max_size: 100
    max_concurrent: 1
    timeout_seconds: 300
  # 按服务类型差异化配置
  services:
    embedding:
      max_concurrent: 4      # CPU 多核并行，可同时处理多个请求
      max_size: 200
      timeout_seconds: 60
    reranker:
      max_concurrent: 4      # CPU 多核并行
      max_size: 200
      timeout_seconds: 120
    asr:
      max_concurrent: 1      # GPU 推理，顺序处理避免显存溢出
      max_size: 50
      timeout_seconds: 600
    mineru:
      max_concurrent: 1      # PDF 解析耗时，顺序处理
      max_size: 20
      timeout_seconds: 1800

# 子服务配置
services:
  embedding:
    enabled: true
    base_url: "http://127.0.0.1:8091"
    timeout_seconds: 60
    max_retries: 3
    models:
      - id: "unsloth/Qwen3-Embedding-0.6B"
        path: "/home/bushuhui/.cache/modelscope/hub/models/unsloth/Qwen3-Embedding-0.6B"
        device: "cpu"
        launch_script: "python embedding_server.py --model-path {path} --device {device}"
        python_path: "/home/tiger/anaconda3/envs/vllm/bin/python"

  asr:
    enabled: true
    base_url: "http://127.0.0.1:8092"
    timeout_seconds: 300
    max_retries: 2
    models:
      - id: "Qwen/Qwen3-ASR-1.7B"
        path: "/home/bushuhui/.cache/modelscope/hub/models/Qwen/Qwen3-ASR-1.7B"
        gpu_memory_utilization: 0.45
        max_model_len: 32768
        launch_script: "python asr_server.py --model-path {path} --gpu-memory-utilization {gpu_memory_utilization}"
        python_path: "/home/tiger/anaconda3/envs/vllm/bin/python"

  reranker:
    enabled: true
    base_url: "http://127.0.0.1:8093"
    timeout_seconds: 120
    max_retries: 3
    models:
      - id: "Qwen/Qwen3-Reranker-0.6B"
        path: "/home/bushuhui/.cache/modelscope/hub/models/Qwen/Qwen3-Reranker-0.6B"
        device: "cpu"
        launch_script: "python reranker_server.py --model-path {path} --device {device}"
        python_path: "/home/tiger/anaconda3/envs/vllm/bin/python"

  mineru:
    enabled: true
    base_url: "http://127.0.0.1:8094"
    timeout_seconds: 600
    max_retries: 1
    launch_script: "./mineru_server.sh start"
    working_directory: "/home/bushuhui/.conda/envs/mineru"
    python_path: "/home/tiger/anaconda3/envs/mineru/bin/python"
    # 传递到 MinerU 的参数
    config:
      vram: "9000"
      model_source: "modelscope"

# 健康检查配置
health_check:
  enabled: true
  interval_seconds: 30    # 轮询间隔
  timeout_seconds: 10     # 单次检查超时
  unhealthy_threshold: 3  # 连续失败次数判定为不健康
```

---

## 5. 核心模块设计

### 5.1 项目目录结构

```
LocalAI/
├── pi-llm-server.py          # 主服务程序
├── pi_llm_server/
│   ├── __init__.py
│   ├── config.py             # 配置管理
│   ├── auth.py               # 认证管理
│   ├── queue_manager.py      # 队列管理
│   ├── health_monitor.py     # 健康监控
│   ├── services/             # 各服务实现（Client+Router 合并）
│   │   ├── __init__.py
│   │   ├── base.py           # 服务基类（可选）
│   │   ├── embedding.py      # Embedding 服务
│   │   ├── asr.py            # ASR 服务
│   │   ├── reranker.py       # Reranker 服务
│   │   └── mineru.py         # MinerU 服务
│   └── utils/
│       ├── __init__.py
│       ├── logging.py
│       └── exceptions.py
├── logs/                     # 日志目录
├── examples/                 # 示例目录
│   └── config.example.yaml   # 配置示例
└── pi-llm-server.service     # systemd 服务配置（可选）
```

**设计说明**：
- `services/` 目录将每个服务的 **HTTP 客户端** 和 **FastAPI 路由** 合并在一起，提高内聚性
- 每个服务文件导出一个 `router` 实例和 `init_xxx_service()` 初始化函数
- 主程序只需导入并注册各服务的 router 即可

### 5.2 核心类设计

#### 5.2.1 服务基类 (可选)

```python
from abc import ABC, abstractmethod
from fastapi import APIRouter

class BaseService(ABC):
    """服务基类"""

    def __init__(self, base_url: str, timeout: int, max_retries: int):
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.client = httpx.AsyncClient(base_url=base_url, timeout=timeout)
        self.router = APIRouter()

    @abstractmethod
    async def health_check(self) -> bool:
        """健康检查"""
        pass

    @abstractmethod
    def register_routes(self):
        """注册路由"""
        pass
```

#### 5.2.2 Embedding 服务示例

```python
from pydantic import BaseModel
from typing import Union, List

class EmbeddingService:
    """Embedding 服务（Client + Router）"""

    def __init__(self, base_url: str, timeout: int, max_retries: int):
        self.base_url = base_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.client = httpx.AsyncClient(base_url=base_url, timeout=timeout)
        self.router = APIRouter(prefix="/v1/embeddings", tags=["embedding"])
        self._register_routes()

    async def create_embeddings(self, input_text: Union[str, List[str]]) -> dict:
        """调用 embedding 服务生成向量"""
        for attempt in range(self.max_retries):
            try:
                response = await self.client.post("/v1/embeddings", json={"input": input_text})
                response.raise_for_status()
                return response.json()
            except Exception as e:
                if attempt == self.max_retries - 1:
                    raise
        return None

    async def calculate_similarity(self, text1: str, text2: str) -> float:
        """计算文本相似度"""
        response = await self.client.post("/v1/similarity", json={"text1": text1, "text2": text2})
        response.raise_for_status()
        return response.json()["similarity"]

    async def health_check(self) -> bool:
        """健康检查"""
        try:
            response = await self.client.get("/health", timeout=5)
            return response.status_code == 200
        except:
            return False

    def _register_routes(self):
        """注册 FastAPI 路由"""
        @self.router.post("")
        async def embeddings_endpoint(request: EmbeddingRequest):
            return await self.create_embeddings(request.input)

        @self.router.post("/similarity")
        async def similarity_endpoint(request: SimilarityRequest):
            score = await self.calculate_similarity(request.text1, request.text2)
            return {"similarity": score}

# 全局实例
embedding_service: EmbeddingService = None

def init_embedding_service(config: ServiceConfig) -> EmbeddingService:
    """初始化 Embedding 服务"""
    global embedding_service
    embedding_service = EmbeddingService(
        base_url=config.base_url,
        timeout=config.timeout_seconds,
        max_retries=config.max_retries
    )
    return embedding_service
```

#### 5.2.3 ConfigManager

```python
class ServiceConfig(BaseModel):
    enabled: bool
    base_url: str
    timeout_seconds: int
    max_retries: int
    models: List[ModelConfig]
    launch_script: str
    python_path: str

class ConfigManager:
    def __init__(self, config_path: str):
        self.config_path = config_path
        self.config: Config = self._load_config()

    def get_service_config(self, service_name: str) -> ServiceConfig:
        """获取指定服务的配置"""

    def get_auth_tokens(self) -> List[str]:
        """获取所有有效 token"""

    def validate_token(self, token: str, endpoint: str) -> bool:
        """验证 token 是否有权访问指定端点"""
```

#### 5.2.4 QueueManager

```python
class QueueManager:
    def __init__(self, max_size: int, max_concurrent: int, timeout: int):
        self.queue = asyncio.Queue(maxsize=max_size)
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.timeout = timeout
        self.processing_count = 0
        self.pending_count = 0

    async def acquire(self) -> bool:
        """获取处理权限，如果队列满则拒绝"""

    async def release(self):
        """释放处理权限"""

    async def process_with_queue(self, func: Callable, *args) -> Any:
        """在队列中执行函数"""

    def get_status(self) -> dict:
        """获取队列状态"""
```

#### 5.2.5 HealthMonitor

```python
class HealthMonitor:
    def __init__(self, config: Config):
        self.services_status = {}
        self.check_interval = config.health_check.interval_seconds

    async def start_background_check(self):
        """后台定期健康检查"""

    async def check_service(self, service_name: str, base_url: str) -> ServiceStatus:
        """检查单个服务健康状态"""

    def get_aggregated_status(self) -> dict:
        """获取聚合状态"""
```

### 5.3 请求处理流程

```
1. 客户端发送请求 → FastAPI 入口
2. Auth 中间件验证 Token → 无效则返回 401
3. QueueManager 获取权限 → 队列满则返回 503
4. Router 路由到对应 Service（services/embedding.py 等）
5. Service 内部调用子服务 HTTP API
6. 子服务处理完成后返回结果
7. QueueManager 释放权限，处理下一个请求
8. 返回结果给客户端
```

### 5.4 主程序注册示例

```python
from fastapi import FastAPI
from pi_llm_server.config import init_config
from pi_llm_server.auth import auth_middleware
from pi_llm_server.queue_manager import QueueManager
from pi_llm_server.health_monitor import HealthMonitor
from pi_llm_server.services import embedding, asr, reranker, mineru

app = FastAPI(title="PI-LLM Server")

# 加载配置
config = init_config("config.yaml")

# 注册认证中间件
app.add_middleware("http")(auth_middleware)

# 初始化队列管理器
queue_manager = QueueManager(
    max_size=config.queue.max_size,
    max_concurrent=config.queue.max_concurrent,
    timeout=config.queue.timeout_seconds
)

# 初始化健康监控
health_monitor = HealthMonitor(config)

# 初始化并注册各服务路由
embedding.init_embedding_service(config.services.embedding)
app.include_router(embedding.embedding_service.router)

asr.init_asr_service(config.services.asr)
app.include_router(asr.asr_service.router, prefix="/v1/audio")

reranker.init_reranker_service(config.services.reranker)
app.include_router(reranker.reranker_service.router, prefix="/v1/rerank")

mineru.init_mineru_service(config.services.mineru)
app.include_router(mineru.mineru_service.router, prefix="/v1/ocr")

# 注册通用路由
@app.get("/health")
async def health_endpoint():
    return health_monitor.get_aggregated_status()

@app.get("/status")
async def status_endpoint():
    return {
        "services": health_monitor.get_aggregated_status(),
        "queue": queue_manager.get_status()
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=config.server.host, port=config.server.port)
```

### 5.5 错误处理策略

| 错误类型 | HTTP 状态码 | 响应格式 |
|----------|------------|----------|
| Token 无效/缺失 | 401 | `{"error": "Unauthorized"}` |
| Token 无权限 | 403 | `{"error": "Forbidden"}` |
| 队列满 | 503 | `{"error": "Service busy, please try again later"}` |
| 子服务不健康 | 503 | `{"error": "Service unavailable", "service": "xxx"}` |
| 子服务超时 | 504 | `{"error": "Gateway timeout"}` |
| 参数校验失败 | 400 | `{"error": "Bad request", "detail": "..."}` |
| 服务器内部错误 | 500 | `{"error": "Internal server error"}` |

---

## 6. 认证与授权设计

### 6.1 认证方式

采用 **Bearer Token** 认证：
```
Authorization: Bearer sk-your-token-here
```

### 6.2 Token 类型

| Token 类型 | 权限范围 | 使用场景 |
|------------|----------|----------|
| **Embedding Token** | 仅访问 `/v1/embeddings`, `/v1/similarity` | Embedding 客户端 |
| **ASR Token** | 仅访问 `/v1/audio/*`, `/v1/chat/completions` | ASR 客户端 |
| **Reranker Token** | 仅访问 `/v1/rerank` | Reranker 客户端 |
| **MinerU Token** | 仅访问 `/v1/ocr/parser` | MinerU 客户端 |
| **Admin Token** | 访问所有端点 | 管理工具、监控 |

### 6.3 认证流程

```python
@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    # 白名单：无需认证的路径
    public_paths = ["/health", "/docs", "/redoc", "/openapi.json"]
    if request.url.path in public_paths:
        return await call_next(request)

    # 获取 Token
    auth_header = request.headers.get("Authorization")
    if not auth_header or not auth_header.startswith("Bearer "):
        return JSONResponse({"error": "Missing or invalid Authorization header"}, status_code=401)

    token = auth_header[7:]  # 移除 "Bearer " 前缀

    # 验证 Token
    if not config_manager.validate_token(token, request.url.path):
        return JSONResponse({"error": "Invalid token"}, status_code=401)

    return await call_next(request)
```

---

## 7. 部署方案

### 7.1 手动启动

```bash
# 1. 确保子服务已启动
python embedding_server.py &
python asr_server.py &
python reranker_server.py &
./mineru_server.sh start &

# 2. 启动统一服务
python pi-llm-server.py

# 或直接使用配置文件启动
python pi-llm-server.py --config config.yaml
```

### 7.2 Systemd 服务

```ini
# /etc/systemd/system/pi-llm-server.service
[Unit]
Description=PI-LLM Unified Server
After=network.target

[Service]
Type=simple
User=pi-lab
WorkingDirectory=/mnt/data0/home/bushuhui_data/msdk/pi-lab/0_demo_codes/code_cook/0_machine_learning_AI/LLM_API/LocalAI
ExecStart=/home/tiger/anaconda3/envs/vllm/bin/python pi-llm-server.py --config config.yaml
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
```

### 7.3 启动脚本

```bash
#!/bin/bash
# start-all-services.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGS_DIR="${SCRIPT_DIR}/logs"

echo "Starting Embedding Server..."
python "${SCRIPT_DIR}/embedding_server.py" > "${LOGS_DIR}/embedding.log" 2>&1 &

echo "Starting ASR Server..."
python "${SCRIPT_DIR}/asr_server.py" > "${LOGS_DIR}/asr.log" 2>&1 &

echo "Starting Reranker Server..."
python "${SCRIPT_DIR}/reranker_server.py" > "${LOGS_DIR}/reranker.log" 2>&1 &

echo "Starting MinerU Server..."
"${SCRIPT_DIR}/mineru_server.sh" start

sleep 5

echo "Starting PI-LLM Unified Server..."
python "${SCRIPT_DIR}/pi-llm-server.py" > "${LOGS_DIR}/pi-llm-server.log" 2>&1 &

echo "All services started!"
```

---

## 8. 技术栈选型

| 组件 | 技术选型 | 理由 |
|------|----------|------|
| **Web 框架** | FastAPI | 异步支持、自动生成文档、性能好 |
| **HTTP 客户端** | httpx | 异步、支持连接池、超时控制 |
| **配置管理** | PyYAML + Pydantic | 类型安全、验证方便 |
| **队列管理** | asyncio.Queue | 原生异步支持 |
| **认证** | Bearer Token + 中间件 | 简单、与 OpenAI 兼容 |
| **日志** | logging + 结构化日志 | 便于排查问题 |
| **进程管理** | systemd / supervisord | 生产环境稳定性 |

---

## 9. 性能考虑

### 9.1 并发控制

- **队列最大并发数 = 1**: 顺序处理，确保 GPU 不会因多请求同时处理而显存溢出
- **可配置并发数**: 根据 GPU 显存大小调整（如 3090 可设置 2-3）

### 9.2 超时设置

| 服务 | 超时时间 | 说明 |
|------|----------|------|
| Embedding | 60s | 单条请求通常 <1s，批量可能较长 |
| ASR | 600s | 长音频可能需要较长时间 |
| Reranker | 120s | 批量文档重排序 |
| MinerU | 1800s | PDF 解析最耗时 |

### 9.3 连接池

使用 `httpx.AsyncClient` 的连接池复用连接：
```python
self.client = httpx.AsyncClient(
    base_url=base_url,
    timeout=timeout,
    limits=httpx.Limits(max_keepalive_connections=10, max_connections=20)
)
```

---

## 10. 安全考虑

1. **Token 管理**:
   - Token 不应硬编码在代码中
   - 配置文件设置权限 `600`
   - 支持从环境变量读取

2. **输入校验**:
   - 文件上传限制大小（MinerU）
   - 音频文件类型校验（ASR）
   - PDF 文件魔数校验（MinerU）

3. **日志脱敏**:
   - 不记录完整 Token
   - 敏感信息打码

4. **速率限制** (可选):
   - 使用 `slowapi` 实现基于 IP 的限流

---

## 11. 监控与可观测性

### 11.1 监控指标

- 请求总数 / 成功数 / 失败数
- 平均响应时间 (P50, P95, P99)
- 队列长度 / 等待时间
- 子服务健康状态

### 11.2 日志格式

```json
{
  "timestamp": "2026-03-16T10:30:00.123Z",
  "level": "INFO",
  "service": "pi-llm-server",
  "endpoint": "/v1/embeddings",
  "method": "POST",
  "status": 200,
  "latency_ms": 45,
  "client_ip": "192.168.1.100",
  "model": "unsloth/Qwen3-Embedding-0.6B",
  "queue_wait_ms": 10
}
```

---

## 12. 开发计划

### 阶段 1: 核心框架 (优先级最高)
- [ ] 项目结构搭建
- [ ] 配置管理模块
- [ ] 认证中间件
- [ ] 队列管理器
- [ ] 基础路由框架

### 阶段 2: 服务集成
- [ ] Embedding 客户端 + 路由
- [ ] Reranker 客户端 + 路由
- [ ] ASR 客户端 + 路由
- [ ] MinerU 客户端 + 路由

### 阶段 3: 监控与运维
- [ ] 健康监控模块
- [ ] 结构化日志
- [ ] 状态聚合 API
- [ ] Systemd 服务配置

### 阶段 4: 优化与扩展
- [ ] 性能基准测试
- [ ] 连接池优化
- [ ] 错误重试优化
- [ ] 速率限制（可选）

---

## 13. 参考资源

1. **FastAPI 官方文档**: https://fastapi.tiangolo.com/
2. **OpenAI API 参考**: https://platform.openai.com/docs/api-reference
3. **httpx 文档**: https://www.python-httpx.org/
4. **LocalAI 项目**: https://github.com/mudler/LocalAI (参考其架构设计)

---

## 14. 附录

### 14.1 现有服务 API 对比

| 功能 | Embedding | ASR | Reranker | MinerU |
|------|-----------|-----|----------|--------|
| 当前端口 | 8091 | 8092 | 8093 | 8094 |
| 基础框架 | FastAPI | vLLM | FastAPI | FastAPI |
| 健康检查 | `/health` | `/health` | `/health` | N/A |
| 模型列表 | `/v1/models` | `/v1/models` | `/v1/models` | N/A |
| 主端点 | `/v1/embeddings` | `/v1/audio/transcriptions` | `/v1/rerank` | `/v1/ocr/parser` |
| 认证方式 | 无 | 无 | 无 | 无 |
| 在线文档 | `/docs` | N/A | `/docs` | `/docs` |

### 14.2 配置项快速参考

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `server.port` | 8090 | 统一服务端口 |
| `auth.enabled` | true | 启用认证 |
| `queue.max_concurrent` | 1 | 最大并发处理数 |
| `queue.timeout_seconds` | 300 | 请求超时 |
| `health_check.interval_seconds` | 30 | 健康检查间隔 |

---

**文档版本**: 1.0
**创建日期**: 2026-03-16
**作者**: PI-Lab Team
**最后更新**: 2026-03-16
