#!/usr/bin/env python3
"""
Qwen3-Reranker 服务器
使用 HuggingFace Transformers + FastAPI 运行 reranker 服务
支持 GPU/CPU 模式

依赖安装:
    pip install fastapi uvicorn torch transformers

使用方法:
    # 基本启动 (默认 CPU)
    python reranker_server.py

    # 使用 GPU
    python reranker_server.py --device cuda

    # 指定 GPU
    python reranker_server.py --device cuda:1

    # 自定义端口
    python reranker_server.py --port 8000

    # 后台运行
    nohup python reranker_server.py > server.log 2>&1 &
"""

import os
import sys
import argparse
import logging
import time
from typing import List, Optional

import torch
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import uvicorn

# 导入版本号
from pi_llm_server import __version__

# 尝试导入 transformers
try:
    from transformers import AutoModelForCausalLM, AutoTokenizer
except ImportError:
    logger.error("需要安装 transformers")
    logger.error("请运行：pip install transformers torch")
    sys.exit(1)

# 配置日志
def setup_logging(service_name: str):
    """配置日志，输出到控制台和文件"""
    logs_dir = os.path.expanduser("~/.cache/pi-llm-server/logs")
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

logger = setup_logging("reranker")

# FastAPI 应用
app = FastAPI(
    title="Qwen3-Reranker API",
    description="Qwen3-Reranker 模型 reranker 服务",
    version=__version__
)

# 全局变量
model = None
tokenizer = None
device = None
model_name = None

# 默认配置
DEFAULT_MODEL_PATH = os.path.expanduser("~/.cache/modelscope/hub/models/Qwen/Qwen3-Reranker-0.6B")
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8093


# ==================== 请求/响应模型 ====================

class RerankRequest(BaseModel):
    model: Optional[str] = ""
    query: str
    documents: List[str]
    top_n: Optional[int] = None
    instruction: Optional[str] = None
    encoding_format: Optional[str] = None  # 保留用于未来扩展


class RerankResult(BaseModel):
    index: int
    document: str
    relevance_score: float


class RerankUsage(BaseModel):
    prompt_tokens: int
    total_tokens: int


class RerankResponse(BaseModel):
    model: str
    results: List[RerankResult]
    usage: RerankUsage


# ==================== 模型加载 ====================

def load_model(model_path: str, device_str: str = "cpu"):
    """加载 reranker 模型"""
    global model, tokenizer, device, model_name

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
        tokenizer = AutoTokenizer.from_pretrained(
            model_path,
            trust_remote_code=True
        )

        if use_cuda:
            logger.info(f"尝试使用 {device_str} 加载...")
            model = AutoModelForCausalLM.from_pretrained(
                model_path,
                trust_remote_code=True,
                dtype=torch.float16
            )
            device = torch.device(device_str)
            model.to(device)
            logger.info(f"模型加载成功，使用 GPU: {gpu_name}")
        else:
            logger.info("使用 CPU 加载...")
            model = AutoModelForCausalLM.from_pretrained(
                model_path,
                trust_remote_code=True,
                dtype=torch.float32,
                low_cpu_mem_usage=True
            )
            device = torch.device("cpu")
            logger.info("模型加载成功，使用 CPU")

    except torch.OutOfMemoryError as e:
        if use_cuda:
            logger.warning(f"GPU 显存不足，切换到 CPU: {e}")
            model = AutoModelForCausalLM.from_pretrained(
                model_path,
                trust_remote_code=True,
                dtype=torch.float32,
                low_cpu_mem_usage=True
            )
            device = torch.device("cpu")
            logger.info("模型已在 CPU 上加载")
        else:
            raise
    except Exception as e:
        logger.error(f"模型加载失败：{e}")
        sys.exit(1)

    model.eval()

    # 显示模型信息
    total_params = sum(p.numel() for p in model.parameters())
    logger.info(f"模型参数：{total_params / 1e6:.1f}M")


