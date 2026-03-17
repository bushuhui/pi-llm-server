#!/usr/bin/env python3
"""
Qwen3-ASR Toolkit 长音频转写客户端（本地 vLLM 版本）

使用 qwen-asr Python SDK 处理长音频文件，支持：
- 自动 VAD 语音活动检测分割
- 多线程并行转写
- 本地 vLLM 推理，无需 DashScope API
- 生成 SRT 字幕文件（可选）

安装依赖:
    pip install qwen-asr[vllm] silero-vad

用法:
    # 基本用法
    python asr_client_toolkit.py transcribe audio.mp3

    # 多线程加速
    python asr_client_toolkit.py transcribe audio.mp3 --threads 8

    # 生成 SRT 字幕
    python asr_client_toolkit.py transcribe audio.mp3 --save-srt

    # 指定模型路径
    python asr_client_toolkit.py transcribe audio.mp3 --model-path /path/to/model
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime
from collections import Counter

# 配置日志
def setup_logging(service_name: str):
    """配置日志，输出到控制台和文件"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    logs_dir = os.path.join(script_dir, "logs")
    os.makedirs(logs_dir, exist_ok=True)

    log_file = os.path.join(logs_dir, f"{service_name}.log")

    # 创建 logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # 清除已有的 handlers
    logger.handlers = []

    # 创建 formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    # 控制台 handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件 handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger

logger = setup_logging("asr_toolkit")

# 默认配置
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
RESULTS_DIR = os.path.join(SCRIPT_DIR, "results")
# 默认模型路径：优先使用本地缓存，如果没有则使用模型名称（会自动下载）
DEFAULT_MODEL_PATH = "/home/bushuhui/.cache/modelscope/hub/models/Qwen/Qwen3-ASR-1.7B"


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

    if missing:
        logger.error("=" * 60)
        logger.error("缺少必要的依赖包")
        logger.error("=" * 60)
        logger.error(f"请安装以下包：{' '.join(missing)}")
        logger.error("")
        logger.error("安装命令:")
        logger.error("  pip install -U qwen-asr[vllm] silero-vad")
        logger.error("=" * 60)
        return False

    return True


def load_audio(audio_path: str, target_sr: int = 16000):
    """
    加载音频文件并转换为单声道 16kHz

    Args:
        audio_path: 音频文件路径
        target_sr: 目标采样率，默认 16kHz

    Returns:
        numpy 数组，包含音频样本
    """
    try:
        import soundfile as sf
        import librosa
    except ImportError:
        logger.error("需要安装 soundfile 和 librosa: pip install soundfile librosa")
        raise

    # 使用 librosa 加载并 resample
    audio, sr = librosa.load(audio_path, sr=target_sr, mono=True)
    return audio


def process_vad(audio_data, vad_model, segment_threshold_s: int = 120):
    """
    使用 VAD 模型分割音频

    Args:
        audio_data: 音频数据
        vad_model: VAD 模型
        segment_threshold_s: 每个片段的最大时长（秒）

    Returns:
        list of (start_sample, end_sample, audio_chunk)
    """
    from silero_vad import get_speech_timestamps
    import numpy as np

    # 获取语音时间戳
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


def save_audio_chunk(audio_chunk: list, output_path: str, sr: int = 16000):
    """保存音频片段为 WAV 文件"""
    import numpy as np
    try:
        import soundfile as sf
    except ImportError:
        logger.error("需要安装 soundfile: pip install soundfile")
        raise

    # 将 chunk 转换为 numpy 数组并保存
    audio_array = np.array(audio_chunk, dtype=np.float32)
    sf.write(output_path, audio_array, sr)


