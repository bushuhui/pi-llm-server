# Qwen3-Embedding-4B vllm 部署指南

## 模型信息

- **模型名称**: Qwen3-Embedding-4B
- **模型路径**: `/home/bushuhui/.cache/modelscope/hub/models/unsloth/Qwen3-Embedding-4B`
- **框架**: vllm (OpenAI 兼容 API)

## 快速开始

### 1. 启动服务器

```bash
# 基本启动
python vllm_embedding_server.py

# 自定义端口
python vllm_embedding_server.py --port 8000

# 后台运行
nohup python vllm_embedding_server.py > server.log 2>&1 &

# 查看日志
tail -f server.log
```

### 2. 测试服务

```bash
# 查看服务器信息
python vllm_embedding_client.py info

# 测试单个文本
python vllm_embedding_client.py embed -t "今天天气很好"

# 批量相似度测试
python vllm_embedding_client.py embed-test

# 语义搜索
python vllm_embedding_client.py embed-search -q "人工智能技术"
```

## API 使用

### 端点

- **Embedding**: `POST /v1/embeddings`
- **模型列表**: `GET /v1/models`

### 请求示例

#### curl

```bash
curl http://localhost:8080/v1/embeddings \
  -H "Content-Type: application/json" \
  -d '{
    "model": "unsloth/Qwen3-Embedding-4B",
    "input": "今天天气很好"
  }'
```

#### Python

```python
import requests

response = requests.post(
    "http://localhost:8080/v1/embeddings",
    json={
        "model": "unsloth/Qwen3-Embedding-4B",
        "input": "今天天气很好"
    }
)

result = response.json()
embedding = result['data'][0]['embedding']
print(f"向量维度：{len(embedding)}")
```

#### OpenAI SDK

```python
from openai import OpenAI

client = OpenAI(
    base_url="http://localhost:8080/v1",
    api_key="not-needed"  # vllm 默认不需要 API key
)

response = client.embeddings.create(
    model="unsloth/Qwen3-Embedding-4B",
    input="今天天气很好"
)

embedding = response.data[0].embedding
print(f"向量维度：{len(embedding)}")
```

## 服务器参数

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--model-path` | `/home/bushuhui/.cache/modelscope/hub/models/unsloth/Qwen3-Embedding-4B` | 模型路径 |
| `--host` | `0.0.0.0` | 监听地址 |
| `--port` | `8080` | 监听端口 |
| `--gpu-memory-utilization` | `0.9` | GPU 显存使用比例 |
| `--max-num-batched-tokens` | `8192` | 最大批处理 token 数 |
| `--max-num-seqs` | `256` | 最大序列数 |
| `--tensor-parallel-size` | `1` | 张量并行大小 (多 GPU) |
| `--dtype` | `auto` | 数据类型 (auto/float16/bfloat16/float32) |
| `--enforce-eager` | - | 强制 eager 模式，减少显存 |
| `--enable-chunked-prefill` | - | 启用分块预填充 |

## 性能优化建议

### 单 GPU

```bash
python vllm_embedding_server.py \
  --gpu-memory-utilization 0.9 \
  --max-num-batched-tokens 8192
```

### 多 GPU

```bash
CUDA_VISIBLE_DEVICES=0,1 python vllm_embedding_server.py \
  --tensor-parallel-size 2
```

### 低显存模式

```bash
python vllm_embedding_server.py \
  --gpu-memory-utilization 0.7 \
  --enforce-eager \
  --enable-chunked-prefill
```

## 输出示例

### embed 命令输出

```
============================================================
文本嵌入 - 使用模型：unsloth/Qwen3-Embedding-4B
============================================================

输入文本：今天天气很好
正在计算嵌入向量...

生成成功!
向量维度：4096
向量预览 (前 10 个值): [0.023, -0.015, 0.042, ...]

完整向量已保存到：embedding_20260313_150000.txt
```

### embed-test 命令输出

```
============================================================
Embedding 批量测试 - 使用模型：unsloth/Qwen3-Embedding-4B
============================================================

测试文本数量：12
正在生成嵌入向量...

  [1/12] 人工智能是计算机科学的一个... -> 维度：4096
  [2/12] AI 技术正在改变各行各业... -> 维度：4096
  ...

相似度矩阵:
          [1]      [2]      [3]      ...
[1] 1.000  0.8923   0.8756   ... <- 人工智能是计算机...
[2] 0.8923 1.000    0.9012   ... <- AI 技术正在改变各...
...

高相似度文本对 (相似度 > 0.85):
  0.8923: 人工智能是计算机... <-> AI 技术正在改变...
  0.9012: AI 技术正在改变... <-> 机器学习是人工...
```

## 故障排除

### 问题：CUDA out of memory

**解决**: 降低 GPU 显存使用比例

```bash
python vllm_embedding_server.py --gpu-memory-utilization 0.7
```

### 问题：连接被拒绝

**解决**: 检查服务器是否启动

```bash
# 检查进程
ps aux | grep vllm

# 检查端口
netstat -tlnp | grep 8080

# 查看日志
tail -f server.log
```

### 问题：模型加载失败

**解决**: 确认模型路径正确

```bash
# 检查模型文件
ls -la /home/bushuhui/.cache/modelscope/hub/models/unsloth/Qwen3-Embedding-4B/
```

## 参考资料

- [vllm 官方文档](https://docs.vllm.ai/)
- [Qwen3-Embedding 模型页面](https://www.modelscope.cn/models/unsloth/Qwen3-Embedding-4B)
- [OpenAI Embedding API](https://platform.openai.com/docs/api-reference/embeddings)
