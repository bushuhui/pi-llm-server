# PI-LLM-Server 架构文档

> 统一 LLM 服务网关 - 集成 Embedding、ASR、Reranker、MinerU 服务

**版本**: 1.1.5
**创建日期**: 2026-04-08
**最后更新**: 2026-04-08

---

## 1. 项目概述

### 1.1 项目定位

PI-LLM-Server 是一个**统一 LLM 服务网关**，为 OpenClaw、Claude Code 等 AI 编程助手提供本地化的 Embedding、ASR、Reranker、OCR 等服务。

### 1.2 解决的问题

| 问题 | 描述 |
|------|------|
| **服务碎片化** | Embedding、ASR、Reranker、OCR 等服务分散部署，管理复杂 |
| **API 不统一** | 各服务接口风格不一致，集成成本高 |
| **缺少队列管理** | 并发请求可能导致显存溢出或服务崩溃 |
| **缺乏健康监控** | 服务异常时无法自动发现和恢复 |

### 1.3 核心价值

- 统一管理多个 AI 子服务，提供一致的服务入口
- 配置请求队列，防止并发过载
- 启用 API 访问控制，保护服务安全
- 实时监控服务健康状态

---

## 2. 系统架构

### 2.1 整体架构图

```
┌─────────────────────────────────────────────────────────────────┐
│                      Client Requests                            │
│            (OpenClaw, Claude Code, HTTP SDK)                    │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PI-LLM-Server Gateway (8090)                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              FastAPI Application                        │   │
│  │  ┌───────────────────────────────────────────────────┐  │   │
│  │  │              Auth Middleware                       │  │   │
│  │  │  - Bearer Token 验证                               │  │   │
│  │  │  - 路径白名单 (/health, /docs)                     │  │   │
│  │  └───────────────────────────────────────────────────┘  │   │
│  │  ┌───────────────────────────────────────────────────┐  │   │
│  │  │              Queue Manager                         │  │   │
│  │  │  - 差异化并发策略 (CPU 多核/GPU 顺序)               │  │   │
│  │  │  - 请求超时控制                                    │  │   │
│  │  └───────────────────────────────────────────────────┘  │   │
│  │  ┌───────────────────────────────────────────────────┐  │   │
│  │  │              Health Monitor                        │  │   │
│  │  │  - 后台轮询健康检查                                │  │   │
│  │  │  - 状态聚合                                        │  │   │
│  │  └───────────────────────────────────────────────────┘  │   │
│  └─────────────────────────────────────────────────────────┘   │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │              Service Routers                            │   │
│  │  ┌──────────┐ ┌──────────┐ ┌──────────┐ ┌──────────┐  │   │
│  │  │Embedding │ │   ASR    │ │ Reranker │ │  MinerU  │  │   │
│  │  │ Router   │ │  Router  │ │  Router  │ │  Router  │  │   │
│  │  └──────────┘ └──────────┘ └──────────┘ └──────────┘  │   │
│  └─────────────────────────────────────────────────────────┘   │
└─────────────────────────────────────────────────────────────────┘
                              │
          ┌───────────────────┼───────────────────┐
          │                   │                   │
          ▼                   ▼                   ▼
┌─────────────────┐ ┌─────────────────┐ ┌─────────────────┐
│ Embedding Server│ │    ASR Server   │ │ Reranker Server │
│   127.0.0.1:8091│ │   127.0.0.1:8092│ │   127.0.0.1:8093│
│  (SentenceTrans)│ │    (vLLM+Qwen)  │ │  (Transformers) │
└─────────────────┘ └─────────────────┘ └─────────────────┘
          │                   │                   │
          └───────────────────┼───────────────────┘
                              │
                              ▼
                    ┌─────────────────┐
                    │  MinerU Server  │
                    │  127.0.0.1:8094 │
                    │   (PDF Parser)  │
                    └─────────────────┘
```

### 2.2 端口分配

| 服务 | 端口 | 协议 | 说明 |
|------|------|------|------|
| **统一网关** | 8090 | HTTP | 主入口，所有外部请求 |
| Embedding 子服务 | 8091 | HTTP | 内部调用，文本向量化 |
| ASR 子服务 | 8092 | HTTP | 内部调用，语音识别 |
| Reranker 子服务 | 8093 | HTTP | 内部调用，文档重排序 |
| MinerU 子服务 | 8094 | HTTP | 内部调用，PDF 解析 |

