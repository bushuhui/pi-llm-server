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

    # 使用 GPU (模型按需加载，空闲 90 秒后自动释放显存)
    python reranker_server.py --device cuda

    # 指定 GPU
    python reranker_server.py --device cuda:1

    # 自定义端口
    python reranker_server.py --port 8000

    # 自定义空闲超时时间 (秒)
    python reranker_server.py --device cuda --idle-timeout 300

    # 后台运行
    nohup python reranker_server.py > server.log 2>&1 &

特性:
    - 模型按需加载：首次请求时才加载到 GPU，启动时不占用显存
    - 空闲自动卸载：超过设定时间无请求时自动释放 GPU 显存
    - 自动重新加载：请求到来时自动重新加载模型
"""

import os
import sys
import argparse
import logging
import time
import asyncio
from typing import List, Optional
from contextlib import asynccontextmanager

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

# 默认配置
DEFAULT_MODEL_PATH = os.path.expanduser("~/.cache/modelscope/hub/models/Qwen/Qwen3-Reranker-0.6B")
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8093
DEFAULT_IDLE_TIMEOUT = 90  # 空闲超时（秒），默认 90 秒

# 全局变量
model = None
tokenizer = None
device = None
model_name = None
model_path_global = None  # 保存模型路径用于重新加载
idle_timeout_seconds = DEFAULT_IDLE_TIMEOUT  # 空闲超时配置
last_request_time = None  # 仅记录业务请求时间（不包括健康检测）
model_unloaded = False  # 标记模型是否已卸载
last_health_check_time = None  # 记录健康检测时间（不用于空闲检测）


# FastAPI 应用
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    # 启动时
    logger.info(f"空闲超时检测已启用，超时时间：{idle_timeout_seconds}秒")
    yield
    # 关闭时
    logger.info("服务关闭，释放资源...")
    unload_model()

app = FastAPI(
    title="Qwen3-Reranker API",
    description="Qwen3-Reranker 模型 reranker 服务",
    version=__version__,
    lifespan=lifespan
)


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


def unload_model():
    """卸载模型，释放 GPU 显存"""
    global model, tokenizer, device, model_unloaded

    if model is None:
        return

    if device is not None and str(device).startswith("cuda"):
        try:
            logger.info("卸载模型，释放 GPU 显存...")

            # 先删除模型引用
            model_copy = model
            tokenizer_copy = tokenizer
            model = None
            tokenizer = None

            # 强制删除引用
            del model_copy
            del tokenizer_copy

            # 等待 Python GC 清理引用
            import gc
            gc.collect()

            # 清理 CUDA 缓存和同步
            torch.cuda.empty_cache()
            torch.cuda.synchronize()

            model_unloaded = True
            logger.info("模型已卸载，GPU 显存已释放")

            # 记录当前显存使用情况（用于调试）
            if torch.cuda.is_available():
                allocated = torch.cuda.memory_allocated() / 1024**3
                reserved = torch.cuda.memory_reserved() / 1024**3
                logger.info(f"显存状态：已分配={allocated:.2f} GB, 预留={reserved:.2f} GB")
        except Exception as e:
            logger.error(f"卸载模型失败：{e}")
    else:
        logger.debug("模型在 CPU 上，无需卸载")


def clear_cuda_cache():
    """清理 CUDA 缓存，释放任务执行过程中的临时显存"""
    if device is not None and str(device).startswith("cuda"):
        try:
            torch.cuda.empty_cache()
            torch.cuda.synchronize()
            logger.debug("已清理 CUDA 临时缓存")
        except Exception as e:
            logger.debug(f"清理 CUDA 缓存失败：{e}")


def ensure_model_loaded(record_request=True):
    """
    确保模型已加载，如果已卸载则重新加载

    Args:
        record_request: 是否记录请求时间用于空闲检测
                       健康检测等接口应设为 False
    """
    global model, tokenizer, device, model_unloaded, last_request_time, model_name

    # 仅当需要时才记录请求时间
    if record_request:
        last_request_time = time.time()

    # 模型已加载，直接返回
    if model is not None and not model_unloaded:
        return

    # 重新加载模型
    logger.info("重新加载模型到 GPU...")
    try:
        use_cuda = str(device).startswith("cuda")

        tokenizer = AutoTokenizer.from_pretrained(
            model_path_global,
            trust_remote_code=True
        )

        if use_cuda:
            model = AutoModelForCausalLM.from_pretrained(
                model_path_global,
                trust_remote_code=True,
                dtype=torch.float16
            )
            model.to(device)
        else:
            model = AutoModelForCausalLM.from_pretrained(
                model_path_global,
                trust_remote_code=True,
                dtype=torch.float32,
                low_cpu_mem_usage=True
            )

        model.eval()
        model_unloaded = False

        # 设置模型名称
        model_name = os.path.basename(os.path.dirname(model_path_global)) + "/" + os.path.basename(model_path_global)

        logger.info("模型已重新加载到 GPU")
    except Exception as e:
        logger.error(f"加载模型失败：{e}")
        raise


async def check_idle_and_unload():
    """
    异步检查空闲超时并卸载模型
    在每次请求后启动，等待 idle_timeout_seconds 后检查
    """
    global model_unloaded

    await asyncio.sleep(idle_timeout_seconds)

    # 检查是否仍然空闲
    if last_request_time is not None:
        idle_time = time.time() - last_request_time
        if idle_time >= idle_timeout_seconds and not model_unloaded:
            # 在线程池中执行同步的 unload_model
            await asyncio.get_event_loop().run_in_executor(None, unload_model)
            logger.info(f"空闲超时 {idle_timeout_seconds} 秒，已卸载模型")


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
    global last_health_check_time
    last_health_check_time = time.time()

    # 获取当前显存使用情况
    gpu_info = {}
    if torch.cuda.is_available():
        gpu_info = {
            "allocated_gb": round(torch.cuda.memory_allocated() / 1024**3, 2),
            "reserved_gb": round(torch.cuda.memory_reserved() / 1024**3, 2),
            "max_gb": round(torch.cuda.get_device_properties(0).total_memory / 1024**3, 2)
        }

    return {
        "status": "healthy",
        "device": str(device) if device else "not_loaded",
        "model_loaded": model is not None and not model_unloaded,
        "idle_timeout": idle_timeout_seconds,
        "last_request": last_request_time,
        "last_health_check": last_health_check_time,
        "gpu_memory": gpu_info
    }


@app.post("/admin/unload-model")
async def unload_model_endpoint():
    """
    手动卸载模型，释放 GPU 显存
    用于在不需要使用时主动释放显存
    """
    global model_unloaded
    if model is not None and not model_unloaded:
        await asyncio.get_event_loop().run_in_executor(None, unload_model)
        return {"status": "ok", "message": "模型已卸载"}
    else:
        return {"status": "ok", "message": "模型已在卸载状态或未加载"}


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
    # 确保模型已加载（记录请求时间）
    ensure_model_loaded(record_request=True)

    # 启动后台检查任务
    asyncio.create_task(check_idle_and_unload())

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
    finally:
        # 任务完成后立即清理临时显存，仅保留模型本身占用
        clear_cuda_cache()


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
    parser.add_argument(
        "--idle-timeout",
        type=int,
        default=DEFAULT_IDLE_TIMEOUT,
        help=f"空闲超时（秒），超过此时间无请求将释放显存 (默认：{DEFAULT_IDLE_TIMEOUT})"
    )

    args = parser.parse_args()

    # 设置全局变量
    global idle_timeout_seconds, model_path_global, device
    idle_timeout_seconds = args.idle_timeout
    model_path_global = args.model_path

    # 检查模型路径
    if not os.path.exists(args.model_path):
        logger.error(f"模型路径不存在：{args.model_path}")
        sys.exit(1)

    # 设置设备（模型将在首次请求时加载）
    use_cuda = args.device.startswith("cuda") and torch.cuda.is_available()
    if use_cuda:
        device = torch.device(args.device)
        gpu_idx = 0
        if ":" in args.device:
            gpu_idx = int(args.device.split(":")[1])
        gpu_name = torch.cuda.get_device_name(gpu_idx)
        gpu_memory = torch.cuda.get_device_properties(gpu_idx).total_memory / 1024**3
        logger.info(f"检测到 GPU: {gpu_name} ({gpu_memory:.1f} GB)")
        logger.info(f"模型将在首次请求时加载到 GPU，空闲 {idle_timeout_seconds} 秒后自动释放显存")
    else:
        device = torch.device("cpu")
        logger.info("使用 CPU 运行模型，空闲超时卸载功能已禁用")

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
