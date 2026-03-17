#!/usr/bin/env python3
"""
Embedding 测试数据生成器
生成测试数据并保存到 JSON 文件
"""

import json
import os
from datetime import datetime

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(SCRIPT_DIR, "data")
RESULTS_DIR = os.path.join(SCRIPT_DIR, "results")

# 测试数据集 - 语义相似度测试
SIMILARITY_TEST_DATA = [
    # AI 技术相关 (高相似度)
    "人工智能是计算机科学的一个分支",
    "AI 技术正在改变各行各业",
    "机器学习是人工智能的核心技术",
    "深度学习用于图像识别和自然语言处理",

    # 天气相关 (高相似度)
    "今天天气真好阳光明媚",
    "晴空万里适合外出游玩",
    "天气预报说明天会下雨",

    # 动物相关 (高相似度)
    "猫咪喜欢吃鱼和老鼠",
    "小狗是人类最忠诚的朋友",
    "熊猫是中国的国宝动物",

    # 科技产品 (高相似度)
    "智能手机已经成为生活必需品",
    "笔记本电脑用于办公和娱乐",
    "平板电脑便于携带和使用",
]

# 语义搜索测试 - 文档库
SEARCH_DOCUMENTS = [
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

# 语义搜索测试 - 查询列表
SEARCH_QUERIES = [
    "AI 和机器学习",
    "处理大量数据",
    "智能机器人",
    "编程语言",
    "网络安全",
]


def generate_test_data():
    """生成测试数据文件"""

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')

    # 生成相似度测试数据文件
    similarity_file = os.path.join(DATA_DIR, f"test_data_similarity_{timestamp}.json")
    with open(similarity_file, 'w', encoding='utf-8') as f:
        data = {
            "description": "Embedding 相似度测试数据",
            "texts": SIMILARITY_TEST_DATA,
            "expected_groups": [
                {"name": "AI 技术", "indices": [0, 1, 2, 3]},
                {"name": "天气", "indices": [4, 5, 6]},
                {"name": "动物", "indices": [7, 8, 9]},
                {"name": "科技产品", "indices": [10, 11, 12]},
            ]
        }
        json.dump(data, f, ensure_ascii=False, indent=2)

    # 生成语义搜索测试数据文件
    search_file = os.path.join(DATA_DIR, f"test_data_search_{timestamp}.json")
    with open(search_file, 'w', encoding='utf-8') as f:
        data = {
            "description": "Embedding 语义搜索测试数据",
            "documents": SEARCH_DOCUMENTS,
            "queries": SEARCH_QUERIES,
            "expected_results": [
                {"query": "AI 和机器学习", "expected_topics": ["人工智能", "机器学习", "深度学习"]},
                {"query": "处理大量数据", "expected_topics": ["大数据", "数据挖掘"]},
                {"query": "智能机器人", "expected_topics": ["机器人", "人工智能"]},
                {"query": "编程语言", "expected_topics": ["Python"]},
                {"query": "网络安全", "expected_topics": ["网络安全"]},
            ]
        }
        json.dump(data, f, ensure_ascii=False, indent=2)

    print("=" * 60)
    print("测试数据生成完成")
    print("=" * 60)
    print(f"\n相似度测试数据：{similarity_file}")
    print(f"  - 文本数量：{len(SIMILARITY_TEST_DATA)}")
    print(f"  - 预期分组：4 组 (AI 技术、天气、动物、科技产品)")

    print(f"\n语义搜索测试数据：{search_file}")
    print(f"  - 文档数量：{len(SEARCH_DOCUMENTS)}")
    print(f"  - 查询数量：{len(SEARCH_QUERIES)}")

    print("\n" + "=" * 60)
    print("使用方法:")
    print("=" * 60)
    print(f"""
1. 确保 qwen3-embedding-4b 模型已启动 (在 LocalAI 后台)

2. 运行批量相似度测试:
   python localai_client.py embed-test -m qwen3-embedding-4b --data-dir {DATA_DIR}

3. 运行语义搜索测试:
   python localai_client.py embed-search -m qwen3-embedding-4b -q "人工智能技术" --data-dir {DATA_DIR}

4. 测试单个文本:
   python localai_client.py embed -m qwen3-embedding-4b -t "今天天气很好"
    """)


if __name__ == "__main__":
    generate_test_data()
