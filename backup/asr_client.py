#!/usr/bin/env python3
"""
vLLM Qwen3-ASR 语音识别客户端
用于测试 Qwen3-ASR 模型的语音识别功能

用法:
    # 语音转文字 (使用 audio_url)
    python asr_client.py transcribe audio_s.mp3

    # 语音转文字 (使用 OpenAI 兼容 API)
    python asr_client.py transcribe audio_s.mp3 --api transcription

    # 长音频转写（使用 Qwen3-ASR Toolkit + 本地 vLLM）
    python asr_client.py transcribe-long-audio audio.mp3

    # 列出可用模型
    python asr_client.py list
"""

import os
import sys
import argparse
import base64
import requests
import logging
from pathlib import Path
from datetime import datetime

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

logger = setup_logging("asr_client")

# 默认配置
DEFAULT_BASE_URL = "http://localhost:8092"
DEFAULT_MODEL = "Qwen/Qwen3-ASR-1.7B"
DEFAULT_MODEL_PATH = "/home/bushuhui/.cache/modelscope/hub/models/Qwen/Qwen3-ASR-1.7B"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
RESULTS_DIR = os.path.join(SCRIPT_DIR, "results")


def list_models(base_url: str):
    """列出可用的模型"""
    logger.info("=" * 60)
    logger.info("vLLM Qwen3-ASR - 可用模型列表")
    logger.info("=" * 60)

    try:
        response = requests.get(f"{base_url}/v1/models", timeout=30)
        response.raise_for_status()

        models_data = response.json()
        models = models_data.get('data', [])

        logger.info(f"总模型数量：{len(models)}")

        for model in models:
            model_id = model.get('id', 'unknown')
            logger.info(f"  • {model_id}")

        return models

    except requests.exceptions.ConnectionError:
        logger.error(f"无法连接到 vLLM 服务：{base_url}")
        logger.error("请确保服务已启动：python asr_server.py")
        return []
    except Exception as e:
        logger.error(f"获取模型列表失败：{e}")
        return []


