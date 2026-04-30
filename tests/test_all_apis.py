import pytest
import httpx
import time
import os
from pathlib import Path

BASE = "http://127.0.0.1:8090"
TOKEN = "sk-5f8b839908d14561590b70227c72ca86"
HEADERS = {"Authorization": f"Bearer {TOKEN}"}

# 数据目录：脚本所在目录的上级（tests/ 的上级是项目根目录）
DATA_DIR = Path(__file__).parent.parent / "data"

results = []


def report(name, ok, detail=""):
    status = "OK" if ok else "FAIL"
    print(f"  [{status}] {name:25s} {detail}")
    results.append((name, ok))


@pytest.mark.asyncio
async def test_health():
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{BASE}/health")
            data = r.json()
            ok = r.status_code == 200 and data.get("status") == "healthy"
            svcs = ", ".join([k for k, v in data.get("services", {}).items() if v.get("status") == "healthy"])
            report("Health Check", ok, f"services: {svcs}")
            assert ok, f"health check failed: {data}"
    except Exception as e:
        report("Health Check", False, str(e)[:40])
        raise


@pytest.mark.asyncio
async def test_models():
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{BASE}/v1/models", headers=HEADERS)
            data = r.json()
            ok = r.status_code == 200 and "data" in data
            ids = [m["id"] for m in data.get("data", [])]
            report("Models List", ok, f"{len(ids)} models")
            assert ok, f"models list failed: {data}"
    except Exception as e:
        report("Models List", False, str(e)[:40])
        raise


@pytest.mark.asyncio
async def test_embedding():
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            t0 = time.time()
            r = await c.post(
                f"{BASE}/v1/embeddings",
                headers={**HEADERS, "Content-Type": "application/json"},
                json={"input": ["人工智能", "机器学习", "深度学习"]},
            )
            data = r.json()
            ok = r.status_code == 200 and len(data.get("data", [])) == 3
            dims = [len(d["embedding"]) for d in data.get("data", [])]
            report("Embedding (batch)", ok, f"3 items, dim={dims[0] if dims else 'N/A'}, {time.time()-t0:.2f}s")
            assert ok, f"embedding failed: {data}"
    except Exception as e:
        report("Embedding (batch)", False, str(e)[:40])
        raise


@pytest.mark.asyncio
async def test_reranker():
    try:
        async with httpx.AsyncClient(timeout=30) as c:
            t0 = time.time()
            r = await c.post(
                f"{BASE}/v1/rerank",
                headers={**HEADERS, "Content-Type": "application/json"},
                json={
                    "query": "深度学习",
                    "documents": ["AI分支", "ML核心技术", "DL用于图像"],
                    "top_n": 2,
                },
            )
            data = r.json()
            ok = r.status_code == 200 and len(data.get("results", [])) == 2
            report("Reranker", ok, f"top_n=2, {time.time()-t0:.2f}s")
            assert ok, f"reranker failed: {data}"
    except Exception as e:
        report("Reranker", False, str(e)[:40])
        raise


@pytest.mark.asyncio
async def test_asr():
    audio_path = DATA_DIR / "audio_s.mp3"
    if not os.path.exists(audio_path):
        report("ASR", False, "no test audio file")
        pytest.skip("no test audio file")
    try:
        async with httpx.AsyncClient(timeout=300) as c:
            t0 = time.time()
            with open(audio_path, "rb") as f:
                r = await c.post(
                    f"{BASE}/v1/audio/transcriptions",
                    headers=HEADERS,
                    files={"file": ("audio.mp3", f, "audio/mpeg")},
                    data={"model": "Qwen/Qwen3-ASR-1.7B"},
                )
            data = r.json()
            ok = r.status_code == 200 and "text" in data
            text = data.get("text", "")[:20]
            report("ASR", ok, f"'{text}...', {time.time()-t0:.1f}s")
            assert ok, f"asr failed: {data}"
    except Exception as e:
        report("ASR", False, str(e)[:40])
        raise


@pytest.mark.asyncio
async def test_mineru():
    pdf_path = DATA_DIR / "InfoLOD.pdf"
    if not os.path.exists(pdf_path):
        report("MinerU (PDF)", False, "no test pdf file")
        pytest.skip("no test pdf file")
    try:
        async with httpx.AsyncClient(timeout=300) as c:
            t0 = time.time()
            with open(pdf_path, "rb") as f:
                r = await c.post(
                    f"{BASE}/v1/ocr/parser",
                    headers=HEADERS,
                    files={"files": ("InfoLOD.pdf", f, "application/pdf")},
                    data={
                        "backend": "pipeline",
                        "parse_method": "auto",
                        "lang_list": "ch",
                        "return_md": "true",
                        "return_images": "false",
                    },
                )
            ok = r.status_code == 200 and len(r.content) > 1000
            report("MinerU (PDF)", ok, f"{len(r.content)/1024:.1f} KB, {time.time()-t0:.1f}s")
            assert ok, f"mineru failed: status={r.status_code}, len={len(r.content)}"
    except Exception as e:
        report("MinerU (PDF)", False, str(e)[:40])
        raise


@pytest.mark.asyncio
async def test_memory():
    try:
        async with httpx.AsyncClient(timeout=10) as c:
            r = await c.get(f"{BASE}/memory/api/memory/stats", headers=HEADERS)
            ok = r.status_code in (200, 404, 502)
            report("Memory", ok, f"HTTP {r.status_code}")
            assert ok, f"memory failed: status={r.status_code}"
    except Exception as e:
        report("Memory", False, str(e)[:40])
        raise


def pytest_terminal_summary(terminalreporter, exitstatus, config):
    print("=" * 60)
    print("PI-LLM-Server API Test Summary")
    print("=" * 60)
    passed = sum(1 for _, ok in results if ok)
    print(f"Result: {passed}/{len(results)} passed")
    print("=" * 60)
