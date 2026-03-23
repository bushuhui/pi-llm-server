#!/usr/bin/env python3
"""
基于 FastAPI 的 Qwen3-ASR 长音频转写服务

使用 qwen-asr SDK 处理长音频文件，支持：
- 自动 VAD 语音活动检测分割
- 本地 vLLM 推理，无需 DashScope API
- 根据音频时长自动选择处理策略

安装依赖:
    pip install fastapi uvicorn python-multipart
    pip install -U qwen-asr[vllm] silero-vad soundfile librosa

用法:
    # 启动服务
    python asr_server.py --port 8092

    # 指定模型路径和端口
    python asr_server.py --model-path /path/to/Qwen3-ASR-1.7B --port 8092
"""

import os
import sys
import argparse
import logging
import shutil
import time
import asyncio
from pathlib import Path
from datetime import datetime
from collections import Counter
from typing import Optional, List

import torch
import warnings
warnings.filterwarnings("ignore")

from pi_llm_server import __version__

from fastapi import FastAPI, File, UploadFile, HTTPException, Form, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

# ==================== 日志配置 ====================

def setup_logging(service_name: str):
    """配置日志，输出到控制台和文件"""
    logs_dir = os.path.expanduser("~/.cache/pi-llm-server/logs")
    os.makedirs(logs_dir, exist_ok=True)

    log_file = os.path.join(logs_dir, f"{service_name}.log")

    logger = logging.getLogger()
    logger.setLevel(logging.INFO)
    logger.handlers = []

    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger

logger = setup_logging("asr_server")

# ==================== 默认配置 ====================

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
RESULTS_DIR = os.path.join(SCRIPT_DIR, "results")
DEFAULT_MODEL_PATH = os.path.expanduser("~/.cache/modelscope/hub/models/Qwen/Qwen3-ASR-1.7B")

# 全局模型实例和配置
asr_model = None
vad_model = None
model_path_global = DEFAULT_MODEL_PATH
model_id_global = "Qwen/Qwen3-ASR-1.7B"  # 模型 ID，用于 /v1/models 端点

# 音频时长阈值（秒）：超过此时长使用 VAD 分割
SHORT_AUDIO_THRESHOLD = 120  # 2 分钟

# ==================== 依赖检查 ====================

def check_dependencies():
    """检查必要的依赖是否已安装"""
    missing = []

    try:
        from qwen_asr import Qwen3ASRModel
    except ImportError:
        missing.append("qwen-asr[vllm]")

    try:
        import silero_vad
    except ImportError:
        missing.append("silero-vad")

    try:
        import soundfile
    except ImportError:
        missing.append("soundfile")

    try:
        import librosa
    except ImportError:
        missing.append("librosa")

    if missing:
        logger.error("=" * 60)
        logger.error("缺少必要的依赖包")
        logger.error("=" * 60)
        logger.error(f"请安装以下包：{' '.join(missing)}")
        logger.error("安装命令:")
        logger.error("  pip install -U qwen-asr[vllm] silero-vad soundfile librosa")
        logger.error("=" * 60)
        return False

    return True

# ==================== 音频处理函数 ====================

def load_audio(audio_path: str, target_sr: int = 16000):
    """
    加载音频文件并转换为单声道 16kHz
    """
    import librosa
    audio, sr = librosa.load(audio_path, sr=target_sr, mono=True)
    return audio


def process_vad(audio_data, vad_model, segment_threshold_s: int = 120):
    """
    使用 VAD 模型分割音频

    Returns:
        list of (start_sample, end_sample, audio_chunk)
    """
    from silero_vad import get_speech_timestamps
    import numpy as np

    speech_timestamps = get_speech_timestamps(
        audio_data,
        vad_model,
        sampling_rate=16000,
        min_speech_duration_ms=500,
        max_speech_duration_s=segment_threshold_s,
        min_silence_duration_ms=300,
    )

    segments = []
    for ts in speech_timestamps:
        start = ts['start']
        end = ts['end']
        chunk = audio_data[start:end]
        if len(chunk) > 0:
            segments.append((start, end, chunk))

    return segments


def save_audio_chunk(audio_chunk, output_path: str, sr: int = 16000):
    """保存音频片段为 WAV 文件"""
    import numpy as np
    import soundfile as sf
    audio_array = np.array(audio_chunk, dtype=np.float32)
    sf.write(output_path, audio_array, sr)