def transcribe_audio_url(base_url: str, audio_file: str, model: str = DEFAULT_MODEL):
    """
    使用 chat/completions API 进行语音识别
    通过 audio_url 方式发送音频
    """
    logger.info("=" * 60)
    logger.info("vLLM Qwen3-ASR - 语音转文字 (audio_url)")
    logger.info("=" * 60)

    # 解析文件路径
    if not os.path.isabs(audio_file):
        audio_file = os.path.join(DATA_DIR, audio_file)

    if not os.path.exists(audio_file):
        logger.error(f"音频文件不存在：{audio_file}")
        return

    logger.info(f"音频文件：{audio_file}")
    logger.info(f"模型：{model}")

    # 读取音频文件并编码为 base64
    with open(audio_file, 'rb') as f:
        audio_data = base64.b64encode(f.read()).decode('utf-8')

    # 创建 data URL
    audio_mime_type = "audio/mpeg" if audio_file.endswith('.mp3') else "audio/wav"
    audio_url = f"data:{audio_mime_type};base64,{audio_data}"

    url = f"{base_url}/v1/chat/completions"

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "audio_url",
                        "audio_url": {"url": audio_url}
                    }
                ]
            }
        ],
        "max_tokens": 512
    }

    logger.info("正在识别...")

    try:
        response = requests.post(url, json=payload, timeout=900)
        response.raise_for_status()

        result = response.json()
        content = result.get('choices', [{}])[0].get('message', {}).get('content', '')

        # 保存结果
        output_file = os.path.join(
            RESULTS_DIR,
            f"asr_transcription_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(content)

        logger.info(f"识别成功，结果已保存到：{output_file}")
        logger.info("=" * 60)
        logger.info("识别结果:")
        logger.info("=" * 60)
        logger.info(content)

        return content

    except requests.exceptions.ConnectionError:
        logger.error("无法连接到 vLLM 服务")
        return None
    except Exception as e:
        logger.error(f"识别失败：{e}")
        return None


def transcribe_audio_api(base_url: str, audio_file: str, model: str = DEFAULT_MODEL):
    """
    使用 OpenAI 兼容的 audio/transcriptions API
    """
    logger.info("=" * 60)
    logger.info("vLLM Qwen3-ASR - 语音转文字 (transcription API)")
    logger.info("=" * 60)

    # 解析文件路径
    if not os.path.isabs(audio_file):
        audio_file = os.path.join(DATA_DIR, audio_file)

    if not os.path.exists(audio_file):
        logger.error(f"音频文件不存在：{audio_file}")
        return

    logger.info(f"音频文件：{audio_file}")
    logger.info(f"模型：{model}")

    url = f"{base_url}/v1/audio/transcriptions"

    with open(audio_file, 'rb') as f:
        files = {
            'file': (os.path.basename(audio_file), f, 'audio/mpeg'),
            'model': (None, model),
        }

        logger.info("正在识别...")

        try:
            response = requests.post(url, files=files, timeout=900)
            response.raise_for_status()

            result = response.json()
            text = result.get('text', '')

            # 保存结果
            output_file = os.path.join(
                RESULTS_DIR,
                f"asr_transcription_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            )

            with open(output_file, 'w', encoding='utf-8') as f:
                f.write(text)

            logger.info(f"识别成功，结果已保存到：{output_file}")
            logger.info("=" * 60)
            logger.info("识别结果:")
            logger.info("=" * 60)
            logger.info(text)

            return text

        except Exception as e:
            logger.error(f"识别失败：{e}")
            return None


def transcribe_with_openai_sdk(base_url: str, audio_file: str, model: str = DEFAULT_MODEL):
    """
    使用 OpenAI Python SDK 进行语音识别
    """
    logger.info("=" * 60)
    logger.info("vLLM Qwen3-ASR - 语音转文字 (OpenAI SDK)")
    logger.info("=" * 60)

    try:
        from openai import OpenAI
    except ImportError:
        logger.error("需要安装 openai 包：pip install openai")
        return

    # 解析文件路径
    if not os.path.isabs(audio_file):
        audio_file = os.path.join(DATA_DIR, audio_file)

    if not os.path.exists(audio_file):
        logger.error(f"音频文件不存在：{audio_file}")
        return

    logger.info(f"音频文件：{audio_file}")
    logger.info(f"模型：{model}")
    logger.info(f"服务地址：{base_url}")

    # 初始化客户端
    client = OpenAI(
        base_url=f"{base_url}/v1",
        api_key="token-abc123"
    )

    logger.info("正在识别...")

    try:
        with open(audio_file, 'rb') as f:
            transcription = client.audio.transcriptions.create(
                model=model,
                file=f,
            )

        text = transcription.text

        # 保存结果
        output_file = os.path.join(
            RESULTS_DIR,
            f"asr_transcription_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(text)

        logger.info(f"识别成功，结果已保存到：{output_file}")
        logger.info("=" * 60)
        logger.info("识别结果:")
        logger.info("=" * 60)
        logger.info(text)

        return text

    except Exception as e:
        logger.error(f"识别失败：{e}")
        return None


def main():
    parser = argparse.ArgumentParser(
        description="vLLM Qwen3-ASR 语音识别客户端",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 列出可用模型
  python asr_client.py list

  # 语音转文字 (使用 audio_url)
  python asr_client.py transcribe audio_s.mp3

  # 语音转文字 (使用 transcription API)
  python asr_client.py transcribe audio_s.mp3 --api transcription

  # 使用 OpenAI SDK
  python asr_client.py transcribe audio_s.mp3 --api sdk

  # 长音频转写（使用 Qwen3-ASR Toolkit + 本地 vLLM）
  python asr_client.py transcribe-long-audio audio.mp3

  # 指定模型路径
  python asr_client.py transcribe-long-audio audio.mp3 --model-path /path/to/model

  # 指定服务地址和模型
  python asr_client.py transcribe audio_s.mp3 --base-url http://localhost:8092
        """
    )

    parser.add_argument(
        '--base-url',
        default=DEFAULT_BASE_URL,
        help=f'vLLM 服务地址 (默认：{DEFAULT_BASE_URL})'
    )

    subparsers = parser.add_subparsers(dest='command', help='命令类型')

    # list 命令
    list_parser = subparsers.add_parser('list', help='列出所有可用模型')

    # transcribe 命令
    transcribe_parser = subparsers.add_parser('transcribe', help='语音转文字')
    transcribe_parser.add_argument('audio_file', help='音频文件路径')
    transcribe_parser.add_argument('--model', '-m', default=DEFAULT_MODEL,
                                   help=f'模型名称 (默认：{DEFAULT_MODEL})')
    transcribe_parser.add_argument('--api', '-a',
                                   choices=['chat', 'transcription', 'sdk'],
                                   default='chat',
                                   help='使用的 API 类型 (默认：chat)')

    # transcribe-long-audio 命令（长音频使用 Toolkit + 本地 vLLM）
    long_audio_parser = subparsers.add_parser('transcribe-long-audio',
                                               help='长音频转写（使用 Qwen3-ASR Toolkit + 本地 vLLM，无需 API key）')
    long_audio_parser.add_argument('audio_file', help='音频文件路径')
    long_audio_parser.add_argument('--model-path', '-m', default=DEFAULT_MODEL_PATH,
                                   help=f'模型路径 (默认：{DEFAULT_MODEL_PATH})')
    long_audio_parser.add_argument('--context', '-c', default='',
                                   help='上下文术语，帮助 ASR 识别专业词汇')
    long_audio_parser.add_argument('--vad-threshold', '-d', type=int, default=120,
                                   help='VAD 分割阈值，单位秒 (默认：120)')
    long_audio_parser.add_argument('--save-srt', '-srt', action='store_true',
                                   help='生成 SRT 字幕文件')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if args.command == 'list':
        list_models(args.base_url)

    elif args.command == 'transcribe':
        if args.api == 'chat':
            transcribe_audio_url(args.base_url, args.audio_file, args.model)
        elif args.api == 'transcription':
            transcribe_audio_api(args.base_url, args.audio_file, args.model)
        elif args.api == 'sdk':
            transcribe_with_openai_sdk(args.base_url, args.audio_file, args.model)

    elif args.command == 'transcribe-long-audio':
        # 调用 toolkit 脚本
        toolkit_script = os.path.join(os.path.dirname(__file__), 'asr_client_toolkit.py')
        if not os.path.exists(toolkit_script):
            logger.error("找不到 asr_client_toolkit.py 脚本")
            return

        import subprocess
        cmd = [sys.executable, toolkit_script, 'transcribe', args.audio_file]
        if args.model_path:
            cmd.extend(['--model-path', args.model_path])
        if args.context:
            cmd.extend(['--context', args.context])
        if args.vad_threshold:
            cmd.extend(['--vad-threshold', str(args.vad_threshold)])
        if args.save_srt:
            cmd.append('--save-srt')

        subprocess.run(cmd)


if __name__ == "__main__":
    main()
