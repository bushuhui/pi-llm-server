# PI-LLM-Server API 文档

> 本文档描述 PI-LLM-Server 网关暴露的 RESTful API 接口，涵盖 Embedding、Reranker、ASR、MinerU 和 pi-memory 服务。

## 目录

- [通用规范](#通用规范)
- [Embedding API](#embedding-api)
- [Reranker API](#reranker-api)
- [ASR API](#asr-api)
- [MinerU API](#mineru-api)
- [pi-memory API](#pi-memory-api)
- [管理接口](#管理接口)

---

## 通用规范

### 基础信息

| 项目 | 说明 |
|------|------|
| 基础 URL | `http://127.0.0.1:8090` |
| 协议 | HTTP/1.1 |
| 数据格式 | JSON (除文件上传接口外) |
| 认证方式 | Bearer Token (若 `auth.enabled=true`) |

### 认证

若配置文件启用了认证，所有接口（除 `/health`、`/`、`/docs` 外）需在请求头中携带 Token：

```bash
curl -H "Authorization: Bearer sk-your-token" ...
```

### 通用响应格式

#### 成功响应

各业务接口返回具体的 JSON 结构，无统一包装。

#### 错误响应

```json
{
  "error": "错误描述",
  "message": "详细错误信息"
}
```

常见 HTTP 状态码：

| 状态码 | 含义 |
|--------|------|
| 400 | 请求参数错误 |
| 401 | 未授权（Token 无效或缺失） |
| 502 | 上游服务错误 |
| 503 | 服务不可用（队列已满） |
| 504 | 上游服务超时 |

---

## Embedding API

> 基于 Qwen3-Embedding 模型，提供文本向量化服务。支持 batch 请求以获得更高吞吐量。

### 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/v1/embeddings` | POST | 生成文本 embedding |

### 请求参数

```json
{
  "input": "你好，世界！",
  "model": "unsloth/Qwen3-Embedding-0.6B",
  "encoding_format": "float"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `input` | `string` / `string[]` | 是 | 输入文本，支持**单个字符串**或**字符串列表**（batch） |
| `model` | `string` | 否 | 模型 ID，默认使用配置中的首个模型 |
| `encoding_format` | `string` | 否 | 编码格式：`float`（默认）或 `base64` |

### 响应格式

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

### 使用示例

#### 单文本请求

```bash
curl -X POST http://localhost:8090/v1/embeddings \
  -H "Authorization: Bearer sk-your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "input": "你好，世界！"
  }'
```

#### Batch 请求（推荐）

**重要**：Embedding 服务在子服务层使用 `sentence-transformers`，其内部支持 batch 计算。一次请求传列表比多次单个请求快 **5~6 倍**。

```bash
curl -X POST http://localhost:8090/v1/embeddings \
  -H "Authorization: Bearer sk-your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "input": [
      "人工智能是计算机科学的一个分支",
      "机器学习是人工智能的核心技术",
      "深度学习用于图像识别"
    ]
  }'
```

#### Python 示例

```python
import requests

url = "http://localhost:8090/v1/embeddings"
headers = {"Authorization": "Bearer sk-your-token"}

# batch 请求
resp = requests.post(url, headers=headers, json={
    "input": ["文本1", "文本2", "文本3"]
})
result = resp.json()
for item in result["data"]:
    print(f"index={item['index']}, dim={len(item['embedding'])}")
```

### 性能建议

| 方式 | 10 条文本总耗时 | 加速比 |
|------|----------------|--------|
| 逐个请求（10 次） | ~0.90s | 1.0x |
| Batch 请求（1 次） | ~0.15s | **6.2x** |

**建议**：始终使用 batch 接口，前端将待向量化文本攒成列表后一次性发送。

---

## Reranker API

> 基于 Qwen3-Reranker 模型，对文档列表按与查询的相关性排序。

### 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/v1/rerank` | POST | 文档重排序 |

### 请求参数

```json
{
  "query": "深度学习",
  "documents": [
    "人工智能是计算机科学的一个分支",
    "机器学习是实现人工智能的方法之一",
    "深度学习是机器学习的子集"
  ],
  "top_n": 2
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `query` | `string` | 是 | 查询文本 |
| `documents` | `string[]` | 是 | 待排序文档列表 |
| `top_n` | `integer` | 否 | 返回前 N 个结果（默认返回全部） |
| `model` | `string` | 否 | 模型 ID |

### 响应格式

```json
{
  "model": "Qwen/Qwen3-Reranker-0.6B",
  "results": [
    {
      "index": 2,
      "document": "深度学习是机器学习的子集",
      "relevance_score": 0.8234
    },
    {
      "index": 1,
      "document": "机器学习是实现人工智能的方法之一",
      "relevance_score": 0.1523
    },
    {
      "index": 0,
      "document": "人工智能是计算机科学的一个分支",
      "relevance_score": 0.0821
    }
  ],
  "usage": {
    "prompt_tokens": 45,
    "total_tokens": 45
  }
}
```

结果按 `relevance_score` 降序排列，`index` 对应输入 `documents` 的原始索引。

### 使用示例

```bash
curl -X POST http://localhost:8090/v1/rerank \
  -H "Authorization: Bearer sk-your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "深度学习",
    "documents": [
      "人工智能是计算机科学的一个分支",
      "机器学习是实现人工智能的方法之一",
      "深度学习是机器学习的子集"
    ],
    "top_n": 2
  }'
```

```python
import requests

url = "http://localhost:8090/v1/rerank"
headers = {"Authorization": "Bearer sk-your-token"}

resp = requests.post(url, headers=headers, json={
    "query": "深度学习",
    "documents": ["文档A", "文档B", "文档C"],
    "top_n": 2
})
result = resp.json()
for item in result["results"]:
    print(f"[{item['index']}] {item['relevance_score']:.4f} {item['document']}")
```

---

## ASR API

> 基于 Qwen3-ASR 模型 + vLLM 推理引擎，提供语音转文字服务。支持 form-data 上传音频文件。

### 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/v1/audio/transcriptions` | POST | 语音转文字（form-data） |
| `/v1/chat/completions` | POST | 语音对话（audio_url 方式） |

### 1. 语音转文字（/v1/audio/transcriptions）

#### 请求参数（multipart/form-data）

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `file` | `File` | 是 | 音频文件（mp3/wav/ogg/flac 等） |
| `model` | `string` | 否 | 模型 ID，默认 `Qwen/Qwen3-ASR-1.7B` |

#### 响应格式

```json
{
  "text": "大家好，这里是最佳拍档..."
}
```

#### 使用示例

```bash
curl -X POST http://localhost:8090/v1/audio/transcriptions \
  -H "Authorization: Bearer sk-your-token" \
  -F "file=@audio.mp3" \
  -F "model=Qwen/Qwen3-ASR-1.7B"
```

```python
import requests

url = "http://localhost:8090/v1/audio/transcriptions"
headers = {"Authorization": "Bearer sk-your-token"}

with open("audio.mp3", "rb") as f:
    resp = requests.post(url, headers=headers, files={
        "file": ("audio.mp3", f, "audio/mpeg")
    }, data={"model": "Qwen/Qwen3-ASR-1.7B"})

result = resp.json()
print(result["text"])
```

### 2. 语音对话（/v1/chat/completions）

通过 `audio_url` 方式传入音频链接进行对话。

#### 请求参数

```json
{
  "model": "Qwen/Qwen3-ASR-1.7B",
  "messages": [
    {
      "role": "user",
      "content": [
        {"type": "audio", "audio_url": "http://example.com/audio.mp3"},
        {"type": "text", "text": "这段音频说了什么？"}
      ]
    }
  ],
  "max_tokens": 512
}
```

---

## MinerU API

> 基于 MinerU 的文档解析服务，支持 PDF、图片、Office 文档（docx/pptx/xlsx）的解析，返回 Markdown 文本和提取的图片。

### 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/v1/ocr/parser` | POST | 解析文档为 Markdown + 图片 ZIP |

### 请求参数（multipart/form-data）

| 字段 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `files` | `File` | 是 | — | 上传的文件 |
| `backend` | `string` | 否 | `pipeline` | 解析后端：`pipeline` / `hybrid-auto-engine` / `vlm-auto-engine` |
| `parse_method` | `string` | 否 | `auto` | 解析方法：`auto` / `txt` / `ocr` |
| `lang_list` | `string` | 否 | `ch` | 语言：`ch` / `en` / `korean` / `japan` |
| `formula_enable` | `boolean` | 否 | `true` | 启用公式解析 |
| `table_enable` | `boolean` | 否 | `true` | 启用表格解析 |
| `return_md` | `boolean` | 否 | `true` | 返回 Markdown |
| `return_images` | `boolean` | 否 | `true` | 返回图片 |

### 支持的文件类型

| 类型 | 扩展名 | 说明 |
|------|--------|------|
| PDF | `.pdf` | 原生支持 |
| 图片 | `.jpg`, `.jpeg`, `.png` | 自动处理 |
| Word | `.docx`, `.doc` | 需安装 libreoffice 转换 |
| PPT | `.pptx`, `.ppt` | 需安装 libreoffice 转换 |
| Excel | `.xlsx`, `.xls` | 需安装 libreoffice 转换 |

### 响应

返回 `application/zip` 格式的二进制数据，HTTP 头包含：

```
Content-Type: application/zip
Content-Disposition: attachment; filename=result.zip
```

ZIP 包内包含：
- `markdown/` — 解析后的 Markdown 文件
- `images/` — 提取的图片资源
- 其他中间文件

### 使用示例

#### PDF 解析

```bash
curl -X POST http://localhost:8090/v1/ocr/parser \
  -H "Authorization: Bearer sk-your-token" \
  -F "files=@document.pdf" \
  -F "backend=pipeline" \
  -F "parse_method=auto" \
  -F "lang_list=ch" \
  -F "return_md=true" \
  -F "return_images=true" \
  -o result.zip
```

#### Office 文档解析

```bash
curl -X POST http://localhost:8090/v1/ocr/parser \
  -H "Authorization: Bearer sk-your-token" \
  -F "files=@report.docx" \
  -o result.zip
```

#### Python 示例

```python
import requests

url = "http://localhost:8090/v1/ocr/parser"
headers = {"Authorization": "Bearer sk-your-token"}

with open("document.pdf", "rb") as f:
    resp = requests.post(url, headers=headers, files={
        "files": ("document.pdf", f, "application/pdf")
    }, data={
        "backend": "pipeline",
        "parse_method": "auto",
        "lang_list": "ch",
        "return_md": "true",
        "return_images": "true",
    })

with open("result.zip", "wb") as out:
    out.write(resp.content)

print(f"ZIP 大小: {len(resp.content) / 1024 / 1024:.2f} MB")
```

---

## pi-memory API

> pi-memory 服务代理，提供记忆管理和知识库搜索功能。需要独立部署 pi-memory 服务。

### 记忆管理

| 端点 | 方法 | 说明 |
|------|------|------|
| `/memory/api/memory/search` | POST | 搜索记忆 |
| `/memory/api/memory/store` | POST | 存储记忆 |
| `/memory/api/memory/{id}` | DELETE | 删除记忆 |
| `/memory/api/memory/{id}` | PATCH | 更新记忆 |
| `/memory/api/memory/list` | GET | 记忆列表 |
| `/memory/api/memory/stats` | GET | 记忆统计 |

### 知识库

| 端点 | 方法 | 说明 |
|------|------|------|
| `/memory/api/knowledge/search` | POST | 知识库搜索 |
| `/memory/api/knowledge/index` | POST | 重建知识库索引 |
| `/memory/api/knowledge/stats` | GET | 知识库统计 |

### 使用示例

#### 记忆搜索

```bash
curl -X POST http://localhost:8090/memory/api/memory/search \
  -H "Authorization: Bearer sk-your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "用户偏好设置",
    "limit": 5
  }'
```

#### 知识库搜索

```bash
curl -X POST http://localhost:8090/memory/api/knowledge/search \
  -H "Authorization: Bearer sk-your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "query": "无人机控制",
    "limit": 10
  }'
```

---

## 管理接口

### 健康检查

| 端点 | 方法 | 认证 | 说明 |
|------|------|------|------|
| `/health` | GET | 否 | 网关及各子服务健康状态 |
| `/status` | GET | 是 | 详细状态（含队列信息） |
| `/v1/models` | GET | 可选 | 可用模型列表 |

#### 健康检查示例

```bash
curl http://localhost:8090/health
```

响应：

```json
{
  "status": "healthy",
  "services": {
    "embedding": {"status": "healthy", "latency_ms": 13.9},
    "asr": {"status": "healthy", "latency_ms": 5.8},
    "reranker": {"status": "healthy", "latency_ms": 1501.2},
    "mineru": {"status": "healthy", "latency_ms": 26.0}
  }
}
```

#### 模型列表示例

```bash
curl -H "Authorization: Bearer sk-your-token" http://localhost:8090/v1/models
```

响应：

```json
{
  "object": "list",
  "data": [
    {"id": "unsloth/Qwen3-Embedding-0.6B", "service": "embedding"},
    {"id": "Qwen/Qwen3-ASR-1.7B", "service": "asr"},
    {"id": "Qwen/Qwen3-Reranker-0.6B", "service": "reranker"}
  ]
}
```

---

## 端口与服务对应关系

| 服务 | 网关端点 | 子服务端口 | 默认设备 |
|------|----------|-----------|----------|
| Embedding | `/v1/embeddings` | 8091 | cuda |
| ASR | `/v1/audio/transcriptions` | 8092 | cuda |
| Reranker | `/v1/rerank` | 8093 | cpu |
| MinerU | `/v1/ocr/parser` | 8094 | cuda |
| pi-memory | `/memory/api/*` | 9873 | — |

---

## 队列并发配置

网关层通过 `queue` 配置控制各服务的最大并发数：

| 服务 | max_concurrent | 建议 |
|------|----------------|------|
| embedding | 1 | 使用 batch 接口提升吞吐，无需调高并发 |
| reranker | 4 | CPU 多核并行，可适当调高 |
| asr | 3 | vLLM continuous batching 支持并发 |
| mineru | 1 | PDF 解析耗时，顺序处理 |
