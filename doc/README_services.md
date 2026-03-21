# PI-LLM-Server - 后台服务文档

本文档介绍 PI-LLM-Server 的四个核心后台服务：Embedding、ASR、Reranker、MinerU (OCR)。

---

## 目录

1. [Embedding 服务](#1-embedding-服务)
2. [Reranker 服务](#2-reranker-服务)
3. [ASR 语音识别服务](#3-asr-语音识别服务)
4. [MinerU PDF 解析服务](#4-mineru-pdf-解析服务)
5. [服务管理](#服务管理)
6. [端口分配](#端口分配)

---

## 1. Embedding 服务

使用 Qwen3-Embedding 模型生成文本向量，支持语义搜索、相似度计算等场景。

### 1.1 依赖安装

```bash
pip install fastapi uvicorn sentence-transformers torch
```

### 1.2 启动服务器

服务器脚本位置：`pi_llm_server/launcher/embedding_server.py`

```bash
# 默认 CPU 模式，端口 8091
python pi_llm_server/launcher/embedding_server.py

# 使用 GPU
python pi_llm_server/launcher/embedding_server.py --device cuda

# 指定 GPU 和端口
python pi_llm_server/launcher/embedding_server.py --device cuda:1 --port 8092

# 自定义模型路径
python pi_llm_server/launcher/embedding_server.py --model-path ~/.cache/modelscope/hub/models/unsloth/Qwen3-Embedding-0.6B

# 后台运行
nohup python pi_llm_server/launcher/embedding_server.py > embedding.log 2>&1 &
```

### 1.3 命令行参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--model-path` | `~/.cache/modelscope/hub/models/unsloth/Qwen3-Embedding-0.6B` | 模型路径 |
| `--host` | `0.0.0.0` | 监听地址 |
| `--port` | `8091` | 监听端口 |
| `--device` | `cpu` | 运行设备 (cpu/cuda/cuda:0) |

### 1.4 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/v1/models` | GET | 列出可用模型 |
| `/v1/embeddings` | POST | 生成 embedding 向量 |
| `/v1/similarity` | POST | 计算两个文本的余弦相似度 |

### 1.4.1 `/v1/embeddings` 请求参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `input` | string \| string[] | 是 | - | 输入文本或文本列表 |
| `model` | string | 否 | - | 模型 ID |
| `encoding_format` | string | 否 | `"float"` | 编码格式：`"float"` 或 `"base64"` |

**encoding_format 说明：**

- **`float`** (默认): 返回 JSON 格式的 float 数组
  ```json
  {
    "data": [{
      "embedding": [0.1234, -0.5678, 0.9012, ...],
      "index": 0,
      "object": "embedding"
    }]
  }
  ```

- **`base64`**: 返回 base64 编码的 float32 二进制数据（减少网络传输）
  ```json
  {
    "data": [{
      "embedding": "AAAAAAAAAAAAAAAAAAAA...==",
      "index": 0,
      "object": "embedding"
    }]
  }
  ```

  > 注意：base64 编码的数据需要使用 `struct.unpack()` 解码，参考 `examples/basic_usage.py`

### 1.5 使用示例

```bash
# 生成 embedding（默认 float 格式）
curl -X POST http://localhost:8091/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"input": "你好，世界！"}'

# 生成 embedding（base64 格式）
curl -X POST http://localhost:8091/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"input": "你好，世界！", "encoding_format": "base64"}'

# 计算相似度
curl -X POST http://localhost:8091/v1/similarity \
  -H "Content-Type: application/json" \
  -d '{"text1": "人工智能", "text2": "机器学习"}'
```

### 1.7 客户端工具

客户端脚本位置：`pi_llm_server/clients/embedding_client.py`

```bash
# 查看服务器信息
python pi_llm_server/clients/embedding_client.py info

# 单个文本 embedding（默认 float 格式）
python pi_llm_server/clients/embedding_client.py embed -t "你好，世界"

# 单个文本 embedding（base64 格式）
python pi_llm_server/clients/embedding_client.py embed -t "你好，世界" -e base64

# 批量相似度测试
python pi_llm_server/clients/embedding_client.py embed-test

# 语义搜索
python pi_llm_server/clients/embedding_client.py embed-search -q "人工智能技术"

# 指定服务地址
python pi_llm_server/clients/embedding_client.py --base-url http://localhost:8091 embed -t "测试"
```

**embedding 命令参数：**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--model`, `-m` | `unsloth/Qwen3-Embedding-0.6B` | 模型名称 |
| `--text`, `-t` | - | 输入文本 |
| `--encoding-format`, `-e` | `float` | 编码格式：`float` 或 `base64` |

---

## 2. Reranker 服务

使用 Qwen3-Reranker 模型对查询 - 文档对进行相关性排序，适用于 RAG 检索增强场景。

### 2.1 依赖安装

```bash
pip install fastapi uvicorn torch transformers
```

### 2.2 启动服务器

服务器脚本位置：`pi_llm_server/launcher/reranker_server.py`

```bash
# 默认 CPU 模式，端口 8093
python pi_llm_server/launcher/reranker_server.py

# 使用 GPU
python pi_llm_server/launcher/reranker_server.py --device cuda

# 指定 GPU 和端口
python pi_llm_server/launcher/reranker_server.py --device cuda:1 --port 8094

# 自定义模型路径
python pi_llm_server/launcher/reranker_server.py --model-path ~/.cache/modelscope/hub/models/Qwen/Qwen3-Reranker-0.6B

# 后台运行
nohup python pi_llm_server/launcher/reranker_server.py > reranker.log 2>&1 &
```

### 2.3 命令行参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--model-path` | `~/.cache/modelscope/hub/models/Qwen/Qwen3-Reranker-0.6B` | 模型路径 |
| `--host` | `0.0.0.0` | 监听地址 |
| `--port` | `8093` | 监听端口 |
| `--device` | `cpu` | 运行设备 (cpu/cuda/cuda:0) |

### 2.4 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/v1/models` | GET | 列出可用模型 |
| `/v1/rerank` | POST | 文档相关性排序 |

### 2.4.1 `/v1/rerank` 请求参数

| 参数 | 类型 | 必填 | 默认值 | 说明 |
|------|------|------|--------|------|
| `query` | string | 是 | - | 查询文本 |
| `documents` | string[] | 是 | - | 文档列表 |
| `top_n` | int | 否 | - | 返回前 N 个结果 |
| `model` | string | 否 | - | 模型 ID |
| `instruction` | string | 否 | - | 任务指令 |
| `encoding_format` | string | 否 | - | 编码格式（保留用于未来扩展） |

### 2.5 使用示例

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

响应示例：
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
  ]
}
```

### 2.7 客户端工具

客户端脚本位置：`pi_llm_server/clients/reranker_client.py`

```bash
# 查看服务器信息
python pi_llm_server/clients/reranker_client.py info

# 单个文本对评分
python pi_llm_server/clients/reranker_client.py rerank -q "什么是人工智能？" -d "人工智能是计算机科学的一个分支"

# 批量测试
python pi_llm_server/clients/reranker_client.py rerank-batch

# 多文档排序
python pi_llm_server/clients/reranker_client.py rerank-docs -q "人工智能技术" -d "文档 1" -d "文档 2" -d "文档 3"
```

**rerank 命令参数：**

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--model`, `-m` | 从服务器获取 | Reranker 模型名称 |
| `--query`, `-q` | - | 查询文本 |
| `--document`, `-d` | - | 文档文本（多文档时使用多次） |
| `--instruction`, `-i` | - | 任务指令（可选） |
| `--encoding-format`, `-e` | - | 编码格式（保留用于未来扩展） |

---

## 3. ASR 语音识别服务

使用 Qwen3-ASR 模型进行语音转文字，基于 vLLM 推理引擎，提供 OpenAI 兼容的 `audio/transcriptions` API。

### 3.1 依赖安装

```bash
pip install -U qwen-asr[vllm] silero-vad soundfile librosa
```

### 3.2 启动服务器

服务器脚本位置：`pi_llm_server/launcher/asr_server.py`

```bash
# 默认启动，端口 8092
python pi_llm_server/launcher/asr_server.py

# 指定模型路径和端口
python pi_llm_server/launcher/asr_server.py --model-path ~/.cache/modelscope/hub/models/Qwen/Qwen3-ASR-1.7B --port 8092

# 调整 GPU 显存使用率和最大序列长度
python pi_llm_server/launcher/asr_server.py --gpu-memory-utilization 0.8 --max-model-len 32768
```

> **注意**：ASR 服务需要 GPU。服务器会自动检测 nvcc 版本，如与 PyTorch CUDA 版本不匹配会自动切换到 TRITON_ATTN 后端。

### 3.3 命令行参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--model-path` | `~/.cache/modelscope/hub/models/Qwen/Qwen3-ASR-1.7B` | 模型路径 |
| `--host` | `0.0.0.0` | 监听地址 |
| `--port` | `8092` | 监听端口 |
| `--reload` | - | 启用热重载（开发模式） |

### 3.4 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/v1/models` | GET | 列出可用模型 |
| `/v1/audio/transcriptions` | POST | 语音转文字（OpenAI 兼容格式） |

### 3.5 使用示例

```bash
# 语音转文字（form-data 方式）
curl -X POST http://localhost:8092/v1/audio/transcriptions \
  -F "file=@audio.mp3" \
  -F "model=Qwen/Qwen3-ASR-1.7B"
```

响应示例：
```json
{
  "text": "今天天气很好，阳光明媚。"
}
```

### 3.6 客户端工具

客户端脚本位置：`pi_llm_server/clients/asr_client.py`

```bash
# 检查服务状态
python pi_llm_server/clients/asr_client.py health

# 语音转文字
python pi_llm_server/clients/asr_client.py transcribe audio.mp3

# 指定 VAD 阈值
python pi_llm_server/clients/asr_client.py transcribe audio.mp3 --vad-threshold 180

# 生成 SRT 字幕
python pi_llm_server/clients/asr_client.py transcribe audio.mp3 --save-srt

# 批量转写
python pi_llm_server/clients/asr_client.py transcribe-batch audio1.mp3 audio2.mp3 audio3.mp3
```

---

## 4. MinerU PDF 解析服务

使用 MinerU 将 PDF 文件解析为 Markdown 和图片。支持 pipeline（传统）和 hybrid/vlm（视觉大模型）两类后端。

### 4.1 依赖安装

```bash
# 需要在 MinerU 的 conda 环境中运行
conda activate mineru
pip install requests
```

### 4.2 模型源配置

MinerU 通过环境变量 `MINERU_MODEL_SOURCE` 控制模型下载来源：

| 模型源 | 说明 | 适用场景 |
|--------|------|----------|
| `huggingface`（默认） | 从 HuggingFace Hub 下载 | 可访问外网时使用 |
| `modelscope` | 从 ModelScope 下载 | **国内网络推荐** |
| `local` | 使用本地模型 | 离线环境 |

### 4.3 解析后端说明

| 后端 | 说明 | 推理方式 | 精度 |
|------|------|----------|------|
| `pipeline` | 传统 pipeline，使用检测+OCR 模型 | 本地 GPU/CPU | 通用 |
| `hybrid-auto-engine` | 混合方案，pipeline + VLM 结合（**默认**） | 本地 GPU (vLLM) | 高 |
| `vlm-auto-engine` | 纯 VLM 视觉大模型 | 本地 GPU (vLLM) | 高 |
| `hybrid-http-client` | 混合方案，VLM 通过远程 API | 远程服务器 | 高 |
| `vlm-http-client` | 纯 VLM，通过远程 API | 远程服务器 | 高 |

### 4.4 启动 API 服务

MinerU 服务需要单独启动，使用 `mineru_server.sh` 脚本。

### 4.5 API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/file_parse` | POST | 解析 PDF 文件为 Markdown+ 图片 |

### 4.6 使用示例

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

**响应**: ZIP 文件，包含：
- `content/` - Markdown 文件和图片
- `layout.pdf` - 版面分析可视化
- `spans.pdf` - 文本块可视化

### 4.7 客户端工具

客户端脚本位置：`pi_llm_server/clients/mineru_client.py`

```bash
# 基本用法（自动生成输出文件名）
python pi_llm_server/clients/mineru_client.py "文档.pdf"

# 指定输出文件和后端
python pi_llm_server/clients/mineru_client.py "文档.pdf" output.zip vlm-auto-engine

# 指定 API 地址
export MINERU_API_URL="http://localhost:8094"
```

---

## 服务管理

### 使用 service_manager.py

服务管理脚本位置：`pi_llm_server/launcher/service_manager.py`

```bash
# 启动所有后台服务
python pi_llm_server/launcher/service_manager.py start --all

# 启动单个服务
python pi_llm_server/launcher/service_manager.py start embedding
python pi_llm_server/launcher/service_manager.py start asr
python pi_llm_server/launcher/service_manager.py start reranker
python pi_llm_server/launcher/service_manager.py start mineru

# 停止所有服务
python pi_llm_server/launcher/service_manager.py stop --all

# 停止单个服务
python pi_llm_server/launcher/service_manager.py stop embedding

# 重启服务
python pi_llm_server/launcher/service_manager.py restart embedding

# 查看服务状态
python pi_llm_server/launcher/service_manager.py status
```

### 服务状态输出示例

```
============================================================
PI-LLM-Server 后台服务状态
============================================================

  ✓ Embedding Server     运行中     端口：8091  (PID: 12345)
  ✓ ASR Server          运行中     端口：8092  (PID: 12346)
  ✓ Reranker Server     运行中     端口：8093  (PID: 12347)
  ✓ MinerU Server       运行中     端口：8094  (PID: 12348)

============================================================
日志目录：/home/user/.cache/pi-llm-server/logs
PID 目录：/home/user/.cache/pi-llm-server/pids
配置文件：/home/user/.config/pi-llm-server/config.yaml
```

### 日志和 PID 文件位置

| 类型 | 位置 |
|------|------|
| 日志目录 | `~/.cache/pi-llm-server/logs/` |
| PID 目录 | `~/.cache/pi-llm-server/pids/` |
| 配置文件 | `~/.config/pi-llm-server/config.yaml` |

---

## 端口分配

| 服务 | 端口 | 启动命令 | 客户端默认 URL |
|------|------|----------|---------------|
| Embedding | 8091 | `python pi_llm_server/launcher/embedding_server.py` | `http://localhost:8091` |
| ASR | 8092 | `python pi_llm_server/launcher/asr_server.py` | `http://localhost:8092` |
| Reranker | 8093 | `python pi_llm_server/launcher/reranker_server.py` | `http://localhost:8093` |
| MinerU | 8094 | `mineru_server.sh` | `http://localhost:8094` |

---

## 模型信息

| 模型 | 参数量 | 用途 | 默认设备 |
|------|--------|------|----------|
| Qwen3-Embedding-0.6B | 0.6B | 文本向量化 | CPU |
| Qwen3-Reranker-0.6B | 0.6B | 文档相关性排序 | CPU |
| Qwen3-ASR-1.7B | 1.7B | 语音识别 | GPU |
| MinerU2.5-2509-1.2B | 1.2B | PDF 解析 (VLM) | GPU |
| PDF-Extract-Kit-1.0 | - | PDF 解析 (pipeline) | GPU |

---

**最后更新**: 2026-03-21

---

## 更新日志

### 2026-03-21
- **Embedding 服务**: 添加 `encoding_format` 参数支持，可选 `float`（默认）或 `base64`
  - `float`: 返回 JSON 格式的 float 数组
  - `base64`: 返回 base64 编码的 float32 二进制数据，减少网络传输
- **Reranker 服务**: 添加 `encoding_format` 参数（保留用于未来扩展）
- **客户端工具**: `embedding_client.py` 和 `reranker_client.py` 添加 `-e/--encoding-format` 参数
