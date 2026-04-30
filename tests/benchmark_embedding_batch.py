#!/usr/bin/env python3
"""
Embedding batch vs 逐个请求 性能对比

用法:
    conda run -n pi-llm-server python benchmark_embedding_batch.py \
        --url http://127.0.0.1:8090 --token sk-xxx
"""
import argparse
import time
import sys
import requests


TEST_TEXTS = [
    "人工智能是计算机科学的一个分支",
    "AI 技术正在改变各行各业",
    "机器学习是人工智能的核心技术",
    "深度学习用于图像识别和自然语言处理",
    "今天天气真好阳光明媚",
    "晴空万里适合外出游玩",
    "天气预报说明天会下雨",
    "猫咪喜欢吃鱼和老鼠",
    "小狗是人类最忠诚的朋友",
    "熊猫是中国的国宝动物",
]


def request_single(url: str, token: str, text: str) -> dict:
    """单个请求"""
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    resp = requests.post(
        f"{url}/v1/embeddings",
        json={"input": text, "model": "unsloth/Qwen3-Embedding-0.6B"},
        headers=headers,
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


def request_batch(url: str, token: str, texts: list) -> dict:
    """batch 请求"""
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    resp = requests.post(
        f"{url}/v1/embeddings",
        json={"input": texts, "model": "unsloth/Qwen3-Embedding-0.6B"},
        headers=headers,
        timeout=60,
    )
    resp.raise_for_status()
    return resp.json()


def benchmark_single(url: str, token: str, texts: list):
    """逐个请求（串行）"""
    print(f"\n[逐个请求] 共 {len(texts)} 条文本...")
    embeddings = []
    start = time.perf_counter()
    for i, text in enumerate(texts):
        t0 = time.perf_counter()
        result = request_single(url, token, text)
        t1 = time.perf_counter()
        emb = result.get("data", [{}])[0].get("embedding", [])
        embeddings.append(emb)
        print(f"  [{i+1}/{len(texts)}] 耗时 {t1-t0:.3f}s, 维度={len(emb)}")
    total = time.perf_counter() - start
    return total, embeddings


def benchmark_batch(url: str, token: str, texts: list):
    """batch 请求"""
    print(f"\n[batch 请求] 共 {len(texts)} 条文本，一次发送...")
    start = time.perf_counter()
    result = request_batch(url, token, texts)
    total = time.perf_counter() - start

    embeddings = []
    for item in result.get("data", []):
        emb = item.get("embedding", [])
        idx = item.get("index", 0)
        embeddings.append((idx, emb))
    embeddings.sort(key=lambda x: x[0])
    embeddings = [e[1] for e in embeddings]

    print(f"  总耗时 {total:.3f}s, 返回 {len(embeddings)} 个向量, 平均维度={len(embeddings[0]) if embeddings else 0}")
    return total, embeddings


def main():
    parser = argparse.ArgumentParser(description="Embedding batch 性能对比")
    parser.add_argument("--url", default="http://127.0.0.1:8090", help="网关地址")
    parser.add_argument("--token", default="", help="API Token")
    args = parser.parse_args()

    print("=" * 60)
    print("Embedding batch vs 逐个请求 性能对比")
    print(f"网关: {args.url}")
    print(f"测试文本数: {len(TEST_TEXTS)}")
    print("=" * 60)

    # 预热
    print("\n[预热]...")
    request_single(args.url, args.token, TEST_TEXTS[0])
    request_batch(args.url, args.token, TEST_TEXTS[:2])
    print("预热完成")

    # 测试 1: 逐个请求
    t_single, embs_single = benchmark_single(args.url, args.token, TEST_TEXTS)

    # 测试 2: batch 请求
    t_batch, embs_batch = benchmark_batch(args.url, args.token, TEST_TEXTS)

    # 验证结果一致性
    print("\n[结果验证]")
    if len(embs_single) == len(embs_batch):
        match = all(
            all(abs(a - b) < 1e-5 for a, b in zip(es, eb))
            for es, eb in zip(embs_single, embs_batch)
        )
        print(f"  向量一致性: {'通过' if match else '不一致!'}")
    else:
        print(f"  向量数量不一致: single={len(embs_single)}, batch={len(embs_batch)}")

    # 汇总
    print("\n" + "=" * 60)
    print("汇总对比")
    print("=" * 60)
    print(f"逐个请求总耗时: {t_single:.3f}s")
    print(f"batch 请求总耗时: {t_batch:.3f}s")
    print(f"加速比: {t_single / t_batch:.2f}x")
    print(f"平均每条节省: {(t_single - t_batch) / len(TEST_TEXTS) * 1000:.1f}ms")


if __name__ == "__main__":
    main()
