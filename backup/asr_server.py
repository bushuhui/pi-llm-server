#!/usr/bin/env python3
"""
基于 vLLM 的 Qwen3-ASR 语音识别服务
使用 Qwen3-ASR-1.7B 模型进行语音识别

启动命令:
    python vllm_asr_server.py --port 8082

或使用 vllm 命令行:
    vllm serve Qwen/Qwen3-ASR-1.7B --port 8082
"""

import os
import sys
import argparse
import subprocess
from pathlib import Path

# 模型路径配置
DEFAULT_MODEL_PATH = "/home/bushuhui/.cache/modelscope/hub/models/Qwen/Qwen3-ASR-1.7B"
DEFAULT_PORT = 8082


def check_vllm_audio_installed():
    """检查 vllm[audio] 是否已安装"""
    try:
        import vllm
        from vllm import LLM
        # 检查音频依赖
        import torchaudio
        return True
    except ImportError as e:
        print(f"错误：缺少必要的依赖包：{e}")
        print("\n请安装 vllm[audio]:")
        print("  pip install 'vllm[audio]'")
        return False


def start_vllm_server(model_path: str, port: int, host: str = "0.0.0.0"):
    """
    启动 vLLM ASR 服务

    Args:
        model_path: 模型路径 (本地路径或 HuggingFace 模型名)
        port: 服务端口
        host: 服务主机地址
    """
    # 构建 vllm serve 命令
    cmd = [
        "vllm", "serve",
        model_path,
        "--host", host,
        "--port", str(port),
        "--api-key", "token-abc123",  # 设置 API key
    ]

    print("=" * 60)
    print("启动 vLLM Qwen3-ASR 服务")
    print("=" * 60)
    print(f"\n模型路径：{model_path}")
    print(f"服务地址：http://{host}:{port}")
    print(f"API 端点：http://{host}:{port}/v1")
    print("\n按 Ctrl+C 停止服务\n")
    print("-" * 60)

    try:
        # 启动服务
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        print(f"\n服务异常退出：{e}")
    except KeyboardInterrupt:
        print("\n\n服务已停止")


def main():
    parser = argparse.ArgumentParser(
        description="vLLM Qwen3-ASR 语音识别服务",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 使用本地模型路径
  python vllm_asr_server.py --model-path /path/to/Qwen3-ASR-1.7B

  # 使用 HuggingFace 模型 (自动下载)
  python vllm_asr_server.py --model-path Qwen/Qwen3-ASR-1.7B

  # 指定端口
  python vllm_asr_server.py --port 8082
        """
    )

    parser.add_argument(
        "--model-path", "-m",
        default=DEFAULT_MODEL_PATH,
        help=f"模型路径或 HuggingFace 模型名 (默认：{DEFAULT_MODEL_PATH})"
    )

    parser.add_argument(
        "--port", "-p",
        type=int,
        default=DEFAULT_PORT,
        help=f"服务端口 (默认：{DEFAULT_PORT})"
    )

    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="服务主机地址 (默认：0.0.0.0)"
    )

    args = parser.parse_args()

    # 检查 vllm 音频依赖
    if not check_vllm_audio_installed():
        sys.exit(1)

    # 检查模型是否存在
    if not os.path.exists(args.model_path):
        # 如果不是有效路径，假设是 HuggingFace 模型名
        if "/" not in args.model_path and not os.path.exists(args.model_path):
            print(f"警告：模型路径不存在：{args.model_path}")
            print("将尝试从 HuggingFace 下载模型...")

    # 启动服务
    start_vllm_server(args.model_path, args.port, args.host)


if __name__ == "__main__":
    main()
