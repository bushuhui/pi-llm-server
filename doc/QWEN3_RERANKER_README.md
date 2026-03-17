# Qwen3-Reranker-0.6B 部署指南

## 模型信息

- **模型名称**: Qwen3-Reranker-0.6B
- **模型路径**: `/home/bushuhui/.cache/modelscope/hub/models/Qwen/Qwen3-Reranker-0.6B`
- **功能**: 文本相关性排序（Reranker）
- **支持语言**: 100+ 语言
- **上下文长度**: 32k

## 快速开始

### 1. 启动服务器

```bash
# 基本启动（默认端口 8083）
python vllm_reranker_server.py

# 自定义端口
python vllm_reranker_server.py --port 8000

# 自定义 GPU 显存使用比例
python vllm_reranker_server.py --gpu-memory-utilization 0.9

# 后台运行
nohup python vllm_reranker_server.py > server.log 2>&1 &
```

### 2. 使用客户端测试

```bash
# 查看服务器信息
python vllm_reranker_client.py info

# 测试单个文本对相关性评分
python vllm_reranker_client.py rerank -q "什么是人工智能？" -d "人工智能是计算机科学的一个分支"

# 批量测试
python vllm_reranker_client.py rerank-batch

# 文档排序（对多个文档按相关性排序）
python vllm_reranker_client.py rerank-docs -q "人工智能技术" \
    -d "人工智能是计算机科学的一个分支" \
    -d "机器学习让计算机从数据中学习" \
    -d "今天天气很好阳光明媚"
```

## API 使用说明

### vLLM OpenAI 兼容 API

服务器启动后，提供 OpenAI 兼容的 `/v1/rerank` API 端点：

- **端点**: `http://localhost:8083/v1/rerank`
- **方法**: POST

#### 请求格式

```json
{
    "model": "/home/bushuhui/.cache/modelscope/hub/models/Qwen/Qwen3-Reranker-0.6B",
    "query": "什么是人工智能？",
    "documents": [
        "人工智能是计算机科学的一个分支",
        "机器学习让计算机从数据中学习"
    ]
}
```

#### 响应格式

```json
{
    "id": "rerank-xxx",
    "model": "...",
    "usage": {
        "prompt_tokens": 10,
        "total_tokens": 10
    },
    "results": [
        {
            "index": 0,
            "document": {
                "text": "人工智能是计算机科学的一个分支"
            },
            "relevance_score": 0.6576
        }
    ]
}
```

## 服务器参数说明

| 参数 | 默认值 | 说明 |
|------|--------|------|
| `--model-path` | `/home/bushuhui/.cache/modelscope/hub/models/Qwen/Qwen3-Reranker-0.6B` | 模型路径 |
| `--host` | `0.0.0.0` | 监听地址 |
| `--port` | `8083` | 监听端口 |
| `--gpu-memory-utilization` | `0.8` | GPU 显存使用比例 |
| `--max-model-len` | `8192` | 最大上下文长度 |
| `--tensor-parallel-size` | `1` | 张量并行大小（多 GPU 使用） |
| `--dtype` | `float16` | 数据类型 |
| `--runner` | `pooling` | 运行器类型（reranker 必须使用 pooling） |
| `--convert` | `embed` | 转换类型（reranker 必须使用 embed） |
| `--attention-backend` | `TRITON_ATTN` | 注意力后端 |
| `--enforce-eager` | `True` | 强制使用 eager 模式 |

## 性能参考

- **显存占用**: 约 1.5GB（0.6B 参数，bfloat16）
- **推理速度**: 取决于 GPU 性能
- **批量处理**: 支持多个查询 - 文档对并行处理

## 注意事项

1. **Instruction 使用**: 建议使用英文 instruction，模型训练时主要使用英文指令
2. **分数解释**: 输出分数表示文档与查询的相关性概率，越接近 1 表示越相关
3. **批处理**: 大量文档 rerank 时建议使用批处理接口
4. **长文档**: 模型支持 32k 上下文，但建议根据实际需求设置 `--max-model-len`

## 相关文件

- `vllm_reranker_server.py` - 服务器启动脚本
- `vllm_reranker_client.py` - 客户端测试工具

## 参考链接

- [ModelScope 模型页面](https://modelscope.cn/models/Qwen/Qwen3-Reranker-0.6B)
- [HuggingFace 模型页面](https://huggingface.co/Qwen/Qwen3-Reranker-0.6B)
- [Qwen3 Embedding 技术博客](https://qwenlm.github.io/blog/qwen3-embedding/)
