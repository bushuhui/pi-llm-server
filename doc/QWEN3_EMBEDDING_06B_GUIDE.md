# Qwen3-Embedding-0.6B 快速开始指南

## ✅ 部署成功！

Qwen3-Embedding-0.6B 模型已成功在 **NVIDIA GeForce GTX 1080 (8GB)** 上运行！

## 模型信息

| 项目 | 值 |
|------|-----|
| 模型名称 | Qwen3-Embedding-0.6B |
| 参数量 | 595.8M |
| 向量维度 | 1024 |
| 显存占用 | ~2GB |
| 模型路径 | `/home/bushuhui/.cache/modelscope/hub/models/unsloth/Qwen3-Embedding-0.6B` |

## 快速启动

### 1. 启动服务器

```bash
cd /home/bushuhui/pi-lab/code_cook/0_machine_learning_AI/LLM_API/LocalAI

# GPU 模式（默认）
python embedding_server_hf.py --port 8081

# CPU 模式
python embedding_server_hf.py --port 8081 --no-cuda

# 后台运行
nohup python embedding_server_hf.py --port 8081 > server.log 2>&1 &
```

### 2. API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/health` | GET | 健康检查 |
| `/v1/models` | GET | 列出模型 |
| `/v1/embeddings` | POST | 生成 embedding |
| `/v1/similarity` | POST | 计算相似度 |

### 3. 使用示例

#### 健康检查
```bash
curl http://localhost:8081/health
# 响应：{"status":"healthy","device":"cuda"}
```

#### 生成单个 embedding
```bash
curl -X POST http://localhost:8081/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"input": "你好，世界！"}'
```

#### 生成批量 embedding
```bash
curl -X POST http://localhost:8081/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{"input": ["文本 1", "文本 2", "文本 3"]}'
```

#### 计算相似度
```bash
curl -X POST http://localhost:8081/v1/similarity \
  -H "Content-Type: application/json" \
  -d '{"text1": "人工智能", "text2": "机器学习"}'
# 响应：{"similarity": 0.79}
```

## Python 客户端

### 简单示例

```python
import requests

BASE_URL = "http://localhost:8081"

# 生成 embedding
def get_embedding(text):
    response = requests.post(
        f"{BASE_URL}/v1/embeddings",
        json={"input": text}
    )
    return response.json()['data'][0]['embedding']

# 计算相似度
def get_similarity(text1, text2):
    response = requests.post(
        f"{BASE_URL}/v1/similarity",
        json={"text1": text1, "text2": text2}
    )
    return response.json()['similarity']

# 测试
emb = get_embedding("你好")
print(f"向量维度：{len(emb)}")  # 1024

sim = get_similarity("人工智能", "机器学习")
print(f"相似度：{sim:.4f}")  # 约 0.79
```

### OpenAI SDK 兼容

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8081/v1",
    api_key="not-needed"
)

response = client.embeddings.create(
    model="unsloth/Qwen3-Embedding-0.6B",
    input="你好，世界！"
)

embedding = response.data[0].embedding
print(f"向量维度：{len(embedding)}")
```

## 性能测试

```bash
# 安装 ab (Apache Bench)
sudo apt install apache2-utils

# 压测
ab -n 100 -c 4 -p embedding.json -T application/json \
  http://localhost:8081/v1/embeddings
```

## 应用场景

### 1. 语义搜索

```python
# 文档库
documents = ["文档 1", "文档 2", "文档 3"]
doc_embeddings = [get_embedding(doc) for doc in documents]

# 查询
query = "搜索内容"
query_emb = get_embedding(query)

# 计算相似度并排序
similarities = [
    cosine_similarity(query_emb, emb)
    for emb in doc_embeddings
]
```

### 2. 文本聚类

```python
from sklearn.cluster import KMeans

texts = ["文本 1", "文本 2", ...]
embeddings = [get_embedding(t) for t in texts]

# K-means 聚类
kmeans = KMeans(n_clusters=5)
labels = kmeans.fit_predict(embeddings)
```

### 3. 推荐系统

```python
# 用户历史兴趣
user_history = ["文章 1", "文章 2", "文章 3"]
user_emb = sum([get_embedding(t) for t in user_history]) / len(user_history)

# 候选物品
candidates = ["物品 1", "物品 2", "物品 3"]
candidate_embs = [get_embedding(c) for c in candidates]

# 推荐最相似的
similarities = [cosine_similarity(user_emb, emb) for emb in candidate_embs]
recommend = candidates[similarities.index(max(similarities))]
```

## 与其他模型对比

| 模型 | 参数量 | 向量维度 | 显存占用 | 速度 | 精度 |
|------|--------|----------|----------|------|------|
| Qwen3-Embedding-0.6B | 0.6B | 1024 | ~2GB | 快 | 良好 |
| Qwen3-Embedding-4B | 4B | 4096 | ~10GB | 中 | 优秀 |
| bge-small-zh-v1.5 | 0.1B | 512 | ~0.5GB | 最快 | 一般 |
| bge-m3 | 0.6B | 1024 | ~2GB | 快 | 良好 |

## 常见问题

### Q: 如何切换到 4B 模型？
A: 修改启动命令：
```bash
python embedding_server_hf.py --model-path /path/to/Qwen3-Embedding-4B
```
**注意**: 4B 模型需要 >10GB 显存，GTX 1080 无法运行。

### Q: 服务器占用多少显存？
A: 约 2-3GB（0.6B 模型）

### Q: 支持并发请求吗？
A: 支持，但批处理性能更好。

### Q: 如何查看日志？
A:
```bash
tail -f server.log
```

## 文件列表

| 文件 | 说明 |
|------|------|
| `embedding_server_hf.py` | 服务器主程序 |
| `vllm_embedding_client.py` | 测试客户端（需要修改模型名） |
| `DEPLOYMENT_FINAL_REPORT.md` | 4B 模型部署报告 |
| `QWEN3_EMBEDDING_06B_GUIDE.md` | 本文档 |

## 总结

✅ **Qwen3-Embedding-0.6B 可以在 GTX 1080 (8GB) 上完美运行**

- 模型加载成功
- GPU 加速正常
- API 响应正常
- 支持批量处理
- 支持相似度计算

**立即可用！**
