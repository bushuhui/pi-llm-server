#!/usr/bin/env python3
"""
Qwen3-Embedding CPU 服务器
使用 HuggingFace Transformers + FastAPI 运行 embedding 服务
适用于 GPU 显存不足的情况，纯 CPU 运行

依赖安装:
    pip install fastapi uvicorn torch transformers

使用方法:
    # 基本启动 (CPU 模式)
    python vllm_embedding_server_cpu.py

    # 自定义端口
    python vllm_embedding_server_cpu.py --port 8000

    # 后台运行
    nohup python vllm_embedding_server_cpu.py > server.log 2>&1 &
"""

import os
import sys
import argparse
import logging
import time
from typing import List, Optional, Union

import torch
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
import uvicorn

# 尝试导入 transformers
try:
    from transformers import AutoModel, AutoTokenizer
except ImportError:
    print("错误：需要安装 transformers")
    print("请运行：pip install transformers torch")
    sys.exit(1)

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# FastAPI 应用
app = FastAPI(
    title="Qwen3-Embedding API",
    description="Qwen3-Embedding 模型 embedding 服务 (CPU 模式)",
    version="1.0.0"
)

# 全局变量
model = None
tokenizer = None
device = None
model_name = None

# 默认配置
DEFAULT_MODEL_PATH = "/home/bushuhui/.cache/modelscope/hub/models/unsloth/Qwen3-Embedding-0.6B"
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8080


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


# ==================== 模型加载 ====================

def load_model(model_path: str):
    """加载 embedding 模型"""
    global model, tokenizer, device, model_name

    device = torch.device("cpu")
    model_name = os.path.basename(os.path.dirname(model_path)) + "/" + os.path.basename(model_path)

    logger.info(f"正在加载模型：{model_path}")
    logger.info("使用 CPU 加载...")

    try:
        tokenizer = AutoTokenizer.from_pretrained(
            model_path,
            trust_remote_code=True
        )

        model = AutoModel.from_pretrained(
            model_path,
            trust_remote_code=True,
            dtype=torch.float32
        )
        model.to(device)
        model.eval()

        logger.info("模型加载完成 (CPU 模式)")

    except Exception as e:
        logger.error(f"模型加载失败：{e}")
        sys.exit(1)


# ==================== 推理函数 ====================

def compute_embeddings(texts: List[str]) -> List[List[float]]:
    """计算文本的 embedding 向量"""
    encoded = tokenizer(
        texts,
        padding=True,
        truncation=True,
        max_length=8192,
        return_tensors="pt"
    )
    encoded = {k: v.to(device) for k, v in encoded.items()}

    with torch.no_grad():
        outputs = model(**encoded)
        # 使用 last token pooling (模型配置: pooling_mode_lasttoken=true)
        attention_mask = encoded["attention_mask"]
        hidden_state = outputs.last_hidden_state
        # 找到每个序列最后一个非 padding token 的位置
        seq_lengths = attention_mask.sum(dim=1) - 1  # 索引从 0 开始
        batch_size = hidden_state.shape[0]
        embeddings = hidden_state[torch.arange(batch_size, device=device), seq_lengths]
        # L2 归一化
        embeddings = torch.nn.functional.normalize(embeddings, p=2, dim=1)

    return embeddings.tolist()


# ==================== API 端点 ====================

@app.post("/v1/embeddings")
async def create_embedding(request: EmbeddingRequest):
    """OpenAI 兼容的 embedding 接口"""
    try:
        # 处理输入
        if isinstance(request.input, str):
            texts = [request.input]
        else:
            texts = request.input

        if not texts:
            raise HTTPException(status_code=400, detail="输入文本不能为空")

        start_time = time.time()
        embeddings = compute_embeddings(texts)
        elapsed = time.time() - start_time

        logger.info(f"处理 {len(texts)} 条文本，耗时 {elapsed:.3f}s")

        # 计算 token 数
        total_tokens = sum(len(tokenizer.encode(t)) for t in texts)

        # 构建响应
        data = [
            EmbeddingData(embedding=emb, index=i)
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
        logger.error(f"Embedding 计算失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/v1/models")
async def list_models():
    """列出可用模型"""
    return {
        "object": "list",
        "data": [
            {
                "id": model_name,
                "object": "model",
                "owned_by": "local",
            }
        ]
    }


@app.get("/health")
async def health():
    """健康检查"""
    return {"status": "ok"}


# ==================== 主函数 ====================

def main():
    parser = argparse.ArgumentParser(
        description="Qwen3-Embedding CPU 服务器 (HuggingFace + FastAPI)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 基本启动
  python vllm_embedding_server_cpu.py

  # 自定义端口
  python vllm_embedding_server_cpu.py --port 8000

  # 后台运行
  nohup python vllm_embedding_server_cpu.py > server.log 2>&1 &
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

    args = parser.parse_args()

    # 检查模型路径
    if not os.path.exists(args.model_path):
        logger.error(f"模型路径不存在：{args.model_path}")
        sys.exit(1)

    # 加载模型
    load_model(args.model_path)

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