### 2.3 技术栈

| 组件 | 技术选型 | 说明 |
|------|----------|------|
| **Web 框架** | FastAPI | 异步支持、自动生成 OpenAPI 文档 |
| **HTTP 客户端** | httpx | 异步、连接池、超时控制 |
| **配置管理** | PyYAML + Pydantic | 类型安全、配置验证 |
| **队列管理** | asyncio.Queue + Semaphore | 异步队列、并发控制 |
| **认证** | Bearer Token 中间件 | 简单、与 OpenAI 兼容 |
| **子服务框架** | FastAPI / vLLM | Embedding/Reranker/MinerU 用 FastAPI，ASR 用 vLLM |

---

## 3. 模块设计

### 3.1 模块关系图

```
pi_llm_server/
├── __main__.py              # 入口：python -m pi_llm_server
├── cli.py                   # 命令行工具（一站式启动）
│   └── 调用 server.py 和 service_manager.py
│
├── server.py                # FastAPI 应用核心 ⭐
│   ├── 初始化 ConfigManager
│   ├── 初始化 QueueManager
│   ├── 初始化 HealthMonitor
│   ├── 初始化各服务 (Embedding/ASR/Reranker/MinerU)
│   └── 注册路由和中间件
│
├── config.py                # 配置管理
│   ├── ConfigManager        # 配置加载器
│   ├── Config               # 配置对象 (Pydantic)
│   └── 服务配置解析
│
├── auth.py                  # 认证管理
│   ├── AuthManager          # 认证管理器
│   └── Bearer Token 验证
│
├── queue_manager.py         # 队列管理
│   ├── QueueManager         # 队列管理器
│   ├── ServiceQueue         # 单个服务队列
│   └── 并发控制 (Semaphore)
│
├── health_monitor.py        # 健康监控
│   ├── HealthMonitor        # 健康监控器
│   ├── ServiceStatus        # 服务状态
│   └── 后台轮询检查
│
├── services/                # 服务代理层（网关内部）
│   ├── embedding.py         # Embedding 服务代理
│   ├── asr.py               # ASR 服务代理
│   ├── reranker.py          # Reranker 服务代理
│   └── mineru.py            # MinerU 服务代理
│   (每个服务包含：HTTP 客户端 + 路由注册 + 健康检查)
│
├── clients/                 # 客户端（备用/独立使用）
│   ├── embedding_client.py
│   ├── asr_client.py
│   ├── reranker_client.py
│   └── mineru_client.py
│
└── launcher/                # 子服务启动器
    ├── embedding_server.py  # Embedding 子服务（独立进程）
    ├── asr_server.py        # ASR 子服务（独立进程）
    ├── reranker_server.py   # Reranker 子服务（独立进程）
    ├── mineru_server.sh     # MinerU 子服务（Shell 脚本）
    └── service_manager.py   # 服务管理工具（启动/停止/状态）
```

### 3.2 核心模块职责

#### 3.2.1 ConfigManager (配置管理)

**文件**: `config.py`

**职责**:
- 加载 YAML 配置文件
- 验证配置项（使用 Pydantic）
- 提供类型安全的配置访问接口
- 支持路径展开（`~` 和环境变量）

**关键类**:
```python
class ConfigManager:
    def __init__(self, config_path: str)
    def get_service_config(service_name: str) -> ServiceConfig
    def get_queue_config(service_name: str) -> ServiceQueueConfig
    def validate_token(token: str, endpoint: str) -> bool
```

**配置结构**:
```yaml
server:
  host: "0.0.0.0"
  port: 8090
  workers: 4

auth:
  enabled: true
  tokens: ["sk-xxx"]

queue:
  enabled: true
  default: { max_concurrent: 1, max_size: 100, timeout_seconds: 300 }
  services:
    embedding: { max_concurrent: 1, ... }
    reranker: { max_concurrent: 4, ... }

services:
  embedding: { enabled: true, base_url: "http://127.0.0.1:8091", ... }
  asr: { ... }
  reranker: { ... }
  mineru: { ... }

health_check:
  enabled: true
  interval_seconds: 30
  unhealthy_threshold: 3
```

---

#### 3.2.2 AuthManager (认证管理)