def _generate_srt(segments, results, output_file: str):
    """生成 SRT 字幕文件"""
    SAMPLE_RATE = 16000

    with open(output_file, 'w', encoding='utf-8') as f:
        for i, ((start, end, _), (_, text)) in enumerate(zip(segments, results)):
            start_time = start / SAMPLE_RATE
            end_time = end / SAMPLE_RATE

            def format_time(seconds):
                hours = int(seconds // 3600)
                minutes = int((seconds % 3600) // 60)
                secs = seconds % 60
                millis = int((secs % 1) * 1000)
                return f"{hours:02d}:{minutes:02d}:{int(secs):02d},{millis:03d}"

            f.write(f"{i + 1}\n")
            f.write(f"{format_time(start_time)} --> {format_time(end_time)}\n")
            f.write(f"{text}\n\n")


# ==================== 核心转写逻辑 ====================

class TranscribeResult:
    """转写结果"""
    def __init__(self):
        self.text: str = ""
        self.language: str = "unknown"
        self.duration: float = 0
        self.segments_count: int = 0
        self.chunks: List[dict] = []  # 详细片段信息


class TranscriptionCancelled(Exception):
    """转写任务被取消异常"""
    pass


def transcribe_audio(
    audio_data: bytes,
    model,
    vad_model,
    context: str = "",
    vad_threshold: int = 120,
    save_srt: bool = False,
    cancel_event = None,  # asyncio.Event 用于跨线程取消信号
) -> TranscribeResult:
    """
    转写音频数据

    Args:
        audio_data: 音频文件二进制数据
        model: ASR 模型实例
        vad_model: VAD 模型实例
        context: 上下文术语
        vad_threshold: VAD 分割阈值（秒）
        save_srt: 是否生成 SRT 字幕
        cancel_event: asyncio.Event 用于检测取消

    Returns:
        TranscribeResult 转写结果
    """
    import tempfile
    import numpy as np

    result = TranscribeResult()

    # 创建临时文件保存上传的音频
    with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp_file:
        tmp_file.write(audio_data)
        tmp_audio_path = tmp_file.name

    try:
        # 加载音频
        logger.info("正在加载音频文件...")
        audio_array = load_audio(tmp_audio_path, target_sr=16000)
        duration = len(audio_array) / 16000
        result.duration = duration

        logger.info(f"音频时长：{duration:.2f}秒 ({duration/60:.2f}分钟)")

        # 检查取消
        if cancel_event and cancel_event.is_set():
            logger.info("任务已取消，清理临时文件")
            raise TranscriptionCancelled("客户端取消任务")

        # 根据音频时长决定处理策略
        if duration >= SHORT_AUDIO_THRESHOLD:
            logger.info(f"音频超过 {SHORT_AUDIO_THRESHOLD/60:.0f} 分钟，使用 VAD 进行分割...")
            segments = process_vad(
                audio_array,
                vad_model,
                segment_threshold_s=vad_threshold,
            )
            logger.info(f"分割为 {len(segments)} 个片段")
        else:
            logger.info("音频较短，直接处理")
            segments = [(0, len(audio_array), audio_array)]

        # 保存片段到临时目录
        tmp_dir = os.path.expanduser("~/.cache/pi-llm-server/tmp")
        os.makedirs(tmp_dir, exist_ok=True)

        chunk_paths = []
        for idx, (start, end, chunk) in enumerate(segments):
            # 检查取消
            if cancel_event and cancel_event.is_set():
                logger.info("任务已取消，清理临时文件")
                raise TranscriptionCancelled("客户端取消任务")

            path = os.path.join(tmp_dir, f"chunk_{idx}.wav")
            save_audio_chunk(chunk, path)
            chunk_paths.append((path, start, end))

        logger.info(f"已保存 {len(chunk_paths)} 个音频片段")

        # 顺序转写
        results = []
        languages = []
        total_chunks = len(chunk_paths)
        completed = 0

        logger.info("开始转写...")
        start_time = time.time()

        for idx, (chunk_path, start_sample, end_sample) in enumerate(chunk_paths):
            # 检查取消
            if cancel_event and cancel_event.is_set():
                logger.info("任务已取消，清理临时文件")
                raise TranscriptionCancelled("客户端取消任务")

            try:
                chunk_start = time.time()
                result_obj = model.transcribe(audio=chunk_path)
                text = result_obj[0].text
                language = result_obj[0].language

                # 转写完成后立即检查取消
                if cancel_event and cancel_event.is_set():
                    logger.info("任务已取消（片段转写完成后检测到），清理临时文件")
                    raise TranscriptionCancelled("客户端取消任务")

                results.append((idx, text, start_sample, end_sample))
                languages.append(language)
                completed += 1

                chunk_time = time.time() - chunk_start
                logger.info(f"完成 {completed}/{total_chunks} 个片段 (耗时 {chunk_time:.2f}s)")
            except TranscriptionCancelled:
                raise
            except Exception as e:
                logger.error(f"片段 {idx} 转写失败：{e}")
                results.append((idx, "[转写失败]", start_sample, end_sample))
                languages.append("unknown")

        total_time = time.time() - start_time
        logger.info(f"转写完成，总耗时 {total_time:.2f}s")

        # 按顺序组合结果
        results.sort(key=lambda x: x[0])
        full_transcript = " ".join(text for _, text, _, _ in results)
        detected_language = Counter(languages).most_common(1)[0][0] if languages else "unknown"

        result.text = full_transcript
        result.language = detected_language
        result.segments_count = len(chunk_paths)

        # 记录详细片段信息
        for idx, text, start, end in results:
            result.chunks.append({
                "index": idx,
                "start": start / 16000,
                "end": end / 16000,
                "text": text,
                "language": languages[idx] if idx < len(languages) else "unknown"
            })

        logger.info("=" * 60)
        logger.info("转写完成!")
        logger.info(f"检测语言：{detected_language}")
        logger.info(f"转写文本长度：{len(full_transcript)} 字符")

        # 生成 SRT 字幕（可选）
        if save_srt:
            os.makedirs(RESULTS_DIR, exist_ok=True)
            srt_file = os.path.join(
                RESULTS_DIR,
                f"asr_transcription_{datetime.now().strftime('%Y%m%d_%H%M%S')}.srt"
            )
            segments_for_srt = [(start, end, None) for _, _, start, end in results]
            results_for_srt = [(idx, text) for idx, text, _, _ in results]
            _generate_srt(segments_for_srt, results_for_srt, srt_file)
            logger.info(f"SRT 字幕已保存到：{srt_file}")

        # 清理临时文件
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)

        return result

    except TranscriptionCancelled:
        # 任务被取消，清理临时文件
        logger.info("任务已取消，清理临时文件")
        raise
    except Exception as e:
        logger.error(f"转写失败：{e}", exc_info=True)
        raise
    finally:
        # 清理临时音频文件
        if os.path.exists(tmp_audio_path):
            os.unlink(tmp_audio_path)


# ==================== FastAPI 应用 ====================

app = FastAPI(
    title="Qwen3-ASR 语音转写服务",
    description="基于 Qwen3-ASR 模型的长音频转写 API 服务",
    version=__version__
)


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    model_path: str


class TranscribeResponse(BaseModel):
    """详细转写响应（保留所有字段）"""
    text: str
    language: str
    duration: float
    segments_count: int
    chunks: Optional[List[dict]] = None


class AudioTranscriptionResponse(BaseModel):
    """OpenAI 兼容的音频转写响应（仅返回 text 字段）"""
    text: str


@app.on_event("startup")
async def startup_event():
    """服务启动时加载模型"""
    global asr_model, vad_model, model_path_global

    logger.info("正在加载模型...")

    try:
        from qwen_asr import Qwen3ASRModel
        from silero_vad import load_silero_vad

        # 加载 VAD 模型
        logger.info("正在加载 VAD 模型...")
        vad_model = load_silero_vad(onnx=True)

        # 加载 ASR 模型
        logger.info(f"正在加载 ASR 模型：{model_path_global}...")
        asr_model = Qwen3ASRModel.from_pretrained(
            model_path_global,
            torch_dtype=torch.float16,
            device_map="cuda",
            max_new_tokens=512,
        )

        logger.info("模型加载完成")

    except Exception as e:
        logger.error(f"模型加载失败：{e}")
        logger.error("请确保已安装 qwen-asr[vllm] 和 silero-vad")
        raise


@app.get("/health", response_model=HealthResponse)
async def health_check():
    """健康检查"""
    return HealthResponse(
        status="healthy",
        model_loaded=(asr_model is not None),
        model_path=model_path_global
    )


@app.post("/v1/audio/transcriptions", response_model=AudioTranscriptionResponse)
async def transcribe(
    request: Request,
    file: UploadFile = File(..., description="音频文件 (MP3, WAV, FLAC 等格式)"),
    model: Optional[str] = Form(None, description="模型名称（可选，用于兼容 OpenAI API 格式）"),
    context: Optional[str] = Form(None, description="上下文术语，帮助 ASR 识别专业词汇"),
    vad_threshold: int = Form(120, description="VAD 分割阈值（秒），默认 120"),
    save_srt: bool = Form(False, description="是否生成 SRT 字幕文件"),
):
    """
    语音转文字接口

    接收音频文件，自动判断时长并选择合适的处理策略：
    - 短音频（< 2 分钟）：直接转写
    - 长音频（>= 2 分钟）：使用 VAD 分割后逐段转写

    超时时间：1200 秒

    支持客户端断开检测：当客户端取消或断开连接时，自动停止转写任务

    兼容 OpenAI API 格式：POST /v1/audio/transcriptions
    """
    import anyio

    if asr_model is None or vad_model is None:
        raise HTTPException(status_code=503, detail="模型未加载，服务不可用")

    # 验证文件类型
    allowed_types = ["audio/mpeg", "audio/wav", "audio/flac", "audio/mp3", "audio/webm", "audio/ogg"]
    if file.content_type and file.content_type not in allowed_types:
        logger.warning(f"不支持的文件类型：{file.content_type}")
        # 不拒绝，继续处理

    logger.info(f"收到转写请求：文件={file.filename}, 大小={file.size or 'unknown'}")

    # 创建取消事件
    cancel_event = asyncio.Event()

    async def check_cancelled():
        """定期检查客户端是否断开"""
        while not cancel_event.is_set():
            try:
                # 检查客户端是否断开连接
                # is_disconnected() 在客户端断开时返回 True
                if await request.is_disconnected():
                    logger.info("客户端已断开连接")
                    cancel_event.set()
                    return
            except RuntimeError:
                # 如果响应已经开始发送，is_disconnected() 可能抛出 RuntimeError
                # 这种情况下，我们假设连接仍然有效
                pass
            except Exception as e:
                # 其他异常也可能是断开的信号
                logger.warning(f"检查连接状态异常：{e}")
                cancel_event.set()
                return
            await asyncio.sleep(1)  # 每秒检查一次

    async def run_transcription():
        """在后台线程中执行转写"""
        loop = asyncio.get_event_loop()

        # 定义一个包装函数，在每次操作前检查取消状态
        def transcribe_with_check():
            return transcribe_audio(
                audio_data,
                asr_model,
                vad_model,
                context or "",
                vad_threshold,
                save_srt,
                cancel_event,  # 传入 event 而不是 list
            )

        return await loop.run_in_executor(None, transcribe_with_check)

    try:
        # 读取音频数据
        audio_data = await file.read()

        if not audio_data:
            raise HTTPException(status_code=400, detail="音频文件为空")

        logger.info(f"读取音频数据 {len(audio_data)} 字节")

        # 启动断开检测任务
        disconnect_task = asyncio.create_task(check_cancelled())

        try:
            # 执行转写，带超时
            result = await asyncio.wait_for(run_transcription(), timeout=1200)
        except asyncio.TimeoutError:
            logger.error("转写超时（> 1200 秒）")
            cancel_event.set()
            raise HTTPException(status_code=408, detail="转写超时，请尝试分割音频文件")
        except TranscriptionCancelled:
            # 任务被取消（客户端断开或其他原因）
            logger.warning("转写任务被取消")
            raise HTTPException(status_code=499, detail="客户端请求已取消")
        finally:
            # 取消检测任务
            disconnect_task.cancel()
            try:
                await disconnect_task
            except asyncio.CancelledError:
                pass

        # 检查是否因断开而取消（冗余检查，正常情况下不会执行到这里）
        if cancel_event.is_set():
            logger.warning("转写任务因客户端断开而取消")
            raise HTTPException(status_code=499, detail="客户端请求已取消")

        # 返回简单响应（仅包含 text 字段，符合 OpenAI API 格式）
        logger.info(f"转写完成，返回文本长度：{len(result.text)} 字符")
        return AudioTranscriptionResponse(text=result.text)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"转写失败：{e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"转写失败：{str(e)}")


@app.get("/v1/models")
async def list_models():
    """
    列出可用模型
    """
    return {
        "object": "list",
        "data": [
            {
                "id": model_id_global,
                "object": "model",
                "owned_by": "local",
                "service": "asr"
            }
        ]
    }


@app.get("/")
async def root():
    """根路径"""
    return {
        "service": "Qwen3-ASR Transcription Service",
        "version": __version__,
        "endpoints": {
            "health": "GET /health",
            "models": "GET /v1/models",
            "transcribe": "POST /v1/audio/transcriptions",
            "docs": "GET /docs"
        }
    }


# ==================== nvcc 检查 ====================

import subprocess as _sp

def _need_triton_backend():
    """检查是否需要使用 TRITON_ATTN 后端"""
    nvcc_path = shutil.which("nvcc")
    if not nvcc_path and not os.path.exists("/usr/local/cuda"):
        return True
    try:
        import torch
        torch_cuda = torch.version.cuda
        torch_major = int(torch_cuda.split(".")[0])
        result = _sp.run([nvcc_path or "nvcc", "--version"],
                         capture_output=True, text=True, timeout=5)
        for line in result.stdout.split("\n"):
            if "release" in line:
                ver = line.split("release")[-1].strip().split(",")[0]
                nvcc_major = int(ver.split(".")[0])
                if nvcc_major != torch_major:
                    return True
                break
    except Exception:
        return True
    return False


if _need_triton_backend():
    os.environ.setdefault("VLLM_ATTENTION_BACKEND", "TRITON_ATTN")
    logger.info("使用 TRITON_ATTN 后端（nvcc 版本不匹配或未安装）")


# ==================== 主函数 ====================

def main():
    parser = argparse.ArgumentParser(
        description="Qwen3-ASR 语音转写服务",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 默认启动（端口 8092）
  python asr_server.py

  # 指定端口
  python asr_server.py --port 8092

  # 指定模型路径
  python asr_server.py --model-path /path/to/Qwen3-ASR-1.7B

  # 指定主机地址
  python asr_server.py --host 0.0.0.0
        """
    )

    parser.add_argument(
        "--model-path", "-m",
        default=DEFAULT_MODEL_PATH,
        help="模型路径（默认：" + DEFAULT_MODEL_PATH + ")"
    )

    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8092,
        help="服务端口（默认：8092）"
    )

    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="监听地址（默认：0.0.0.0）"
    )

    parser.add_argument(
        "--reload",
        action="store_true",
        help="启用热重载（开发模式）"
    )

    args = parser.parse_args()

    # 从模型路径推断模型 ID（取路径最后两部分，如 Qwen/Qwen3-ASR-1.7B）
    def extract_model_id(model_path: str) -> str:
        """从模型路径提取模型 ID"""
        # 移除末尾的 /
        path = model_path.rstrip('/')
        # 取最后两部分作为 ID
        parts = path.split(os.sep)
        if len(parts) >= 2:
            return f"{parts[-2]}/{parts[-1]}"
        # 如果路径太短，返回整个路径
        return os.path.basename(path)

    # 更新全局模型路径和模型 ID
    global model_path_global, model_id_global
    model_path_global = args.model_path
    model_id_global = extract_model_id(args.model_path)

    # 检查依赖
    if not check_dependencies():
        logger.error("依赖检查失败，请安装必要的包")
        sys.exit(1)

    logger.info("=" * 60)
    logger.info("启动 Qwen3-ASR 语音转写服务")
    logger.info("=" * 60)
    logger.info(f"模型路径：{args.model_path}")
    logger.info(f"服务地址：http://{args.host}:{args.port}")
    logger.info(f"API 文档：http://{args.host}:{args.port}/docs")
    logger.info(f"短音频阈值：{SHORT_AUDIO_THRESHOLD}秒")
    logger.info(f"转写超时：1200 秒")
    logger.info("=" * 60)

    uvicorn.run(
        "asr_server:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
        log_level="info"
    )


if __name__ == "__main__":
    main()