def transcribe_long_audio(
    audio_file: str,
    model_path: str = DEFAULT_MODEL_PATH,
    context: str = "",
    num_threads: int = 4,
    vad_segment_threshold: int = 120,
    tmp_dir: str = None,
    save_srt: bool = False,
):
    """
    使用 qwen-asr SDK 转写长音频

    Args:
        audio_file: 音频文件路径
        model_path: 本地模型路径
        context: 文本上下文，用于指导 ASR 模型识别专业术语
        num_threads: 并行处理线程数
        vad_segment_threshold: VAD 分割阈值（秒），默认 120 秒
        tmp_dir: 临时文件目录
        save_srt: 是否生成 SRT 字幕文件
    """
    logger.info("=" * 60)
    logger.info("Qwen3-ASR Toolkit - 长音频转写（本地 vLLM）")
    logger.info("=" * 60)

    # 解析文件路径
    if not os.path.isabs(audio_file):
        audio_file = os.path.join(DATA_DIR, audio_file)

    if not os.path.exists(audio_file):
        logger.error(f"音频文件不存在：{audio_file}")
        return None

    logger.info(f"音频文件：{audio_file}")
    logger.info(f"文件类型：{Path(audio_file).suffix}")
    logger.info(f"文件大小：{os.path.getsize(audio_file) / 1024 / 1024:.2f} MB")
    logger.info(f"并行线程数：{num_threads}")
    logger.info(f"VAD 分割阈值：{vad_segment_threshold}秒")
    logger.info(f"模型路径：{model_path}")
    logger.info(f"上下文：{context if context else '(无)'}")

    try:
        # 导入必要的模块
        import torch
        import warnings
        warnings.filterwarnings("ignore")
        from qwen_asr import Qwen3ASRModel
        from silero_vad import load_silero_vad

        # 加载 VAD 模型
        logger.info("正在加载 VAD 模型...")
        vad_model = load_silero_vad(onnx=True)

        # 加载音频
        logger.info("正在加载音频文件...")
        audio_data = load_audio(audio_file, target_sr=16000)
        duration = len(audio_data) / 16000
        logger.info(f"音频时长：{duration:.2f}秒 ({duration/60:.2f}分钟)")

        # 根据音频时长决定处理策略
        if duration >= 180:  # 3 分钟以上，使用 VAD 分割
            logger.info(f"音频超过 3 分钟，使用 VAD 进行分割...")
            segments = process_vad(
                audio_data,
                vad_model,
                segment_threshold_s=vad_segment_threshold,
            )
            logger.info(f"分割为 {len(segments)} 个片段")
        else:
            logger.info("音频较短，直接处理")
            segments = [(0, len(audio_data), audio_data)]

        # 保存片段到临时文件
        if tmp_dir is None:
            tmp_dir = os.path.join(SCRIPT_DIR, ".asr_tmp")
        os.makedirs(tmp_dir, exist_ok=True)

        chunk_paths = []
        for idx, (start, end, chunk) in enumerate(segments):
            path = os.path.join(tmp_dir, f"chunk_{idx}.wav")
            save_audio_chunk(chunk, path)
            chunk_paths.append(path)

        logger.info(f"已保存 {len(chunk_paths)} 个音频片段到 {tmp_dir}")

        # 加载 ASR 模型（只加载一次）
        logger.info("正在加载 ASR 模型...")
        asr_model = Qwen3ASRModel.from_pretrained(
            model_path,
            torch_dtype=torch.float16,
            device_map="cuda",
            max_new_tokens=512,
        )
        logger.info("模型加载完成")

        # 顺序转写（qwen-asr 模型不支持多线程并发）
        results = []
        languages = []
        total_chunks = len(chunk_paths)
        completed = 0

        logger.info("开始转写...")

        for idx, chunk_path in enumerate(chunk_paths):
            try:
                result = asr_model.transcribe(audio=chunk_path)
                text = result[0].text
                language = result[0].language
                results.append((idx, text))
                languages.append(language)
                completed += 1
                logger.info(f"完成 {completed}/{total_chunks} 个片段")
            except Exception as e:
                logger.error(f"片段 {idx} 转写失败：{e}")
                results.append((idx, "[转写失败]"))
                languages.append("unknown")

        # 按顺序组合结果
        results.sort(key=lambda x: x[0])
        full_transcript = " ".join(text for _, text in results)
        detected_language = Counter(languages).most_common(1)[0][0] if languages else "unknown"

        logger.info("=" * 60)
        logger.info("转写完成!")
        logger.info(f"检测语言：{detected_language}")
        logger.info(f"转写文本长度：{len(full_transcript)} 字符")

        # 保存结果
        os.makedirs(RESULTS_DIR, exist_ok=True)
        output_file = os.path.join(
            RESULTS_DIR,
            f"asr_toolkit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"语言：{detected_language}\n")
            f.write(f"音频文件：{audio_file}\n")
            f.write(f"音频时长：{duration:.2f}秒\n")
            f.write(f"分割片段数：{len(chunk_paths)}\n")
            f.write("\n")
            f.write(full_transcript)

        logger.info(f"结果已保存到：{output_file}")

        # 生成 SRT 字幕（可选）
        if save_srt:
            srt_file = os.path.splitext(output_file)[0] + ".srt"
            _generate_srt(segments, results, srt_file)
            logger.info(f"SRT 字幕已保存到：{srt_file}")

        # 清理临时文件
        import shutil
        if os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)
            logger.info(f"已清理临时文件：{tmp_dir}")

        logger.info("=" * 60)
        logger.info("转写预览 (前 500 字):")
        logger.info("-" * 60)
        logger.info(full_transcript[:500] + ("..." if len(full_transcript) > 500 else ""))

        return full_transcript

    except Exception as e:
        logger.error(f"转写失败：{e}", exc_info=True)
        return None


