#!/usr/bin/env python3
"""
Qwen3-ASR 语音识别客户端（使用 qwen-asr 包）

用法:
    # 离线推理（直接使用 qwen-asr 包）
    python vllm_asr_client_qwen.py transcribe audio_s.mp3

    # 通过服务 API 调用
    python vllm_asr_client_qwen.py transcribe audio_s.mp3 --via-api

    # 列出模型
    python vllm_asr_client_qwen.py list
"""

import os
import sys
import argparse
from pathlib import Path
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
RESULTS_DIR = os.path.join(SCRIPT_DIR, "results")
DEFAULT_MODEL_PATH = "/home/bushuhui/.cache/modelscope/hub/models/Qwen/Qwen3-ASR-1.7B"
DEFAULT_BASE_URL = "http://localhost:8082"


def transcribe_offline(audio_file: str, model_path: str = DEFAULT_MODEL_PATH):
    """
    使用 qwen-asr 包进行离线语音识别（使用 transformers 后端，显存占用低）
    """
    print("=" * 60)
    print("Qwen3-ASR - 离线语音转文字 (Transformers 后端)")
    print("=" * 60)

    try:
        import torch
        import warnings
        warnings.filterwarnings("ignore")
        from qwen_asr import Qwen3ASRModel
    except ImportError as e:
        print("错误：需要安装 qwen-asr 包")
        print(f"  错误详情：{e}")
        print("  pip install -U qwen-asr")
        return

    # 解析文件路径
    if not os.path.isabs(audio_file):
        audio_file = os.path.join(DATA_DIR, audio_file)

    if not os.path.exists(audio_file):
        print(f"错误：音频文件不存在：{audio_file}")
        return

    print(f"\n音频文件：{audio_file}")
    print(f"模型：{model_path}")
    print(f"正在加载模型...\n")

    try:
        # 使用 transformers 后端加载模型（显存占用更低）
        model = Qwen3ASRModel.from_pretrained(
            model_path,
            torch_dtype=torch.float16,
            device_map="cuda",
            max_inference_batch_size=1,  # 单条推理，避免 OOM
            max_new_tokens=256,
        )

        print("正在识别...\n")

        # 执行识别
        results = model.transcribe(audio=audio_file)

        text = results[0].text
        language = results[0].language

        # 保存结果
        output_file = os.path.join(
            RESULTS_DIR,
            f"asr_transcription_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
        )

        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"语言：{language}\n\n")
            f.write(text)

        print("=" * 60)
        print("识别结果:")
        print("=" * 60)
        print(f"检测语言：{language}")
        print(text)
        print("=" * 60)
        print(f"\n结果已保存到：{output_file}")

        return text

    except Exception as e:
        print(f"错误：{e}")
        import traceback
        traceback.print_exc()
        return None


def transcribe_via_api(base_url: str, audio_file: str, model: str = "Qwen/Qwen3-ASR-1.7B"):
    """
    通过 HTTP API 调用语音识别服务
    """
    print("=" * 60)
    print("Qwen3-ASR - 语音转文字 (API 调用)")
    print("=" * 60)

    import base64
    import requests

    # 解析文件路径
    if not os.path.isabs(audio_file):
        audio_file = os.path.join(DATA_DIR, audio_file)

    if not os.path.exists(audio_file):
        print(f"错误：音频文件不存在：{audio_file}")
        return

    print(f"\n音频文件：{audio_file}")
    print(f"服务地址：{base_url}")
    print(f"模型：{model}")

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

    print(f"\n正在识别...\n")

    try:
        response = requests.post(url, json=payload, timeout=300)
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

        print("=" * 60)
        print("识别结果:")
        print("=" * 60)
        print(content)
        print("=" * 60)
        print(f"\n结果已保存到：{output_file}")

        return content

    except requests.exceptions.ConnectionError:
        print("错误：无法连接到服务，请确保服务已启动")
        print(f"  启动命令：python vllm_asr_server_qwen.py")
        return None
    except Exception as e:
        print(f"错误：{e}")
        return None


def list_models(base_url: str = DEFAULT_BASE_URL):
    """列出可用的模型"""
    print("=" * 60)
    print("Qwen3-ASR - 可用模型列表")
    print("=" * 60)

    import requests

    try:
        response = requests.get(f"{base_url}/v1/models", timeout=30)
        response.raise_for_status()

        models_data = response.json()
        models = models_data.get('data', [])

        print(f"\n总模型数量：{len(models)}\n")

        for model in models:
            model_id = model.get('id', 'unknown')
            print(f"  • {model_id}")

        return models

    except requests.exceptions.ConnectionError:
        print("错误：无法连接到服务，请确保服务已启动")
        print(f"  启动命令：python vllm_asr_server_qwen.py")
        return []
    except Exception as e:
        print(f"错误：{e}")
        return []


def main():
    parser = argparse.ArgumentParser(
        description="Qwen3-ASR 语音识别客户端",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 离线推理（推荐，最快）
  python vllm_asr_client_qwen.py transcribe audio_s.mp3

  # 通过 API 调用
  python vllm_asr_client_qwen.py transcribe audio_s.mp3 --via-api

  # 列出可用模型
  python vllm_asr_client_qwen.py list

  # 指定模型路径
  python vllm_asr_client_qwen.py transcribe audio_s.mp3 --model-path /path/to/model
        """
    )

    parser.add_argument(
        '--base-url',
        default=DEFAULT_BASE_URL,
        help=f'服务地址 (默认：{DEFAULT_BASE_URL})'
    )

    subparsers = parser.add_subparsers(dest='command', help='命令类型')

    # list 命令
    list_parser = subparsers.add_parser('list', help='列出所有可用模型')

    # transcribe 命令
    transcribe_parser = subparsers.add_parser('transcribe', help='语音转文字')
    transcribe_parser.add_argument('audio_file', help='音频文件路径')
    transcribe_parser.add_argument(
        '--model-path', '-m',
        default=DEFAULT_MODEL_PATH,
        help=f'模型路径 (默认：{DEFAULT_MODEL_PATH})'
    )
    transcribe_parser.add_argument(
        '--via-api', '-a',
        action='store_true',
        help='通过 HTTP API 调用（需要服务已启动）'
    )

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if args.command == 'list':
        list_models(args.base_url)

    elif args.command == 'transcribe':
        if args.via_api:
            transcribe_via_api(args.base_url, args.audio_file)
        else:
            transcribe_offline(args.audio_file, args.model_path)


if __name__ == "__main__":
    main()
