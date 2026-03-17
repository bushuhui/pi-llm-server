# MinerU API 使用说明

## 概述

MinerU API 是一个将 PDF 转换为 Markdown 和图片的 FastAPI 服务。

## 启动方式

```bash
# 使用启动脚本
./mineru_server.sh start
./mineru_server.sh stop
./mineru_server.sh restart

# 直接启动
mineru-api --host 0.0.0.0 --port 8000 --vram 9000
```

## 配置参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--host` | 服务器主机地址 | 127.0.0.1 |
| `--port` | 服务器端口 | 8000 |
| `--vram` | GPU 显存限制 (MB) | 9000 |
| `--reload` | 开发模式自动重载 | False |

## 环境变量

| 变量名 | 说明 | 默认值 |
|--------|------|--------|
| `MINERU_API_MAX_CONCURRENT_REQUESTS` | 最大并发请求数 | 0 (无限制) |
| `MINERU_API_ENABLE_FASTAPI_DOCS` | 是否启用 API 文档 | 1 |
| `MINERU_LOG_LEVEL` | 日志级别 | INFO |

## 并发控制机制

### 工作原理

MinerU API 内置了基于 `asyncio.Semaphore` 的并发控制机制：

1. **并发限制**：通过 `MINERU_API_MAX_CONCURRENT_REQUESTS` 环境变量设置最大并发数
2. **请求处理**：
   - 当并发数未满：请求正常进入处理队列
   - 当并发数已满：**新请求被立即拒绝**，返回 503 Service Unavailable 错误

### 源码位置

```
/home/tiger/anaconda3/envs/mineru/lib/python3.13/site-packages/mineru/cli/fast_api.py
```

### 关键代码逻辑

```python
# 并发控制器
_request_semaphore: Optional[asyncio.Semaphore] = None

# 初始化（从环境变量读取）
max_concurrent_requests = int(os.getenv("MINERU_API_MAX_CONCURRENT_REQUESTS", "0"))
if max_concurrent_requests > 0:
    _request_semaphore = asyncio.Semaphore(max_concurrent_requests)

# 并发限制依赖函数
async def limit_concurrency():
    if _request_semaphore is not None:
        # 检查信号量是否已用尽，如果是则拒绝请求
        if _request_semaphore._value == 0:
            raise HTTPException(
                status_code=503,
                detail="Server is at maximum capacity...",
            )
        async with _request_semaphore:
            yield
    else:
        yield
```

### 使用示例

```bash
# 设置最大并发数为 1（一次只处理一个任务）
export MINERU_API_MAX_CONCURRENT_REQUESTS=1
mineru-api --host 0.0.0.0 --port 8000

# 设置最大并发数为 2
export MINERU_API_MAX_CONCURRENT_REQUESTS=2
mineru-api --host 0.0.0.0 --port 8000
```

### 注意事项

**当前实现不是真正的任务队列**：

- 当并发数达到限制时，新请求会被**立即拒绝**（返回 503 错误）
- **不会**将请求放入队列等待
- 如果需要实现真正的队列功能（请求排队等待而非被拒绝），需要修改 `limit_concurrency()` 函数

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/file_parse` | POST | 解析 PDF 文件 |
| `/docs` | GET | Swagger UI 文档 |
| `/openapi.json` | GET | OpenAPI 规范 |

## 使用方法

```bash
# 使用客户端脚本调用
python mineru_client.py "input.pdf" "output.zip"

# 使用 curl 调用
curl -X POST http://127.0.0.1:8000/file_parse \
  -F "files=@input.pdf" \
  -F "backend=pipeline" \
  -F "response_format_zip=true" \
  -o output.zip
```

## 常见问题

### 1. Swagger UI 无法访问

- API 服务正常运行，`/docs` 端点返回正确的 HTML
- 如果浏览器显示空白，可能是无法加载 CDN 资源（cdn.jsdelivr.net）
- 解决方案：直接访问 `/openapi.json` 或使用 API 客户端

### 2. 首次运行卡在模型加载

```
INFO | mineru.backend.pipeline.model_init:__init__:209 - DocAnalysis init, this may take some times...
```

- 首次运行需要下载和加载深度学习模型，可能需要几分钟
- 请耐心等待，这是正常现象

### 3. 多请求处理

- 支持同时接收多个请求
- 通过 `MINERU_API_MAX_CONCURRENT_REQUESTS` 限制同时执行的任务数
- 超过限制的请求会被拒绝（503），不会自动排队

## 相关资源

- 项目地址：https://mineru.net/
- PyPI: https://pypi.org/project/mineru/
