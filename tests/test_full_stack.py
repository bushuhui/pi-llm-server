#!/usr/bin/env python3
"""
PI-LLM-Server 完整测试脚本

测试流程:
1. 启动所有子服务 (embedding, asr, reranker, mineru)
2. 启动 pi-llm-server 网关
3. 等待所有服务启动完成
4. 测试所有 API 端点
5. 输出测试结果
6. 停止所有服务
"""

import subprocess
import time
import sys
import os
import json
import httpx
from pathlib import Path

# 配置
GATEWAY_URL = "http://127.0.0.1:8090"
SERVICE_PORTS = {
    'embedding': 8091,
    'asr': 8092,
    'reranker': 8093,
    'mineru': 8094,
}
HEALTH_CHECK_TIMEOUT = 180  # 等待服务启动的最大时间 (秒)
API_CHECK_TIMEOUT = 30  # 单个 API 调用超时 (秒)
TEST_TOKEN = "sk-5f8b839908d14561590b70227c72ca86"  # 测试 Token

# 测试数据目录
DATA_DIR = Path(__file__).parent.parent / "data"

# 项目根目录
PROJECT_ROOT = Path(__file__).parent.parent

#  ANSI 颜色代码
COLORS = {
    "green": "\033[92m",
    "red": "\033[91m",
    "yellow": "\033[93m",
    "blue": "\033[94m",
    "reset": "\033[0m",
    "bold": "\033[1m",
}


def colored(text, color):
    """返回彩色文本"""
    return f"{COLORS.get(color, '')}{text}{COLORS['reset']}"


def print_header(text):
    """打印标题"""
    print(f"\n{COLORS['bold']}{'=' * 60}{COLORS['reset']}")
    print(f"{COLORS['bold']}{text}{COLORS['reset']}")
    print(f"{COLORS['bold']}{'=' * 60}{COLORS['reset']}")


def print_status(name, status, detail=""):
    """打印测试状态"""
    color = "green" if status == "PASS" else ("red" if status == "FAIL" else "yellow")
    status_str = f"[{status}]"
    print(f"  {status_str:8} {name}", end="")
    if detail:
        print(f" - {detail}")
    else:
        print()


def check_port_open(port, timeout=5):
    """检查端口是否开放"""
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(timeout)
    try:
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        return result == 0
    except Exception:
        return False


def wait_for_port(port, max_wait=60, service_name=""):
    """等待端口开放"""
    start_time = time.time()
    while time.time() - start_time < max_wait:
        if check_port_open(port):
            print(f"  {colored('✓', 'green')} {service_name} 已启动 (端口 {port})")
            return True
        elapsed = int(time.time() - start_time)
        print(f"  等待 {service_name}... ({elapsed}s/{max_wait}s)", end="\r")
        time.sleep(2)
    print(f"\n  {colored(f'✗ {service_name} 启动超时!', 'red')}")
    return False


