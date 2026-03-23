"""
PI-LLM-Server 基本使用示例

本示例展示如何使用 Python 客户端调用 PI-LLM-Server 提供的服务。
"""

import httpx
import base64

# 服务地址
BASE_URL = "http://127.0.0.1:8090"

# API Token（从配置文件获取）
API_TOKEN = "sk-5f8b839908d14561590b70227c72ca86"

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


def generate_embedding(text: str, model: str = "unsloth/Qwen3-Embedding-0.6B", encoding_format: str = "float"):
    """生成文本 embedding

    Args:
        text: 输入文本
        model: 模型名称
        encoding_format: 编码格式，支持 "float" 或 "base64"
    """
    payload = {
        "model": model,
        "input": [text],
        "encoding_format": encoding_format,
    }
    response = httpx.post(
        f"{BASE_URL}/v1/embeddings",
        json=payload,
        headers=HEADERS,
        timeout=60,
    )
    result = response.json()

    if encoding_format == "base64":
        # base64 格式，解码并显示预览
        import base64
        import struct
        embedding_data = result['data'][0]['embedding']
        decoded = base64.b64decode(embedding_data)
        float_count = len(decoded) // 4  # float32 占 4 字节
        floats = struct.unpack(f'{float_count}f', decoded)
        print(f"Embedding 维度：{len(floats)} (base64 编码)")
        print(f"向量预览 (前 10 个值): {floats[:10]}")
    else:
        # float 格式
        print(f"Embedding 维度：{len(result['data'][0]['embedding'])}")

    return result


def rerank_documents(query: str, documents: list, encoding_format: str = None):
    """对文档进行重排序

    Args:
        query: 查询文本
        documents: 文档列表
        encoding_format: 编码格式，支持 "float" 或 "base64" (可选，保留用于未来扩展)
    """
    payload = {
        "query": query,
        "documents": documents,
    }
    if encoding_format:
        payload["encoding_format"] = encoding_format
    response = httpx.post(
        f"{BASE_URL}/v1/rerank",
        json=payload,
        headers=HEADERS,
        timeout=120,
    )
    result = response.json()
    print("重排序结果:")
    for item in result.get("results", []):
        print(f"  文档 {item['index']}: 得分 {item['relevance_score']:.4f}")
    return result


def transcribe_audio(audio_path: str):
    """语音转文字 (ASR)"""
    # 读取音频文件
    with open(audio_path, "rb") as f:
        audio_data = f.read()

    # 使用 multipart/form-data 上传
    files = {"file": ("audio.mp3", audio_data, "audio/mpeg")}
    response = httpx.post(
        f"{BASE_URL}/v1/audio/transcriptions",
        files=files,
        headers={"Authorization": f"Bearer {API_TOKEN}"},
        timeout=300,
    )
    result = response.json()
    print("转录结果:", result.get("text", ""))
    return result


def parse_pdf(pdf_path: str):
    """解析 PDF 文件 (MinerU/OCR)"""
    # 读取 PDF 文件
    with open(pdf_path, "rb") as f:
        pdf_data = f.read()

    files = {"files": ("document.pdf", pdf_data, "application/pdf")}
    response = httpx.post(
        f"{BASE_URL}/v1/ocr/parser",
        files=files,
        headers={"Authorization": f"Bearer {API_TOKEN}"},
        timeout=600,
    )

    # 检查响应
    if response.status_code != 200:
        try:
            error_data = response.json()
            print(f"请求失败：{response.status_code}")
            print(f"错误信息：{error_data}")
        except:
            print(f"请求失败：{response.status_code}")
            print(f"响应内容：{response.text[:200]}")
        return None

    content_type = response.headers.get("content-type", "")
    if "application/zip" not in content_type:
        print(f"警告：响应类型不是 ZIP ({content_type})")
        return None

    print(f"PDF 解析完成，ZIP 大小：{len(response.content)} bytes ({len(response.content) / 1024 / 1024:.2f} MB)")
    return response.content


def transcribe_audio_sample():
    """ASR 语音转文字示例"""
    import os

    audio_file = "data/audio_s.mp3"
    if not os.path.exists(audio_file):
        print(f"警告：音频文件不存在：{audio_file}")
        return None

    print(f"使用音频文件：{audio_file}")
    return transcribe_audio(audio_file)


def parse_pdf_sample():
    """OCR/PDF 解析示例"""
    import os

    pdf_file = "data/InfoLOD.pdf"
    if not os.path.exists(pdf_file):
        print(f"警告：PDF 文件不存在：{pdf_file}")
        return None

    print(f"使用 PDF 文件：{pdf_file}")
    return parse_pdf(pdf_file)


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

    # 6. ASR 语音转文字
    print("6. ASR 语音转文字")
    print("-" * 40)
    transcribe_audio_sample()
    print()

    # 7. OCR/PDF 解析
    print("7. OCR/PDF 解析")
    print("-" * 40)
    parse_pdf_sample()
    print()

    print("=" * 60)
    print("示例完成")
    print("=" * 60)


if __name__ == "__main__":
    main()