**文件**: `auth.py`

**职责**:
- Bearer Token 验证
- 路径白名单管理
- 认证中间件实现

**关键类**:
```python
class AuthManager:
    PUBLIC_PATHS = {"/health", "/docs", "/redoc", "/openapi.json", "/"}
    
    def __init__(self, tokens: List[str], enabled: bool = True)
    def validate_token(self, token: str) -> bool
    async def __call__(self, request: Request, call_next)
```

**认证流程**:
```
1. 请求到达 → 检查是否在白名单
2. 白名单外 → 提取 Authorization header
3. 验证 token 是否在有效列表中
4. 无效 → 返回 401 Unauthorized
5. 有效 → 放行到下一个处理环节
```

---

#### 3.2.3 QueueManager (队列管理)

**文件**: `queue_manager.py`

**职责**:
- 请求排队和顺序执行
- 并发数控制（信号量）
- 超时控制
- 差异化策略（CPU 多核并行 / GPU 顺序处理）

**关键类**:
```python
class QueueManager:
    def __init__(self)
    def add_queue(service_name: str, config: ServiceQueueConfig)
    async def process_request(service_name: str, func: Callable, ...)

class ServiceQueue:
    def __init__(self, config: ServiceQueueConfig)
    async def process_with_queue(func: Callable, ...)
```

**差异化并发策略**:

| 服务 | 并发数 | 原因 |
|------|--------|------|
| Embedding | 1 | GPU 推理，顺序处理避免显存溢出 |
| Reranker | 4 | CPU 多核并行 |
| ASR | 1 | GPU 推理，顺序处理 |
| MinerU | 1 | PDF 解析耗时，顺序处理 |

**队列处理流程**:
```
1. acquire() → 获取信号量权限
2. 队列满 → 拒绝请求 (503)
3. 队列中等待 → 获取权限
4. 执行处理函数
5. release() → 释放权限
```

---

#### 3.2.4 HealthMonitor (健康监控)

**文件**: `health_monitor.py`

**职责**:
- 后台定期健康检查
- 服务状态聚合
- 连续失败判定

**关键类**:
```python
class HealthMonitor:
    def __init__(self, check_interval: int = 30, timeout: int = 10, ...)
    def register_service(name: str, health_check_func: callable)
    async def check_service(name: str) -> ServiceStatus
    async def start_background_check()
    def get_aggregated_status() -> dict
```

**健康检查流程**:
```
1. 启动后台任务 (asyncio.create_task)
2. 每隔 interval_seconds 轮询所有服务
3. 调用各服务的 health_check() 函数
4. 更新 ServiceStatus
5. 连续 unhealthy_threshold 次失败 → 标记为 unhealthy
```

---

#### 3.2.5 Services (服务代理层)

**目录**: `services/`

**职责**:
- HTTP 客户端（调用子服务）
- FastAPI 路由注册
- 健康检查函数
- 模型列表获取

**模块结构**:

| 模块 | 子服务端口 | API 端点 |
|------|-----------|---------|
| `embedding.py` | 8091 | `/v1/embeddings`, `/v1/similarity` |
| `asr.py` | 8092 | `/v1/audio/transcriptions`, `/v1/chat/completions` |
| `reranker.py` | 8093 | `/v1/rerank` |
| `mineru.py` | 8094 | `/v1/ocr/parser` |

**服务类结构** (以 Embedding 为例):
```python
class EmbeddingService:
    def __init__(self, config: ServiceConfig):
        self.client = httpx.AsyncClient(base_url=config.base_url)
        self.router = APIRouter(tags=["embedding"])
        self._register_routes()
    
    async def create_embeddings(input_text: str) -> dict
    async def calculate_similarity(text1: str, text2: str) -> float
    async def health_check() -> dict
    async def get_models() -> List[dict]
    async def close()
```

---

### 3.3 子服务启动器 (launcher/)

**目录**: `launcher/`

**职责**: 管理后台子服务进程（独立于网关）

**关键文件**:

| 文件 | 说明 |
|------|------|
| `embedding_server.py` | Embedding 子服务（SentenceTransformer + FastAPI） |
| `asr_server.py` | ASR 子服务（vLLM + Qwen-ASR） |
| `reranker_server.py` | Reranker 子服务（Transformers + FastAPI） |
| `mineru_server.sh` | MinerU 子服务（Shell 脚本封装） |
| `service_manager.py` | 服务管理工具（启动/停止/状态） |