# ==================== Rerank 计算 ====================

# Qwen3-Reranker 的 prompt 模板
RERANK_PREFIX = '<|im_start|>system\nJudge whether the Document is relevant to the Query. Answer only "yes" or "no".<|im_end|>\n<|im_start|>user\n'
RERANK_SUFFIX = '<|im_end|>\n<|im_start|>assistant\n'
RERANK_TOKEN_FALSE = 'no'
RERANK_TOKEN_TRUE = 'yes'


def format_pairs(query: str, documents: List[str]) -> List[str]:
    """格式化 query-document 对"""
    pairs = []
    for doc in documents:
        text = f"{RERANK_PREFIX}<Query>{query}</Query>\n<Document>{doc}</Document>{RERANK_SUFFIX}"
        pairs.append(text)
    return pairs


def compute_rerank_scores(query: str, documents: List[str]) -> List[float]:
    """计算 rerank 分数"""
    pairs = format_pairs(query, documents)

    # 获取 yes/no token id
    token_false_id = tokenizer.convert_tokens_to_ids(RERANK_TOKEN_FALSE)
    token_true_id = tokenizer.convert_tokens_to_ids(RERANK_TOKEN_TRUE)

    scores = []
    for text in pairs:
        inputs = tokenizer(
            text,
            return_tensors="pt",
            padding=True,
            truncation=True,
            max_length=8192
        )
        inputs = {k: v.to(device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = model(**inputs)
            # CausalLM: 取最后一个 token 的 logits（预测下一个 token）
            logits = outputs.logits[:, -1, :]

            # 获取 yes/no 的 logit
            true_logit = logits[0, token_true_id].item()
            false_logit = logits[0, token_false_id].item()

            # sigmoid 归一化
            import math
            score = 1.0 / (1.0 + math.exp(-(true_logit - false_logit)))
            scores.append(score)

    return scores


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


@app.post("/v1/rerank")
async def rerank(request: RerankRequest):
    """Rerank 接口"""
    if model is None:
        raise HTTPException(status_code=503, detail="模型未加载")

    try:
        if not request.query:
            raise HTTPException(status_code=400, detail="query 不能为空")
        if not request.documents:
            raise HTTPException(status_code=400, detail="documents 不能为空")

        start_time = time.time()
        scores = compute_rerank_scores(request.query, request.documents)
        elapsed = time.time() - start_time

        logger.info(f"Rerank {len(request.documents)} 条文档，耗时 {elapsed:.3f}s")

        # 构建结果
        results = [
            RerankResult(
                index=i,
                document=doc,
                relevance_score=score
            )
            for i, (doc, score) in enumerate(zip(request.documents, scores))
        ]

        # 按分数降序排列
        results.sort(key=lambda x: x.relevance_score, reverse=True)

        # top_n 截断
        if request.top_n is not None and request.top_n > 0:
            results = results[:request.top_n]

        # 计算 token 数
        total_tokens = sum(
            len(tokenizer.encode(f"{request.query} {doc}"))
            for doc in request.documents
        )

        return RerankResponse(
            model=model_name,
            results=results,
            usage=RerankUsage(
                prompt_tokens=total_tokens,
                total_tokens=total_tokens
            )
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Rerank 失败：{e}")
        raise HTTPException(status_code=500, detail=str(e))


# ==================== 主函数 ====================

def main():
    parser = argparse.ArgumentParser(
        description="Qwen3-Reranker 服务器 (HuggingFace + FastAPI)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 基本启动 (默认 CPU)
  python reranker_server.py

  # GPU 模式
  python reranker_server.py --device cuda

  # 指定 GPU
  python reranker_server.py --device cuda:1

  # 自定义端口和模型
  python reranker_server.py --port 8000 --model-path /path/to/model

  # 后台运行
  nohup python reranker_server.py > server.log 2>&1 &
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
