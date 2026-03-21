#!/usr/bin/env python3
"""
Embedding 性能测试脚本
测试 CPU 和 GPU 运行 Embedding 的时间差异

使用方法:
    # 测试 CPU 性能
    python tests/benchmark_embedding.py --device cpu --iterations 20

    # 测试 GPU 性能
    python tests/benchmark_embedding.py --device cuda --iterations 20

    # 完整对比测试 (自动运行 CPU 和 GPU)
    python tests/benchmark_embedding.py --mode compare --iterations 20
"""

import os
import sys
import argparse
import time
import statistics
import json
from datetime import datetime
from typing import List, Tuple, Optional
import torch

# 添加项目路径
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

try:
    from sentence_transformers import SentenceTransformer
except ImportError:
    print("需要安装 sentence-transformers")
    print("请运行：pip install sentence-transformers")
    sys.exit(1)


# ==================== 测试数据 ====================

# 长文本测试数据 - 模拟真实场景中的长文档
LONG_TEST_TEXTS = [
    # 技术文档类 (约 500 字)
    """人工智能（Artificial Intelligence，简称 AI）是计算机科学的一个分支，致力于创建能够执行需要智能行为的任务的系统。
    机器学习是人工智能的核心技术，它使计算机能够从数据中学习并做出决策或预测，而无需明确编程。深度学习作为机器学习的一个重要子集，
    使用多层神经网络来模拟人脑的工作方式，在图像识别、语音识别、自然语言处理等领域取得了突破性进展。近年来，随着大数据、云计算和
    图形处理器（GPU）等技术的发展，人工智能技术得到了广泛应用，包括自动驾驶汽车、智能语音助手、医疗诊断、金融风控、智能制造等
    众多领域。同时，人工智能的发展也带来了一些伦理和社会问题，如就业替代、隐私保护、算法偏见等，需要社会各界共同关注和解决。
    未来，随着技术的不断进步和应用场景的拓展，人工智能将继续深刻改变人类社会的生活方式和工作模式。""",

    # 新闻报道类 (约 400 字)
    """据新华社报道，在刚刚结束的全国科技创新大会上，多位院士和专家学者就人工智能发展战略进行了深入探讨。
    会议指出，当前全球人工智能技术竞争日趋激烈，各国都在加大研发投入力度，争夺技术制高点。我国在人工智能领域取得了显著成就，
    在计算机视觉、语音识别、自然语言处理等方向已经达到或接近世界领先水平。然而，在基础算法、高端芯片、开发框架等核心领域，
    仍存在一定差距。会议强调，要坚持自主创新，加强基础研究，突破关键核心技术，培养高水平人才队伍，完善产业政策生态，
    推动人工智能与实体经济深度融合，为经济高质量发展提供强劲动力。与会代表一致认为，人工智能是推动新一轮科技革命和
    产业变革的战略性技术，必须把握发展机遇，应对风险挑战，确保人工智能健康有序发展。""",

    # 学术论文摘要类 (约 350 字)
    """摘要：本文提出了一种基于 Transformer 架构的新型自然语言处理模型，用于改进长文本理解和生成任务。
    传统方法在处理长序列时面临计算复杂度高、长程依赖建模困难等挑战。我们设计的模型引入了分层注意力机制和
    动态位置编码策略，有效降低了计算复杂度，同时增强了模型对长距离语义关系的捕捉能力。在多个基准数据集上的
    实验结果表明，该方法在文本分类、情感分析、问答系统等任务上均取得了优异表现，相比现有主流模型，
    在保持相当或更好准确率的同时，训练速度提升了约 30%，推理延迟降低了约 25%。此外，我们还进行了详细的
    消融实验，验证了各个模块的有效性。本研究的创新点在于提出了一种高效且可扩展的架构设计，为长文本处理
    任务提供了新的思路和方法。""",

    # 产品说明类 (约 450 字)
    """本产品是一款基于先进人工智能技术的智能客服系统，旨在帮助企业提升客户服务效率和质量。
    系统核心功能包括：智能问答，能够准确理解用户问题并提供精准回答，支持多轮对话和上下文理解；
    自动工单分类，根据用户描述自动识别问题类型并分配给相应部门处理；情感分析，实时监测用户情绪状态，
    对负面情绪及时预警并转接人工客服；知识库管理，支持企业快速构建和维护专属知识库，系统会自动学习
    和优化答案；多渠道接入，支持网页、APP、微信公众号、小程序等多个平台，实现统一的客户服务管理；
    数据分析报表，提供详细的客服数据分析和可视化报表，帮助企业持续优化服务质量。系统采用云端部署方式，
    无需企业自建服务器，即开即用，支持按需扩展。目前已在电商、金融、教育、医疗等多个行业成功应用，
    服务覆盖数百万终端用户，客户满意度达到 98% 以上。""",

    # 百科条目类 (约 550 字)
    """量子计算（Quantum Computing）是利用量子力学原理进行计算的一种全新计算范式，被认为是突破传统计算
    极限、解决特定复杂问题的关键技术。与经典计算机使用比特（0 或 1）作为基本信息单位不同，量子计算机使用
    量子比特（qubit），可以同时处于 0 和 1 的叠加态，这种现象称为量子叠加。此外，量子比特之间还存在量子纠缠
    现象，使得一个量子比特的状态变化可以瞬间影响另一个量子比特，无论它们相距多远。这些独特的量子特性使得
    量子计算机在某些特定问题上具有经典计算机无法比拟的计算优势，例如大数分解、组合优化、量子系统模拟、
    机器学习加速等。当前，全球科技巨头如 IBM、Google、微软等，以及众多初创公司和研究机构都在积极研发
    量子计算技术。2019 年，Google 宣布实现了"量子霸权"，其量子计算机在特定任务上超越了最强超级计算机。
    然而，量子计算仍面临诸多技术挑战，包括量子比特的稳定性、错误率控制、规模化扩展等。预计在未来 10-20 年内，
    量子计算将在密码学、材料科学、药物研发、金融建模等领域产生重要影响。""",
]

