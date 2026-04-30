#!/usr/bin/env python3
"""
ASR 并发性能压测脚本

测试场景：
1. 串行发送 N 个请求，测量总时间和单请求平均延迟
2. 并发发送 N 个请求，测量总时间和单请求延迟

用法:
    conda run -n pi-llm-server python benchmark_asr_concurrent.py --url http://127.0.0.1:8090 --audio data/audio_s.mp3 --token sk-xxx
"""
import argparse
import asyncio
import time
import sys
from pathlib import Path
from dataclasses import dataclass
from typing import List

import httpx


@dataclass
class BenchmarkResult:
    concurrent: int
    total_time: float
    latencies: List[float]
    errors: int


def format_result(r: BenchmarkResult) -> str:
    if not r.latencies:
        return f"并发={r.concurrent}: 全部失败，错误数={r.errors}"
    avg = sum(r.latencies) / len(r.latencies)
    min_l = min(r.latencies)
    max_l = max(r.latencies)
    throughput = len(r.latencies) / r.total_time if r.total_time > 0 else 0
    return (
        f"并发={r.concurrent}: 总耗时={r.total_time:.2f}s, "
        f"平均延迟={avg:.2f}s, 最小={min_l:.2f}s, 最大={max_l:.2f}s, "
        f"吞吐量={throughput:.2f} req/s, 成功={len(r.latencies)}, 失败={r.errors}"
    )


async def send_request(
    client: httpx.AsyncClient,
    url: str,
    audio_path: Path,
    token: str,
    idx: int,
) -> float:
    """发送单个 ASR 请求，返回耗时（秒），失败抛出异常"""
    headers = {}
    if token:
        headers["Authorization"] = f"Bearer {token}"

    with open(audio_path, "rb") as f:
        files = {"file": (audio_path.name, f, "audio/mpeg")}
        data = {"model": "Qwen/Qwen3-ASR-1.7B"}

        start = time.perf_counter()
        resp = await client.post(
            f"{url}/v1/audio/transcriptions",
            files=files,
            data=data,
            headers=headers,
            timeout=httpx.Timeout(300.0),
        )
        resp.raise_for_status()
        elapsed = time.perf_counter() - start

    result = resp.json()
    text = result.get("text", "")
    print(f"  [请求 {idx}] 耗时 {elapsed:.2f}s, 转写长度={len(text)} 字")
    return elapsed


async def run_benchmark(
    url: str,
    audio_path: Path,
    token: str,
    concurrent: int,
) -> BenchmarkResult:
    """运行一次压测"""
    latencies: List[float] = []
    errors = 0

    limits = httpx.Limits(max_keepalive_connections=concurrent, max_connections=concurrent * 2)
    async with httpx.AsyncClient(limits=limits) as client:
        # 先做一次预热请求
        print(f"\n预热请求...")
        try:
            await send_request(client, url, audio_path, token, 0)
        except Exception as e:
            print(f"  预热失败: {e}")
            return BenchmarkResult(concurrent=concurrent, total_time=0, latencies=[], errors=1)

        print(f"\n开始压测：并发={concurrent}, 音频={audio_path.name}")
        start = time.perf_counter()

        async def wrapped(idx: int) -> float:
            try:
                return await send_request(client, url, audio_path, token, idx)
            except Exception as e:
                print(f"  [请求 {idx}] 失败: {e}")
                raise

        tasks = [asyncio.create_task(wrapped(i + 1)) for i in range(concurrent)]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        total_time = time.perf_counter() - start

        for r in results:
            if isinstance(r, Exception):
                errors += 1
            else:
                latencies.append(r)

    return BenchmarkResult(
        concurrent=concurrent,
        total_time=total_time,
        latencies=latencies,
        errors=errors,
    )


async def main():
    parser = argparse.ArgumentParser(description="ASR 并发性能压测")
    parser.add_argument("--url", default="http://127.0.0.1:8090", help="网关地址")
    parser.add_argument("--audio", default="data/audio_s.mp3", help="测试音频文件")
    parser.add_argument("--token", default="", help="API Token (可选)")
    parser.add_argument("--levels", default="1,2,3", help="并发级别，逗号分隔")
    args = parser.parse_args()

    audio_path = Path(args.audio)
    if not audio_path.exists():
        print(f"错误：音频文件不存在 {audio_path}")
        sys.exit(1)

    levels = [int(x.strip()) for x in args.levels.split(",")]

    print("=" * 60)
    print("ASR 并发性能压测")
    print(f"网关: {args.url}")
    print(f"音频: {audio_path} ({audio_path.stat().st_size / 1024 / 1024:.2f} MB)")
    print(f"并发级别: {levels}")
    print("=" * 60)

    results: List[BenchmarkResult] = []
    for level in levels:
        result = await run_benchmark(args.url, audio_path, args.token, level)
        results.append(result)
        print(format_result(result))

    # 汇总对比
    print("\n" + "=" * 60)
    print("汇总对比")
    print("=" * 60)
    baseline = None
    for r in results:
        print(format_result(r))
        if r.latencies and baseline is None:
            baseline = sum(r.latencies) / len(r.latencies)
        elif r.latencies and baseline:
            avg = sum(r.latencies) / len(r.latencies)
            slowdown = avg / baseline
            throughput_gain = (r.concurrent / r.total_time) / (1 / baseline) if r.total_time > 0 and baseline > 0 else 0
            print(f"  -> 相对单请求延迟倍数: {slowdown:.2f}x, 吞吐量提升: {throughput_gain:.2f}x")


if __name__ == "__main__":
    asyncio.run(main())
