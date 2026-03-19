# PI-LLM-Server - 统一 LLM 服务网关

统一集成 Embedding、ASR、Reranker、MinerU 四个子服务，提供标准化的 Python 包管理、统一的 API 入口、
请求队列管理、认证管理和健康监控等功能。

## 目录结构

```
pi-llm-server/
├── pyproject.toml                # 项目配置文件
├── README.md                     # 项目说明
├── pi-llm-server.py              # 主程序入口（兼容旧版）
├── pi_llm_server/                # 主包
│   ├── __init__.py
│   ├── __main__.py               # python -m 入口
│   ├── cli.py                    # 命令行入口
│   ├── server.py                 # FastAPI 应用
│   ├── config.py
│   ├── auth.py
│   ├── queue_manager.py
│   ├── health_monitor.py
│   ├── services/
│   │   ├── embedding.py
│   │   ├── asr.py
│   │   ├── reranker.py
│   │   └── mineru.py
│   └── utils/
│       ├── logging.py
│       └── exceptions.py
├── scripts/                      # 辅助脚本
│   ├── embedding_server.py
│   ├── embedding_client.py
│   ├── asr_server.py
│   ├── asr_client.py
│   ├── reranker_server.py
│   ├── reranker_client.py
│   ├── mineru_server.sh
│   ├── mineru_client.py
│   ├── service_manager.py        # 服务管理工具
│   └── start_all_services.sh
├── tests/                        # 测试目录
└── examples/                     # 使用示例
```

---

## 快速开始

### 1. 安装

#### 方式 1: pip 安装（推荐）

```bash
# 进入项目目录
cd pi-llm-server

# 可编辑模式安装（开发推荐）
pip install -e ".[all]"

# 或只安装核心依赖
pip install -e .

# 或安装核心 + Embedding
pip install -e ".[embedding]"
```

#### 方式 2: 直接运行

```bash
# 确保依赖已安装
pip install fastapi uvicorn httpx pyyaml pydantic python-multipart

# 直接运行
python pi-llm-server.py --config config.yaml
```

### 2. 配置

配置文件默认位置：`~/.config/pi-llm-server/config.yaml`

首次运行时会自动从 `examples/config.example.yaml` 复制配置文件。

```bash
# 手动复制配置文件
cp examples/config.example.yaml ~/.config/pi-llm-server/config.yaml

# 或运行程序自动创建
pi-llm-server
```

主要配置项：
- `server.host/port`: 服务地址和端口
- `auth.tokens`: 访问 token 列表
- `queue.services`: 各服务队列配置
- `services.*.base_url`: 各子服务地址

### 3. 启动服务

#### 方式 1: 使用命令行工具（推荐）

```bash
# 启动所有子服务
python scripts/service_manager.py start --all

# 启动所有服务（包括网关）
python scripts/service_manager.py start --with-gateway

# 启动单个服务
python scripts/service_manager.py start embedding

# 查看服务状态
python scripts/service_manager.py status

# 停止所有服务
python scripts/service_manager.py stop --all
```

#### 方式 2: 使用 bash 脚本

```bash
# 一键启动所有服务
./scripts/start_all_services.sh
```

#### 方式 3: 使用新的命令行入口

```bash
# 启动主服务
pi-llm-server

# 或指定配置
pi-llm-server --config /path/to/config.yaml --port 8090
```

#### 方式 4: 使用 python -m

```bash
python -m pi_llm_server
```

#### 方式 5: 直接运行主程序（兼容旧版）

```bash
python pi-llm-server.py --config config.yaml
```

### API 端点

| 端点 | 方法 | 说明 | 认证 |
|------|------|------|------|
| `/` | GET | 根路径 | 否 |
| `/health` | GET | 健康检查 | 否 |
| `/status` | GET | 详细状态（含子服务和队列） | 是 |
| `/v1/models` | GET | 列出所有可用模型 | 可选 |
| `/docs` | GET | Swagger UI 文档 | 否 |
| `/v1/embeddings` | POST | 生成 embedding 向量 | 是 |
| `/v1/similarity` | POST | 计算文本相似度 | 是 |
| `/v1/rerank` | POST | 文档重排序 | 是 |
| `/v1/audio/transcriptions` | POST | 语音转文字 | 是 |
| `/v1/ocr/parser` | POST | PDF 解析 | 是 |

### 使用示例

