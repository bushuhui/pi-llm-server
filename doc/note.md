
## TODO

- [ ] 将实验室的 OpenClaw 也做成一个API，这样其他的程序就可以调用 OpenClaw 检索知识，执行命令等
  - [ ] graphify 等也可以转化成统一API接口，检索，查询


- [x] 修正 rerank 程序总是退出的问题 （好像又消失了？）
- [x] 修改 embedding API服务程序，默认输出 base64 的输出， 就是输入参数 `encoding_format` 没有指定的情况下。并使用JavaScript的openai库测试输出的base64数据的格式是否正确
- [x] PI-LLM OCR 增加接收 docx, doc, ppt, pptx, xls, xlsx等文件的功能
  - [x] 将 docx 转成 PDF, 使用 `libreoffice --headless --convert-to pdf input.docx`
  - [x] 然后调用现有 PDF 解析流程



- [x] 配置文件里面的模型需要改成 ~/.cache 开头的路径。
- [x] 如果用1个Conda环境，能够同时运行mineru和其他vllm服务程序，则配置文件里面的Python程序路径配置项可以去掉
- [x] pi-llm-server 的gateway 测试

- [x] 统一调整目录，把embedding等脚本挪到 backend 或者 scripts 目录；把 pi_llm_server 挪到 src 目录（或者其他目录）
- [x] 查一下pip安装的时候，如何把脚本等放到PATH能找到的目录

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


## pypi

```bash
# 本地安装工具
pip install -U setuptools wheel twine build

# 打包
python -m build

# 上传
twine upload dist/*

# 本地安装
pip install --upgrade -e ".[all]"
# pip安装
pip install pi-llm-server[all]
```


## git tag

```bash
# 增加tag
git tag -a v1.1.4 -m "发布 v1.1.4 版本，检查所有功能都能正确工作"

# 为指定提交创建标签
git tag -a v0.9 abc1234 -m "修复 v1.0 前的关键 bug"

# 列出tag
git tag

# 推送所有本地未推送的标签到远程
git push origin --tags

# 拉取服务器上的tags
git fetch --tags
```