# 中等长度文本 (约 200 字)
MEDIUM_TEST_TEXTS = [
    "机器学习是人工智能的一个分支，它使用算法从数据中学习模式，并做出决策或预测。常见的机器学习方法包括监督学习、无监督学习、强化学习等。",
    "深度学习是机器学习的一个子集，主要使用神经网络模型。卷积神经网络用于图像处理，循环神经网络用于序列数据，Transformer 模型用于自然语言处理。",
    "自然语言处理（NLP）是人工智能的一个重要领域，致力于让计算机理解、生成和处理人类语言。应用包括机器翻译、情感分析、聊天机器人等。",
    "计算机视觉是人工智能的另一个重要领域，让计算机能够看懂图像和视频。应用包括人脸识别、目标检测、医学影像分析、自动驾驶等。",
    "推荐系统通过分析用户行为和偏好，向用户推荐可能感兴趣的内容或商品。广泛应用于电商平台、视频网站、社交媒体等。",
]

# 短文本 (约 50 字)
SHORT_TEST_TEXTS = [
    "今天天气真好，适合出去散步。",
    "机器学习让计算机从数据中学习。",
    "深度学习使用神经网络模拟人脑。",
    "自然语言处理用于理解和生成语言。",
    "计算机视觉让计算机看懂图像。",
]


# ==================== 性能测试函数 ====================

def warm_up_model(model: SentenceTransformer, device: str):
    """预热模型，避免冷启动影响测试结果"""
    print(f"正在预热模型 (设备：{device})...")
    test_texts = ["预热文本"] * 3
    for _ in range(3):
        model.encode(test_texts, convert_to_tensor=False, show_progress_bar=False)
    print("预热完成")


def run_benchmark(
    model: SentenceTransformer,
    texts: List[str],
    device: str,
    iterations: int = 20,
    batch_size: int = 1
) -> Tuple[List[float], List[float], dict]:
    """
    运行性能测试

    Args:
        model: 加载的模型
        texts: 测试文本列表
        device: 运行设备
        iterations: 测试迭代次数
        batch_size: 批次大小

    Returns:
        Tuple: (单次处理时间列表，每 token 时间列表，统计信息字典)
    """
    single_times = []
    per_token_times = []

    print(f"\n开始性能测试 - 设备：{device}, 迭代次数：{iterations}")
    print("-" * 70)

    for i in range(iterations):
        iter_start = time.time()

        # 处理所有文本
        for text in texts:
            single_start = time.time()
            embeddings = model.encode(
                text,
                convert_to_tensor=False,
                show_progress_bar=False,
                batch_size=batch_size
            )
            single_end = time.time()
            single_time = (single_end - single_start) * 1000  # 转换为毫秒
            single_times.append(single_time)

            # 估算 token 数 (使用简单字符估算)
            estimated_tokens = len(text) // 4  # 中文约 4 字符 1 token

        iter_end = time.time()
        iter_time = (iter_end - iter_start) * 1000
        print(f"  Iteration {i+1:2d}/{iterations}: {iter_time:7.2f} ms (单次平均：{sum(single_times[-len(texts):])/len(texts):.2f} ms)")

    # 计算统计信息
    mean_time = statistics.mean(single_times)
    median_time = statistics.median(single_times)
    std_dev = statistics.stdev(single_times) if len(single_times) > 1 else 0
    min_time = min(single_times)
    max_time = max(single_times)

    # 计算总吞吐量
    total_texts = len(texts) * iterations
    total_time_sec = sum(single_times) / 1000
    texts_per_second = total_texts / total_time_sec if total_time_sec > 0 else 0

    stats = {
        'device': device,
        'iterations': iterations,
        'total_texts': total_texts,
        'mean_ms': mean_time,
        'median_ms': median_time,
        'std_dev_ms': std_dev,
        'min_ms': min_time,
        'max_ms': max_time,
        'texts_per_second': texts_per_second,
        'total_time_sec': total_time_sec,
    }

    return single_times, per_token_times, stats


