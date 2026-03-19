#!/usr/bin/env python3
"""
vllm Reranker 客户端测试工具
用于测试 vllm 提供的 reranker 服务

使用方法:
1. 测试单个文本对相关性评分:
   python reranker_client.py rerank -q "什么是人工智能？" -d "人工智能是计算机科学的一个分支"

2. 批量测试相关性评分:
   python reranker_client.py rerank-batch

3. 文档排序 (rerank 多个文档):
   python reranker_client.py rerank-docs -q "人工智能技术" -d "文档 1" "文档 2" "文档 3"

4. 查看 API 信息:
   python reranker_client.py info
"""

import os
import sys
import argparse
import requests
import json
import math
import logging
from datetime import datetime

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

logger = setup_logging("reranker_client")

# 默认配置
DEFAULT_BASE_URL = "http://localhost:8093"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
RESULTS_DIR = os.path.join(SCRIPT_DIR, "results")


# ==================== 信息查询功能 ====================

def get_server_info(base_url: str):
    """获取服务器信息和可用模型"""
    logger.info("=" * 60)
    logger.info("vllm Reranker 服务器信息")
    logger.info("=" * 60)

    try:
        # 获取模型列表
        response = requests.get(f"{base_url}/v1/models", timeout=30)
        response.raise_for_status()
        models_data = response.json()
        models = models_data.get('data', [])

        logger.info(f"服务器地址：{base_url}, 可用模型数量：{len(models)}")

        for model in models:
            logger.info(f"  - ID: {model.get('id', 'unknown')}")
            logger.info(f"    对象：{model.get('object', 'unknown')}")
            logger.info(f"    最大长度：{model.get('max_model_len', 'N/A')}")

        # 测试健康检查
        health_response = requests.get(f"{base_url}/health", timeout=10)
        if health_response.status_code == 200:
            logger.info("健康检查：OK")
        else:
            logger.info("健康检查：未知")

        return models

    except requests.exceptions.ConnectionError:
        logger.error(f"无法连接到服务器：{base_url}，请确认服务器已启动")
        return []
    except Exception as e:
        logger.error(f"获取服务器信息失败：{e}")
        return []


# ==================== 单个文本对 Rerank ====================

def get_model_name(base_url: str, model: str = None) -> str:
    """获取模型名称"""
    if model:
        return model
    try:
        response = requests.get(f"{base_url}/v1/models", timeout=30)
        response.raise_for_status()
        models_data = response.json()
        models = models_data.get('data', [])
        if models:
            return models[0].get('id', '')
    except:
        pass
    return ''


def rerank_single_pair(base_url: str, model: str, query: str, document: str, instruction: str = None):
    """
    对单个查询 - 文档对进行相关性评分

    Args:
        base_url: vllm 服务地址
        model: 模型名称
        query: 查询文本
        document: 文档文本
        instruction: 任务指令 (可选)
    """
    # 自动获取模型名称
    model_name = get_model_name(base_url, model)

    logger.info("=" * 60)
    logger.info(f"Reranker 相关性评分 - 使用模型：{model_name}")
    logger.info("=" * 60)
    logger.info(f"查询：{query}")
    logger.info(f"文档：{document[:100]}{'...' if len(document) > 100 else ''}")
    logger.info("正在计算相关性评分...")

    url = f"{base_url}/v1/rerank"

    payload = {
        "model": model_name,
        "query": query,
        "documents": [document],
    }

    if instruction:
        payload["instruction"] = instruction

    try:
        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()

        # 解析结果
        results = result.get('results', [])
        if results:
            score = results[0].get('relevance_score', 0.0)
            logger.info(f"评分成功，相关性得分：{score:.6f}")
            # 显示得分条
            score_bar = "█" * int(score * 20)
            logger.info(f"可视化：{score_bar} ({score:.4f})")
        else:
            logger.warning("未返回结果")

        return results

    except Exception as e:
        logger.error(f"错误：{e}")
        return None


# ==================== 批量 Rerank ====================

