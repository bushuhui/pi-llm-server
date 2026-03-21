#!/usr/bin/env python3
"""
vllm Embedding 客户端测试工具
用于测试 vllm 提供的 embedding 服务

使用方法:
1. 测试单个文本:
   python vllm_embedding_client.py embed -t "今天天气很好"

2. 批量测试相似度:
   python vllm_embedding_client.py embed-test

3. 语义搜索:
   python vllm_embedding_client.py embed-search -q "人工智能技术"

4. 查看 API 信息:
   python vllm_embedding_client.py info
"""

import os
import sys
import argparse
import requests
import json
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

logger = setup_logging("embedding_client")

# 默认配置
DEFAULT_BASE_URL = "http://localhost:8091"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
RESULTS_DIR = os.path.join(SCRIPT_DIR, "results")


# ==================== 工具函数 ====================

def cosine_similarity(vec1: list, vec2: list) -> float:
    """计算两个向量的余弦相似度"""
    import math
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot_product / (norm1 * norm2)


# ==================== 信息查询功能 ====================

def get_server_info(base_url: str):
    """获取服务器信息和可用模型"""
    logger.info("=" * 60)
    logger.info("vllm Embedding 服务器信息")
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

        # 测试健康检查
        logger.info("健康检查：OK")

        return models

    except requests.exceptions.ConnectionError:
        logger.error(f"无法连接到服务器：{base_url}, 请确认服务器已启动")
        return []
    except Exception as e:
        logger.error(f"获取服务器信息失败：{e}")
        return []


# ==================== 单个文本 Embedding ====================

