# Qwen3-Embedding-4B 部署指南

## 问题总结

在尝试部署 Qwen3-Embedding-4B 时遇到了以下硬件限制：

### 硬件环境
- **GPU**: NVIDIA GeForce GTX 1080 (8GB 显存)
- **Compute Capability**: 6.1 (不支持 bfloat16)

### 遇到的问题

1. **torch 版本兼容性**
   - torch 2.10.0 与 vllm 0.17.1 不兼容
   - 解决方案：降级到 torch 2.5.1 + vllm 0.7.3

2. **bfloat16 不支持**
   - GTX 1080 (Compute Capability 6.1) 不支持 bfloat16
   - 解决方案：使用 `--dtype float16`

3. **显存不足 (OOM)**
   - Qwen3-Embedding-4B 需要约 9-10GB 显存
   - GTX 1080 只有 8GB，即使降低 `gpu-memory-utilization` 也无法加载
   - vllm 启动时尝试加载模型就 OOM

## 解决方案

### 方案 1：使用 HuggingFace Transformers + FastAPI (推荐)

创建了一个轻量级的 embedding 服务器 `embedding_server_hf.py`，支持 CPU/GPU 模式。

**启动方法:**

```bash
cd /home/bushuhui/pi-lab/code_cook/0_machine_learning_AI/LLM_API/LocalAI

# CPU 模式（稳定但慢）
python embedding_server_hf.py --port 8081

# GPU 模式（如果显存足够）
python embedding_server_hf.py --port 8081

# 强制 CPU 模式
python embedding_server_hf.py --port 8081 --no-cuda
```

**API 端点:**

- `GET /health` - 健康检查
- `GET /v1/models` - 列出模型
- `POST /v1/embeddings` - 生成 embedding 向量
- `POST /v1/similarity` - 计算文本相似度

**测试示例:**

```bash
# 健康检查
curl http://localhost:8081/health

# 生成 embedding
curl -X POST http://localhost:8081/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"input": "今天天气很好"}'

# 计算相似度
curl -X POST http://localhost:8081/v1/similarity \
  -H "Content-Type: application/json" \
  -d '{"text1": "人工智能", "text2": "机器学习"}'
```

**Python 客户端:**

```python
import requests

# 生成 embedding
response = requests.post(
    "http://localhost:8081/v1/embeddings",
    json={"input": "今天天气很好"}
)
embedding = response.json()['data'][0]['embedding']
print(f"向量维度：{len(embedding)}")

# 计算相似度
response = requests.post(
    "http://localhost:8081/v1/similarity",
    json={"text1": "人工智能", "text2": "机器学习"}
)
print(f"相似度：{response.json()['similarity']}")
```

### 方案 2：使用更小的模型

如果速度太慢，可以考虑使用更小的 embedding 模型：

- **Qwen3-Embedding-0.6B** - 约 1GB 显存
- **Qwen3-Embedding-1B** - 约 2GB 显存
- **bge-m3** - 约 1GB 显存
- **bge-small-zh-v1.5** - 约 0.5GB 显存

### 方案 3：升级 GPU

如果需要高性能和大批量处理，建议使用：

- **RTX 3090/4090** (24GB 显存)
- **RTX 4080** (16GB 显存)
- **Tesla V100/A100** (16-80GB 显存)

## 文件说明

| 文件 | 说明 |
|------|------|
| `embedding_server_hf.py` | HuggingFace Transformers + FastAPI 服务器（推荐） |
| `vllm_embedding_server.py` | vllm GPU 服务器（需要大显存 GPU） |
| `vllm_embedding_server_cpu.py` | vllm CPU 服务器（实验性） |
| `vllm_embedding_client.py` | vllm 客户端测试工具 |

## vllm 版本信息

已安装的兼容版本：
- **vllm**: 0.7.3
- **torch**: 2.5.1+cu124
- **torchvision**: 0.20.1
- **torchaudio**: 2.5.1

## 性能参考

| 模式 | 设备 | 速度 | 备注 |
|------|------|------|------|
| GPU | GTX 1080 | OOM | 显存不足无法运行 |
| CPU | 8 核 | ~1-2 秒/句 | 慢但可用 |
| GPU | RTX 3090 | ~50ms/句 | 推荐 |

## 建议

1. **开发测试**: 使用 `embedding_server_hf.py` CPU 模式
2. **生产部署**: 升级到更大显存的 GPU
3. **大批量处理**: 考虑使用 API 服务（如 OpenAI、阿里云等）
