#!/usr/bin/env python3
"""
Qwen3-Embedding-4B vllm 服务器启动脚本

使用方法:
1. 直接启动服务器:
   python vllm_embedding_server.py

2. 自定义端口启动:
   python vllm_embedding_server.py --port 8000

3. 查看帮助:
   python vllm_embedding_server.py --help

4. 后台启动 (推荐):
   nohup python vllm_embedding_server.py > server.log 2>&1 &

5. 使用 GPU 启动 (多 GPU 支持):
   CUDA_VISIBLE_DEVICES=0,1 python vllm_embedding_server.py

模型路径: /home/bushuhui/.cache/modelscope/hub/models/unsloth/Qwen3-Embedding-4B
"""

import os
import sys
import argparse
import subprocess
import signal
# 设置环境变量，解决部分 torch 版本兼容问题
os.environ.setdefault('VLLM_USE_MODELSCOPE', 'False')
os.environ.setdefault('VLLM_TARGET_DEVICE', 'cuda')
# 防止 CUDA 显存碎片化
os.environ.setdefault('PYTORCH_CUDA_ALLOC_CONF', 'expandable_segments:True')
import atexit

# 默认配置
DEFAULT_MODEL_PATH = "/home/bushuhui/.cache/modelscope/hub/models/unsloth/Qwen3-Embedding-4B"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8080


def parse_args():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(
        description="Qwen3-Embedding-4B vllm 服务器启动脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 基本启动
  python vllm_embedding_server.py

  # 自定义端口
  python vllm_embedding_server.py --port 8000

  # 自定义模型路径
  python vllm_embedding_server.py --model-path /path/to/model

  # 限制 GPU 显存使用
  python vllm_embedding_server.py --gpu-memory-utilization 0.8

  # 设置最大批处理大小
  python vllm_embedding_server.py --max-num-batched-tokens 4096

  # 后台运行
  nohup python vllm_embedding_server.py > server.log 2>&1 &
        """
    )

    parser.add_argument(
        "--model-path",
        type=str,
        default=DEFAULT_MODEL_PATH,
        help=f"模型路径 (默认：{DEFAULT_MODEL_PATH})"
    )
    parser.add_argument(
        "--host",
        type=str,
        default=DEFAULT_HOST,
        help=f"监听地址 (默认：{DEFAULT_HOST})"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PORT,
        help=f"监听端口 (默认：{DEFAULT_PORT})"
    )
    parser.add_argument(
        "--gpu-memory-utilization",
        type=float,
        default=0.6,
        help="GPU 显存使用比例 (默认：0.6，8GB GPU 建议使用 0.5-0.6)"
    )
    parser.add_argument(
        "--max-model-len",
        type=int,
        default=8192,
        help="最大模型长度 (默认：8192，减少显存占用)"
    )
    parser.add_argument(
        "--max-num-batched-tokens",
        type=int,
        default=8192,
        help="最大批处理 token 数 (默认：8192)"
    )
    parser.add_argument(
        "--max-num-seqs",
        type=int,
        default=256,
        help="最大序列数 (默认：256)"
    )
    parser.add_argument(
        "--tensor-parallel-size",
        type=int,
        default=1,
        help="张量并行大小，多 GPU 时使用 (默认：1)"
    )
    parser.add_argument(
        "--dtype",
        type=str,
        default="float16",
        choices=["auto", "float16", "bfloat16", "float32"],
        help="数据类型 (默认：float16，GTX 1080 等旧 GPU 必须使用 float16/half)"
    )
    parser.add_argument(
        "--trust-remote-code",
        action="store_true",
        help="信任远程代码 (HuggingFace 模型可能需要)"
    )
    parser.add_argument(
        "--enforce-eager",
        action="store_true",
        help="强制使用 eager 模式，减少显存占用"
    )
    parser.add_argument(
        "--enable-chunked-prefill",
        action="store_true",
        help="启用分块预填充，减少显存峰值"
    )
    parser.add_argument(
        "--api-key",
        type=str,
        default=None,
        help="API 密钥 (可选)"
    )
    parser.add_argument(
        "--ssl-keyfile",
        type=str,
        default=None,
        help="SSL 私钥文件路径 (可选)"
    )
    parser.add_argument(
        "--ssl-certfile",
        type=str,
        default=None,
        help="SSL 证书文件路径 (可选)"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="显示详细日志"
    )

    return parser.parse_args()


def build_vllm_command(args):
    """构建 vllm 启动命令"""
    cmd = [
        "python", "-m", "vllm.entrypoints.openai.api_server",
        "--model", args.model_path,
        "--task", "embedding",
        "--host", args.host,
        "--port", str(args.port),
        "--gpu-memory-utilization", str(args.gpu_memory_utilization),
        "--max-num-batched-tokens", str(args.max_num_batched_tokens),
        "--max-model-len", str(args.max_model_len),
        "--max-num-seqs", str(args.max_num_seqs),
        "--tensor-parallel-size", str(args.tensor_parallel_size),
        "--dtype", args.dtype,
    ]

    if args.trust_remote_code:
        cmd.append("--trust-remote-code")

    if args.enforce_eager:
        cmd.append("--enforce-eager")

    if args.enable_chunked_prefill:
        cmd.append("--enable-chunked-prefill")

    if args.api_key:
        cmd.extend(["--api-key", args.api_key])

    if args.ssl_keyfile:
        cmd.extend(["--ssl-keyfile", args.ssl_keyfile])

    if args.ssl_certfile:
        cmd.extend(["--ssl-certfile", args.ssl_certfile])

    if args.verbose:
        cmd.append("--verbose")

    return cmd


def start_server(args):
    """启动 vllm 服务器"""
    print("=" * 60)
    print("Qwen3-Embedding-4B vllm 服务器")
    print("=" * 60)

    # 检查模型路径
    if not os.path.exists(args.model_path):
        print(f"\n错误：模型路径不存在：{args.model_path}")
        print("请确认模型已下载到正确位置")
        sys.exit(1)

    print(f"\n模型路径：{args.model_path}")
    print(f"监听地址：http://{args.host}:{args.port}")
    print(f"GPU 显存使用比例：{args.gpu_memory_utilization}")
    print(f"最大批处理 tokens: {args.max_num_batched_tokens}")
    print(f"最大序列数：{args.max_num_seqs}")
    if args.tensor_parallel_size > 1:
        print(f"张量并行大小：{args.tensor_parallel_size}")

    print("\n" + "=" * 60)
    print("正在启动服务器...")
    print("=" * 60 + "\n")

    # 构建命令
    cmd = build_vllm_command(args)
    print(f"启动命令：{' '.join(cmd)}\n")

    # 启动进程
    process = subprocess.Popen(cmd)

    # 注册退出处理
    def cleanup():
        print("\n正在关闭服务器...")
        process.terminate()
        process.wait()

    atexit.register(cleanup)

    # 处理信号
    def signal_handler(sig, frame):
        print("\n收到退出信号，正在关闭...")
        process.terminate()
        process.wait()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    # 等待进程结束
    try:
        process.wait()
    except KeyboardInterrupt:
        print("\n用户中断，正在关闭...")
        process.terminate()
        process.wait()


def main():
    """主函数"""
    args = parse_args()
    start_server(args)


if __name__ == "__main__":
    main()