class ServiceTest:
    """服务测试类"""

    def __init__(self, base_url, token):
        self.base_url = base_url
        self.token = token
        self.client = httpx.Client(
            base_url=base_url,
            timeout=httpx.Timeout(API_CHECK_TIMEOUT),
            headers={"Authorization": f"Bearer {token}"}
        )
        self.results = []

    def wait_for_gateway(self, max_wait=HEALTH_CHECK_TIMEOUT):
        """等待网关启动"""
        print_header("等待网关服务启动")
        start_time = time.time()

        while time.time() - start_time < max_wait:
            try:
                response = self.client.get("/health", timeout=5.0)
                if response.status_code == 200:
                    data = response.json()
                    print(f"  {colored('✓', 'green')} 网关已启动！")
                    print(f"  健康状态：{json.dumps(data, indent=2, ensure_ascii=False)}")
                    return True
            except httpx.ConnectError:
                pass
            except Exception as e:
                print(f"  检查健康状态时出错：{e}")

            elapsed = int(time.time() - start_time)
            print(f"  等待网关启动... ({elapsed}s/{max_wait}s)", end="\r")
            time.sleep(2)

        print(f"\n  {colored('网关启动超时!', 'red')}")
        return False

    def test_endpoint(self, method, path, name, **kwargs):
        """测试单个 API 端点"""
        try:
            func = getattr(self.client, method.lower())
            response = func(path, **kwargs)

            if response.status_code < 300:
                print_status(name, "PASS", f"status={response.status_code}")
                self.results.append((name, "PASS", response.status_code))
                return response
            else:
                print_status(name, "FAIL", f"status={response.status_code}, body={response.text[:200]}")
                self.results.append((name, "FAIL", response.status_code))
                return None

        except httpx.TimeoutException:
            print_status(name, "FAIL", "timeout")
            self.results.append((name, "FAIL", "timeout"))
            return None
        except Exception as e:
            print_status(name, "FAIL", str(e))
            self.results.append((name, "FAIL", str(e)))
            return None

    def run_all_tests(self):
        """运行所有测试"""
        print_header("开始 API 测试")

        # 1. 根路径
        print("\n[1] 基础端点测试")
        self.test_endpoint("get", "/", "根路径 /")

        # 2. 健康检查
        print("\n[2] 健康检查端点")
        health_resp = self.test_endpoint("get", "/health", "健康检查 /health")
        if health_resp:
            print(f"      响应：{json.dumps(health_resp.json(), indent=2, ensure_ascii=False)}")

        # 3. 状态详情
        print("\n[3] 状态详情端点")
        status_resp = self.test_endpoint("get", "/status", "状态详情 /status")
        if status_resp:
            status_data = status_resp.json()
            print(f"      响应预览：{json.dumps(status_data, indent=2, ensure_ascii=False)[:500]}...")

        # 4. 模型列表
        print("\n[4] 模型列表端点")
        models_resp = self.test_endpoint("get", "/v1/models", "模型列表 /v1/models")
        if models_resp:
            models_data = models_resp.json()
            models = models_data.get("data", [])
            print(f"      可用模型数量：{len(models)}")
            for m in models[:5]:
                print(f"        - {m.get('id', 'unknown')} ({m.get('service', 'unknown')})")

        # 5. Embedding 服务测试
        print("\n[5] Embedding 服务测试")

        # 5.1 测试 embedding 向量生成
        embedding_request = {
            "input": "人工智能是计算机科学的一个分支",
            "model": "unsloth/Qwen3-Embedding-0.6B"
        }
        emb_resp = self.test_endpoint(
            "post", "/v1/embeddings",
            "Embedding 向量生成",
            json=embedding_request
        )
        if emb_resp:
            data = emb_resp.json()
            if "data" in data and len(data["data"]) > 0:
                vec = data["data"][0].get("embedding", [])
                print(f"      向量维度：{len(vec)}")

        # 5.2 测试相似度计算
        similarity_request = {
            "text1": "人工智能是计算机科学的一个分支",
            "text2": "AI 技术正在改变各行各业"
        }
        sim_resp = self.test_endpoint(
            "post", "/v1/similarity",
            "相似度计算",
            json=similarity_request
        )
        if sim_resp:
            print(f"      相似度：{sim_resp.json().get('similarity', 'N/A')}")

        # 5.3 使用测试数据进行批量测试
        print("\n[6] Embedding 批量测试 (使用 data/ 测试数据)")
        test_data_file = DATA_DIR / "test_data_similarity.json"
        if test_data_file.exists():
            with open(test_data_file) as f:
                test_data = json.load(f)

            documents = test_data.get("documents", [])[:3]  # 取前 3 个
            queries = test_data.get("queries", [])[:2]  # 取前 2 个

            print(f"      测试文档数：{len(documents)}")
            print(f"      测试查询数：{len(queries)}")

            # 批量生成 embedding
            if documents:
                batch_request = {"input": documents}
                batch_resp = self.test_endpoint(
                    "post", "/v1/embeddings",
                    "批量 Embedding 生成",
                    json=batch_request
                )
                if batch_resp:
                    data = batch_resp.json()
                    vecs = data.get("data", [])
                    print(f"      生成向量数：{len(vecs)}")

            # 搜索测试
            for query in queries:
                search_request = {"input": query}
                search_resp = self.test_endpoint(
                    "post", "/v1/embeddings",
                    f"搜索查询：{query[:20]}...",
                    json=search_request
                )
        else:
            print_status("测试数据文件不存在", "SKIP")

        # 7. ASR 服务测试
        print("\n[7] ASR 服务测试")
        audio_file = DATA_DIR / "audio_s.mp3"
        if audio_file.exists():
            print(f"      测试音频文件：{audio_file}")
            audio_size = audio_file.stat().st_size / (1024 * 1024)
            print(f"      文件大小：{audio_size:.2f} MB")

            with open(audio_file, "rb") as f:
                files = {"file": ("audio_s.mp3", f, "audio/mp3")}
                data = {"model": "Qwen/Qwen3-ASR-1.7B"}

                asr_start = time.time()
                asr_resp = self.test_endpoint(
                    "post", "/v1/audio/transcriptions",
                    "语音识别 (短音频)",
                    files=files,
                    data=data,
                    timeout=120.0  # ASR 可能耗时较长，增加超时
                )
                asr_elapsed = time.time() - asr_start

                if asr_resp:
                    result = asr_resp.json()
                    print(f"      识别结果：{result.get('text', 'N/A')[:100]}...")
                    print(f"      耗时：{asr_elapsed:.2f}s")
        else:
            print_status("音频文件不存在", "SKIP")

        # 8. Reranker 服务测试
        print("\n[8] Reranker 服务测试")
        rerank_request = {
            "query": "什么是人工智能",
            "documents": [
                "人工智能是计算机科学的一个分支，致力于创建智能系统",
                "机器学习使用算法让计算机从数据中学习",
                "深度学习是机器学习的子集，使用神经网络"
            ]
        }
        rerank_resp = self.test_endpoint(
            "post", "/v1/rerank",
            "Reranker 重排序",
            json=rerank_request
        )
        if rerank_resp:
            result = rerank_resp.json()
            results = result.get("results", [])
            print(f"      返回结果数：{len(results)}")
            if results:
                for i, r in enumerate(results[:2]):
                    print(f"        [{i}] score={r.get('relevance_score', r.get('score', 'N/A')):.4f}")

        # 9. MinerU 服务测试
        print("\n[9] MinerU 服务测试")
        pdf_file = DATA_DIR / "InfoLOD.pdf"
        if pdf_file.exists():
            print(f"      测试 PDF 文件：{pdf_file}")

            # 获取文件大小
            file_size_mb = pdf_file.stat().st_size / (1024 * 1024)
            print(f"      文件大小：{file_size_mb:.2f} MB")

            # MinerU 使用 /file_parse 端点
            with open(pdf_file, "rb") as f:
                files = {"file": ("InfoLOD.pdf", f, "application/pdf")}
                data = {
                    "backend": "pipeline",
                    "parse_method": "auto",
                    "lang_list": "ch",
                    "formula_enable": "true",
                    "table_enable": "true",
                    "return_md": "true",
                    "return_images": "false",  # 不返回图片以加快测试
                }

                mineru_start = time.time()
                mineru_resp = self.test_endpoint(
                    "post", "/file_parse",
                    "MinerU PDF 解析",
                    files=files,
                    data=data,
                    timeout=60.0  # PDF 解析耗时，增加超时
                )
                mineru_elapsed = time.time() - mineru_start

                if mineru_resp:
                    try:
                        result = mineru_resp.json()
                        status = result.get("status", "N/A")
                        print(f"      解析状态：{status}")
                        if "data" in result and result["data"]:
                            text = result["data"].get("markdown", "")
                            print(f"      文本长度：{len(text)}")
                            print(f"      文本预览：{text[:200]}...")
                        elif "message" in result:
                            print(f"      消息：{result.get('message', '')[:200]}")
                    except:
                        print(f"      响应内容：{mineru_resp.text[:200]}...")
                    print(f"      耗时：{mineru_elapsed:.2f}s")
        else:
            print_status("PDF 文件不存在", "SKIP")

        # 打印测试总结
        self.print_summary()

    def print_summary(self):
        """打印测试总结"""
        print_header("测试总结")

        passed = sum(1 for _, status, _ in self.results if status == "PASS")
        failed = sum(1 for _, status, _ in self.results if status in ("FAIL", "timeout"))
        skipped = sum(1 for _, status, _ in self.results if status == "SKIP")

        print(f"  总计：{len(self.results)} 项")
        print(f"  {colored('通过：' + str(passed), 'green')}")
        print(f"  {colored('失败：' + str(failed), 'red')}")
        if skipped > 0:
            print(f"  {colored('跳过：' + str(skipped), 'yellow')}")

        if failed > 0:
            print(f"\n  {colored('失败的测试:', 'red')}")
            for name, status, detail in self.results:
                if status in ("FAIL", "timeout"):
                    print(f"    - {name}: {detail}")

        print()


