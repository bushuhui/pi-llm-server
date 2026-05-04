#!/bin/bash
# MinerU API 启动脚本
# 使用方法：./mineru_server.sh [start|stop|restart] [--host HOST] [--port PORT] [--vram VRAM] [--model-source SOURCE]
#
# 参数说明:
#   --host          服务监听地址（默认：0.0.0.0）
#   --port          服务端口（默认：8094）
#   --vram          显存限制 MB（默认：9000）
#   --model-source  模型源：huggingface/modelscope/local（默认：modelscope）
#   --python-path   Python 解释器路径（必需）

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 配置日志和 PID 目录（使用用户目录）
LOGS_DIR="${HOME}/.cache/pi-llm-server/logs"
PID_DIR="${HOME}/.cache/pi-llm-server/pids"
mkdir -p "$LOGS_DIR" "$PID_DIR"
LOG_FILE="${LOGS_DIR}/mineru.log"
PID_FILE="${PID_DIR}/mineru.pid"

# 默认配置
HOST="0.0.0.0"
PORT="8094"
PYTHON_PATH=""

# 解析命令行参数
while [[ $# -gt 0 ]]; do
    case "$1" in
        --host)
            HOST="$2"
            shift 2
            ;;
        --port)
            PORT="$2"
            shift 2
            ;;
        --vram)
            # VRAM 保存为变量，稍后转换为 GB 并设置到 MINERU_VIRTUAL_VRAM_SIZE
            VRAM="$2"
            shift 2
            ;;
        --model-source)
            # 模型源通过环境变量传递
            MODEL_SOURCE="$2"
            shift 2
            ;;
        --python-path)
            PYTHON_PATH="$2"
            shift 2
            ;;
        start|stop|restart)
            ACTION="$1"
            shift
            ;;
        *)
            echo "未知参数：$1"
            echo "使用方法：$0 [start|stop|restart] [--host HOST] [--port PORT] [--vram VRAM] [--model-source SOURCE] --python-path PATH"
            exit 1
            ;;
    esac
done

# 默认 action 为 start
ACTION="${ACTION:-start}"

# 检查 Python 路径是否提供（仅 start/restart 需要）
if [ "$ACTION" != "stop" ] && [ -z "$PYTHON_PATH" ]; then
    echo "错误：必须指定 --python-path 参数"
    echo "示例：$0 start --python-path /home/tiger/anaconda3/envs/mineru/bin/python"
    exit 1
fi

# 检查 Python 解释器是否存在（仅 start/restart 需要）
if [ "$ACTION" != "stop" ] && [ ! -x "$PYTHON_PATH" ]; then
    echo "错误：Python 解释器不存在或不可执行：$PYTHON_PATH"
    exit 1
fi

start_server() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "MinerU API 已在运行中 (PID: $PID)"
            return 1
        else
            # PID 文件存在但进程不存在，清理旧文件
            echo "$(date '+%Y-%m-%d %H:%M:%S') 检测到旧的 PID 文件，但进程不存在，清理中..."
            rm -f "$PID_FILE"
        fi
    fi

    # 设置 VRAM 和 MODEL_SOURCE 默认值（如果未提供）
    VRAM="${VRAM:-9000}"
    MODEL_SOURCE="${MODEL_SOURCE:-modelscope}"

    echo "$(date '+%Y-%m-%d %H:%M:%S') 启动 MinerU API 服务..."
    echo "$(date '+%Y-%m-%d %H:%M:%S') Host: $HOST, Port: $PORT, VRAM: ${VRAM}MB, 模型源：$MODEL_SOURCE"
    echo "$(date '+%Y-%m-%d %H:%M:%S') Python: $PYTHON_PATH"

    # 后台启动，设置模型源和 VRAM 环境变量
    # 使用 mineru-api 命令启动（等价于 python -m mineru.cli.fast_api）
    # VRAM 通过环境变量 MINERU_VIRTUAL_VRAM_SIZE 传递（单位：GB）
    # 模型源通过环境变量 MINERU_MODEL_SOURCE 传递（huggingface/modelscope/local）
    export MINERU_MODEL_SOURCE="$MODEL_SOURCE"
    export MINERU_VIRTUAL_VRAM_SIZE="$(( VRAM / 1024 ))"
    nohup "$PYTHON_PATH" -m mineru.cli.fast_api \
        --host "$HOST" \
        --port "$PORT" \
        >> "$LOG_FILE" 2>&1 &

    echo $! > "$PID_FILE"
    sleep 3

    if ps -p $(cat "$PID_FILE") > /dev/null 2>&1; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') MinerU API 启动成功!"
        echo "$(date '+%Y-%m-%d %H:%M:%S') API 文档地址：http://${HOST}:${PORT}/docs"
        echo "$(date '+%Y-%m-%d %H:%M:%S') 日志文件：$LOG_FILE"
        return 0
    else
        echo "$(date '+%Y-%m-%d %H:%M:%S') MinerU API 启动失败，请查看日志：$LOG_FILE"
        return 1
    fi
}

stop_server() {
    KILLED_ANY=0

    # 1. 尝试停止 PID 文件中的主进程
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "$(date '+%Y-%m-%d %H:%M:%S') 停止 MinerU API 主进程 (PID: $PID)..."
            kill "$PID" 2>/dev/null
            KILLED_ANY=1
        else
            echo "$(date '+%Y-%m-%d %H:%M:%S') PID 文件中进程不存在 (PID: $PID)"
        fi
        rm -f "$PID_FILE"
    fi

    # 2. 杀掉所有残留子进程（mineru.cli.fast_api 会 fork 多个子进程）
    sleep 1
    CHILD_PIDS=$(pgrep -f "mineru.cli.fast_api.*--port $PORT" 2>/dev/null)
    if [ -n "$CHILD_PIDS" ]; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') 发现残留子进程，正在清理: $CHILD_PIDS"
        echo "$CHILD_PIDS" | xargs kill 2>/dev/null
        sleep 1
        # 强制清理仍未退出的进程
        REMAINING=$(pgrep -f "mineru.cli.fast_api.*--port $PORT" 2>/dev/null)
        if [ -n "$REMAINING" ]; then
            echo "$(date '+%Y-%m-%d %H:%M:%S') 强制终止残留进程: $REMAINING"
            echo "$REMAINING" | xargs kill -9 2>/dev/null
        fi
        KILLED_ANY=1
    fi

    if [ "$KILLED_ANY" -eq 1 ]; then
        echo "$(date '+%Y-%m-%d %H:%M:%S') 已停止"
        return 0
    fi

    echo "$(date '+%Y-%m-%d %H:%M:%S') MinerU API 未运行"
    return 1
}

case "$ACTION" in
    start)
        start_server
        ;;
    stop)
        stop_server
        ;;
    restart)
        stop_server
        sleep 1
        start_server
        ;;
    *)
        echo "使用方法：$0 {start|stop|restart} [--host HOST] [--port PORT] [--vram VRAM] [--model-source SOURCE] --python-path PATH"
        exit 1
        ;;
esac