```bash
# 查看服务状态
curl http://localhost:8090/health

# 列出所有模型
curl http://localhost:8090/v1/models

# 生成 embedding（需要 token）
curl -X POST http://localhost:8090/v1/embeddings \
  -H "Authorization: Bearer sk-admin-token-001" \
  -H "Content-Type: application/json" \
  -d '{"input": "你好，世界！"}'

# 语音转文字
curl -X POST http://localhost:8090/v1/audio/transcriptions \
  -H "Authorization: Bearer sk-admin-token-001" \
  -F "file=@audio.mp3" \
  -F "model=Qwen/Qwen3-ASR-1.7B"

# PDF 解析
curl -X POST http://localhost:8090/v1/ocr/parser \
  -H "Authorization: Bearer sk-admin-token-001" \
  -F "files=@document.pdf" \
  -F "backend=pipeline" \
  --output result.zip
```

### 默认端口分配

| 服务 | 端口 | 说明 |
|------|------|------|
| PI-LLM-Server | 8090 | 统一服务入口 |
| └─ Embedding | 8091 | 子服务（内部调用） |
| └─ ASR | 8092 | 子服务（内部调用） |
| └─ Reranker | 8093 | 子服务（内部调用） |
| └─ MinerU | 8094 | 子服务（内部调用） |

---

## 测试

运行测试套件：

```bash
# 安装开发依赖
pip install -e ".[dev]"

# 运行所有测试
pytest tests/ -v

# 运行单个测试文件
pytest tests/test_config.py -v

# 带覆盖率报告
pytest tests/ -v --cov=pi_llm_server
```

## 子服务文档

## 1. Embedding 服务

使用 Qwen3-Embedding 模型生成文本向量，支持语义搜索、相似度计算等场景。

### 依赖安装

```bash
pip install fastapi uvicorn sentence-transformers torch requests
```

### 启动服务器

```bash
# 默认 CPU 模式，端口 8091
python embedding_server.py

# 使用 GPU
python embedding_server.py --device cuda

# 指定 GPU 和端口
python embedding_server.py --device cuda:1 --port 8092

# 自定义模型路径
python embedding_server.py --model-path /path/to/Qwen3-Embedding-0.6B

# 后台运行
nohup python embedding_server.py > embedding.log 2>&1 &
```

### API 端点

| 端点 | 方法 | 说明 | 请求示例 |
|------|------|------|----------|
| `/health` | GET | 健康检查 | `curl http://localhost:8091/health` |
| `/v1/models` | GET | 列出可用模型 | `curl http://localhost:8091/v1/models` |
| `/v1/embeddings` | POST | 生成 embedding 向量 | 见下方请求/响应示例 |
| `/v1/similarity` | POST | 计算两个文本的余弦相似度 | 见下方请求/响应示例 |

#### `/v1/embeddings` 请求/响应示例

**请求:**
```bash
curl -X POST http://localhost:8091/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "input": "你好，世界！"
  }'
```

**响应:**
```json
{
  "object": "list",
  "data": [
    {
      "object": "embedding",
      "embedding": [0.0123, -0.0456, 0.0789, ...],
      "index": 0
    }
  ],
  "model": "unsloth/Qwen3-Embedding-0.6B",
  "usage": {
    "prompt_tokens": 5,
    "total_tokens": 5
  }
}
```

#### `/v1/similarity` 请求/响应示例

**请求:**
```bash
curl -X POST http://localhost:8091/v1/similarity \
  -H "Content-Type: application/json" \
  -d '{
    "text1": "人工智能",
    "text2": "机器学习"
  }'
```

**响应:**
```json
{
  "similarity": 0.8523
}
```

### 客户端使用

```bash
# 查看服务器信息
python embedding_client.py info

# 单个文本 embedding
python embedding_client.py embed -t "你好，世界"

# 批量相似度测试
python embedding_client.py embed-test

# 语义搜索
python embedding_client.py embed-search -q "人工智能技术"

# 指定服务地址
python embedding_client.py --base-url http://localhost:8081 embed -t "测试"
```

### Python 调用示例

```python
import requests

BASE_URL = "http://localhost:8091"

# 生成 embedding
resp = requests.post(f"{BASE_URL}/v1/embeddings", json={"input": "你好，世界！"})
embedding = resp.json()['data'][0]['embedding']
print(f"向量维度：{len(embedding)}")  # 1024

# 计算相似度
resp = requests.post(f"{BASE_URL}/v1/similarity",
    json={"text1": "人工智能", "text2": "机器学习"})
print(f"相似度：{resp.json()['similarity']:.4f}")
```

---

## 2. Reranker 服务

使用 Qwen3-Reranker 模型对查询-文档对进行相关性排序，适用于 RAG 检索增强场景。

### 依赖安装

```bash
pip install fastapi uvicorn torch transformers requests
```

