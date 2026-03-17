#!/usr/bin/env python3
"""
LocalAI 命令行客户端工具
支持多种模型类型和功能:
- 列出所有可用模型
- 语音转文字 (Whisper 模型)
- 文本生成 (LLM 模型)
- 图片生成 (Stable Diffusion 等)
- 图片识别 (Vision 模型)
- 文本嵌入 (Embedding 模型)
"""

import os
import sys
import argparse
import requests
from datetime import datetime

# LocalAI 服务配置
DEFAULT_BASE_URL = "http://localhost:8080"
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
RESULTS_DIR = os.path.join(SCRIPT_DIR, "results")


# ==================== 模型查询功能 ====================

def list_models(base_url: str, category: str = None):
    """
    查询 LocalAI 可用的模型列表

    Args:
        base_url: LocalAI 服务地址
        category: 模型类别过滤 (whisper, llm, embedding, image, vision)
    """
    print("=" * 60)
    print("LocalAI 可用模型列表")
    print("=" * 60)

    try:
        response = requests.get(f"{base_url}/v1/models", timeout=30)
        response.raise_for_status()

        models_data = response.json()
        models = models_data.get('data', [])

        # 按类别分类
        categorized = {
            'whisper': [],
            'llm': [],
            'embedding': [],
            'image': [],
            'vision': [],
            'other': []
        }

        for model in models:
            model_id = model.get('id', 'unknown').lower()

            if 'whisper' in model_id or 'audio' in model_id:
                categorized['whisper'].append(model)
            elif 'embedding' in model_id or 'embed' in model_id:
                categorized['embedding'].append(model)
            elif 'stable-diffusion' in model_id or 'sd-' in model_id or 'image' in model_id:
                categorized['image'].append(model)
            elif 'vision' in model_id or 'clip' in model_id:
                categorized['vision'].append(model)
            elif any(x in model_id for x in ['llama', 'mistral', 'gpt', 'qwen', 'phi']):
                categorized['llm'].append(model)
            else:
                categorized['other'].append(model)

        print(f"\n总模型数量：{len(models)}\n")

        # 显示所有类别或指定类别
        categories_to_show = [category] if category else ['whisper', 'llm', 'embedding', 'image', 'vision', 'other']

        category_names = {
            'whisper': '🎤 语音识别 (Whisper)',
            'llm': '💬 文本生成 (LLM)',
            'embedding': '📊 文本嵌入 (Embedding)',
            'image': '🎨 图片生成 (Image)',
            'vision': '👁️ 图片识别 (Vision)',
            'other': '📦 其他模型'
        }

        # 模型类别对应的 API 端点
        api_endpoints = {
            'whisper': 'POST /v1/audio/transcriptions',
            'llm': 'POST /v1/chat/completions',
            'embedding': 'POST /v1/embeddings',
            'image': 'POST /v1/images/generations',
            'vision': 'POST /v1/chat/completions (Vision)',
            'other': '-'
        }

        # 需要特殊 backend 的模型前缀（可能未安装）
        special_backends = ['whisperx-']

        for cat in categories_to_show:
            if cat not in categorized:
                print(f"未知类别：{cat}")
                continue

            cat_models = categorized[cat]
            if not cat_models:
                continue

            api_info = api_endpoints.get(cat, '-')
            print(f"\n{category_names.get(cat, cat)} - 数量：{len(cat_models)}")
            print(f"调用接口：{api_info}")
            print("-" * 40)
            for model in cat_models:
                model_id = model.get('id', 'unknown')

                # 检查是否需要特殊 backend
                warning = ""
                for backend in special_backends:
                    if model_id.startswith(backend):
                        warning = f" ⚠️  需要 {backend.rstrip('-')} backend"
                        break

                print(f"  • {model_id}{warning}")

        return models

    except requests.exceptions.ConnectionError:
        print("错误：无法连接到 LocalAI 服务，请确保服务已在 localhost:8080 启动")
        return []
    except Exception as e:
        print(f"错误：{e}")
        return []