def rerank_batch(base_url: str, model: str, instruction: str = None):
    """
    批量测试 Reranker 模型

    Args:
        base_url: vllm 服务地址
        model: 模型名称
        instruction: 任务指令 (可选)
    """
    # 自动获取模型名称
    model_name = get_model_name(base_url, model)

    logger.info("=" * 60)
    logger.info(f"Reranker 批量测试 - 使用模型：{model_name}")
    logger.info("=" * 60)

    # 默认测试数据
    test_data = [
        # AI 技术相关
        {"query": "什么是人工智能？", "documents": [
            "人工智能是计算机科学的一个分支，致力于创建智能系统",
            "机器学习使用算法让计算机从数据中学习并改进性能",
            "今天天气真好阳光明媚"
        ]},
        # 天气相关
        {"query": "今天天气如何", "documents": [
            "今天晴空万里，阳光明媚，适合外出活动",
            "根据天气预报，明天有 80% 的降水概率",
            "人工智能正在改变我们的生活"
        ]},
        # 科技产品
        {"query": "智能手机推荐", "documents": [
            "最新的智能手机具有强大的处理器和高清晰度的摄像头",
            "选择笔记本电脑时需考虑处理器、内存和存储容量",
            "猫咪喜欢吃鱼和老鼠"
        ]},
    ]

    url = f"{base_url}/v1/rerank"
    all_results = []

    logger.info(f"测试查询数量：{len(test_data)}")
    logger.info("正在计算相关性评分...")

    try:
        for i, item in enumerate(test_data):
            payload = {
                "model": model,
                "query": item['query'],
                "documents": item['documents'],
            }

            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()
            result = response.json()

            results = result.get('results', [])

            logger.info(f"[{i+1}/{len(test_data)}] 查询：{item['query']}")
            logger.info("-" * 60)

            query_results = []
            for res in results:
                idx = res.get('index', 0)
                score = res.get('relevance_score', 0.0)
                doc_text = item['documents'][idx][:50] + "..." if len(item['documents'][idx]) > 50 else item['documents'][idx]
                score_bar = "█" * int(score * 20)
                logger.info(f"  [{idx}] 相关性：{score:.4f} {score_bar}")
                logger.info(f"      文档：{doc_text}")
                query_results.append({
                    'query': item['query'],
                    'document_index': idx,
                    'document': item['documents'][idx],
                    'score': score
                })

            all_results.extend(query_results)

        # 保存结果
        output_file = os.path.join(RESULTS_DIR, f"reranker_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        output_data = {
            "model": model,
            "timestamp": datetime.now().isoformat(),
            "instruction": instruction,
            "results": all_results
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        logger.info(f"详细结果已保存到：{output_file}")

    except Exception as e:
        logger.error(f"错误：{e}")


# ==================== 文档排序 ====================

def rerank_documents(base_url: str, model: str, query: str, documents: list, instruction: str = None):
    """
    对多个文档进行相关性排序

    Args:
        base_url: vllm 服务地址
        model: 模型名称
        query: 查询文本
        documents: 文档列表
        instruction: 任务指令 (可选)
    """
    # 自动获取模型名称
    model_name = get_model_name(base_url, model)

    logger.info("=" * 60)
    logger.info(f"Reranker 文档排序 - 使用模型：{model_name}")
    logger.info("=" * 60)

    if not documents:
        logger.error("错误：请提供文档列表")
        return

    url = f"{base_url}/v1/rerank"

    payload = {
        "model": model,
        "query": query,
        "documents": documents,
    }

    if instruction:
        payload["instruction"] = instruction

    logger.info(f"查询：{query}")
    logger.info(f"文档数量：{len(documents)}")
    logger.info("正在计算相关性评分...")

    try:
        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()
        result = response.json()

        results = result.get('results', [])

        # 构建结果列表
        ranked_results = []
        for res in results:
            idx = res.get('index', 0)
            score = res.get('relevance_score', 0.0)
            ranked_results.append({
                'index': idx,
                'document': documents[idx],
                'score': score
            })
            logger.info(f"文档 [{idx}] 相关性：{score:.4f}")

        # 按相关性分数排序
        ranked_results.sort(key=lambda x: x['score'], reverse=True)

        logger.info("排序结果 (按相关性从高到低):")
        logger.info("=" * 60)

        for i, result in enumerate(ranked_results):
            score_bar = "█" * int(result['score'] * 20)
            logger.info(f"  [{i+1}] 相关性：{result['score']:.4f} {score_bar}")
            logger.info(f"      文档：{result['document']}")

        # 保存结果
        output_file = os.path.join(RESULTS_DIR, f"reranker_ranked_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        output_data = {
            "model": model,
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "instruction": instruction,
            "ranked_results": [
                {
                    "rank": i+1,
                    "document": r['document'],
                    "original_index": r['index'],
                    "score": round(r['score'], 6)
                }
                for i, r in enumerate(ranked_results)
            ]
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(output_data, f, ensure_ascii=False, indent=2)

        logger.info(f"详细结果已保存到：{output_file}")

    except Exception as e:
        logger.error(f"错误：{e}")


# ==================== 主函数 ====================

def main():
    parser = argparse.ArgumentParser(
        description="vllm Reranker 客户端测试工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 查看服务器信息
  python reranker_client.py info

  # 测试单个文本对
  python reranker_client.py rerank -q "什么是人工智能？" -d "人工智能是计算机科学的一个分支"

  # 批量测试
  python reranker_client.py rerank-batch

  # 文档排序
  python reranker_client.py rerank-docs -q "人工智能技术" -d "文档 1" -d "文档 2" -d "文档 3"
        """
    )

    parser.add_argument('--base-url', default=DEFAULT_BASE_URL,
                        help=f'vllm 服务地址 (默认：{DEFAULT_BASE_URL})')

    subparsers = parser.add_subparsers(dest='command', help='命令类型')

    # info 命令
    info_parser = subparsers.add_parser('info', help='查看服务器信息')

    # rerank 命令 (单个文本对)
    rerank_parser = subparsers.add_parser('rerank', help='单个文本对相关性评分')
    rerank_parser.add_argument('--model', '-m', default=None,
                               help='Reranker 模型名称 (默认：从服务器获取)')
    rerank_parser.add_argument('--query', '-q', required=True, help='查询文本')
    rerank_parser.add_argument('--document', '-d', required=True, help='文档文本')
    rerank_parser.add_argument('--instruction', '-i', default=None, help='任务指令 (可选)')

    # rerank-batch 命令 (批量测试)
    rerank_batch_parser = subparsers.add_parser('rerank-batch', help='批量测试相关性评分')
    rerank_batch_parser.add_argument('--model', '-m', default=None,
                                     help='Reranker 模型名称 (默认：从服务器获取)')
    rerank_batch_parser.add_argument('--instruction', '-i', default=None, help='任务指令 (可选)')

    # rerank-docs 命令 (文档排序)
    rerank_docs_parser = subparsers.add_parser('rerank-docs', help='文档排序 (rerank 多个文档)')
    rerank_docs_parser.add_argument('--model', '-m', default=None,
                                    help='Reranker 模型名称 (默认：从服务器获取)')
    rerank_docs_parser.add_argument('--query', '-q', required=True, help='查询文本')
    rerank_docs_parser.add_argument('--document', '-d', action='append', required=True, help='文档文本 (可指定多个)')
    rerank_docs_parser.add_argument('--instruction', '-i', default=None, help='任务指令 (可选)')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # 执行对应命令
    if args.command == 'info':
        get_server_info(args.base_url)

    elif args.command == 'rerank':
        rerank_single_pair(args.base_url, args.model, args.query, args.document, args.instruction)

    elif args.command == 'rerank-batch':
        rerank_batch(args.base_url, args.model, args.instruction)

    elif args.command == 'rerank-docs':
        rerank_documents(args.base_url, args.model, args.query, args.document, args.instruction)


if __name__ == "__main__":
    main()