### 启动服务器

```bash
# 默认 CPU 模式，端口 8093
python reranker_server.py

# 使用 GPU
python reranker_server.py --device cuda

# 指定 GPU 和端口
python reranker_server.py --device cuda:1 --port 8094

# 自定义模型路径
python reranker_server.py --model-path /path/to/Qwen3-Reranker-0.6B

# 后台运行
nohup python reranker_server.py > reranker.log 2>&1 &
```

### API 端点

| 端点 | 方法 | 说明 | 请求示例 |
|------|------|------|----------|
| `/health` | GET | 健康检查 | `curl http://localhost:8093/health` |
| `/v1/models` | GET | 列出可用模型 | `curl http://localhost:8093/v1/models` |
| `/v1/rerank` | POST | 文档相关性排序 | 见下方请求/响应示例 |

#### `/v1/rerank` 请求/响应示例

**请求:**
```bash
curl -X POST http://localhost:8093/v1/rerank \
  -H "Content-Type: application/json" \
  -d '{
    "query": "什么是人工智能？",
    "documents": [
      "人工智能是计算机科学的一个分支",
      "今天天气真好",
      "机器学习使用算法从数据中学习"
    ],
    "top_n": 2
  }'
```

**响应:**
```json
{
  "model": "Qwen/Qwen3-Reranker-0.6B",
  "results": [
    {
      "index": 0,
      "document": "人工智能是计算机科学的一个分支",
      "relevance_score": 0.9523
    },
    {
      "index": 2,
      "document": "机器学习使用算法从数据中学习",
      "relevance_score": 0.7234
    }
  ],
  "usage": {
    "prompt_tokens": 45,
    "total_tokens": 45
  }
}
```

### 客户端使用

```bash
# 查看服务器信息
python reranker_client.py info

# 单个文本对评分
python reranker_client.py rerank -q "什么是人工智能？" -d "人工智能是计算机科学的一个分支"

# 批量测试（内置测试数据）
python reranker_client.py rerank-batch

# 多文档排序
python reranker_client.py rerank-docs -q "人工智能技术" -d "文档1" -d "文档2" -d "文档3"

# 指定服务地址
python reranker_client.py --base-url http://localhost:8084 rerank-batch
```

### Python 调用示例

```python
import requests

BASE_URL = "http://localhost:8093"

resp = requests.post(f"{BASE_URL}/v1/rerank", json={
    "query": "什么是人工智能？",
    "documents": [
        "人工智能是计算机科学的一个分支",
        "今天天气真好",
        "机器学习使用算法从数据中学习"
    ]
})

for r in resp.json()['results']:
    print(f"[{r['index']}] {r['relevance_score']:.4f} - {r['document'][:50]}")
```

---

## 3. ASR 语音识别服务

使用 Qwen3-ASR 模型进行语音转文字，基于 vLLM 推理引擎，提供 OpenAI 兼容的 chat/completions 和 audio/transcriptions API。

### 依赖安装

```bash
pip install -U qwen-asr[vllm] requests openai
```

### 启动服务器

```bash
# 默认启动，端口 8092
python asr_server.py

# 指定模型路径和端口
python asr_server.py --model-path /path/to/Qwen3-ASR-1.7B --port 8092

# 调整 GPU 显存使用率和最大序列长度
python asr_server.py --gpu-memory-utilization 0.8 --max-model-len 16384

# 使用 vllm serve 命令（替代 qwen-asr-serve）
python asr_server.py --use-vllm
```

> 注意：ASR 服务需要 GPU。服务器会自动检测 nvcc 版本，如与 PyTorch CUDA 版本不匹配会自动切换到 TRITON_ATTN 后端。

### API 端点

| 端点 | 方法 | 说明 | 请求示例 |
|------|------|------|----------|
| `/health` | GET | 健康检查 | `curl http://localhost:8092/health` |
| `/v1/models` | GET | 列出可用模型 | `curl http://localhost:8092/v1/models` |
| `/v1/chat/completions` | POST | 语音识别（audio_url 方式） | 见下方示例 |
| `/v1/audio/transcriptions` | POST | 语音识别（form-data 方式） | 见下方示例 |

#### `/v1/chat/completions` 请求示例（audio_url 方式）

```bash
curl -X POST http://localhost:8092/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "Qwen/Qwen3-ASR-1.7B",
    "messages": [
      {
        "role": "user",
        "content": [
          {
            "type": "audio_url",
            "audio_url": {
              "url": "data:audio/mpeg;base64,<base64_encoded_audio>"
            }
          }
        ]
      }
    ],
    "max_tokens": 512
  }'
```

