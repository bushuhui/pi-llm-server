#!/usr/bin/env python3
"""
Qwen3-Embedding 服务器
使用 HuggingFace sentence-transformers + FastAPI 运行 embedding 服务
支持 Qwen3-Embedding-0.6B 和 Qwen3-Embedding-4B 模型

依赖安装:
    pip install fastapi uvicorn sentence-transformers torch

使用方法:
    # 使用 Qwen3-Embedding-0.6B (默认 CPU)
    python embedding_server.py

    # 使用 GPU
    python embedding_server.py --device cuda

    # 使用 Qwen3-Embedding-4B (需要 >10GB 显存)
    python embedding_server.py --device cuda --model-path /path/to/Qwen3-Embedding-4B

    # 指定 GPU
    python embedding_server.py --device cuda:1

    # 后台运行
    nohup python embedding_server.py > server.log 2>&1 &
"""

import os
import sys
import argparse
import logging
import time
from typing import List, Optional, Union

import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

# 尝试导入 sentence-transformers
try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    logger.error("需要安装 sentence-transformers")
    logger.error("请运行：pip install sentence-transformers")
    sys.exit(1)

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

logger = setup_logging("embedding")

# FastAPI 应用
app = FastAPI(
    title="Qwen3-Embedding API",
    description="Qwen3-Embedding 模型 embedding 服务",
    version="1.0.0"
)

# 全局变量
model = None
device = None
model_name = None

# 默认配置
DEFAULT_MODEL_PATH = "/home/bushuhui/.cache/modelscope/hub/models/unsloth/Qwen3-Embedding-0.6B"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8091


# ==================== 请求/响应模型 ====================

class EmbeddingRequest(BaseModel):
    input: Union[str, List[str]]
    model: str = ""
    encoding_format: Optional[str] = "float"


class EmbeddingData(BaseModel):
    object: str = "embedding"
    embedding: List[float]
    index: int


class EmbeddingUsage(BaseModel):
    prompt_tokens: int
    total_tokens: int


class EmbeddingResponse(BaseModel):
    object: str = "list"
    data: List[EmbeddingData]
    model: str
    usage: EmbeddingUsage


class SimilarityRequest(BaseModel):
    text1: str
    text2: str


# ==================== 模型加载 ====================

def load_model(model_path: str, device_str: str = "cuda"):
    """加载 embedding 模型"""
    global model, device, model_name

    # 从路径提取模型名
    model_name = os.path.basename(os.path.dirname(model_path)) + "/" + os.path.basename(model_path)

    # 判断设备
    use_cuda = device_str.startswith("cuda") and torch.cuda.is_available()

    if device_str.startswith("cuda") and not torch.cuda.is_available():
        logger.warning("未检测到 GPU，自动切换到 CPU")

    if use_cuda:
        gpu_idx = 0
        if ":" in device_str:
            gpu_idx = int(device_str.split(":")[1])
        gpu_name = torch.cuda.get_device_name(gpu_idx)
        gpu_memory = torch.cuda.get_device_properties(gpu_idx).total_memory / 1024**3
        logger.info(f"检测到 GPU: {gpu_name} ({gpu_memory:.1f} GB)")

    logger.info(f"正在加载模型：{model_path}")

    try:
        if use_cuda:
            logger.info(f"尝试使用 {device_str} 加载...")
            model = SentenceTransformer(
                model_path,
                device=device_str,
                trust_remote_code=True
            )
            device = torch.device(device_str)
            logger.info(f"模型加载成功，使用 GPU: {gpu_name}")
        else:
            logger.info("使用 CPU 加载...")
            model = SentenceTransformer(
                model_path,
                device="cpu",
                trust_remote_code=True,
                model_kwargs={"low_cpu_mem_usage": True}
            )
            device = torch.device("cpu")
            logger.info("模型加载成功，使用 CPU")

    except torch.OutOfMemoryError as e:
        if use_cuda:
            logger.warning(f"GPU 显存不足，切换到 CPU: {e}")
            model = SentenceTransformer(
                model_path,
                device="cpu",
                trust_remote_code=True,
                model_kwargs={"low_cpu_mem_usage": True}
            )
            device = torch.device("cpu")
            logger.info("模型已在 CPU 上加载")
        else:
            raise

    # 显示模型信息
    total_params = sum(p.numel() for p in model.parameters())
    embedding_dim = model.get_sentence_embedding_dimension()
    logger.info(f"模型参数：{total_params / 1e6:.1f}M, 向量维度：{embedding_dim}")


