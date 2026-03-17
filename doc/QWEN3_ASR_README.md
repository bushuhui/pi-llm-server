# vLLM Qwen3-ASR 语音识别部署指南（完整版）

## 📋 模型信息

| 项目 | 说明 |
|------|------|
| 模型名称 | Qwen3-ASR-1.7B |
| 模型路径 | `/home/bushuhui/.cache/modelscope/hub/models/Qwen/Qwen3-ASR-1.7B` |
| 参数量 | 1.7B |
| 支持语言 | 30 种语言 + 22 种中文方言 |
| 功能 | 语音识别 (ASR)、语言识别、时间戳预测 |

## 🔧 环境安装

### 方式 1: 使用 qwen-asr 包（推荐）

这是最简单的方式，由 Qwen 官方提供：

```bash
# 创建虚拟环境（推荐 Python 3.12）
conda create -n qwen3-asr python=3.12 -y
conda activate qwen3-asr

# 安装 qwen-asr 包（包含 vLLM 后端）
pip install -U qwen-asr[vllm]

# 可选：安装 FlashAttention 2 加速推理
pip install -U flash-attn --no-build-isolation
```

### 方式 2: 使用 vLLM nightly 版本

```bash
# 使用 uv 创建环境
uv venv
source .venv/bin/activate

# 安装 vLLM nightly 版本
uv pip install -U vllm --pre \
    --extra-index-url https://wheels.vllm.ai/nightly/cu129 \
    --extra-index-url https://download.pytorch.org/whl/cu129 \
    --index-strategy unsafe-best-match

# 安装音频依赖
uv pip install "vllm[audio]"
```

## 🚀 快速开始

### 方式 1: 离线推理（最快，无需启动服务）

```bash
cd 0_machine_learning_AI/LLM_API/LocalAI

# 直接使用 qwen-asr 包进行离线推理
python vllm_asr_client_qwen.py transcribe audio_s.mp3
```

这是最简单的方式，不需要启动服务，直接加载模型进行推理。

### 方式 2: 启动服务 + API 调用

#### 步骤 1: 启动服务

```bash
# 使用 qwen-asr-serve 启动（推荐）
python vllm_asr_server_qwen.py --model-path /home/bushuhui/.cache/modelscope/hub/models/Qwen/Qwen3-ASR-1.7B --port 8082

# 或直接使用 qwen-asr-serve 命令
qwen-asr-serve Qwen/Qwen3-ASR-1.7B --gpu-memory-utilization 0.8 --host 0.0.0.0 --port 8082
```

#### 步骤 2: 调用 API

```bash
# 列出模型
python vllm_asr_client_qwen.py list

# 语音转文字（通过 API）
python vllm_asr_client_qwen.py transcribe audio_s.mp3 --via-api
```

## 📁 脚本文件说明

| 脚本 | 说明 | 使用场景 |
|------|------|----------|
| `vllm_asr_server_qwen.py` | 服务启动脚本（使用 qwen-asr） | 需要启动 HTTP 服务时 |
| `vllm_asr_client_qwen.py` | 客户端（支持离线和 API） | 推荐使用离线模式 |
| `vllm_asr_server.py` | 服务启动脚本（使用 vLLM 原生） | vLLM nightly 版本 |
| `vllm_asr_client.py` | 客户端（使用 vLLM 原生） | vLLM nightly 版本 |

## 💻 Python 代码示例

### 离线推理（最简单）

```python
import torch
from qwen_asr import Qwen3ASRModel

# 加载模型
model = Qwen3ASRModel.LLM(
    model="Qwen/Qwen3-ASR-1.7B",
    gpu_memory_utilization=0.7,
    max_new_tokens=256,
)

# 执行识别
results = model.transcribe(audio="audio_s.mp3")
print(f"语言：{results[0].language}")
print(f"文本：{results[0].text}")
```

### 通过 API 调用