def start_sub_services():
    """启动所有子服务"""
    print_header("启动子服务")

    service_manager = PROJECT_ROOT / "pi_llm_server" / "launcher" / "service_manager.py"

    print(f"  使用 service_manager.py 启动子服务...")
    print(f"  服务列表：{list(SERVICE_PORTS.keys())}")

    # 检查子服务是否已经在运行
    running_services = []
    for name, port in SERVICE_PORTS.items():
        if check_port_open(port):
            running_services.append(name)
            print(f"  {colored('✓', 'yellow')} {name} 已在运行 (端口 {port})")

    if running_services:
        print(f"  已有服务：{running_services}")
        use_existing = input("  是否使用现有服务进行测试？(y/n): ").strip().lower()
        if use_existing == 'y':
            return True
        # 否则停止现有服务
        print("  正在停止现有服务...")
        subprocess.run(
            [sys.executable, str(service_manager), "stop", "--all"],
            cwd=PROJECT_ROOT
        )
        time.sleep(3)

    # 启动所有子服务
    print("\n  启动子服务...")
    result = subprocess.run(
        [sys.executable, str(service_manager), "start", "--all"],
        cwd=PROJECT_ROOT,
        capture_output=False
    )

    if result.returncode != 0:
        print(f"  {colored('✗ 子服务启动失败!', 'red')}")
        return False

    # 等待各服务端口就绪
    print("\n  等待服务端口就绪...")
    all_ready = True
    for name, port in SERVICE_PORTS.items():
        if not wait_for_port(port, max_wait=60, service_name=name):
            all_ready = False

    return all_ready


