#!/usr/bin/env python3
"""
Qwen3-ASR 语音转写客户端

配套 asr_server.py 使用，提供语音转文字功能
API 端点：POST /v1/audio/transcriptions (OpenAI 兼容格式)

用法:
    # 基本用法（短音频）
    python asr_client.py transcribe audio.mp3

    # 长音频（自动处理）
    python asr_client.py transcribe long_audio.mp3

    # 指定服务地址
    python asr_client.py --base-url http://localhost:8092 transcribe audio.mp3

    # 生成 SRT 字幕
    python asr_client.py transcribe audio.mp3 --save-srt

    # 指定模型名称
    python asr_client.py transcribe audio.mp3 --model Qwen/Qwen3-ASR-1.7B

    # 批量转写
    python asr_client.py transcribe-batch *.mp3
"""

import os
import sys
import argparse
import base64
import requests
import logging
from pathlib import Path
from datetime import datetime
from typing import List

# ==================== 日志配置 ====================

def setup_logging(service_name: str):
    """配置日志，输出到控制台和文件"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    logs_dir = os.path.join(script_dir, "logs")
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


logger = setup_logging("asr_client")

# ==================== 默认配置 ====================

DEFAULT_BASE_URL = "http://localhost:8092"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
RESULTS_DIR = os.path.join(SCRIPT_DIR, "results")


def check_server_health(base_url: str) -> bool:
    """检查服务健康状态"""
    try:
        response = requests.get(f"{base_url}/health", timeout=10)
        if response.status_code == 200:
            data = response.json()
            status = data.get("status", "unknown")
            model_loaded = data.get("model_loaded", False)
            logger.info(f"服务状态：{status}, 模型已加载：{model_loaded}")
            return model_loaded
        else:
            logger.error(f"健康检查失败：HTTP {response.status_code}")
            return False
    except requests.exceptions.ConnectionError:
        logger.error(f"无法连接到服务：{base_url}")
        logger.error("请确保 asr_server.py 已启动")
        return False
    except Exception as e:
        logger.error(f"健康检查异常：{e}")
        return False


def transcribe_audio(
    base_url: str,
    audio_file: str,
    context: str = "",
    vad_threshold: int = 120,
    save_srt: bool = False,
    model: str = None,
) -> dict:
    """
    语音转文字

    Args:
        base_url: 服务地址
        audio_file: 音频文件路径
        context: 上下文术语
        vad_threshold: VAD 分割阈值（秒）
        save_srt: 是否生成 SRT 字幕
        model: 模型名称（可选，用于兼容 OpenAI API 格式）

    Returns:
        转写结果字典
    """
    logger.info("=" * 60)
    logger.info("Qwen3-ASR 语音转写")
    logger.info("=" * 60)

    # 解析文件路径
    if not os.path.isabs(audio_file):
        audio_file = os.path.join(DATA_DIR, audio_file)

    if not os.path.exists(audio_file):
        logger.error(f"音频文件不存在：{audio_file}")
        return None

    file_size = os.path.getsize(audio_file)
    file_size_mb = file_size / 1024 / 1024

    logger.info(f"音频文件：{audio_file}")
    logger.info(f"文件大小：{file_size_mb:.2f} MB")
    logger.info(f"服务地址：{base_url}")
    logger.info(f"VAD 阈值：{vad_threshold}秒")
    logger.info(f"生成 SRT：{save_srt}")

    # 使用新的 API 端点
    url = f"{base_url}/v1/audio/transcriptions"

    # 准备文件和数据
    with open(audio_file, 'rb') as f:
        files = {'file': (os.path.basename(audio_file), f, 'audio/mpeg')}
        data = {
            'vad_threshold': vad_threshold,
            'save_srt': save_srt,
        }
        if context:
            data['context'] = context
        if model:
            data['model'] = model

        logger.info("正在上传并转写...")
        logger.info("(长音频可能需要较长时间，请耐心等待)")

        try:
            # 设置 1200 秒超时
            response = requests.post(url, files=files, data=data, timeout=1200)
            response.raise_for_status()

            result = response.json()

            # 提取结果（新 API 只返回 text 字段）
            text = result.get('text', '')

            logger.info("=" * 60)
            logger.info("转写完成!")
            logger.info(f"转写文本长度：{len(text)} 字符")

            # 保存结果
            os.makedirs(RESULTS_DIR, exist_ok=True)
            output_file = os.path.join(
                RESULTS_DIR,
                f"asr_transcription_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            )

            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(f"音频文件：{audio_file}\n")
                f.write(f"文件大小：{file_size_mb:.2f} MB\n")
                f.write("\n")
                f.write("=" * 60 + "\n")
                f.write("转写内容:\n")
                f.write("=" * 60 + "\n")
                f.write(text)

            logger.info(f"结果已保存到：{output_file}")

            logger.info("=" * 60)
            logger.info("转写预览 (前 500 字):")
            logger.info("-" * 60)
            logger.info(text[:500] + ("..." if len(text) > 500 else ""))

            return {"text": text}

        except requests.exceptions.Timeout:
            logger.error("请求超时（> 1200 秒），请尝试将音频文件分割成更小的片段")
            return None
        except requests.exceptions.ConnectionError:
            logger.error("无法连接到服务")
            logger.error(f"请确保 asr_server.py 已启动：python asr_server.py --port {DEFAULT_BASE_URL.split(':')[-1]}")
            return None
        except Exception as e:
            logger.error(f"转写失败：{e}")
            return None


def transcribe_batch(
    base_url: str,
    audio_files: List[str],
    context: str = "",
    vad_threshold: int = 120,
    save_srt: bool = False,
    model: str = None,
):
    """批量转写音频文件"""
    logger.info("=" * 60)
    logger.info(f"批量转写：共 {len(audio_files)} 个文件")
    logger.info("=" * 60)

    results = []
    for idx, audio_file in enumerate(audio_files, 1):
        logger.info(f"\n[{idx}/{len(audio_files)}] 处理：{audio_file}")
        logger.info("-" * 40)

        result = transcribe_audio(
            base_url=base_url,
            audio_file=audio_file,
            context=context,
            vad_threshold=vad_threshold,
            save_srt=save_srt,
            model=model,
        )

        if result:
            results.append((audio_file, "成功", result.get('text', '')[:50]))
        else:
            results.append((audio_file, "失败", ""))

    # 汇总结果
    logger.info("\n" + "=" * 60)
    logger.info("批量处理汇总")
    logger.info("=" * 60)

    success_count = sum(1 for _, status, _ in results if status == "成功")
    fail_count = len(results) - success_count

    logger.info(f"总计：{len(results)} 个文件")
    logger.info(f"成功：{success_count} 个")
    logger.info(f"失败：{fail_count} 个")

    if fail_count > 0:
        logger.info("\n失败文件:")
        for file, status, _ in results:
            if status == "失败":
                logger.info(f"  - {file}")

    return results


def save_srt_from_chunks(chunks: List[dict], output_file: str):
    """从分片段数据生成 SRT 字幕"""
    with open(output_file, 'w', encoding='utf-8') as f:
        for i, chunk in enumerate(chunks, 1):
            start = chunk.get('start', 0)
            end = chunk.get('end', 0)
            text = chunk.get('text', '')

            def format_time(seconds):
                hours = int(seconds // 3600)
                minutes = int((seconds % 3600) // 60)
                secs = seconds % 60
                millis = int((secs % 1) * 1000)
                return f"{hours:02d}:{minutes:02d}:{int(secs):02d},{millis:03d}"

            f.write(f"{i}\n")
            f.write(f"{format_time(start)} --> {format_time(end)}\n")
            f.write(f"{text}\n\n")


def main():
    parser = argparse.ArgumentParser(
        description="Qwen3-ASR 语音转写客户端",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 检查服务状态
  python asr_client.py health

  # 单个文件转写
  python asr_client.py transcribe audio.mp3

  # 指定 VAD 阈值
  python asr_client.py transcribe audio.mp3 --vad-threshold 180

  # 添加上下文术语
  python asr_client.py transcribe audio.mp3 --context "AI,LLM,transformer"

  # 生成 SRT 字幕
  python asr_client.py transcribe audio.mp3 --save-srt

  # 批量转写
  python asr_client.py transcribe-batch audio1.mp3 audio2.mp3 audio3.mp3

  # 指定服务地址
  python asr_client.py --base-url http://localhost:8092 transcribe audio.mp3
        """
    )

    parser.add_argument(
        '--base-url',
        default=DEFAULT_BASE_URL,
        help=f'服务地址 (默认：{DEFAULT_BASE_URL})'
    )

    subparsers = parser.add_subparsers(dest='command', help='命令类型')

    # health 命令
    health_parser = subparsers.add_parser('health', help='检查服务健康状态')

    # transcribe 命令
    transcribe_parser = subparsers.add_parser('transcribe', help='语音转文字')
    transcribe_parser.add_argument('audio_file', help='音频文件路径')
    transcribe_parser.add_argument('--context', '-c', default='',
                                   help='上下文术语，帮助 ASR 识别专业词汇')
    transcribe_parser.add_argument('--vad-threshold', '-d', type=int, default=120,
                                   help='VAD 分割阈值，单位秒 (默认：120)')
    transcribe_parser.add_argument('--save-srt', '-srt', action='store_true',
                                   help='生成 SRT 字幕文件')
    transcribe_parser.add_argument('--model', '-m', default=None,
                                   help='模型名称（可选，用于兼容 OpenAI API 格式）')

    # transcribe-batch 命令
    batch_parser = subparsers.add_parser('transcribe-batch', help='批量转写音频文件')
    batch_parser.add_argument('audio_files', nargs='+', help='音频文件路径列表')
    batch_parser.add_argument('--context', '-c', default='',
                              help='上下文术语')
    batch_parser.add_argument('--vad-threshold', '-d', type=int, default=120,
                              help='VAD 分割阈值，单位秒')
    batch_parser.add_argument('--save-srt', '-srt', action='store_true',
                              help='生成 SRT 字幕文件')
    batch_parser.add_argument('--model', '-m', default=None,
                              help='模型名称（可选，用于兼容 OpenAI API 格式）')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # 检查服务健康状态（transcribe 命令时）
    if args.command in ['transcribe', 'transcribe-batch']:
        if not check_server_health(args.base_url):
            sys.exit(1)

    if args.command == 'health':
        check_server_health(args.base_url)

    elif args.command == 'transcribe':
        result = transcribe_audio(
            base_url=args.base_url,
            audio_file=args.audio_file,
            context=args.context,
            vad_threshold=args.vad_threshold,
            save_srt=args.save_srt,
            model=args.model,
        )
        if not result:
            sys.exit(1)

    elif args.command == 'transcribe-batch':
        results = transcribe_batch(
            base_url=args.base_url,
            audio_files=args.audio_files,
            context=args.context,
            vad_threshold=args.vad_threshold,
            save_srt=args.save_srt,
            model=args.model,
        )
        if any(status == "失败" for _, status, _ in results):
            sys.exit(1)


if __name__ == "__main__":
    main()
