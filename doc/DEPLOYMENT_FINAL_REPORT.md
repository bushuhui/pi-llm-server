# Qwen3-Embedding-4B 部署最终报告

## 硬件环境

- **GPU**: NVIDIA GeForce GTX 1080 (8GB 显存，Compute Capability 6.1)
- **系统内存**: 31GB
- **问题**: 不支持 bfloat16，显存不足

## 尝试的方案及结果

### 方案 1: vllm GPU 部署
**结果**: ❌ 失败 - CUDA OOM

```
torch.OutOfMemoryError: CUDA out of memory. Tried to allocate 48.00 MiB.
GPU 0 has a total capacity of 7.92 GiB of which 45.69 MiB is free.
Including non-PyTorch memory, this process has 7.28 GiB memory in use.
```

**原因**: 模型权重本身就占用 ~7.16GB，超过 8GB 显存上限

### 方案 2: vllm CPU 部署
**结果**: ❌ 失败 - 系统 OOM

进程被 OOM killer 直接杀死（exit code 137）

### 方案 3: HuggingFace Transformers + FastAPI
**结果**: ❌ 失败 - 系统 OOM

即使在 CPU 上加载，也需要约 8-10GB 连续内存，进程被杀死

### 方案 4: 降低精度/量化
**结果**: ❌ 无法测试 - 模型加载阶段就 OOM

## 内存需求分析

Qwen3-Embedding-4B 模型参数约 4B：

| 精度 | 每参数大小 | 总内存需求 |
|------|-----------|-----------|
| float32 | 4 bytes | ~16 GB |
| float16 | 2 bytes | ~8 GB |
| int8 | 1 byte | ~4 GB |

**问题**: 即使使用 float16，也需要约 8GB 连续内存，加上 Python 开销和框架开销，实际需要 10-12GB。

## 推荐解决方案

### 方案 A: 使用更小的模型 (立即可用)

推荐替代模型（按性能排序）：

1. **bge-m3** (~1GB 显存)
   ```bash
   pip install sentence-transformers
   python -c "from sentence_transformers import SentenceTransformer; m = SentenceTransformer('BAAI/bge-m3')"
   ```

2. **bge-small-zh-v1.5** (~0.5GB 显存)
   ```bash
   python -c "from sentence_transformers import SentenceTransformer; m = SentenceTransformer('BAAI/bge-small-zh-v1.5')"
   ```

3. **Qwen3-Embedding-0.6B** (需下载)
   ```bash
   # 下载较小的 Qwen3 版本
   ```

### 方案 B: 升级硬件

推荐 GPU（按性价比排序）：

1. **RTX 3060 12GB** - 约 2000 元，性价比最高
2. **RTX 4060 Ti 16GB** - 约 3500 元
3. **RTX 3090 24GB (二手)** - 约 5000 元
4. **RTX 4090 24GB** - 约 14000 元

### 方案 C: 使用云服务

1. **阿里云百炼** - Qwen embedding API
2. **OpenAI API** - text-embedding-3-large
3. **火山引擎** - 豆包 embedding

## 当前可用的文件

| 文件 | 状态 | 用途 |
|------|------|------|
| `embedding_server_hf.py` | ⚠️ 需要更小模型 | FastAPI 服务器框架 |
| `vllm_embedding_server.py` | ❌ 需要 >10GB 显存 | vllm GPU 服务器 |
| `vllm_embedding_client.py` | ✅ 可用 | 测试客户端 |
| `EMBEDDING_DEPLOYMENT.md` | ✅ 可用 | 部署文档 |

## 快速开始（使用 bge-small-zh-v1.5）

1. 修改 `embedding_server_hf.py` 中的模型路径：
```python
--model-path BAAI/bge-small-zh-v1.5
```

2. 启动服务：
```bash
python embedding_server_hf.py --port 8081
```

3. 测试：
```bash
curl http://localhost:8081/health
curl -X POST http://localhost:8081/v1/embeddings -d '{"input": "你好"}'
```

## 结论

**Qwen3-Embedding-4B 无法在以下环境运行**：
- ❌ 8GB 显存的 GPU（如 GTX 1080）
- ❌ 32GB 以下系统内存的纯 CPU 环境

**建议**：
1. 开发测试：使用 bge-small-zh-v1.5 或 bge-m3
2. 生产部署：升级 GPU 到 12GB+ 显存
3. 快速上线：使用云服务 API
