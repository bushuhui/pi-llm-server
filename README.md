# PI-LLM-Server - 统一 LLM 服务网关

> 为 OpenClaw、Claude Code 等 AI 编程助手提供本地化的 Embedding、ASR、Reranker、OCR 等服务

**问题背景**: 阿里云等 Coding Plan 产品提供了大模型 API，但未包含 Embedding、Reranker、ASR、OCR 等辅助服务。这些模型通常较小，可本地部署以获得更低延迟和更好的隐私保护。

**解决方案**: PI-LLM-Server 统一管理多种本地服务，提供标准化 API 网关，为 AI 编程助手提供一站式服务接入。

---

## 目录

- [项目目的](#项目目的)
- [快速开始](#快速开始)
- [模型下载](#模型下载)
- [使用方法](#使用方法)
- [配置说明](#配置说明)
- [API 文档](#api-文档)
- [关联项目](#关联项目)

---

## 项目目的

PI-LLM-Server 旨在解决以下问题：

1. **服务碎片化**: Embedding、ASR、Reranker、OCR 等服务分散部署，管理复杂
2. **API 不统一**: 各服务接口风格不一致，集成成本高
3. **缺少队列管理**: 并发请求可能导致显存溢出或服务崩溃
4. **缺乏健康监控**: 服务异常时无法自动发现和恢复

通过本项目，您可以：

- 统一管理多个 AI 子服务，提供一致的服务入口
- 配置请求队列，防止并发过载
- 启用 API 访问控制，保护服务安全
- 实时监控服务健康状态
- 为 OpenClaw、Claude Code 等工具提供本地化服务支持

---

## 快速开始

### 1. 环境准备

详细的 conda 安装可以参考： [安装Python环境](https://github.com/bushuhui/machinelearning_notebook/blob/master/references_tips/InstallPython.md)

```bash
# 创建 Conda 环境
conda create -n pi-llm-server python=3.13
conda activate pi-llm-server
```

### 2. 安装项目

```bash
# 通过pip安装（推荐）， pip install uv
uv pip install pi-llm-server[all]

# 源码安装: 进入项目目录安装
cd pi-llm-server
uv pip install -e ".[all]"

# 方式 2: 只安装核心服务（按需选择）
uv pip install -e ".[embedding,reranker,asr,mineru]"
```

### 3. 系统依赖

#### CUDA Toolkit 安装（需要 GPU 时使用）

```bash
# 访问 NVIDIA CUDA 下载页面
# https://developer.nvidia.com/cuda-toolkit-archive

# 或使用快捷链接（例如 CUDA 12.8）
# https://developer.nvidia.com/cuda-12-8-1-download-archive

# 安装后创建符号链接（如需要）
cd /usr/bin
sudo ln -s /usr/local/cuda-12.8/bin/nvcc nvcc

# 设置环境变量，把如下的内容放入 /etc/bash.bashrc (如果使用的是bash，其他的sh类似)
export CUDA_HOME=/usr/local/cuda-12.8
export PATH=$CUDA_HOME/bin:$CUDA_HOME/nvvm/bin:$PATH
export CPLUS_INCLUDE_PATH=$CUDA_HOME/include:$CPLUS_INCLUDE_PATH
export LIBRARY_PATH=$CUDA_HOME/lib64:$LIBRARY_PATH
export LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH
```


---

## 模型下载

### 方式 1: 使用 ModelScope 下载（推荐国内用户）

```bash
# Embedding 模型
modelscope download --model unsloth/Qwen3-Embedding-0.6B

# ASR 模型
modelscope download --model Qwen/Qwen3-ASR-1.7B

# Reranker 模型
modelscope download --model Qwen/Qwen3-Reranker-0.6B
```

### 方式 2: 模型存储位置

ModelScope 模型默认下载到：
```
~/.cache/modelscope/hub/models/<组织>/<模型名>
```

例如：
- Embedding: `~/.cache/modelscope/hub/models/unsloth/Qwen3-Embedding-4B`
- ASR: `~/.cache/modelscope/hub/models/Qwen/Qwen3-ASR-1.7B`
- Reranker: `~/.cache/modelscope/hub/models/Qwen/Qwen3-Reranker-0.6B`

### 方式 3: 使用 HuggingFace（需要网络条件）

```bash
# 使用 huggingface-cli 下载
huggingface-cli download unsloth/Qwen3-Embedding-4B --local-dir ~/.cache/huggingface/hub/models/unsloth/Qwen3-Embedding-4B
```

---

## 使用方法

### 1. 配置目录结构

首次运行时会自动创建配置文件，或手动创建：

```bash
# 创建配置目录
mkdir -p ~/.config/pi-llm-server

# 复制示例配置
cp examples/config.example.yaml ~/.config/pi-llm-server/config.yaml
```

### 2. 编辑配置文件

如果使用的模型和上面下载的不同，需要编辑 `~/.config/pi-llm-server/config.yaml`，主要配置项：

```yaml
server:
  host: "0.0.0.0"
  port: 8090

auth:
  enabled: true
  tokens:
    - "your-api-token-here"

services:
  embedding:
    enabled: true
    base_url: "http://127.0.0.1:8091"
  asr:
    enabled: true
    base_url: "http://127.0.0.1:8092"
  reranker:
    enabled: true
    base_url: "http://127.0.0.1:8093"
  mineru:
    enabled: true
    base_url: "http://127.0.0.1:8094"
```

### 3. 启动服务

```bash
# 启动后台服务 + 网关（一站式启动）
python -m pi_llm_server start-all
```


#### 方式 A: 启动统一网关

```bash
# 使用命令行工具启动网关服务
pi-llm-server

# 或指定配置
pi-llm-server --config ~/.config/pi-llm-server/config.yaml --port 8090

# 后台运行
nohup pi-llm-server > ~/.cache/pi-llm-server/logs/gateway.log 2>&1 &
```

#### 方式 B: 启动子服务

```bash
# Embedding 服务
python pi_llm_server/launcher/embedding_server.py --model-path ~/.cache/modelscope/hub/models/unsloth/Qwen3-Embedding-0.6B --device cpu

# ASR 服务（需要 GPU）
python pi_llm_server/launcher/asr_server.py --model-path ~/.cache/modelscope/hub/models/Qwen/Qwen3-ASR-1.7B

# Reranker 服务
python pi_llm_server/launcher/reranker_server.py --model-path ~/.cache/modelscope/hub/models/Qwen/Qwen3-Reranker-0.6B --device cpu

# MinerU 服务
# 注意：MinerU 需要 GPU 支持，建议使用独立显存（9GB 以上）
./mineru_server.sh start --python-path /path/to/python
```

#### 方式 C: 使用服务管理器

```bash
# 启动所有服务
python pi_llm_server/launcher/service_manager.py start --all

# 查看服务状态
python pi_llm_server/launcher/service_manager.py status

# 停止所有服务
python pi_llm_server/launcher/service_manager.py stop --all
```

### 4. 验证服务

```bash
# 健康检查
curl http://localhost:8090/health

# 列出可用模型
curl -H "Authorization: Bearer YOUR_TOKEN" http://localhost:8090/v1/models
# 例如
curl -H "Authorization: Bearer sk-5f8b839908d14561590b70227c72ca86" http://localhost:8090/v1/models

# 生成 Embedding
curl -X POST http://localhost:8090/v1/embeddings \
  -H "Authorization: Bearer sk-your-token" \
  -H "Content-Type: application/json" \
  -d '{"input": "你好，世界！"}'
```

### 5. Python 客户端示例

项目提供了完整的 Python 使用示例 [`examples/basic_usage.py`](examples/basic_usage.py)：

```python
"""
PI-LLM-Server 基本使用示例

本示例展示如何使用 Python 客户端调用 PI-LLM-Server 提供的服务。
"""

import httpx

# 服务地址
BASE_URL = "http://127.0.0.1:8090"

# API Token（从配置文件获取）
API_TOKEN = "sk-5f8b839908d14561590b70227c72ca86"

# 请求头
HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json",
}


def check_health():
    """检查服务健康状态"""
    response = httpx.get(f"{BASE_URL}/health")
    print("健康状态:", response.json())
    return response.json()


def list_models():
    """列出所有可用模型"""
    response = httpx.get(f"{BASE_URL}/v1/models", headers=HEADERS)
    print("可用模型:", response.json())
    return response.json()


def get_status():
    """获取服务详细状态"""
    response = httpx.get(f"{BASE_URL}/status", headers=HEADERS)
    print("服务状态:", response.json())
    return response.json()


def generate_embedding(text: str, model: str = "unsloth/Qwen3-Embedding-0.6B"):
    """生成文本 embedding"""
    payload = {
        "model": model,
        "input": [text],
    }
    response = httpx.post(
        f"{BASE_URL}/v1/embeddings",
        json=payload,
        headers=HEADERS,
        timeout=60,
    )
    result = response.json()
    print(f"Embedding 维度：{len(result['data'][0]['embedding'])}")
    return result


def rerank_documents(query: str, documents: list):
    """对文档进行重排序"""
    payload = {
        "query": query,
        "documents": documents,
    }
    response = httpx.post(
        f"{BASE_URL}/v1/rerank",
        json=payload,
        headers=HEADERS,
        timeout=120,
    )
    result = response.json()
    print("重排序结果:")
    for item in result.get("results", []):
        print(f"  文档 {item['index']}: 得分 {item['relevance_score']:.4f}")
    return result


def transcribe_audio(audio_path: str):
    """语音转文字 (ASR)"""
    # 读取音频文件
    with open(audio_path, "rb") as f:
        audio_data = f.read()

    # 使用 multipart/form-data 上传
    files = {"file": ("audio.mp3", audio_data, "audio/mpeg")}
    response = httpx.post(
        f"{BASE_URL}/v1/audio/transcriptions",
        files=files,
        headers={"Authorization": f"Bearer {API_TOKEN}"},
        timeout=300,
    )
    result = response.json()
    print("转录结果:", result.get("text", ""))
    return result


def parse_pdf(pdf_path: str):
    """解析 PDF 文件 (MinerU/OCR)"""
    # 读取 PDF 文件
    with open(pdf_path, "rb") as f:
        pdf_data = f.read()

    files = {"files": ("document.pdf", pdf_data, "application/pdf")}
    response = httpx.post(
        f"{BASE_URL}/v1/ocr/parser",
        files=files,
        headers={"Authorization": f"Bearer {API_TOKEN}"},
        timeout=600,
    )
    print(f"PDF 解析完成，ZIP 大小：{len(response.content)} bytes")
    return response.content


if __name__ == "__main__":
    # 运行所有测试
    check_health()
    list_models()
    generate_embedding("你好，世界！")
    rerank_documents("深度学习", [
        "人工智能是计算机科学的一个分支",
        "机器学习是实现人工智能的方法之一",
        "深度学习是机器学习的子集",
    ])
    # transcribe_audio("data/audio_s.mp3")  # ASR 测试
    # parse_pdf("data/InfoLOD.pdf")         # PDF 解析测试
```

**运行示例**:

```bash
cd pi-llm-server
python examples/basic_usage.py
```

示例会自动使用 `data/` 目录下的测试文件：
- `data/audio_s.mp3` - ASR 语音识别测试
- `data/InfoLOD.pdf` - PDF 解析测试

---

## 配置说明

### 配置文件位置

- 默认路径：`~/.config/pi-llm-server/config.yaml`
- 可通过 `--config` 参数指定其他路径

### 主要配置项

| 配置项 | 说明 | 默认值 |
|--------|------|--------|
| `server.host` | 监听地址 | `0.0.0.0` |
| `server.port` | 监听端口 | `8090` |
| `server.workers` | 工作进程数 | `4` |
| `server.log_level` | 日志级别 | `info` |
| `auth.enabled` | 是否启用认证 | `true` |
| `auth.tokens` | 有效 Token 列表 | `[]` |
| `queue.enabled` | 是否启用队列 | `true` |
| `services.*.enabled` | 是否启用子服务 | `true` |
| `services.*.base_url` | 子服务地址 | 需配置 |

### 队列配置策略

| 服务 | 并发数 | 队列大小 | 超时 (秒) | 说明 |
|------|--------|----------|-----------|------|
| embedding | 4 | 200 | 60 | CPU 多核并行 |
| reranker | 4 | 200 | 120 | CPU 多核并行 |
| asr | 1 | 50 | 600 | GPU 推理顺序处理 |
| mineru | 1 | 20 | 1800 | PDF 解析耗时 |

### 端口分配

| 服务 | 端口 | 说明 |
|------|------|------|
| 统一网关 | 8090 | 主入口 |
| Embedding | 8091 | 文本向量化 |
| ASR | 8092 | 语音识别 |
| Reranker | 8093 | 文档重排序 |
| MinerU | 8094 | PDF 解析 |

---

## API 文档

### 端点列表

| 端点 | 方法 | 说明 | 认证 |
|------|------|------|------|
| `/` | GET | 欢迎信息 | 否 |
| `/health` | GET | 健康检查 | 否 |
| `/status` | GET | 详细状态 | 是 |
| `/v1/models` | GET | 可用模型列表 | 可选 |
| `/v1/embeddings` | POST | 生成 Embedding | 是 |
| `/v1/rerank` | POST | 文档重排序 | 是 |
| `/v1/audio/transcriptions` | POST | 语音转文字 | 是 |
| `/v1/ocr/parser` | POST | PDF 解析 | 是 |
| `/docs` | GET | Swagger 文档 | 否 |

### API 使用示例

#### 1. 生成 Embedding

**请求**:
```bash
curl -X POST http://localhost:8090/v1/embeddings \
  -H "Authorization: Bearer sk-your-token" \
  -H "Content-Type: application/json" \
  -d '{
    "model": "unsloth/Qwen3-Embedding-0.6B",
    "input": ["你好，世界！"]
  }'
```

**响应**:
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

#### 2. 文档重排序 (Rerank)

**请求**:
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
    ]
  }'
```

**响应**:
```json
{
  "model": "Qwen/Qwen3-Reranker-0.6B",
  "results": [
    {"index": 2, "document": "深度学习是机器学习的子集", "relevance_score": 0.8234},
    {"index": 1, "document": "机器学习是实现人工智能的方法之一", "relevance_score": 0.1523},
    {"index": 0, "document": "人工智能是计算机科学的一个分支", "relevance_score": 0.0821}
  ]
}
```

#### 3. 语音转文字 (ASR)

**请求**:
```bash
curl -X POST http://localhost:8090/v1/audio/transcriptions \
  -H "Authorization: Bearer sk-your-token" \
  -F "file=@audio.mp3"
```

**响应**:
```json
{
  "text": "大家好，这里是最佳拍档..."
}
```

#### 4. PDF 解析 (MinerU/OCR)

**请求**:
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

**响应**: ZIP 文件，包含：
- `markdown/` - 解析后的 Markdown 文件
- `images/` - 提取的图片
- 其他中间文件

**参数说明**:
| 参数 | 默认值 | 说明 |
|------|--------|------|
| `backend` | pipeline | 解析后端：pipeline/hybrid-auto-engine/vlm-auto-engine |
| `parse_method` | auto | 解析方法：auto/txt/ocr |
| `lang_list` | ch | 语言：ch/en/korean/japan |
| `return_md` | true | 返回 Markdown |
| `return_images` | true | 返回图片 |

---

## 关联项目

### VLLM

[VLLM](https://github.com/vllm-project/vllm) 是一个高吞吐、大吞吐量的 LLM 推理和服务引擎。

- **关系**: PI-LLM-Server 使用 VLLM 作为 ASR 服务的推理后端
- **区别**: VLLM 专注于 LLM 推理引擎，PI-LLM-Server 专注于服务集成和统一管理
- **协作**: 可以结合使用，VLLM 提供底层推理能力，PI-LLM-Server 提供上层服务编排

### LocalAI

[LocalAI](https://github.com/mudler/LocalAI) 是一个开源的 OpenAI API 替代品，支持多种模型。

- **关系**: LocalAI 也是提供本地化 AI 服务的项目
- **区别**:
  - LocalAI 是"All-in-One"的大而全方案，支持更多模型类型
  - PI-LLM-Server 更轻量，专注于 Embedding、ASR、Reranker、OCR 等辅助服务
  - PI-LLM-Server 更适合作为其他服务的补充，而非替代
- **协作**: 可以与 LocalAI 并存，各自负责不同的服务场景

### 阿里云百炼/通义灵码

- **背景**: 提供大模型 API，但缺少 Embedding、Reranker 等辅助服务
- **PI-LLM-Server 定位**: 补充这些本地可部署的小模型服务，提供更快的响应速度
- **优势**:
  - 本地部署，零网络延迟
  - 数据隐私，敏感信息不出内网
  - 成本更低，无需调用付费 API

### 典型架构

```
┌─────────────────┐
│  AI 编程助手     │
│ OpenClaw/Code   │
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ PI-LLM-Server   │ ← 统一网关 (8090)
│  网关服务        │
└────────┬────────┘
         │
    ┌────┼────┬─────────┬──────────┐
    ▼    ▼    ▼         ▼          ▼
┌────────┐ ┌─────┐ ┌────────┐ ┌────────┐
│Embedding│ │ ASR │ │Reranker│ │ MinerU │
│ :8091  │ │:8092│ │ :8093  │ │ :8094  │
└────────┘ └─────┘ └────────┘ └────────┘
     │        │        │          │
     ▼        ▼        ▼          ▼
┌─────────┐ ┌─────┐ ┌────────┐ ┌────────┐
│Qwen3-   │ │Qwen3│ │Qwen3-  │ │MinerU  │
│Embedding│ │-ASR │ │Reranker│ │VLM     │
└─────────┘ └─────┘ └────────┘ └────────┘
```

---

## 故障排查

### 常见问题

1. **服务启动失败**: 检查端口是否被占用，使用 `netstat -tlnp | grep 8090` 查看

2. **模型加载失败**: 确认模型路径正确，检查 `~/.cache/modelscope/hub/models/` 目录

3. **GPU 显存不足**: 调整 `gpu_memory_utilization` 参数，降低显存使用率

4. **CUDA 版本不匹配**: 检查 PyTorch CUDA 版本与系统 CUDA 是否一致


### 日志位置

```bash
# 网关日志
~/.cache/pi-llm-server/logs/gateway.log

# 子服务日志
~/.cache/pi-llm-server/logs/<service>.log

# 查看最新日志
tail -f ~/.cache/pi-llm-server/logs/gateway.log
```

---

## License

MIT License