```python
import base64
import requests

BASE_URL = "http://localhost:8082"

# 读取音频文件
with open("audio_s.mp3", "rb") as f:
    audio_data = base64.b64encode(f.read()).decode('utf-8')

# 创建 data URL
audio_url = f"data:audio/mpeg;base64,{audio_data}"

# 发送请求
response = requests.post(
    f"{BASE_URL}/v1/chat/completions",
    json={
        "model": "Qwen/Qwen3-ASR-1.7B",
        "messages": [{
            "role": "user",
            "content": [{
                "type": "audio_url",
                "audio_url": {"url": audio_url}
            }]
        }]
    }
)

result = response.json()
print(result['choices'][0]['message']['content'])
```

### 使用 OpenAI SDK

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8082/v1",
    api_key="token-abc123"
)

with open("audio_s.mp3", "rb") as f:
    transcription = client.audio.transcriptions.create(
        model="Qwen/Qwen3-ASR-1.7B",
        file=f,
    )

print(transcription.text)
```

## 🔌 API 端点

服务启动后，提供以下 API 端点：

| 端点 | 方法 | 说明 |
|------|------|------|
| `/v1/models` | GET | 列出可用模型 |
| `/v1/chat/completions` | POST | 语音识别 (使用 audio_url) |
| `/v1/audio/transcriptions` | POST | 语音识别 (OpenAI 兼容) |

## 📊 性能参考

根据官方测试数据：

| 数据集 | Qwen3-ASR-1.7B |
|--------|----------------|
| Librispeech (en) | 1.63% / 3.38% WER |
| Fleurs (zh) | 2.41% WER |
| AISHELL-2 | 2.71% WER |
| 中文方言 | 5.10% WER |

## ❓ 常见问题

### Q: 安装时遇到依赖冲突怎么办？

建议使用独立的虚拟环境：
```bash
conda create -n qwen3-asr python=3.12 -y
conda activate qwen3-asr
pip install -U qwen-asr[vllm]
```

### Q: 如何检查 GPU 显存是否足够？

```bash
nvidia-smi
```

1.7B 模型约需 4-6GB 显存。

### Q: 如何停止服务？

```bash
# 前台运行时按 Ctrl+C
# 或查找进程并终止
pkill -f qwen-asr-serve
```

### Q: 识别结果不准确？

- 检查音频质量（推荐 16kHz 采样率）
- 确保音频语言在支持的语言列表中
- 尝试指定语言参数：`model.transcribe(audio="...", language="Chinese")`

### Q: 如何支持长音频？

设置更大的 `max_new_tokens`：
```python
model = Qwen3ASRModel.LLM(
    model="Qwen/Qwen3-ASR-1.7B",
    max_new_tokens=4096,  # 增加最大 token 数
)
```

### Q: 如何获取时间戳？

```python
from qwen_asr import Qwen3ASRModel

model = Qwen3ASRModel.from_pretrained(
    "Qwen/Qwen3-ASR-1.7B",
    dtype=torch.bfloat16,
    device_map="cuda:0",
    forced_aligner="Qwen/Qwen3-ForcedAligner-0.6B",  # 需要对齐器模型
)

results = model.transcribe(
    audio="audio.mp3",
    return_time_stamps=True,  # 返回时间戳
)

for ts in results[0].time_stamps:
    print(f"{ts.start_time:.2f}s - {ts.end_time:.2f}s: {ts.text}")
```

## 🔗 参考文档

- [Qwen3-ASR GitHub](https://github.com/QwenLM/Qwen3-ASR)
- [vLLM Qwen3-ASR 指南](https://docs.vllm.ai/projects/recipes/en/latest/Qwen/Qwen3-ASR.html)
- [ModelScope 模型页面](https://www.modelscope.cn/models/Qwen/Qwen3-ASR-1.7B)
- [HuggingFace 模型页面](https://huggingface.co/Qwen/Qwen3-ASR-1.7B)

---

**最后更新**: 2026-03-13
