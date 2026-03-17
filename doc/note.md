
## TODO

- [ ] 统一调整目录，把embedding等脚本挪到 backend 或者 scripts 目录；把 pi_llm_server 挪到 src 目录（或者其他目录）
- [ ] 查一下pip安装的时候，如何把脚本等放到PATH能找到的目录
- [ ] LLM service 测试

- [x] 统一设置端口号
- [x] 统一设置API的URL访问地址，列出模型，状态，访问
- [x] 日志、pid文件设置logs目录
- [x] LLM service 
  - [x] API具有队列能力，等处理完了再处理下一个
  - [x] 能够像LocalAI提供模型查询能力，状态、健康查询
  - [x] 能够把访问token设置在配置文件
  - [x] 能够设置每类的模型，模型文件地址
  - [x] 使用FastAPI，能够提供API的访问文档



## models

embedding:
Qwen3-Embedding-8B
Qwen3-Embedding-4B


rerank:
https://huggingface.co/Qwen/Qwen3-Reranker-4B
BGE-reranker-v2-m3

Qwen/Qwen3-Reranker-0.6B
https://modelscope.cn/models/Qwen/Qwen3-Reranker-0.6B


## install vllm & modelscop

```bash

# nvidia driver & cuda toolkit
# https://developer.nvidia.com/cuda-toolkit-archive
# 从这里打开 https://developer.nvidia.com/cuda-12-8-1-download-archive ，选择适合自己的版本，安装到系统


cd /usr/bin
sudo ln -s /usr/local/cuda-12.8/bin/nvcc nvcc

export CUDA_HOME=/usr/local/cuda-12.8
export PATH=$CUDA_HOME/bin:$CUDA_HOME/nvvm/bin:$PATH                                                                                            
export CPLUS_INCLUDE_PATH=$CUDA_HOME/include:$CPLUS_INCLUDE_PATH
export LIBRARY_PATH=$CUDA_HOME/lib64:$LIBRARY_PATH
export LD_LIBRARY_PATH=$CUDA_HOME/lib64:$LD_LIBRARY_PATH



# conda - vllm environment
conda create -n vllm python=3.13

uv pip install modelscope
uv pip install vllm
uv pip install sentence-transformers
uv pip install -U qwen-asr
uv pip install "vllm[audio]"


# conda - mineru environment
conda create -n mineru python=3.13

conda create -n mineru python=3.13
uv pip install -U "mineru[all]"




# https://www.modelscope.cn/models/unsloth/Qwen3-Embedding-4B/summary
# model download at: /home/bushuhui/.cache/modelscope/hub/models/unsloth/Qwen3-Embedding-4B
modelscope download --model unsloth/Qwen3-Embedding-4B


# model download at: /home/bushuhui/.cache/modelscope/hub/models/unsloth/Qwen3-Embedding-0.6B
modelscope download --model unsloth/Qwen3-Embedding-0.6B


# https://www.modelscope.cn/models/Qwen/Qwen3-ASR-1.7B
# model download at: /home/bushuhui/.cache/modelscope/hub/models/Qwen/Qwen3-ASR-1.7B
modelscope download --model Qwen/Qwen3-ASR-1.7B


# https://modelscope.cn/models/Qwen/Qwen3-Reranker-0.6B
# model download at: /home/bushuhui/.cache/modelscope/hub/models/Qwen/Qwen3-Reranker-0.6B
modelscope download --model Qwen/Qwen3-Reranker-0.6B

```


## commands

```bash


## mineru

# mineru API service - start
./mineru_server.sh start

# mineru API call demo
python mineru_client.py



## embedding

# 默认使用CPU
python embedding_server.py
# 使用GPU ， 指定的模型
python embedding_server.py --device cuda --model-path /path/to/Qwen3-Embedding-4B
# 测试
python vllm_embedding_client.py embed -t "今天天气很好"



## rerank
# 默认使用CPU
python reranker_server.py
# 使用GPU
python reranker_server.py --device cuda



## ASR

python asr_server.py

python asr_client.py transcribe audio_s.mp3

```


## LocalAI command

```bash
# localai client
  # 1. 列出所有模型
  python localai_client.py list

  # 2. 按类别查看
  python localai_client.py list -c whisper
  python localai_client.py list -c llm

  # 3. 语音转文字
  python localai_client.py transcribe audio_s.mp3
  python localai_client.py transcribe audio_s.mp3 -m whisper-base

  # 4. 文本生成
  python localai_client.py generate -m llama-3.2-1b-instruct -p "什么是人工智能？"

  # 5. 图片生成
  python localai_client.py image -p "一只在月光下奔跑的猫"

  # 6. 文本嵌入
  python localai_client.py embed -m text-embedding-ada-002 -t "今天天气很好"

  # 7. 图片识别
  python localai_client.py vision image.jpg -m claude-3-haiku
```
