#!/usr/bin/env python3
"""
Qwen3-ASR 语音识别客户端（使用 transformers 后端）

用法:
    # 离线推理（使用 transformers 后端）
    python vllm_asr_client_transformers.py transcribe audio_s.mp3
"""

import os
import sys
import argparse
import warnings
warnings.filterwarnings("ignore")

from pathlib import Path
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
RESULTS_DIR = os.path.join(SCRIPT_DIR, "results")
DEFAULT_MODEL_PATH = "/home/bushuhui/.cache/modelscope/hub/models/Qwen/Qwen3-ASR-1.7B"


def transcribe_with_transformers(audio_file: str, model_path: str = DEFAULT_MODEL_PATH):
    """
    使用 transformers 后端进行语音识别
    """
    print("=" * 60)
    print("Qwen3-ASR - 离线语音转文字 (Transformers 后端)")
    print("=" * 60)

    try:
        import torch
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
        # 使用 transformers 后端加载模型
        # 注意：GTX 1080 (Compute Capability 6.1) 不被 PyTorch 2.10 支持，使用 CPU 模式
        model = Qwen3ASRModel.from_pretrained(
            model_path,
            dtype=torch.float32,
            device_map="cpu",  # 使用 CPU 模式
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
            f.write(f"检测语言：{language}\n\n")
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


def main():
    parser = argparse.ArgumentParser(
        description="Qwen3-ASR 语音识别客户端 (Transformers 后端)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 离线推理
  python vllm_asr_client_transformers.py transcribe audio_s.mp3

  # 指定模型路径
  python vllm_asr_client_transformers.py transcribe audio_s.mp3 -m /path/to/model
        """
    )

    parser.add_argument(
        'command',
        choices=['transcribe'],
        help='命令类型'
    )

    parser.add_argument(
        'audio_file',
        help='音频文件路径'
    )

    parser.add_argument(
        '--model-path', '-m',
        default=DEFAULT_MODEL_PATH,
        help=f'模型路径 (默认：{DEFAULT_MODEL_PATH})'
    )

    args = parser.parse_args()

    if args.command == 'transcribe':
        transcribe_with_transformers(args.audio_file, args.model_path)


if __name__ == "__main__":
    main()