**子服务特性**:
- 独立进程运行
- 各自监听不同端口
- 网关通过 HTTP 调用
- 支持空闲超时卸载模型（GPU 模式）

---

## 4. 请求处理流程

### 4.1 Embedding 请求流程

```
┌──────────┐     ┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│  Client  │     │   Gateway   │     │   Queue     │     │  Embedding  │
│          │     │  (8090)     │     │   Manager   │     │   Server    │
│          │     │             │     │             │     │   (8091)    │
└────┬─────┘     └──────┬──────┘     └──────┬──────┘     └──────┬──────┘
     │                  │                   │                   │
     │ POST /v1/embeddings                  │                   │
     │─────────────────>│                   │                   │
     │                  │ Auth Middleware   │                   │
     │                  │ (验证 Token)       │                   │
     │                  │                   │                   │
     │                  │ Queue.acquire()   │                   │
     │                  │──────────────────>│                   │
     │                  │                   │                   │
     │                  │ proxy.create_embeddings()             │
     │                  │──────────────────────────────────────>│
     │                  │                   │                   │
     │                  │                   │  HTTP POST        │
     │                  │                   │──────────────────>│
     │                  │                   │                   │
     │                  │                   │  HTTP Response    │
     │                  │<──────────────────────────────────────│
     │                  │                   │                   │
     │                  │ Queue.release()   │                   │
     │                  │<──────────────────│                   │
     │                  │                   │                   │
     │ Response         │                   │                   │
     │<─────────────────│                   │                   │
     │                  │                   │                   │
```

### 4.2 完整请求生命周期

```
1. 客户端发送 HTTP 请求到网关 (8090)
         │
         ▼
2. Auth Middleware 验证 Token
   - 白名单路径 (/health, /docs) → 跳过
   - 提取 Authorization header
   - 验证 token 有效性
   - 无效 → 返回 401
         │
         ▼
3. QueueManager 获取处理权限
   - acquire() → 信号量控制
   - 队列满 → 返回 503
   - 等待 → 顺序处理
         │
         ▼
4. Service 代理调用子服务
   - httpx.AsyncClient 发送 HTTP 请求
   - 子服务处理 (8091/8092/8093/8094)
   - 重试机制 (max_retries)
   - 超时控制 (timeout_seconds)
         │
         ▼
5. QueueManager 释放权限
   - release() → 信号量
   - 处理下一个请求
         │
         ▼
6. 返回响应给客户端
```

---

## 5. API 设计

### 5.1 端点列表

| 端点 | 方法 | 说明 | 认证 |
|------|------|------|------|
| `/` | GET | 欢迎信息 | 否 |
| `/health` | GET | 健康检查 | 否 |
| `/status` | GET | 详细状态 | 是 |
| `/v1/models` | GET | 可用模型列表 | 可选 |
| `/v1/embeddings` | POST | 生成 Embedding | 是 |
| `/v1/similarity` | POST | 文本相似度 | 是 |
| `/v1/rerank` | POST | 文档重排序 | 是 |
| `/v1/audio/transcriptions` | POST | 语音转文字 (form-data) | 是 |
| `/v1/chat/completions` | POST | 语音识别 (audio_url) | 是 |
| `/v1/ocr/parser` | POST | PDF 解析 | 是 |
| `/docs` | GET | Swagger UI | 否 |
| `/redoc` | GET | ReDoc | 否 |

### 5.2 API 响应格式

#### `/v1/embeddings` 响应
```json
{
  "object": "list",
  "data": [
    {
      "object": "embedding",
      "index": 0,
      "embedding": [-0.012, 0.045, ...]
    }
  ],
  "model": "unsloth/Qwen3-Embedding-0.6B",
  "usage": {
    "prompt_tokens": 5,
    "total_tokens": 5
  }
}
```

#### `/v1/rerank` 响应
```json
{
  "model": "Qwen/Qwen3-Reranker-0.6B",
  "results": [
    {"index": 2, "document": "...", "relevance_score": 0.8234},
    {"index": 1, "document": "...", "relevance_score": 0.1523}
  ]
}
```