# ==================== API 端点 ====================

@app.get("/health")
async def health_check():
    """健康检查"""
    return {"status": "healthy", "device": str(device) if device else "not_loaded"}


@app.get("/v1/models")
async def list_models():
    """列出可用模型"""
    return {
        "object": "list",
        "data": [
            {
                "id": model_name,
                "object": "model",
                "owned_by": "local"
            }
        ]
    }


@app.post("/v1/embeddings")
async def create_embeddings(request: EmbeddingRequest):
    """OpenAI 兼容的 embedding 接口"""
    if model is None:
        raise HTTPException(status_code=503, detail="模型未加载")

    try:
        # 处理输入
        if isinstance(request.input, str):
            input_texts = [request.input]
        else:
            input_texts = request.input

        if not input_texts:
            raise HTTPException(status_code=400, detail="输入文本不能为空")

        start_time = time.time()

        # 生成 embedding
        embeddings = model.encode(
            input_texts,
            convert_to_tensor=False,
            show_progress_bar=False
        )

        elapsed = time.time() - start_time
        logger.info(f"处理 {len(input_texts)} 条文本，耗时 {elapsed:.3f}s")

        # 精确计算 token 数
        tokenizer = model.tokenizer
        total_tokens = sum(len(tokenizer.encode(t)) for t in input_texts)

        # 构建响应
        data = [
            EmbeddingData(
                embedding=emb.tolist() if hasattr(emb, 'tolist') else list(emb),
                index=i
            )
            for i, emb in enumerate(embeddings)
        ]

        return EmbeddingResponse(
            data=data,
            model=model_name,
            usage=EmbeddingUsage(
                prompt_tokens=total_tokens,
                total_tokens=total_tokens
            )
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"生成 embedding 失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/v1/similarity")
async def calculate_similarity(request: SimilarityRequest):
    """
    计算两个文本的余弦相似度

    响应格式: {"similarity": 0.95}
    """
    if model is None:
        raise HTTPException(status_code=503, detail="模型未加载")

    try:
        emb1 = model.encode(request.text1, convert_to_tensor=True)
        emb2 = model.encode(request.text2, convert_to_tensor=True)

        sim = torch.nn.functional.cosine_similarity(
            emb1.unsqueeze(0), emb2.unsqueeze(0)
        ).item()

        return {"similarity": sim}

    except Exception as e:
        logger.error(f"计算相似度失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 主函数 ====================

def main():
    parser = argparse.ArgumentParser(
        description="Qwen3-Embedding 服务器 (HuggingFace + FastAPI)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 基本启动 (默认 CPU)
  python embedding_server.py

  # GPU 模式
  python embedding_server.py --device cuda

  # 指定 GPU
  python embedding_server.py --device cuda:1

  # 自定义端口和模型
  python embedding_server.py --port 8000 --model-path /path/to/model

  # 后台运行
  nohup python embedding_server.py > server.log 2>&1 &
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
        "--device",
        type=str,
        default="cpu",
        help="运行设备 (默认：cpu，可选：cpu, cuda, cuda:0, cuda:1 等)"
    )

    args = parser.parse_args()

    # 检查模型路径
    if not os.path.exists(args.model_path):
        logger.error(f"模型路径不存在：{args.model_path}")
        sys.exit(1)

    # 加载模型
    load_model(args.model_path, device_str=args.device)

    # 启动服务
    logger.info(f"启动服务器：http://{args.host}:{args.port}")
    uvicorn.run(
        app,
        host=args.host,
        port=args.port,
        log_level="info"
    )


if __name__ == "__main__":
    main()