#### `/v1/audio/transcriptions` 请求示例（form-data 方式）

```bash
curl -X POST http://localhost:8092/v1/audio/transcriptions \
  -F "file=@audio.mp3" \
  -F "model=Qwen/Qwen3-ASR-1.7B"
```

**响应:**
```json
{
  "text": "今天天气很好，阳光明媚。"
}
```

### 客户端使用

```bash
# 列出可用模型
python asr_client.py list

# 语音转文字（chat API，默认方式）
python asr_client.py transcribe audio_s.mp3

# 语音转文字（transcription API）
python asr_client.py transcribe audio_s.mp3 --api transcription

# 语音转文字（OpenAI SDK）
python asr_client.py transcribe audio_s.mp3 --api sdk

# 指定服务地址和模型
python asr_client.py --base-url http://localhost:8092 transcribe audio_s.mp3
```

音频文件默认从 `data/` 目录读取，识别结果保存到 `results/` 目录。

---

## 4. MinerU PDF 解析服务

使用 MinerU 将 PDF 文件解析为 Markdown 和图片。支持 pipeline（传统）和 hybrid/vlm（视觉大模型）两类后端。

### 依赖安装

```bash
# 需要在 MinerU 的 conda 环境中运行
conda activate mineru
pip install requests
```

### 模型源配置

MinerU 通过环境变量 `MINERU_MODEL_SOURCE` 控制模型下载来源，支持三种模型源：

| 模型源 | 说明 | 适用场景 |
|--------|------|----------|
| `huggingface`（默认） | 从 HuggingFace Hub 下载 | 可访问外网时使用 |
| `modelscope` | 从 ModelScope 下载 | **国内网络推荐** |
| `local` | 使用本地模型 | 离线环境 |

对应的模型仓库：

| 模型源 | pipeline 模型 | VLM 模型 |
|--------|---------------|----------|
| huggingface | `opendatalab/PDF-Extract-Kit-1.0` | `opendatalab/MinerU2.5-2509-1.2B` |
| modelscope | `OpenDataLab/PDF-Extract-Kit-1.0` | `OpenDataLab/MinerU2.5-2509-1.2B` |

> **注意**：两个源的模型内容完全相同，只是仓库来源不同。切换模型源会重新下载模型。

### 解析后端说明

| 后端 | 说明 | 推理方式 | 精度 |
|------|------|----------|------|
| `pipeline` | 传统 pipeline，使用检测+OCR 模型 | 本地 GPU/CPU | 通用 |
| `hybrid-auto-engine` | 混合方案，pipeline + VLM 结合（**默认**） | 本地 GPU (vLLM) | 高 |
| `vlm-auto-engine` | 纯 VLM 视觉大模型 | 本地 GPU (vLLM) | 高 |
| `hybrid-http-client` | 混合方案，VLM 通过远程 API | 远程服务器 | 高 |
| `vlm-http-client` | 纯 VLM，通过远程 API | 远程服务器 | 高 |

### 命令行使用

```bash
# 基本用法（默认 hybrid-auto-engine 后端）
mineru -p data/InfoLOD.pdf -o results/

# 指定 pipeline 后端（不需要 VLM 模型，显存占用更低）
mineru -p data/InfoLOD.pdf -o results/ -b pipeline

# 使用 modelscope 模型源（国内推荐）
mineru -p data/InfoLOD.pdf -o results/ --source modelscope

# 通过环境变量设置模型源
MINERU_MODEL_SOURCE=modelscope mineru -p data/InfoLOD.pdf -o results/

# 指定页码范围（从 0 开始）
mineru -p data/InfoLOD.pdf -o results/ -s 0 -e 5

# 指定语言（提升 OCR 精度）
mineru -p data/InfoLOD.pdf -o results/ -l ch
```

### RTX 2080 Ti 显存问题

使用 `hybrid-auto-engine` 或 `vlm-auto-engine` 后端时，MinerU 会通过 vLLM 加载 VLM 模型。RTX 2080 Ti (11GB) 在默认配置下可能报错：

```
ValueError: To serve at least one request with the models's max seq len (16384),
0.19 GiB KV cache is needed, which is larger than the available KV cache memory (0.18 GiB).
```

**原因**：MinerU 对 >8GB 显存的 GPU 默认只使用 50% 显存（`gpu_memory_utilization=0.5`），11GB 的 50% 加载模型后 KV cache 差 0.01 GiB。

**解决方法**：修改 MinerU 源码中的显存利用率默认值：