#### `/health` 响应
```json
{
  "status": "healthy",
  "timestamp": "2026-04-08T10:30:00Z",
  "services": {
    "embedding": {"status": "healthy", "latency_ms": 15},
    "asr": {"status": "healthy", "latency_ms": 50},
    "reranker": {"status": "healthy", "latency_ms": 20},
    "mineru": {"status": "healthy", "latency_ms": 100}
  }
}
```

---

## 6. 部署架构

### 6.1 启动模式

```
┌─────────────────────────────────────────────────────────────┐
│                    启动方式                                  │
├─────────────────────────────────────────────────────────────┤
│ 1. pi-llm-server start-all                                  │
│    → 启动所有后台服务 + 网关                                 │
│                                                             │
│ 2. pi-llm-server services start --all                       │
│    → 仅启动后台服务                                          │
│                                                             │
│ 3. pi-llm-server                                            │
│    → 仅启动网关 (子服务需已运行)                              │
│                                                             │
│ 4. systemd service                                          │
│    → 生产环境推荐                                            │
└─────────────────────────────────────────────────────────────┘
```

### 6.2 进程关系

```
┌─────────────────────────────────────────────────────────────┐
│                     系统进程                                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  pi-llm-server gateway (PID: 12345)                         │
│  └─ uvicorn workers (4 个)                                  │
│       └─ FastAPI app + 各服务代理                            │
│                                                             │
│  embedding_server.py (PID: 12346)                           │
│  └─ SentenceTransformer 模型 (GPU/CPU)                       │
│                                                             │
│  asr_server.py (PID: 12347)                                 │
│  └─ vLLM + Qwen-ASR 模型 (GPU)                              │
│                                                             │
│  reranker_server.py (PID: 12348)                            │
│  └─ Transformers 模型 (CPU)                                  │
│                                                             │
│  mineru_server.sh (PID: 12349)                              │
│  └─ MinerU pipeline (GPU)                                   │
│                                                             │
└─────────────────────────────────────────────────────────────┘
```

### 6.3 Systemd 服务配置

```ini
# /etc/systemd/system/pi-llm-server.service

[Unit]
Description=PI-LLM-Server Gateway
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/pi-llm-server
ExecStart=/path/to/python -m pi_llm_server
Restart=always

[Install]
WantedBy=multi-user.target
```

---

## 7. 错误处理

### 7.1 错误类型与响应

| 错误 | HTTP 状态码 | 响应格式 |
|------|------------|----------|
| Token 无效/缺失 | 401 | `{"error": "Unauthorized"}` |
| 无权限 | 403 | `{"error": "Forbidden"}` |
| 队列满 | 503 | `{"error": "Service busy"}` |
| 子服务不健康 | 503 | `{"error": "Service unavailable"}` |
| 子服务超时 | 504 | `{"error": "Gateway timeout"}` |
| 参数校验失败 | 400 | `{"error": "Bad request"}` |
| 服务器错误 | 500 | `{"error": "Internal server error"}` |

### 7.2 重试策略

```python
for attempt in range(max_retries):
    try:
        response = await client.post(...)
        response.raise_for_status()
        return response.json()
    except httpx.TimeoutException:
        if attempt == max_retries - 1:
            raise HTTPException(status_code=504)
    except httpx.HTTPError:
        if attempt == max_retries - 1:
            raise HTTPException(status_code=502)
```

---

## 8. 性能考虑

### 8.1 并发控制

- **信号量**: `asyncio.Semaphore(max_concurrent)`
- **队列大小**: `asyncio.Queue(maxsize=max_size)`
- **超时**: `asyncio.wait_for(func, timeout)`

### 8.2 连接池

```python
self.client = httpx.AsyncClient(
    base_url=base_url,
    timeout=timeout,
    limits=httpx.Limits(
        max_keepalive_connections=10,
        max_connections=20
    )
)
```

### 8.3 GPU 显存管理

- **空闲卸载**: 超过 `idle_timeout` 无请求时自动卸载模型
- **按需加载**: 首次请求时才加载模型到 GPU
- **缓存清理**: 任务完成后清理临时显存

---

## 9. 监控与可观测性

### 9.1 健康检查指标

```python
ServiceStatus:
    status: str          # healthy / unhealthy / unknown
    latency_ms: float    # 响应延迟
    status_code: int     # HTTP 状态码
    error: str           # 错误信息
    consecutive_failures: int  # 连续失败次数
```

