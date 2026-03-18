# Prompt

## 2026-03-13

我在本机部署了一个LocalAI的大模型服务，端口是8080，你帮我在 0_machine_learning_AI/LLM_API/LocalAI 目录里写一个Python程序，测试查询已有的模型，调用里面的 whisper-small 模型，实现语音转文字，示例音频文件可以使用 audio_s.mp3 ，把识别后的文字保存到程序相同的目录。



帮我改进一下程序，程序接收命令行参数，可以输入命令，例如列出所有的模型（类别，调用接口），调用whipser模型，以及后续的其他类型的模型


我下载了 Qwen3-Reranker-0.6B 模型， 模型文件在 /home/bushuhui/.cache/modelscope/hub/models/Qwen/Qwen3-Reranker-0.6B ， 模型的说明在 https://modelscope.cn/models/Qwen/Qwen3-Reranker-0.6B 。 你可以参考已有的embedding 的程序写法，帮我写一个reranker的服务器端程序和客户端实例程序


reranker 模型使用显存太多了，帮我写一个CPU版本的server


## 2026-03-15

帮我把 0_machine_learning_AI/LLM_API/LocalAI 里面的embedding， reranker， asr， mineru的默认端口改成 8091， 8092， 8093， 8094 。同时修改README.md 里面的说明


帮我改进 0_machine_learning_AI/LLM_API/LocalAI 里面的embedding， reranker， asr， mineru 里面的服务器端、客户端程序，使用日志，日志文件保存到程序所在目录的 logs 目录，日志文件加上服务器类型的前缀


帮我把 0_machine_learning_AI/LLM_API/LocalAI/mineru_api_start.sh 改名成 mineru_server.sh ，README.md 等文档和相关的程序也同样修改

帮我把 0_machine_learning_AI/LLM_API/LocalAI/mineru_api_call.py 该名成 mineru_client.py , README.md 等文档和相关的程序也同样修改

帮我改进 0_machine_learning_AI/LLM_API/LocalAI 里面的embedding， reranker， asr， mineru 里面的服务器端、客户端程序里面的日志，检查一下日志是不是在终端、日志文件都有输出；把多余、重复的print等打印删除


## 2026-03-16

帮我仔细看一下README.md, 仔细阅读一下 embedding, reranker, asr, mineru 的服务API的使用方法和各个client的实现。
想帮我设计一下统一接口的服务，就是把多个服务器集成到统一的一个服务。需要的功能有：
  - API具有队列能力，等处理完了再处理下一个
  - 能够像LocalAI提供模型查询能力，状态、健康查询
  - 能够把访问token设置在配置文件
  - 能够设置每类的模型，模型文件地址
  - 使用FastAPI
  - 能够提供API的访问文档，可以参考 mineru-api的 http://127.0.0.1:8094/docs 这样的在线文档
  - 在配置里面可以设置各个服务启动的脚本，使用的Python路径，以及mineru-api的路径
  - 这个统一服务程序命名为 pi-llm-server.py
先不用写程序，把整体的架构设计、设计方案等设计好，设计文档保存到 doc 目录下



你帮我把 asr_client.py 和 asr_client_toolkit.py 的对长音频的拆分然后解析的做法，做成web服务，可以参考 asr_server_0.py （具体的API 可以参考 README.md）里面的说明。可以使用FastAPI作为web服务的库。新写的程序可以保存为 asr_server.py 


## 2026-03-18

在 doc/PYTHON_PACKAGE_REFACTOR_PLAN.md 设计文档里面， 把 pi_llm_server 放在 src目录下，是不是目录太深了，把 pi_llm_server 直接放在项目根目录如何。先不写代码，只是把设计方案改进好

