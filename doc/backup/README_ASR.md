# Qwen3-ASR 语音识别服务使用指南

## 目录

- [快速开始](#快速开始)
- [短音频转写（<2 分钟）](#短音频转写 -2-分钟)
- [长音频转写（>2 分钟）](#长音频转写 -2-分钟)
- [API 说明](#api-说明)
- [常见问题](#常见问题)

---

## 快速开始

### 1. 安装依赖

```bash
# 安装基础 ASR 依赖
pip install -U qwen-asr[vllm]

# 安装长音频处理依赖（可选）
pip install qwen3-asr-toolkit silero-vad dashscope
```

### 2. 启动 ASR 服务

```bash
# 使用本地模型
python asr_server.py --model-path /path/to/Qwen3-ASR-1.7B --port 8092

# 或使用 HuggingFace 模型名
python asr_server.py --model-path Qwen/Qwen3-ASR-1.7B --port 8092
```

---

## 短音频转写（<2 分钟）

适用于 2 分钟以内的短音频文件。

### 方法 1: 使用 chat/completions API

```bash
python asr_client.py transcribe audio.mp3
```

### 方法 2: 使用 transcription API

```bash
python asr_client.py transcribe audio.mp3 --api transcription
```

### 方法 3: 使用 OpenAI SDK

```bash
python asr_client.py transcribe audio.mp3 --api sdk
```

---

## 长音频转写（>2 分钟）

**超过 2 分钟的音频请使用此方法**，支持任意时长音频转写。

### 原理

Qwen3-ASR Toolkit 通过以下方式处理长音频：

1. **VAD 语音活动检测** - 自动识别音频中的语音段和静音段
2. **智能分割** - 在静音处分割，避免切断词语
3. **并行转写** - 多线程同时处理多个音频片段（使用 DashScope API）
4. **结果合并** - 自动拼接各片段结果，生成完整转写

### 前提条件

需要 DashScope API Key：
- 访问 https://dashscope.aliyun.com/ 注册账号
- 获取 API Key

### 基本用法

```bash
# 转写长音频（需要 API Key）
python asr_client.py transcribe-long-audio audio.mp3 --api-key sk-xxx

# 或使用环境变量
export DASHSCOPE_API_KEY=sk-xxx
python asr_client.py transcribe-long-audio audio.mp3
```

### 高级选项

```bash
# 设置 API Key（或使用环境变量）
export DASHSCOPE_API_KEY=sk-xxx

# 使用 8 个线程并行处理（加快速度）
python asr_client.py transcribe-long-audio audio.mp3 --threads 8

# 生成 SRT 字幕文件
python asr_client.py transcribe-long-audio audio.mp3 --save-srt

# 添加上下文术语（帮助识别专业词汇）
python asr_client.py transcribe-long-audio audio.mp3 --context "AI,LLM,transformer"

# 自定义 VAD 分割阈值（默认 120 秒）
python asr_client.py transcribe-long-audio audio.mp3 --vad-threshold 180
```

### 完整参数说明

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `audio_file` | 音频文件路径（必填） | - |
| `--api-key, -k` | DashScope API Key（必填，也可使用环境变量） | - |
| `--context, -c` | 上下文术语，帮助 ASR 识别专业词汇 | 空 |
| `--threads, -j` | 并行处理线程数 | 4 |
| `--vad-threshold, -d` | VAD 分割阈值（秒） | 120 |
| `--save-srt, -srt` | 生成 SRT 字幕文件 | false |

---

## API 说明

### 语音转写 API

**端点**: `POST /v1/chat/completions`

**请求示例**:
```python
import requests
import base64

with open("audio.mp3", "rb") as f:
    audio_data = base64.b64encode(f.read()).decode("utf-8")

payload = {
    "model": "Qwen/Qwen3-ASR-1.7B",
    "messages": [{
        "role": "user",
        "content": [{
            "type": "audio_url",
            "audio_url": {"url": f"data:audio/mpeg;base64,{audio_data}"}
        }]
    }],
    "max_tokens": 512
}

response = requests.post("http://localhost:8092/v1/chat/completions", json=payload)
print(response.json()["choices"][0]["message"]["content"])
```

**端点**: `POST /v1/audio/transcriptions`

**请求示例**:
```bash
curl -X POST http://localhost:8092/v1/audio/transcriptions \
  -F "file=@audio.mp3" \
  -F "model=Qwen/Qwen3-ASR-1.7B"
```

---

## 常见问题

### Q1: 为什么超过 2 分钟的音频会卡死？

**原因**:
- 短音频使用单次 HTTP 请求发送整个音频文件
- 音频越长，base64 编码后文件越大，处理时间越长
- 默认超时时间可能不足以处理长音频

**解决方案**: 使用 `transcribe-long-audio` 命令，它会自动分割音频并并行处理。

### Q2: 长音频转写需要 API Key 吗？

**需要**。Qwen3-ASR Toolkit 使用 DashScope API 进行转写。

- 获取 API Key: https://dashscope.aliyun.com/
- 设置方式:
  - 命令行参数：`--api-key sk-xxx`
  - 环境变量：`export DASHSCOPE_API_KEY=sk-xxx`

### Q3: 转写速度如何？

- **DashScope API**: 云端处理，速度较快
- **并行处理**: 使用多线程可显著加速，4 线程约提升 3 倍速度
- 音频时长与处理时间比约为 1:10 至 1:30（取决于网络和并发数）

### Q4: 支持哪些音频格式？

支持 FFmpeg 能解码的所有音频格式：
- MP3, WAV, FLAC, M4A, OGG, AAC 等

### Q5: 转写结果保存在哪里？

转写结果保存在 `results/` 目录下，文件名包含时间戳：
```
results/asr_transcription_20250316_143022.txt
results/asr_toolkit_20250316_143022.txt
```

### Q6: 如何获取带时间戳的字幕？

使用 `--save-srt` 参数生成 SRT 字幕文件：
```bash
python asr_client.py transcribe-long-audio audio.mp3 --save-srt
```

---

## 相关资源

- [Qwen3-ASR GitHub](https://github.com/qwenlm/qwen3-asr)
- [Qwen3-ASR Toolkit GitHub](https://github.com/qwenlm/qwen3-asr-toolkit)
- [DashScope 文档](https://help.aliyun.com/zh/dashscope/)