# ==================== 语音转文字功能 ====================

def transcribe_audio(base_url: str, audio_file: str, model: str = "whisper-small", output: str = None):
    """
    使用 Whisper 模型进行语音转文字

    Args:
        base_url: LocalAI 服务地址
        audio_file: 音频文件路径
        model: 使用的 Whisper 模型名称
        output: 输出文件路径
    """
    print("=" * 60)
    print(f"语音转文字 - 使用模型：{model}")
    print("=" * 60)

    # 解析文件路径
    if not os.path.isabs(audio_file):
        audio_file = os.path.join(DATA_DIR, audio_file)

    if not os.path.exists(audio_file):
        print(f"错误：音频文件不存在：{audio_file}")
        return

    if output is None:
        output = os.path.join(RESULTS_DIR, f"transcription_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")

    print(f"\n音频文件：{audio_file}")
    print(f"输出文件：{output}")

    url = f"{base_url}/v1/audio/transcriptions"

    with open(audio_file, 'rb') as f:
        files = {
            'file': (os.path.basename(audio_file), f, 'audio/mpeg'),
            'model': (None, model),
        }

        print(f"\n正在处理...")
        try:
            response = requests.post(url, files=files, timeout=300)
            response.raise_for_status()

            result = response.json()
            text = result.get('text', '')

            with open(output, 'w', encoding='utf-8') as f:
                f.write(text)

            print(f"\n✓ 识别成功!")
            print(f"结果长度：{len(text)} 字符")
            print(f"已保存到：{output}")
            print(f"\n内容预览:")
            print("-" * 40)
            print(text[:300] + ("..." if len(text) > 300 else ""))
            print("-" * 40)

        except Exception as e:
            print(f"\n错误：{e}")


# ==================== 文本生成功能 ====================