### 9.2 队列状态监控

```python
QueueStatus:
    pending: int         # 等待中请求数
    processing: int      # 处理中请求数
    total_processed: int # 累计处理数
    total_rejected: int  # 累计拒绝数
```

### 9.3 日志配置

- **网关日志**: `~/.cache/pi-llm-server/logs/gateway.log`
- **子服务日志**: `~/.cache/pi-llm-server/logs/{service}.log`
- **PID 文件**: `~/.cache/pi-llm-server/pids/{service}.pid`

---

## 10. 项目结构总览

```
pi-llm-server/
├── pi_llm_server/                # 主包目录
│   ├── __init__.py               # 包初始化 + 版本号
│   ├── __main__.py               # python -m 入口
│   ├── cli.py                    # 命令行工具
│   ├── server.py                 # FastAPI 应用 ⭐
│   ├── config.py                 # 配置管理
│   ├── auth.py                   # 认证管理
│   ├── queue_manager.py          # 队列管理
│   ├── health_monitor.py         # 健康监控
│   │
│   ├── services/                 # 服务代理层
│   │   ├── embedding.py
│   │   ├── asr.py
│   │   ├── reranker.py
│   │   └── mineru.py
│   │
│   ├── clients/                  # 客户端（备用）
│   │   ├── embedding_client.py
│   │   ├── asr_client.py
│   │   ├── reranker_client.py
│   │   └── mineru_client.py
│   │
│   ├── launcher/                 # 子服务启动器
│   │   ├── embedding_server.py
│   │   ├── asr_server.py
│   │   ├── reranker_server.py
│   │   ├── mineru_server.sh
│   │   └── service_manager.py
│   │
│   ├── utils/                    # 工具函数
│   │   ├── logging.py
│   │   └── exceptions.py
│   │
│   └── examples/                 # 示例
│       ├── config.example.yaml
│       ├── basic_usage.py
│       ├── install-service.sh
│       └── pi-llm-server.service.template
│
├── tests/                        # 测试目录
├── doc/                          # 文档目录
├── data/                         # 测试数据
├── backup/                       # 备份代码
├── pyproject.toml                # 项目配置
├── README.md                     # 使用说明
└── CHANGELOG.md                  # 变更记录
```

---

## 11. 关键设计决策

### 11.1 网关 + 子服务分离

**决策**: 网关与子服务独立进程运行，通过 HTTP 通信

**原因**:
- 子服务可能使用不同的 Python 环境（如 MinerU 需要独立 conda 环境）
- 独立进程可避免一个服务崩溃影响其他服务
- 便于水平扩展和负载均衡

**权衡**:
- 增加 HTTP 通信开销（毫秒级）
- 需要管理多个进程

### 11.2 差异化并发策略

**决策**: 不同服务配置不同的并发数

**原因**:
- GPU 推理需要顺序处理避免显存溢出
- CPU 推理可以多核并行
- PDF 解析耗时长，顺序处理避免资源耗尽

### 11.3 Bearer Token 认证

**决策**: 使用简单 Bearer Token，而非 JWT/OAuth2

**原因**:
- 内网部署，无需复杂认证
- 与 OpenAI SDK 兼容
- 配置简单，易于管理

---

## 12. 扩展点

### 12.1 新增服务类型

1. 在 `services/` 目录创建新服务文件
2. 实现 `Service` 类（HTTP 客户端 + 路由 + 健康检查）
3. 在 `server.py` 中注册服务和路由
4. 在配置文件中添加服务配置

### 12.2 自定义认证策略

1. 扩展 `AuthManager` 类
2. 实现自定义 `validate_token` 逻辑
3. 支持按端点授权

### 12.3 集成监控系统

1. 在 `health_monitor.py` 中添加 Prometheus 指标导出
2. 在 `queue_manager.py` 中添加队列监控
3. 集成 Grafana 仪表盘

---

## 13. 参考资料

- [README.md](../README.md) - 使用说明
- [config.example.yaml](../pi_llm_server/examples/config.example.yaml) - 配置示例
- [FastAPI 文档](https://fastapi.tiangolo.com/)
- [OpenAI API 参考](https://platform.openai.com/docs/api-reference)

---

**文档结束**