def print_report(stats: dict, title: str = ""):
    """打印测试报告"""
    print("\n" + "=" * 70)
    if title:
        print(f" {title}")
    print("=" * 70)
    print(f"  设备：            {stats['device']}")
    print(f"  测试次数：        {stats['iterations']}")
    print(f"  处理文本总数：    {stats['total_texts']}")
    print("-" * 70)
    print(f"  平均耗时：        {stats['mean_ms']:.2f} ms")
    print(f"  中位数：          {stats['median_ms']:.2f} ms")
    print(f"  标准差：          {stats['std_dev_ms']:.2f} ms")
    print(f"  最小值：          {stats['min_ms']:.2f} ms")
    print(f"  最大值：          {stats['max_ms']:.2f} ms")
    print("-" * 70)
    print(f"  总耗时：          {stats['total_time_sec']:.2f} 秒")
    print(f"  吞吐量：          {stats['texts_per_second']:.2f} 文本/秒")
    print("=" * 70)


def compare_results(cpu_stats: dict, gpu_stats: dict):
    """对比 CPU 和 GPU 测试结果"""
    print("\n" + "=" * 70)
    print(" CPU vs GPU 性能对比")
    print("=" * 70)

    cpu_mean = cpu_stats['mean_ms']
    gpu_mean = gpu_stats['mean_ms']

    speedup = cpu_mean / gpu_mean if gpu_mean > 0 else float('inf')
    improvement = ((cpu_mean - gpu_mean) / cpu_mean) * 100 if cpu_mean > 0 else 0

    print(f"\n  性能提升倍数：    {speedup:.2f}x")
    print(f"  性能提升百分比：  {improvement:.1f}%")
    print(f"\n  CPU 平均耗时：     {cpu_mean:.2f} ms")
    print(f"  GPU 平均耗时：     {gpu_mean:.2f} ms")
    print(f"\n  CPU 吞吐量：       {cpu_stats['texts_per_second']:.2f} 文本/秒")
    print(f"  GPU 吞吐量：       {gpu_stats['texts_per_second']:.2f} 文本/秒")
    print("=" * 70)


def save_results(cpu_stats: dict, gpu_stats: dict, output_file: str):
    """保存测试结果到 JSON 文件"""
    results = {
        'timestamp': datetime.now().isoformat(),
        'cpu': cpu_stats,
        'gpu': gpu_stats,
        'comparison': {
            'speedup': cpu_stats['mean_ms'] / gpu_stats['mean_ms'] if gpu_stats['mean_ms'] > 0 else float('inf'),
            'improvement_percent': ((cpu_stats['mean_ms'] - gpu_stats['mean_ms']) / cpu_stats['mean_ms']) * 100 if cpu_stats['mean_ms'] > 0 else 0,
        }
    }

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n测试结果已保存到：{output_file}")


# ==================== 主函数 ====================

def load_model(model_path: str, device: str) -> SentenceTransformer:
    """加载模型"""
    print(f"\n正在加载模型：{model_path}")
    print(f"目标设备：{device}")

    if device.startswith("cuda") and not torch.cuda.is_available():
        print("警告：未检测到 GPU，将使用 CPU 运行")
        device = "cpu"

    try:
        if device == "cpu":
            model = SentenceTransformer(
                model_path,
                device="cpu",
                trust_remote_code=True,
                model_kwargs={"low_cpu_mem_usage": True}
            )
        else:
            model = SentenceTransformer(
                model_path,
                device=device,
                trust_remote_code=True
            )

        # 显示模型信息
        total_params = sum(p.numel() for p in model.parameters())
        embedding_dim = model.get_sentence_embedding_dimension()
        print(f"模型加载成功 - 参数量：{total_params/1e6:.1f}M, 维度：{embedding_dim}")

        if device.startswith("cuda"):
            gpu_idx = 0
            if ":" in device:
                gpu_idx = int(device.split(":")[1])
            gpu_name = torch.cuda.get_device_name(gpu_idx)
            gpu_memory = torch.cuda.get_device_properties(gpu_idx).total_memory / 1024**3
            print(f"使用 GPU: {gpu_name} ({gpu_memory:.1f} GB)")

        return model

    except Exception as e:
        print(f"模型加载失败：{e}")
        if device.startswith("cuda"):
            print("尝试切换到 CPU...")
            model = SentenceTransformer(
                model_path,
                device="cpu",
                trust_remote_code=True,
                model_kwargs={"low_cpu_mem_usage": True}
            )
            return model
        raise