def generate_text(base_url: str, model: str, prompt: str, max_tokens: int = 500):
    """
    使用 LLM 模型生成文本

    Args:
        base_url: LocalAI 服务地址
        model: 模型名称
        prompt: 输入提示词
        max_tokens: 最大生成 token 数
    """
    print("=" * 60)
    print(f"文本生成 - 使用模型：{model}")
    print("=" * 60)

    url = f"{base_url}/v1/chat/completions"

    payload = {
        "model": model,
        "messages": [
            {"role": "user", "content": prompt}
        ],
        "max_tokens": max_tokens
    }

    print(f"\n提示词：{prompt[:100]}{'...' if len(prompt) > 100 else ''}")
    print(f"正在生成...\n")

    try:
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()

        result = response.json()
        content = result.get('choices', [{}])[0].get('message', {}).get('content', '')

        print("生成结果:")
        print("-" * 40)
        print(content)
        print("-" * 40)

        # 保存到文件
        output_file = os.path.join(RESULTS_DIR, f"generation_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"提示词：{prompt}\n\n")
            f.write(f"生成结果:\n{content}")

        print(f"\n结果已保存到：{output_file}")

    except Exception as e:
        print(f"错误：{e}")


# ==================== 图片生成功能 ====================

def generate_image(base_url: str, prompt: str, model: str = "stable-diffusion-v2", size: str = "512x512"):
    """
    使用 Stable Diffusion 等模型生成图片

    Args:
        base_url: LocalAI 服务地址
        prompt: 图片描述
        model: 模型名称
        size: 图片尺寸
    """
    print("=" * 60)
    print(f"图片生成 - 使用模型：{model}")
    print("=" * 60)

    url = f"{base_url}/v1/images/generations"

    payload = {
        "model": model,
        "prompt": prompt,
        "size": size
    }

    print(f"\n提示词：{prompt}")
    print(f"正在生成...\n")

    try:
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()

        result = response.json()

        # LocalAI 返回格式
        if 'data' in result and len(result['data']) > 0:
            img_url = result['data'][0].get('url')
            print(f"生成成功!")
            print(f"图片 URL: {img_url}")
        else:
            print(f"结果：{result}")

    except Exception as e:
        print(f"错误：{e}")


# ==================== 文本嵌入功能 ====================

def create_embedding(base_url: str, model: str, text: str):
    """
    使用 Embedding 模型生成文本嵌入向量

    Args:
        base_url: LocalAI 服务地址
        model: 模型名称
        text: 输入文本
    """
    print("=" * 60)
    print(f"文本嵌入 - 使用模型：{model}")
    print("=" * 60)

    url = f"{base_url}/v1/embeddings"

    payload = {
        "model": model,
        "input": text
    }

    print(f"\n输入文本：{text[:100]}{'...' if len(text) > 100 else ''}")
    print(f"正在计算嵌入向量...\n")

    try:
        response = requests.post(url, json=payload, timeout=60)
        response.raise_for_status()

        result = response.json()
        embedding = result.get('data', [{}])[0].get('embedding', [])

        print(f"生成成功!")
        print(f"向量维度：{len(embedding)}")
        print(f"向量预览 (前 10 个值): {embedding[:10]}")

        # 保存到文件
        output_file = os.path.join(RESULTS_DIR, f"embedding_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"输入文本：{text}\n")
            f.write(f"模型：{model}\n")
            f.write(f"向量维度：{len(embedding)}\n")
            f.write(f"完整向量:\n{embedding}")

        print(f"\n完整向量已保存到：{output_file}")

    except Exception as e:
        print(f"错误：{e}")


# ==================== Embedding 批量测试功能 ====================

def cosine_similarity(vec1: list, vec2: list) -> float:
    """计算两个向量的余弦相似度"""
    import math
    dot_product = sum(a * b for a, b in zip(vec1, vec2))
    norm1 = math.sqrt(sum(a * a for a in vec1))
    norm2 = math.sqrt(sum(b * b for b in vec2))
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return dot_product / (norm1 * norm2)


def test_embedding_batch(base_url: str, model: str, test_data: list = None):
    """
    批量测试 Embedding 模型，计算文本相似度

    Args:
        base_url: LocalAI 服务地址
        model: 模型名称
        test_data: 测试文本列表
    """
    print("=" * 60)
    print(f"Embedding 批量测试 - 使用模型：{model}")
    print("=" * 60)

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

    print(f"\n测试文本数量：{len(test_data)}")
    print(f"正在生成嵌入向量...\n")

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
            print(f"  [{i+1}/{len(test_data)}] {text[:30]}... -> 维度：{len(embedding)}")

        # 计算相似度矩阵
        print(f"\n相似度矩阵:")
        print("-" * 60)

        n = len(embeddings)
        header = "          "
        for i in range(n):
            header += f"[{i+1}]     "
        print(header)

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
            print(row + f" <- {embeddings[i]['text'][:25]}")

        # 保存结果
        output_file = os.path.join(RESULTS_DIR, f"embedding_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"Embedding 批量测试结果\n")
            f.write(f"模型：{model}\n")
            f.write(f"时间：{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write("=" * 60 + "\n\n")

            f.write("测试文本:\n")
            for i, item in enumerate(embeddings):
                f.write(f"  [{i+1}] {item['text']}\n")

            f.write(f"\n向量维度：{len(embeddings[0]['embedding'])}\n\n")

            f.write("相似度矩阵:\n")
            for i in range(n):
                for j in range(i+1, n):
                    sim = cosine_similarity(embeddings[i]['embedding'], embeddings[j]['embedding'])
                    f.write(f"  [{i+1}] vs [{j+1}]: {sim:.4f}\n")

        print(f"\n详细结果已保存到：{output_file}")

    except Exception as e:
        print(f"错误：{e}")


# ==================== Embedding 语义搜索功能 ====================

def test_embedding_search(base_url: str, model: str, query: str, documents: list = None):
    """
    使用 Embedding 模型进行语义搜索测试

    Args:
        base_url: LocalAI 服务地址
        model: 模型名称
        query: 查询文本
        documents: 文档列表
    """
    print("=" * 60)
    print(f"Embedding 语义搜索测试 - 使用模型：{model}")
    print("=" * 60)

    # 默认文档库
    if documents is None:
        documents = [
            "人工智能是计算机科学的一个分支",
            "机器学习是人工智能的核心技术",
            "深度学习用于图像识别和自然语言处理",
            "Python 是一种流行的编程语言",
            "云计算提供弹性计算资源",
            "大数据技术处理海量信息",
            "区块链是一种分布式账本技术",
            "物联网连接物理设备",
        ]

    if not query:
        print("错误：请提供查询文本")
        return

    url = f"{base_url}/v1/embeddings"

    print(f"\n查询：{query}")
    print(f"文档库大小：{len(documents)}")
    print(f"正在计算向量...\n")

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

        # 计算相似度并排序
        results = []
        for doc in doc_embeddings:
            sim = cosine_similarity(query_embedding, doc['embedding'])
            results.append({'text': doc['text'], 'similarity': sim})

        results.sort(key=lambda x: x['similarity'], reverse=True)

        print("搜索结果 (按相似度排序):")
        print("-" * 60)
        for i, result in enumerate(results):
            score = result['similarity']
            bar = "█" * int(score * 20)
            print(f"  [{i+1}] 相似度：{score:.4f} {bar}")
            print(f"      文档：{result['text']}")
            print()

        # 保存结果
        output_file = os.path.join(RESULTS_DIR, f"embedding_search_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt")
        with open(output_file, 'w', encoding='utf-8') as f:
            f.write(f"Embedding 语义搜索结果\n")
            f.write(f"模型：{model}\n")
            f.write(f"查询：{query}\n")
            f.write("=" * 60 + "\n\n")
            for i, result in enumerate(results):
                f.write(f"[{i+1}] 相似度：{result['similarity']:.4f}\n")
                f.write(f"    文档：{result['text']}\n\n")

        print(f"详细结果已保存到：{output_file}")

    except Exception as e:
        print(f"错误：{e}")


# ==================== 图片识别功能 ====================

def vision_image(base_url: str, model: str, image_url: str, prompt: str = "描述这张图片"):
    """
    使用 Vision 模型识别图片内容

    Args:
        base_url: LocalAI 服务地址
        model: 模型名称
        image_url: 图片 URL 或本地文件路径
        prompt: 问题或指令
    """
    print("=" * 60)
    print(f"图片识别 - 使用模型：{model}")
    print("=" * 60)

    # 如果是本地文件，转换为 base64
    if os.path.exists(image_url):
        import base64
        with open(image_url, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')
        image_url = f"data:image/jpeg;base64,{image_data}"

    url = f"{base_url}/v1/chat/completions"

    payload = {
        "model": model,
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": prompt},
                    {"type": "image_url", "image_url": {"url": image_url}}
                ]
            }
        ],
        "max_tokens": 500
    }

    print(f"\n图片：{image_url[:50]}...")
    print(f"问题：{prompt}")
    print(f"正在识别...\n")

    try:
        response = requests.post(url, json=payload, timeout=120)
        response.raise_for_status()

        result = response.json()
        content = result.get('choices', [{}])[0].get('message', {}).get('content', '')

        print("识别结果:")
        print("-" * 40)
        print(content)
        print("-" * 40)

    except Exception as e:
        print(f"错误：{e}")


# ==================== 主函数 ====================

def main():
    parser = argparse.ArgumentParser(
        description="LocalAI 命令行客户端工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 列出所有模型
  python localai_client.py list

  # 按类别查看模型
  python localai_client.py list --category whisper
  python localai_client.py list --category llm

  # 语音转文字
  python localai_client.py transcribe audio_s.mp3
  python localai_client.py transcribe audio_s.mp3 --model whisper-base

  # 文本生成
  python localai_client.py generate --model llama-3.2-1b-instruct --prompt "什么是人工智能？"

  # 图片生成
  python localai_client.py image --prompt "一只在月光下奔跑的猫"

  # 文本嵌入 (单个)
  python localai_client.py embed --model qwen3-embedding-4b --text "今天天气很好"

  # Embedding 批量测试 (生成相似度矩阵)
  python localai_client.py embed-test --model qwen3-embedding-4b

  # Embedding 语义搜索
  python localai_client.py embed-search --model qwen3-embedding-4b --query "人工智能技术"

  # 图片识别
  python localai_client.py vision image.jpg --model claude-3-haiku
        """
    )

    parser.add_argument('--base-url', default=DEFAULT_BASE_URL,
                        help=f'LocalAI 服务地址 (默认：{DEFAULT_BASE_URL})')

    subparsers = parser.add_subparsers(dest='command', help='命令类型')

    # list 命令
    list_parser = subparsers.add_parser('list', help='列出所有可用模型')
    list_parser.add_argument('--category', '-c',
                             choices=['whisper', 'llm', 'embedding', 'image', 'vision', 'other'],
                             help='模型类别过滤')

    # transcribe 命令
    transcribe_parser = subparsers.add_parser('transcribe', help='语音转文字')
    transcribe_parser.add_argument('audio_file', help='音频文件路径')
    transcribe_parser.add_argument('--model', '-m', default='whisper-small',
                                   help='Whisper 模型名称 (默认：whisper-small)')
    transcribe_parser.add_argument('--output', '-o', help='输出文件路径')

    # generate 命令
    generate_parser = subparsers.add_parser('generate', help='文本生成')
    generate_parser.add_argument('--model', '-m', required=True, help='LLM 模型名称')
    generate_parser.add_argument('--prompt', '-p', required=True, help='输入提示词')
    generate_parser.add_argument('--max-tokens', type=int, default=500, help='最大生成 token 数')

    # image 命令
    image_parser = subparsers.add_parser('image', help='图片生成')
    image_parser.add_argument('--prompt', '-p', required=True, help='图片描述')
    image_parser.add_argument('--model', '-m', default='stable-diffusion-v2', help='图片生成模型')
    image_parser.add_argument('--size', '-s', default='512x512', help='图片尺寸')

    # embed 命令 (单个文本)
    embed_parser = subparsers.add_parser('embed', help='文本嵌入 (单个)')
    embed_parser.add_argument('--model', '-m', required=True, help='Embedding 模型名称')
    embed_parser.add_argument('--text', '-t', required=True, help='输入文本')

    # embed-test 命令 (批量测试)
    embed_test_parser = subparsers.add_parser('embed-test', help='Embedding 批量测试 (相似度矩阵)')
    embed_test_parser.add_argument('--model', '-m', required=True, help='Embedding 模型名称')

    # embed-search 命令 (语义搜索)
    embed_search_parser = subparsers.add_parser('embed-search', help='Embedding 语义搜索')
    embed_search_parser.add_argument('--model', '-m', required=True, help='Embedding 模型名称')
    embed_search_parser.add_argument('--query', '-q', required=True, help='查询文本')

    # vision 命令
    vision_parser = subparsers.add_parser('vision', help='图片识别')
    vision_parser.add_argument('image_file', help='图片文件路径或 URL')
    vision_parser.add_argument('--model', '-m', required=True, help='Vision 模型名称')
    vision_parser.add_argument('--prompt', '-p', default='描述这张图片', help='问题或指令')

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    # 执行对应命令
    if args.command == 'list':
        list_models(args.base_url, args.category)

    elif args.command == 'transcribe':
        transcribe_audio(args.base_url, args.audio_file, args.model, args.output)

    elif args.command == 'generate':
        generate_text(args.base_url, args.model, args.prompt, args.max_tokens)

    elif args.command == 'image':
        generate_image(args.base_url, args.prompt, args.model, args.size)

    elif args.command == 'embed':
        create_embedding(args.base_url, args.model, args.text)

    elif args.command == 'embed-test':
        test_embedding_batch(args.base_url, args.model)

    elif args.command == 'embed-search':
        test_embedding_search(args.base_url, args.model, args.query)

    elif args.command == 'vision':
        vision_image(args.base_url, args.model, args.image_file, args.prompt)


if __name__ == "__main__":
    main()
