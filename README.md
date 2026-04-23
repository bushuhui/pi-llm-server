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
- [命令行工具](#命令行工具)
- [配置说明](#配置说明)
- [服务守护进程](#服务守护进程)
- [API 文档](#api-文档)
- [项目结构](#项目结构)
- [关联项目](#关联项目)
- [故障排查](#故障排查)

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

首次运行时会自动创建配置文件，无需手动复制：

```bash
# 首次运行时会自动创建配置目录和配置文件
# 配置文件位置：~/.config/pi-llm-server/config.yaml
```

如需手动配置，可以从包内复制示例配置：

```bash
# 创建配置目录
mkdir -p ~/.config/pi-llm-server

# 从已安装的包中复制示例配置（如果自动创建失败）
cp $(python -c "from pathlib import Path; import pi_llm_server; print(Path(pi_llm_server.__file__).parent / 'examples' / 'config.example.yaml')") ~/.config/pi-llm-server/config.yaml
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

#### 方式 A: 一站式启动（推荐）

```bash
# 启动所有服务（后台服务 + 统一网关）
pi-llm-server start-all

# 查看所有服务状态
pi-llm-server status

# 停止所有服务
pi-llm-server stop-all
```

#### 方式 B: 仅启动统一网关

#### 方式 B: 仅启动统一网关

```bash
# 使用命令行工具启动网关服务
pi-llm-server

# 或指定配置
pi-llm-server --config ~/.config/pi-llm-server/config.yaml --port 8090

# 后台运行
nohup pi-llm-server > ~/.cache/pi-llm-server/logs/gateway.log 2>&1 &
```

#### 方式 C: 后台服务管理

```bash
# 启动所有后台服务
pi-llm-server services start --all

# 查看服务状态
pi-llm-server services status

# 停止所有后台服务
pi-llm-server services stop --all

# 单独启动/停止某个服务
pi-llm-server services start embedding
pi-llm-server services stop asr
```

#### 方式 D: 使用 systemd 服务（生产环境推荐）

**自动安装（推荐）**：

```bash
# 运行自动配置脚本，会检测当前环境并生成合适的配置
cd pi-llm-server
bash pi_llm_server/examples/install-service.sh
```

脚本会自动：
- 检测当前用户和组
- 检测 Python/Conda 环境路径
- 检测项目安装模式（pip 或源码）
- 生成合适的 service 文件并安装

**手动配置**：

```bash
# 1. 复制模板文件
cp pi_llm_server/examples/pi-llm-server.service.template /tmp/pi-llm-server.service

# 2. 编辑模板，替换以下占位符：
#    - YOUR_USERNAME -> 你的用户名（运行 whoami 获取）
#    - YOUR_GROUPNAME -> 你的用户组（运行 id -gn 获取）
#    - /path/to/python -> Python 路径（运行 which python 获取）
#    - WorkingDirectory（源码模式需要，pip 安装可删除此行）
nano /tmp/pi-llm-server.service

# 3. 安装到 systemd
sudo mv /tmp/pi-llm-server.service /etc/systemd/system/pi-llm-server.service
sudo systemctl daemon-reload

# 4. 管理服务
sudo systemctl start pi-llm-server
sudo systemctl enable pi-llm-server
```

**服务管理命令**：

```bash
# 启动服务
sudo systemctl start pi-llm-server

# 设置开机自启
sudo systemctl enable pi-llm-server

# 查看服务状态
sudo systemctl status pi-llm-server

# 查看日志
sudo journalctl -u pi-llm-server -f

# 停止服务
sudo systemctl stop pi-llm-server

# 卸载服务
sudo systemctl disable pi-llm-server
sudo rm /etc/systemd/system/pi-llm-server.service
sudo systemctl daemon-reload
```

#### 方式 E: 手动启动子服务（开发调试用）

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

项目提供了完整的 Python 使用示例 [`pi_llm_server/examples/basic_usage.py`](pi_llm_server/examples/basic_usage.py)：

**主要功能**:
- 健康检查和服务状态查询
- 生成 Embedding（支持 float 和 base64 编码格式）
- 文档重排序（Reranker）
- 语音转文字（ASR）
- PDF 解析（MinerU/OCR）

**运行示例**:

```bash
# 确保服务已启动
pi-llm-server status

# 运行示例程序
python pi_llm_server/examples/basic_usage.py
```

**示例代码结构**:

```python
"""
PI-LLM-Server 基本使用示例

本示例展示如何使用 Python 客户端调用 PI-LLM-Server 提供的服务。
"""

import httpx
import base64

# 服务地址
BASE_URL = "http://127.0.0.1:8090"

# API Token（从配置文件获取）
API_TOKEN = "sk-5f8b839908d14561590b70227c72ca86"

# 请求头
HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json",
}


def generate_embedding(text: str, model: str = "unsloth/Qwen3-Embedding-0.6B", encoding_format: str = "float"):
    """生成文本 embedding

    Args:
        text: 输入文本
        model: 模型名称
        encoding_format: 编码格式，支持 "float" 或 "base64"
    """
    payload = {
        "model": model,
        "input": [text],
        "encoding_format": encoding_format,
    }
    response = httpx.post(
        f"{BASE_URL}/v1/embeddings",
        json=payload,
        headers=HEADERS,
        timeout=60,
    )
    result = response.json()

    if encoding_format == "base64":
        # base64 格式，解码并显示预览
        import struct
        embedding_data = result['data'][0]['embedding']
        decoded = base64.b64decode(embedding_data)
        float_count = len(decoded) // 4  # float32 占 4 字节
        floats = struct.unpack(f'{float_count}f', decoded)
        print(f"Embedding 维度：{len(floats)} (base64 编码)")
        print(f"向量预览 (前 10 个值): {floats[:10]}")
    else:
        # float 格式
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
    with open(audio_path, "rb") as f:
        audio_data = f.read()

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
    with open(pdf_path, "rb") as f:
        pdf_data = f.read()

    files = {"files": ("document.pdf", pdf_data, "application/pdf")}
    response = httpx.post(
        f"{BASE_URL}/v1/ocr/parser",
        files=files,
        headers={"Authorization": f"Bearer {API_TOKEN}"},
        timeout=600,
    )
    print(f"PDF 解析完成，ZIP 大小：{len(response.content)} bytes ({len(response.content) / 1024 / 1024:.2f} MB)")
    return response.content
```

**测试数据文件**:

示例程序使用以下测试文件（需自行准备）：
- `data/audio_s.mp3` - ASR 语音识别测试
- `data/InfoLOD.pdf` - PDF 解析测试

---

## 命令行工具

安装后可以使用 `pi-llm-server` 命令：

```bash
# 查看所有命令
pi-llm-server --help

# 一站式启动所有服务（后台服务 + 网关）
pi-llm-server start-all

# 一站式停止所有服务
pi-llm-server stop-all

# 查看所有服务状态
pi-llm-server status

# 后台服务管理（start/stop/restart/status）
pi-llm-server services start --all
pi-llm-server services stop --all
pi-llm-server services status

# 仅启动网关（默认行为）
pi-llm-server
pi-llm-server --port 8090
pi-llm-server --config ~/.config/pi-llm-server/config.yaml
```

### 命令说明

| 命令 | 说明 |
|------|------|
| `start-all` | 一站式启动所有服务（后台服务 + 统一网关） |
| `stop-all` | 一站式停止所有服务（网关 + 后台服务） |
| `status` | 查看所有服务状态（网关 + 后台服务） |
| `services` | 后台服务管理（start/stop/restart/status） |
| 无命令 | 仅启动统一网关（默认行为） |

---

## 配置说明

### 配置文件位置

- 默认路径：`~/.config/pi-llm-server/config.yaml`
- 可通过 `--config` 参数指定其他路径
- 首次运行时会自动从包内复制示例配置文件

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
| `queue.default.max_size` | 默认队列大小 | `100` |
| `queue.default.max_concurrent` | 默认并发数 | `1` |
| `queue.default.timeout_seconds` | 默认超时时间 | `300` |
| `services.*.enabled` | 是否启用子服务 | `true` |
| `services.*.base_url` | 子服务地址 | 需配置 |
| `health_check.enabled` | 是否启用健康检查 | `true` |
| `health_check.interval_seconds` | 健康检查间隔 | `30` |
| `health_check.unhealthy_threshold` | 不健康判定阈值 | `3` |

### 配置文件示例

完整配置示例请参考 [`pi_llm_server/examples/config.example.yaml`](pi_llm_server/examples/config.example.yaml)：

```yaml
# =============================================
# 服务基础配置
# =============================================
server:
  host: "0.0.0.0"
  port: 8090
  workers: 4
  log_level: "info"

# =============================================
# API 访问控制
# =============================================
auth:
  enabled: true
  tokens:
    - "sk-5f8b839908d14561590b70227c72ca86"

# =============================================
# 请求队列配置 - 差异化策略
# =============================================
queue:
  enabled: true
  default:
    max_size: 100
    max_concurrent: 1
    timeout_seconds: 300
  services:
    embedding:
      max_concurrent: 1
      max_size: 200
      timeout_seconds: 60
    reranker:
      max_concurrent: 4
      max_size: 200
      timeout_seconds: 120
    asr:
      max_concurrent: 1
      max_size: 50
      timeout_seconds: 600
    mineru:
      max_concurrent: 1
      max_size: 20
      timeout_seconds: 1800

# =============================================
# 子服务配置
# =============================================
services:
  embedding:
    enabled: true
    base_url: "http://127.0.0.1:8091"
    models:
      - id: "unsloth/Qwen3-Embedding-0.6B"
        path: "~/.cache/modelscope/hub/models/unsloth/Qwen3-Embedding-0.6B"
        device: "cuda"
  asr:
    enabled: true
    base_url: "http://127.0.0.1:8092"
    models:
      - id: "Qwen/Qwen3-ASR-1.7B"
        path: "~/.cache/modelscope/hub/models/Qwen/Qwen3-ASR-1.7B"
        gpu_memory_utilization: 0.9
  reranker:
    enabled: true
    base_url: "http://127.0.0.1:8093"
    models:
      - id: "Qwen/Qwen3-Reranker-0.6B"
        path: "~/.cache/modelscope/hub/models/Qwen/Qwen3-Reranker-0.6B"
        device: "cpu"
  mineru:
    enabled: true
    base_url: "http://127.0.0.1:8094"
    config:
      vram: "9000"
      model_source: "modelscope"

# =============================================
# 健康检查配置
# =============================================
health_check:
  enabled: true
  interval_seconds: 30
  timeout_seconds: 10
  unhealthy_threshold: 3
```

### 队列配置策略

| 服务 | 并发数 | 队列大小 | 超时 (秒) | 说明 |
|------|--------|----------|-----------|------|
| embedding | 1 | 200 | 60 | GPU 推理，顺序处理避免显存溢出 |
| reranker | 4 | 200 | 120 | CPU 多核并行 |
| asr | 1 | 50 | 600 | GPU 推理，顺序处理避免显存溢出 |
| mineru | 1 | 20 | 1800 | PDF 解析耗时，顺序处理 |

### 端口分配

| 服务 | 端口 | 说明 |
|------|------|------|
| 统一网关 | 8090 | 主入口 |
| Embedding | 8091 | 文本向量化 |
| ASR | 8092 | 语音识别 |
| Reranker | 8093 | 文档重排序 |
| MinerU | 8094 | PDF 解析 |

---

## 服务守护进程

PI-LLM-Server 提供独立的服务守护进程 (`service_daemon.py`)，自动监控各子服务健康状态并在服务异常时自动重启。

### 主要功能

| 功能 | 说明 |
|------|------|
| **推理健康检测** | 使用实际 API 调用验证服务可用，而非仅 HTTP 端点响应 |
| **自动重启** | 连续失败达到阈值（默认 3 次）后自动重启服务 |
| **服务级冷却期** | 防止服务启动期间误判为失败而触发重启 |
| **最大重启限制** | 达到上限（默认 3 次）后停止自动重启，等待人工干预 |
| **状态持久化** | 重启计数和状态保存在 JSON 文件，防止重启循环 |

### 检测流程

```
1. HTTP 健康检查 → 调用 /health 端点
2. 推理检测 → 调用实际 API（使用测试数据）
3. 失败计数 → 连续失败达到阈值触发重启
4. 冷却期 → 重启后一段时间内不进行检测
```

### 推理检测测试数据

| 服务 | 测试数据 | 说明 |
|------|----------|------|
| Embedding | `"健康检测测试"` | 测试文本调用 Embedding API |
| ASR | 1 秒 WAV 音频 | 16kHz, mono, 16bit 测试音频 |
| Reranker | 测试查询 + 文档列表 | 重排序 API 测试 |
| MinerU | 200x50 PNG 图片 | 图片解析测试 |

### 守护进程管理

```bash
# 一站式启动（守护进程随 start-all 自动启动）
pi-llm-server start-all

# 单独启动守护进程
pi-llm-server services start daemon

# 查看守护进程状态
pi-llm-server status

# 停止守护进程
pi-llm-server services stop daemon
```

### 守护进程配置

配置文件 (`config.yaml`) 新增 `daemon` 配置节：

```yaml
daemon:
  enabled: true                # 是否启用守护进程
  check_interval: 30           # 健康检查间隔（秒）
  http_timeout: 10             # HTTP 检查超时（秒）
  inference_timeout: 5         # 推理检测超时（秒）
  unhealthy_threshold: 3       # 连续失败判定阈值
  restart_cooldown: 120        # 默认重启后冷却时间（秒）
  max_restart_attempts: 3      # 单次最多重启尝试次数
  services:                    # 服务级别配置覆盖
    embedding:
      restart_cooldown: 60     # 模型加载快
      inference_timeout: 3     # 短文本推理快
    asr:
      restart_cooldown: 180    # GPU 模型加载慢
      inference_timeout: 10    # 音频转写需要时间
    reranker:
      restart_cooldown: 60     # CPU 模型加载较快
      inference_timeout: 3     # 短查询推理快
    mineru:
      restart_cooldown: 120    # PDF 解析服务启动需要时间
      inference_timeout: 30    # 图片解析需要时间
```

### 配置项说明

| 配置项 | 默认值 | 说明 |
|--------|--------|------|
| `enabled` | `true` | 是否启用守护进程 |
| `check_interval` | `30` | 健康检查间隔（秒） |
| `http_timeout` | `10` | HTTP 检查超时（秒） |
| `inference_timeout` | `5` | 推理检测超时（秒） |
| `unhealthy_threshold` | `3` | 连续失败多少次判定为不健康 |
| `restart_cooldown` | `120` | 重启后冷却时间（秒），期间不检测 |
| `max_restart_attempts` | `3` | 单次最多重启尝试，达到上限后停止 |

### 服务级冷却时间

各服务根据启动时间配置不同的冷却期：

| 服务 | 冷却时间 | 说明 |
|------|----------|------|
| Embedding | 60 秒 | CPU 模型加载快 |
| ASR | 180 秒 | GPU 模型加载慢，需要 3 分钟 |
| Reranker | 60 秒 | CPU 模型加载较快 |
| MinerU | 120 秒 | PDF 解析服务启动需要时间 |

### 日志和状态文件

```bash
# 守护进程日志
~/.cache/pi-llm-server/logs/daemon.log

# 守护进程 PID 文件
~/.cache/pi-llm-server/pids/daemon.pid

# 守护进程状态文件（重启计数等）
~/.cache/pi-llm-server/daemon_state.json

# 查看守护进程日志
tail -f ~/.cache/pi-llm-server/logs/daemon.log
```

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

**支持的文件类型**:
| 类型 | 扩展名 | 说明 |
|------|--------|------|
| PDF | `.pdf` | 原生 PDF 文档 |
| 图片 | `.jpg`, `.jpeg`, `.png` | 图片文件（自动转换为 PDF 处理） |
| Word 文档 | `.docx`, `.doc` | 需要安装 libreoffice 进行转换 |
| PPT 演示文稿 | `.pptx`, `.ppt` | 需要安装 libreoffice 进行转换 |
| Excel 表格 | `.xlsx`, `.xls` | 需要安装 libreoffice 进行转换 |

**Office 文档转换依赖**:
```bash
# Ubuntu/Debian
sudo apt-get install libreoffice

# macOS (使用 Homebrew)
brew install libreoffice

# CentOS/RHEL
sudo yum install libreoffice
```

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

## 项目结构

```
pi-llm-server/
├── pi_llm_server/              # 主包目录
│   ├── __init__.py
│   ├── __main__.py             # python -m pi_llm_server 入口
│   ├── cli.py                  # 命令行工具（一站式启动）
│   ├── server.py               # FastAPI 应用主服务
│   ├── config.py               # 配置管理
│   ├── launcher/               # 子服务启动器
│   │   ├── embedding_server.py
│   │   ├── asr_server.py
│   │   ├── reranker_server.py
│   │   ├── service_manager.py  # 服务管理器
│   │   ├── service_daemon.py   # 服务守护进程（自动监控重启）
│   │   └── mineru_server.sh
│   ├── services/               # 服务实现
│   │   ├── embedding.py
│   │   ├── asr.py
│   │   ├── reranker.py
│   │   └── mineru.py
│   ├── clients/                # 子服务客户端
│   │   ├── embedding_client.py
│   │   ├── asr_client.py
│   │   ├── reranker_client.py
│   │   └── mineru_client.py
│   ├── utils/                  # 工具函数
│   │   ├── logging.py
│   │   └── queue_manager.py
│   └── examples/               # 示例文件和配置
│       ├── __init__.py
│       ├── basic_usage.py      # Python 客户端使用示例
│       ├── config.example.yaml # 配置文件示例
│       ├── install-service.sh  # systemd 服务自动安装脚本
│       └── pi-llm-server.service.template # systemd 服务模板
├── README.md                   # 项目说明
├── CHANGELOG.md                # 变更日志
├── pyproject.toml              # 项目配置和依赖
└── setup.py                    # 安装脚本（已废弃，使用 pyproject.toml）
```

### 示例文件说明

| 文件 | 说明 |
|------|------|
| `examples/basic_usage.py` | Python 客户端调用示例，包含 Embedding、Reranker、ASR、PDF 解析等完整示例 |
| `examples/config.example.yaml` | 配置文件模板，复制为 `~/.config/pi-llm-server/config.yaml` 使用 |
| `examples/install-service.sh` | systemd 服务自动安装脚本，推荐方式使用此脚本安装服务 |
| `examples/pi-llm-server.service.template` | systemd 服务模板文件，供手动配置时参考 |

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

# 守护进程日志
~/.cache/pi-llm-server/logs/daemon.log

# 查看最新日志
tail -f ~/.cache/pi-llm-server/logs/gateway.log
```

---

## License

MIT License