def main():
    parser = argparse.ArgumentParser(
        description="Embedding 性能测试脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 只测试 CPU
  python tests/benchmark_embedding.py --device cpu --iterations 20

  # 只测试 GPU
  python tests/benchmark_embedding.py --device cuda --iterations 20

  # 对比测试 (自动运行 CPU 和 GPU)
  python tests/benchmark_embedding.py --mode compare --iterations 20

  # 使用长文本测试
  python tests/benchmark_embedding.py --mode compare --text-length long
        """
    )

    parser.add_argument(
        "--model-path",
        type=str,
        default=os.path.expanduser("~/.cache/modelscope/hub/models/unsloth/Qwen3-Embedding-0.6B"),
        help="模型路径"
    )
    parser.add_argument(
        "--device",
        type=str,
        default="cpu",
        choices=["cpu", "cuda"],
        help="运行设备 (默认：cpu)"
    )
    parser.add_argument(
        "--mode",
        type=str,
        default="single",
        choices=["single", "compare"],
        help="测试模式：single=单次测试，compare=CPU/GPU 对比测试"
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=20,
        help="测试迭代次数 (默认：20)"
    )
    parser.add_argument(
        "--text-length",
        type=str,
        default="long",
        choices=["short", "medium", "long", "all"],
        help="测试文本长度 (默认：long)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="结果输出文件路径 (JSON 格式)"
    )

    args = parser.parse_args()

    # 选择测试文本
    if args.text_length == "short":
        test_texts = SHORT_TEST_TEXTS
    elif args.text_length == "medium":
        test_texts = MEDIUM_TEST_TEXTS
    elif args.text_length == "long":
        test_texts = LONG_TEST_TEXTS
    else:  # all
        test_texts = SHORT_TEST_TEXTS + MEDIUM_TEST_TEXTS + LONG_TEST_TEXTS

    print("\n" + "=" * 70)
    print(" Embedding 性能测试")
    print("=" * 70)
    print(f" 模型路径：{args.model_path}")
    print(f" 测试文本长度：{args.text_length} (共 {len(test_texts)} 条)")
    print(f" 迭代次数：{args.iterations}")

    # 计算测试文本的总字符数
    total_chars = sum(len(t) for t in test_texts)
    print(f" 测试文本总字符数：{total_chars}")
    print("=" * 70)

    results = {}

    if args.mode == "compare":
        # 对比测试模式
        cpu_stats = None
        gpu_stats = None

        # CPU 测试
        print("\n" + "#" * 70)
        print("# CPU 性能测试")
        print("#" * 70)
        cpu_model = load_model(args.model_path, "cpu")
        warm_up_model(cpu_model, "cpu")
        _, _, cpu_stats = run_benchmark(
            cpu_model, test_texts, "cpu",
            iterations=args.iterations
        )
        print_report(cpu_stats, "CPU 测试结果")

        # GPU 测试
        print("\n" + "#" * 70)
        print("# GPU 性能测试")
        print("#" * 70)
        gpu_model = load_model(args.model_path, "cuda")
        warm_up_model(gpu_model, "cuda")
        _, _, gpu_stats = run_benchmark(
            gpu_model, test_texts, "cuda",
            iterations=args.iterations
        )
        print_report(gpu_stats, "GPU 测试结果")

        # 对比结果
        compare_results(cpu_stats, gpu_stats)

        # 保存结果
        if args.output:
            save_results(cpu_stats, gpu_stats, args.output)
        elif args.model_path:
            # 默认保存到测试结果目录
            output_dir = os.path.join(SCRIPT_DIR, "results")
            os.makedirs(output_dir, exist_ok=True)
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            default_output = os.path.join(output_dir, f"embedding_benchmark_{timestamp}.json")
            save_results(cpu_stats, gpu_stats, default_output)

    else:
        # 单次测试模式
        model = load_model(args.model_path, args.device)
        warm_up_model(model, args.device)
        _, _, stats = run_benchmark(
            model, test_texts, args.device,
            iterations=args.iterations
        )
        print_report(stats, f"{args.device.upper()} 测试结果")

        if args.output:
            # 单次测试也保存结果
            with open(args.output, 'w', encoding='utf-8') as f:
                json.dump(stats, f, ensure_ascii=False, indent=2)
            print(f"\n测试结果已保存到：{args.output}")


if __name__ == "__main__":
    main()
