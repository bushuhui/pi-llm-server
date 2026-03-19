# Prompt

## 2026-03-13

我在本机部署了一个LocalAI的大模型服务，端口是8080，你帮我在 这个项目 目录里写一个Python程序，测试查询已有的模型，调用里面的 whisper-small 模型，实现语音转文字，示例音频文件可以使用 audio_s.mp3 ，把识别后的文字保存到程序相同的目录。



帮我改进一下程序，程序接收命令行参数，可以输入命令，例如列出所有的模型（类别，调用接口），调用whipser模型，以及后续的其他类型的模型


我下载了 Qwen3-Reranker-0.6B 模型， 模型文件在 /home/bushuhui/.cache/modelscope/hub/models/Qwen/Qwen3-Reranker-0.6B ， 模型的说明在 https://modelscope.cn/models/Qwen/Qwen3-Reranker-0.6B 。 你可以参考已有的embedding 的程序写法，帮我写一个reranker的服务器端程序和客户端实例程序


reranker 模型使用显存太多了，帮我写一个CPU版本的server


## 2026-03-15

帮我把 这个项目 里面的embedding， reranker， asr， mineru的默认端口改成 8091， 8092， 8093， 8094 。同时修改README.md 里面的说明


帮我改进 这个项目 里面的embedding， reranker， asr， mineru 里面的服务器端、客户端程序，使用日志，日志文件保存到程序所在目录的 logs 目录，日志文件加上服务器类型的前缀


帮我把 这个项目 mineru_api_start.sh 改名成 mineru_server.sh ，README.md 等文档和相关的程序也同样修改

帮我把 这个项目 mineru_api_call.py 该名成 mineru_client.py , README.md 等文档和相关的程序也同样修改

帮我改进 这个项目 里面的embedding， reranker， asr， mineru 里面的服务器端、客户端程序里面的日志，检查一下日志是不是在终端、日志文件都有输出；把多余、重复的print等打印删除


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

在设计文档 doc/PYTHON_PACKAGE_REFACTOR_PLAN.md 中， scripts目录里面的子服务启动的脚步，后续计划写一个Python程序自动启动，这部分的程序、脚本，是不是放在 pi_llm_server/backends 里面更好？先不写代码等，先把方案设计弄好


采用方案A，那么如何写一个 cli 的工具能够将多个子服务启动起来；另外, script 目录里面的程序、脚本的名字保持目前已有的名字不变，例如还是 embedding_server.py embedding_client.py


这个项目的目录与结构设计文档 doc/PYTHON_PACKAGE_REFACTOR_PLAN.md 需要改进一下：
1. `.pids` 文件夹使用Linux的存储pid文件的方式
2. `logs` 文件夹使用Linux默认的Log记录方式，存储在 /var/log
3. 项目的配置文件放到 ~/.config/pi-llm-server/config.yml ， 程序运行的如果配置目录不存在，则新建，并将config.yaml.example 拷贝到 ~/.config/pi-llm-server/config.yml 作为初始的配置。然后提醒修改这个文件
先写程序，把设计文档修改好


我修改了这个项目的目录与结构设计文档 doc/PYTHON_PACKAGE_REFACTOR_PLAN.md ， 你再仔细检查一下，是否有错误、前后不一致的地方，如果有修改一下


按照项目的目录与结构设计文档 doc/PYTHON_PACKAGE_REFACTOR_PLAN.md 里面写的，实现出来


你帮我分析一下 conda 的 vllm的环境里面的包，把主要的安装包信息更新到 doc/requirements_vllm.txt


你参考 doc/requirements_vllm.txt 的包（只列出直接依赖的包，放宽一些包的版本，大于等于某个版本）。帮我把conda 环境 mineru 里面的包 整理成 doc/requirements_mineru.txt


配置文件 config.yaml 的示例在 examples/config.example.yaml ； 改进 scripts/mineru_server.sh 把里面写死的 Python路径，改成从命令行参数读取 ； 在 service_manager.py 中添加配置读取功能，启动 mineru, embedding 等服务启动程序、脚本的时候传递参数


参考 pi_llm_server/cli.py 里面如果 config.yaml 不存在的时候的处理方法，加入到 scripts/service_manager.py


帮我新建一下 doc/requirements_pi_llm_server.txt ，整合 doc/requirements_vllm.txt 和 doc/requirements_mineru.txt， 统一到 vllm 环境


你帮我调试一下 conda 的 pi-llm-server 这个环境是否还缺包。运行mineru服务的命令是： ./scripts/mineru_server.sh --python-path /home/tiger/anaconda3/envs/pi-llm-server/bin/python  测试PDF解析的命令是： python scripts/mineru_client.py data/InfoLOD.pdf results/InfoLOD.zip 运行的日志是 /home/bushuhui/.cache/pi-llm-server/logs/mineru.log 。需要运行了PDF解析的程序，mineru才开始运行，才能发现问题，可以通过log文件发现问题。你帮我把问题都解决完，把缺失的包写入到 doc/requirements_pi_llm_server.txt