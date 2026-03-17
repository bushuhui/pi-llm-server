#!/usr/bin/env python3
"""
基于 vLLM 的 Qwen3-ASR 语音识别服务（使用 qwen-asr 包）

使用方法:
    # 安装依赖
    pip install -U qwen-asr[vllm]

    # 启动服务
    python asr_server.py --model-path /home/bushuhui/.cache/modelscope/hub/models/Qwen/Qwen3-ASR-1.7B --port 8092

    # 或使用 HuggingFace 模型名
    python asr_server.py --model-path Qwen/Qwen3-ASR-1.7B --port 8092
"""

import os
import sys
import argparse
import subprocess
import logging
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

logger = setup_logging("asr")

# 检查 nvcc 版本是否与 PyTorch CUDA 版本匹配，不匹配则使用 TRITON_ATTN 后端
import shutil
import subprocess as _sp

def _need_triton_backend():
    """检查是否需要使用 TRITON_ATTN 后端（nvcc 不存在或版本不匹配）"""
    nvcc_path = shutil.which("nvcc")
    if not nvcc_path and not os.path.exists("/usr/local/cuda"):
        return True
    try:
        import torch
        torch_cuda = torch.version.cuda  # e.g. "12.8"
        torch_major = int(torch_cuda.split(".")[0])
        result = _sp.run([nvcc_path or "nvcc", "--version"],
                         capture_output=True, text=True, timeout=5)
        # 从输出中提取版本号，如 "release 10.1, V10.1.243"
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


def check_qwen_asr_installed():
    """检查 qwen-asr 是否已安装"""
    try:
        from qwen_asr import Qwen3ASRModel
        return True
    except ImportError:
        logger.error("=" * 60)
        logger.error("qwen-asr 包未安装")
        logger.error("=" * 60)
        logger.error("请安装 qwen-asr[vllm] 包:")
        logger.error("  pip install -U qwen-asr[vllm]")
        logger.error("  uv pip install -U qwen-asr[vllm]")
        logger.error("如需最快推理速度，还可安装 FlashAttention 2:")
        logger.error("  pip install -U flash-attn --no-build-isolation")
        logger.error("=" * 60)
        return False


def start_qwen_asr_server(model_path: str, port: int, host: str = "0.0.0.0",
                          gpu_memory_utilization: float = 0.9, max_model_len: int = 32768):
    """
    使用 qwen-asr-serve 命令启动服务

    Args:
        model_path: 模型路径
        port: 服务端口
        host: 服务主机地址
        gpu_memory_utilization: GPU 显存使用率
        max_model_len: 最大模型长度
    """
    # 使用 qwen-asr-serve 命令（qwen-asr 包提供的包装器）
    # 从路径提取短模型名，如 "Qwen/Qwen3-ASR-1.7B"
    served_name = os.path.basename(os.path.dirname(model_path)) + "/" + os.path.basename(model_path)

    cmd = [
        "qwen-asr-serve",
        model_path,
        "--gpu-memory-utilization", str(gpu_memory_utilization),
        "--max-model-len", str(max_model_len),
        "--enforce-eager",
        "--served-model-name", served_name,
        "--host", host,
        "--port", str(port),
    ]

    logger.info("=" * 60)
    logger.info("启动 Qwen3-ASR vLLM 服务")
    logger.info("=" * 60)
    logger.info(f"模型路径：{model_path}")
    logger.info(f"服务地址：http://{host}:{port}")
    logger.info(f"API 端点：http://{host}:{port}/v1")
    logger.info(f"GPU 显存使用率：{gpu_memory_utilization}")
    logger.info(f"最大模型长度：{max_model_len}")
    logger.info("按 Ctrl+C 停止服务")
    logger.info("-" * 60)

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"服务异常退出：{e}")
    except KeyboardInterrupt:
        logger.info("服务已停止")
    except FileNotFoundError:
        logger.error("找不到 qwen-asr-serve 命令，请确保已正确安装 qwen-asr[vllm] 包")


def start_with_vllm_serve(model_path: str, port: int, host: str = "0.0.0.0"):
    """
    使用 vllm serve 命令启动服务（需要 nightly 版本）
    """
    cmd = [
        "vllm", "serve",
        model_path,
        "--host", host,
        "--port", str(port),
    ]

    logger.info("=" * 60)
    logger.info("启动 vLLM Qwen3-ASR 服务")
    logger.info("=" * 60)
    logger.info(f"模型路径：{model_path}")
    logger.info(f"服务地址：http://{host}:{port}")

    try:
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"服务异常退出：{e}")
    except KeyboardInterrupt:
        logger.info("服务已停止")


def main():
    parser = argparse.ArgumentParser(
        description="Qwen3-ASR vLLM 语音识别服务",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 使用本地模型路径
  python asr_server.py --model-path /path/to/Qwen3-ASR-1.7B

  # 使用 HuggingFace 模型名
  python asr_server.py --model-path Qwen/Qwen3-ASR-1.7B

  # 指定端口和 GPU 显存使用率
  python asr_server.py --port 8082 --gpu-memory-utilization 0.8
        """
    )

    parser.add_argument(
        "--model-path", "-m",
        default="/home/bushuhui/.cache/modelscope/hub/models/Qwen/Qwen3-ASR-1.7B",
        help="模型路径或 HuggingFace 模型名"
    )

    parser.add_argument(
        "--port", "-p",
        type=int,
        default=8092,
        help="服务端口 (默认：8082)"
    )

    parser.add_argument(
        "--host",
        default="0.0.0.0",
        help="服务主机地址 (默认：0.0.0.0)"
    )

    parser.add_argument(
        "--gpu-memory-utilization",
        type=float,
        default=0.45,
        help="GPU 显存使用率 (默认：0.45 for 24G VRAM)"
    )

    parser.add_argument(
        "--max-model-len",
        type=int,
        default=32768,
        help="最大模型长度 (默认：32768，减小可节省显存)"
    )

    parser.add_argument(
        "--use-vllm",
        action="store_true",
        help="使用 vllm serve 命令而不是 qwen-asr-serve"
    )

    args = parser.parse_args()

    # 检查依赖
    if not check_qwen_asr_installed():
        sys.exit(1)

    # 启动服务
    if args.use_vllm:
        start_with_vllm_serve(args.model_path, args.port, args.host)
    else:
        start_qwen_asr_server(args.model_path, args.port, args.host, args.gpu_memory_utilization, args.max_model_len)


if __name__ == "__main__":
    main()