def start_gateway(config_path):
    """启动网关服务"""
    print_header("启动网关服务")

    cmd = [
        sys.executable, "-m", "pi_llm_server",
        "--config", str(config_path),
        "--log-level", "info"
    ]

    print(f"  启动命令：{' '.join(cmd)}")

    process = subprocess.Popen(
        cmd,
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1
    )

    return process


def main():
    """主函数"""
    print_header("PI-LLM-Server 完整测试")
    print(f"  网关地址：{GATEWAY_URL}")
    print(f"  测试 Token: {TEST_TOKEN[:10]}...")
    print(f"  数据目录：{DATA_DIR}")
    print(f"  服务端口：{SERVICE_PORTS}")

    # 查找配置文件
    config_path = Path.home() / ".config" / "pi-llm-server" / "config.yaml"
    if not config_path.exists():
        print(f"  {colored(f'配置文件不存在：{config_path}', 'red')}")
        sys.exit(1)

    print(f"  配置文件：{config_path}")

    # 步骤 1: 启动子服务
    if not start_sub_services():
        print("\n  子服务启动失败，终止测试")
        sys.exit(1)

    print("\n  子服务已全部启动!")

    # 步骤 2: 启动网关
    print("\n[步骤 2] 启动网关服务...")
    gateway_process = start_gateway(config_path)

    # 步骤 3: 等待网关启动
    test = ServiceTest(GATEWAY_URL, TEST_TOKEN)
    if not test.wait_for_gateway():
        print("\n  网关启动失败，终止测试")
        gateway_process.terminate()
        stop_sub_services()
        sys.exit(1)

    # 步骤 4: 运行 API 测试
    test.run_all_tests()

    # 步骤 5: 停止服务
    print("\n[步骤 5] 停止服务...")
    print("  停止网关服务...")
    gateway_process.terminate()
    try:
        gateway_process.wait(timeout=10)
        print("  网关已停止")
    except subprocess.TimeoutExpired:
        print("  网关停止超时，强制终止")
        gateway_process.kill()

    stop_sub_services()

    print("\n" + "=" * 60)
    print("测试完成!")
    print("=" * 60)


def stop_sub_services():
    """停止所有子服务"""
    service_manager = PROJECT_ROOT / "pi_llm_server" / "launcher" / "service_manager.py"
    print("  正在停止子服务...")
    subprocess.run(
        [sys.executable, str(service_manager), "stop", "--all"],
        cwd=PROJECT_ROOT
    )
    print("  子服务已停止")


if __name__ == "__main__":
    main()