```bash
# 找到文件位置
vim $(python -c "import mineru; print(mineru.__path__[0])")/backend/vlm/utils.py
```

找到 `set_default_gpu_memory_utilization()` 函数，在 `gpu_memory <= 8` 分支后增加 `gpu_memory <= 12` 分支：

```python
def set_default_gpu_memory_utilization() -> float:
    from vllm import __version__ as vllm_version
    device = get_device()
    gpu_memory = get_vram(device)
    if version.parse(vllm_version) >= version.parse("0.11.0") and gpu_memory <= 8:
        return 0.7
    elif gpu_memory <= 12:   # 新增：RTX 2080 Ti / RTX 3060 12GB 等
        return 0.6
    else:
        return 0.5
```

> **注意**：升级 MinerU 版本后此修改会被覆盖，需要重新修改。

### 启动 API 服务

```bash
# 启动服务（默认使用 modelscope 模型源）
./mineru_server.sh start

# 临时指定使用 huggingface
MINERU_MODEL_SOURCE=huggingface ./mineru_server.sh start

# 停止/重启
./mineru_server.sh stop
./mineru_server.sh restart
```

`mineru_server.sh` 配置项（直接编辑脚本修改）：

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `HOST` | `0.0.0.0` | 监听地址 |
| `PORT` | `8094` | 监听端口 |
| `VRAM` | `9000` | VRAM 限制（MB），2080 Ti 建议 9000-11000 |
| `MODEL_SOURCE` | `modelscope` | 模型源，可通过环境变量 `MINERU_MODEL_SOURCE` 覆盖 |

### API 端点

| 端点 | 方法 | 说明 | 请求示例 |
|------|------|------|----------|
| `/file_parse` | POST | 解析 PDF 文件为 Markdown+ 图片 | 见下方请求/响应示例 |

#### `/file_parse` 请求/响应示例

**请求:**
```bash
curl -X POST http://localhost:8094/file_parse \
  -F "files=@document.pdf" \
  -F "backend=pipeline" \
  -F "parse_method=auto" \
  -F "lang_list=ch" \
  -F "formula_enable=true" \
  -F "table_enable=true" \
  -F "return_md=true" \
  -F "return_images=true" \
  -F "response_format_zip=true"
```

**响应:** ZIP 文件，包含：
- `content/` - Markdown 文件和图片
- `layout.pdf` - 版面分析可视化
- `spans.pdf` - 文本块可视化

**主要参数说明:**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `backend` | pipeline | 解析后端：pipeline / hybrid-auto-engine / vlm-auto-engine |
| `parse_method` | auto | 解析方法：auto / txt / ocr |
| `lang_list` | ch | 语言列表：ch / en / korean / japan 等 |
| `formula_enable` | true | 是否启用公式解析 |
| `table_enable` | true | 是否启用表格解析 |
| `return_md` | true | 是否返回 markdown 文件 |
| `return_images` | true | 是否返回提取的图片 |
| `response_format_zip` | true | 是否以 zip 格式返回 |

### 客户端使用

```bash
# 基本用法（自动生成输出文件名）
python mineru_client.py "文档.pdf"

# 指定输出文件和后端
python mineru_client.py "文档.pdf" output.zip vlm-auto-engine

# 指定 API 地址
export MINERU_API_URL="http://localhost:8094"
```

> **注意**：`mineru_client.py` 是 HTTP 客户端，模型源配置在服务端（`mineru_server.sh`）中设置，客户端无需关心模型源。

---

## 默认端口分配

| 服务 | 端口 | 启动命令 | 客户端默认 URL |
|------|------|----------|---------------|
| Embedding | 8091 | `python embedding_server.py` | `http://localhost:8091` |
| ASR | 8092 | `python asr_server.py` | `http://localhost:8092` |
| Reranker | 8093 | `python reranker_server.py` | `http://localhost:8093` |
| MinerU | 8094 | `./mineru_server.sh` | `http://localhost:8094` (可通过 `MINERU_API_URL` 修改) |

## 模型信息

| 模型 | 参数量 | 用途 | 默认设备 |
|------|--------|------|----------|
| Qwen3-Embedding-0.6B | 0.6B | 文本向量化 | CPU |
| Qwen3-Reranker-0.6B | 0.6B | 文档相关性排序 | CPU |
| Qwen3-ASR-1.7B | 1.7B | 语音识别 | GPU |
| MinerU2.5-2509-1.2B | 1.2B | PDF 解析 (VLM) | GPU |
| PDF-Extract-Kit-1.0 | - | PDF 解析 (pipeline) | GPU |

---

**最后更新**: 2026-03-16
