"""
PI-LLM-Server 基本使用示例

本示例展示如何使用 Python 客户端调用 PI-LLM-Server 提供的服务。
"""

import httpx
import base64

# 服务地址
BASE_URL = "http://127.0.0.1:8090"

# API Token（从配置文件获取）
API_TOKEN = "sk-admin-token-001"

# 请求头
HEADERS = {
    "Authorization": f"Bearer {API_TOKEN}",
    "Content-Type": "application/json",
}


def check_health():
    """检查服务健康状态"""
    response = httpx.get(f"{BASE_URL}/health")
    print("健康状态:", response.json())
    return response.json()


def list_models():
    """列出所有可用模型"""
    response = httpx.get(f"{BASE_URL}/v1/models", headers=HEADERS)
    print("可用模型:", response.json())
    return response.json()


def get_status():
    """获取服务详细状态"""
    response = httpx.get(f"{BASE_URL}/status", headers=HEADERS)
    print("服务状态:", response.json())
    return response.json()


def generate_embedding(text: str, model: str = "unsloth/Qwen3-Embedding-0.6B"):
    """生成文本 embedding"""
    payload = {
        "model": model,
        "input": [text],
    }
    response = httpx.post(
        f"{BASE_URL}/v1/embeddings",
        json=payload,
        headers=HEADERS,
        timeout=60,
    )
    result = response.json()
    print(f"Embedding 维度：{len(result['data'][0]['embedding'])}")
    return result


def rerank_documents(query: str, documents: list):
    """对文档进行重排序"""
    payload = {
        "query": query,
        "documents": documents,
    }
    response = httpx.post(
        f"{BASE_URL}/v1/rerank",
        json=payload,
        headers=HEADERS,
        timeout=120,
    )
    result = response.json()
    print("重排序结果:")
    for item in result.get("results", []):
        print(f"  文档 {item['index']}: 得分 {item['score']:.4f}")
    return result


def transcribe_audio(audio_path: str):
    """语音转文字"""
    # 读取音频文件
    with open(audio_path, "rb") as f:
        audio_data = f.read()

    # 使用 multipart/form-data 上传
    files = {"audio": ("audio.wav", audio_data, "audio/wav")}
    response = httpx.post(
        f"{BASE_URL}/v1/asr/transcribe",
        files=files,
        headers={"Authorization": f"Bearer {API_TOKEN}"},
        timeout=300,
    )
    result = response.json()
    print("转录结果:", result.get("text", ""))
    return result


def parse_pdf(pdf_path: str):
    """解析 PDF 文件"""
    # 读取 PDF 文件
    with open(pdf_path, "rb") as f:
        pdf_data = f.read()

    files = {"file": ("document.pdf", pdf_data, "application/pdf")}
    response = httpx.post(
        f"{BASE_URL}/v1/mineru/parse",
        files=files,
        headers={"Authorization": f"Bearer {API_TOKEN}"},
        timeout=600,
    )
    result = response.json()
    print("PDF 解析结果:", result)
    return result


def main():
    """主函数 - 演示各服务调用"""
    print("=" * 60)
    print("PI-LLM-Server 使用示例")
    print("=" * 60)
    print()

    # 1. 检查健康状态
    print("1. 检查健康状态")
    print("-" * 40)
    check_health()
    print()

    # 2. 获取服务状态
    print("2. 获取服务状态")
    print("-" * 40)
    get_status()
    print()

    # 3. 列出模型
    print("3. 列出可用模型")
    print("-" * 40)
    list_models()
    print()

    # 4. 生成 Embedding
    print("4. 生成 Embedding")
    print("-" * 40)
    embedding_result = generate_embedding("你好，世界！这是一个测试。")
    print()

    # 5. 重排序文档
    print("5. 重排序文档")
    print("-" * 40)
    docs = [
        "人工智能是计算机科学的一个分支",
        "机器学习是实现人工智能的方法之一",
        "深度学习是机器学习的子集",
    ]
    rerank_result = rerank_documents("深度学习", docs)
    print()

    print("=" * 60)
    print("示例完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