def create_embedding(base_url: str, model: str, text: str, encoding_format: str = "float"):
    """
    使用 Embedding 模型生成文本嵌入向量

    Args:
        base_url: vllm 服务地址
        model: 模型名称
        text: 输入文本
        encoding_format: 编码格式：float | base64 (可选，默认 float)
    """
    logger.info("=" * 60)
    logger.info(f"文本嵌入 - 使用模型：{model}")
    logger.info("=" * 60)
    logger.info(f"输入文本：{text[:100]}{'...' if len(text) > 100 else ''}")
    logger.info(f"编码格式：{encoding_format}")
    logger.info("正在计算嵌入向量...")

    url = f"{base_url}/v1/embeddings"

    payload = {
        "model": model,
        "input": text,
        "encoding_format": encoding_format,
    }

    try:
        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()

        result = response.json()
        embedding = result.get('data', [{}])[0].get('embedding', [])

        logger.info("生成成功")
        logger.info(f"向量维度：{len(embedding)}")
        logger.info(f"向量预览 (前 10 个值): {embedding[:10]}")

        # 保存到文件
        output_file = os.path.join(RESULTS_DIR, f"embedding_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"输入文本：{text}\n")
            f.write(f"模型：{model}\n")
            f.write(f"向量维度：{len(embedding)}\n")
            f.write(f"完整向量:\n{embedding}")

        logger.info(f"完整向量已保存到：{output_file}")

        return embedding

    except Exception as e:
        logger.error(f"错误：{e}")
        return None


# ==================== 批量相似度测试 ====================

def test_embedding_batch(base_url: str, model: str, test_data: list = None):
    """
    批量测试 Embedding 模型，计算文本相似度

    Args:
        base_url: vllm 服务地址
        model: 模型名称
        test_data: 测试文本列表
    """
    logger.info("=" * 60)
    logger.info(f"Embedding 批量测试 - 使用模型：{model}")
    logger.info("=" * 60)

    # 默认测试数据 (按语义分组)
    if test_data is None:
        test_data = [
            # AI 技术相关
            "人工智能是计算机科学的一个分支",
            "AI 技术正在改变各行各业",
            "机器学习是人工智能的核心技术",
            "深度学习用于图像识别和自然语言处理",
            # 天气相关
            "今天天气真好阳光明媚",
            "晴空万里适合外出游玩",
            "天气预报说明天会下雨",
            # 动物相关
            "猫咪喜欢吃鱼和老鼠",
            "小狗是人类最忠诚的朋友",
            "熊猫是中国的国宝动物",
            # 科技产品
            "智能手机已经成为生活必需品",
            "笔记本电脑用于办公和娱乐",
        ]

    url = f"{base_url}/v1/embeddings"

    logger.info(f"测试文本数量：{len(test_data)}")
    logger.info("正在生成嵌入向量...")

    embeddings = []

    try:
        # 为每个文本生成 embedding
        for i, text in enumerate(test_data):
            payload = {
                "model": model,
                "input": text
            }
            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()
            result = response.json()
            embedding = result.get('data', [{}])[0].get('embedding', [])
            embeddings.append({
                'text': text,
                'embedding': embedding
            })
            logger.info(f"  [{i+1}/{len(test_data)}] {text[:30]}... -> 维度：{len(embedding)}")

        # 计算相似度矩阵
        logger.info("相似度矩阵:")
        logger.info("-" * 60)

        n = len(embeddings)
        header = "          "
        for i in range(n):
            header += f"[{i+1}]     "
        logger.info(header)

        for i in range(n):
            row = f"[{i+1}] "
            for j in range(n):
                if i == j:
                    sim = 1.000
                elif i > j:
                    sim = cosine_similarity(embeddings[i]['embedding'], embeddings[j]['embedding'])
                else:
                    sim = cosine_similarity(embeddings[i]['embedding'], embeddings[j]['embedding'])
                row += f"{sim:.4f}  "
            logger.info(row + f" <- {embeddings[i]['text'][:25]}")

        # 保存结果
        output_file = os.path.join(RESULTS_DIR, f"embedding_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        results = {
            "model": model,
            "timestamp": datetime.now().isoformat(),
            "texts": [e['text'] for e in embeddings],
            "dimension": len(embeddings[0]['embedding']),
            "similarity_matrix": []
        }

        for i in range(n):
            for j in range(i+1, n):
                sim = cosine_similarity(embeddings[i]['embedding'], embeddings[j]['embedding'])
                results['similarity_matrix'].append({
                    "text1": embeddings[i]['text'],
                    "text2": embeddings[j]['text'],
                    "similarity": round(sim, 4)
                })

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(results, f, ensure_ascii=False, indent=2)

        logger.info(f"详细结果已保存到：{output_file}")

        # 显示高相似度对
        logger.info("高相似度文本对 (相似度 > 0.85):")
        logger.info("-" * 60)
        high_sim_count = 0
        for item in results['similarity_matrix']:
            if item['similarity'] > 0.85:
                high_sim_count += 1
                logger.info(f"  {item['similarity']:.4f}: {item['text1'][:20]}... <-> {item['text2'][:20]}...")

        if high_sim_count == 0:
            logger.info("无高相似度文本对")

    except Exception as e:
        logger.error(f"错误：{e}")


# ==================== 语义搜索 ====================

def test_embedding_search(base_url: str, model: str, query: str, documents: list = None):
    """
    使用 Embedding 模型进行语义搜索测试

    Args:
        base_url: vllm 服务地址
        model: 模型名称
        query: 查询文本
        documents: 文档列表
    """
    logger.info("=" * 60)
    logger.info(f"Embedding 语义搜索测试 - 使用模型：{model}")
    logger.info("=" * 60)

    # 默认文档库
    if documents is None:
        documents = [
            "人工智能是计算机科学的一个分支，致力于创建智能系统",
            "机器学习使用算法让计算机从数据中学习",
            "深度学习是机器学习的子集，使用神经网络",
            "自然语言处理让计算机理解和生成人类语言",
            "计算机视觉让计算机能够理解图像和视频",
            "语音识别技术将语音转换为文本",
            "推荐系统根据用户偏好推荐内容",
            "数据挖掘从大量数据中发现模式和知识",
            "机器人技术设计和制造智能机器",
            "算法是解决问题的步骤和规则",
            "大数据技术处理海量信息的存储和分析",
            "云计算提供按需计算资源和服务",
            "物联网连接物理设备和传感器",
            "区块链是分布式账本技术用于安全交易",
            "网络安全保护系统免受攻击",
            "Python 是流行的编程语言用于 AI 开发",
        ]

    if not query:
        logger.error("错误：请提供查询文本")
        return

    url = f"{base_url}/v1/embeddings"

    logger.info(f"查询：{query}")
    logger.info(f"文档库大小：{len(documents)}")
    logger.info("正在计算向量...")

    try:
        # 生成查询向量
        payload = {"model": model, "input": query}
        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()
        query_embedding = response.json().get('data', [{}])[0].get('embedding', [])

        # 生成所有文档向量
        doc_embeddings = []
        for doc in documents:
            payload = {"model": model, "input": doc}
            response = requests.post(url, json=payload, timeout=60)
            response.raise_for_status()
            embedding = response.json().get('data', [{}])[0].get('embedding', [])
            doc_embeddings.append({'text': doc, 'embedding': embedding})
            logger.info(f"已处理文档：{doc[:30]}... -> 维度：{len(embedding)}")

        # 计算相似度并排序
        results = []
        for doc in doc_embeddings:
            sim = cosine_similarity(query_embedding, doc['embedding'])
            results.append({'text': doc['text'], 'similarity': sim})

        results.sort(key=lambda x: x['similarity'], reverse=True)

        logger.info("搜索结果 (按相似度排序):")
        logger.info("-" * 60)
        for i, result in enumerate(results):
            score = result['similarity']
            bar = "█" * int(score * 20)
            logger.info(f"  [{i+1}] 相似度：{score:.4f} {bar}")
            logger.info(f"      文档：{result['text']}")

        # 保存结果
        output_file = os.path.join(RESULTS_DIR, f"embedding_search_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        search_results = {
            "model": model,
            "timestamp": datetime.now().isoformat(),
            "query": query,
            "results": [{"rank": i+1, "text": r['text'], "similarity": round(r['similarity'], 4)} for i, r in enumerate(results)]
        }

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(search_results, f, ensure_ascii=False, indent=2)

        logger.info(f"详细结果已保存到：{output_file}")

    except Exception as e:
        logger.error(f"错误：{e}")


# ==================== 主函数 ====================

def main():
    parser = argparse.ArgumentParser(
        description="vllm Embedding 客户端测试工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 查看服务器信息
  python vllm_embedding_client.py info

  # 测试单个文本
  python vllm_embedding_client.py embed -t "今天天气很好"

  # 批量相似度测试
  python vllm_embedding_client.py embed-test

  # 语义搜索
  python vllm_embedding_client.py embed-search -q "人工智能技术"
        """
    )

    parser.add_argument('--base-url', default=DEFAULT_BASE_URL,
                        help=f'vllm 服务地址 (默认：{DEFAULT_BASE_URL})')

    subparsers = parser.add_subparsers(dest='command', help='命令类型')

    # info 命令
    info_parser = subparsers.add_parser('info', help='查看服务器信息')

    # embed 命令 (单个文本)
    embed_parser = subparsers.add_parser('embed', help='文本嵌入 (单个)')
    embed_parser.add_argument('--model', '-m', default='unsloth/Qwen3-Embedding-0.6B',
                              help='Embedding 模型名称 (默认：unsloth/Qwen3-Embedding-0.6B)')
    embed_parser.add_argument('--text', '-t', required=True, help='输入文本')
    embed_parser.add_argument('--encoding-format', '-e', default='float',
                              help='编码格式：float | base64 (默认：float)')

    # embed-test 命令 (批量测试)
    embed_test_parser = subparsers.add_parser('embed-test', help='Embedding 批量测试 (相似度矩阵)')
    embed_test_parser.add_argument('--model', '-m', default='unsloth/Qwen3-Embedding-0.6B',
                                   help='Embedding 模型名称 (默认：unsloth/Qwen3-Embedding-0.6B)')

    # embed-search 命令 (语义搜索)
    embed_search_parser = subparsers.add_parser('embed-search', help='Embedding 语义搜索')
    embed_search_parser.add_argument('--model', '-m', default='unsloth/Qwen3-Embedding-0.6B',
                                     help='Embedding 模型名称 (默认：unsloth/Qwen3-Embedding-0.6B)')
    embed_search_parser.add_argument('--query', '-q', required=True, help='查询文本')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # 执行对应命令
    if args.command == 'info':
        get_server_info(args.base_url)

    elif args.command == 'embed':
        create_embedding(args.base_url, args.model, args.text, args.encoding_format)

    elif args.command == 'embed-test':
        test_embedding_batch(args.base_url, args.model)

    elif args.command == 'embed-search':
        test_embedding_search(args.base_url, args.model, args.query)


if __name__ == "__main__":
    main()