def _generate_srt(segments, results, output_file: str):
    """生成 SRT 字幕文件"""
    SAMPLE_RATE = 16000

    with open(output_file, 'w', encoding='utf-8') as f:
        for i, ((start, end, _), (_, text)) in enumerate(zip(segments, results)):
            start_time = start / SAMPLE_RATE
            end_time = end / SAMPLE_RATE

            # 格式化为 SRT 时间格式 (HH:MM:SS,mmm)
            def format_time(seconds):
                hours = int(seconds // 3600)
                minutes = int((seconds % 3600) // 60)
                secs = seconds % 60
                millis = int((secs % 1) * 1000)
                return f"{hours:02d}:{minutes:02d}:{int(secs):02d},{millis:03d}"

            f.write(f"{i + 1}\n")
            f.write(f"{format_time(start_time)} --> {format_time(end_time)}\n")
            f.write(f"{text}\n\n")


def main():
    parser = argparse.ArgumentParser(
        description="Qwen3-ASR Toolkit 长音频转写客户端（本地 vLLM 版本）",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 基本用法
  python asr_client_toolkit.py transcribe audio.mp3

  # 使用 8 个线程并行处理（VAD 分割）
  python asr_client_toolkit.py transcribe audio.mp3 --threads 8

  # 生成 SRT 字幕文件
  python asr_client_toolkit.py transcribe audio.mp3 --save-srt

  # 添加上下文术语
  python asr_client_toolkit.py transcribe audio.mp3 --context "AI,LLM,transformer"

  # 指定模型路径
  python asr_client_toolkit.py transcribe audio.mp3 --model-path /path/to/model
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='命令类型')

    # transcribe 命令
    transcribe_parser = subparsers.add_parser('transcribe', help='转写长音频')
    transcribe_parser.add_argument('audio_file', help='音频文件路径')
    transcribe_parser.add_argument('--model-path', '-m', default=DEFAULT_MODEL_PATH,
                                   help=f'模型路径 (默认：{DEFAULT_MODEL_PATH})')
    transcribe_parser.add_argument('--context', '-c', default='',
                                   help='上下文术语，帮助 ASR 识别专业词汇')
    transcribe_parser.add_argument('--threads', '-j', type=int, default=1,
                                   help='保留参数，但当前版本使用顺序处理')
    transcribe_parser.add_argument('--vad-threshold', '-d', type=int, default=120,
                                   help='VAD 分割阈值，单位秒 (默认：120)')
    transcribe_parser.add_argument('--tmp-dir', '-t',
                                   help='临时文件目录')
    transcribe_parser.add_argument('--save-srt', '-srt', action='store_true',
                                   help='生成 SRT 字幕文件')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # 检查依赖
    if not check_dependencies():
        sys.exit(1)

    if args.command == 'transcribe':
        transcribe_long_audio(
            audio_file=args.audio_file,
            model_path=args.model_path,
            context=args.context,
            num_threads=args.threads,
            vad_segment_threshold=args.vad_threshold,
            tmp_dir=args.tmp_dir,
            save_srt=args.save_srt,
        )


if __name__ == "__main__":
    main()
