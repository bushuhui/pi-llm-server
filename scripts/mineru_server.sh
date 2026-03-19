#!/bin/bash
# MinerU API 启动脚本
# 使用方法：./mineru_server.sh [start|stop|restart]

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# 配置日志和 PID 目录（使用用户目录）
LOGS_DIR="${HOME}/.cache/pi-llm-server/logs"
PID_DIR="${HOME}/.cache/pi-llm-server/pids"
mkdir -p "$LOGS_DIR" "$PID_DIR"
LOG_FILE="${LOGS_DIR}/mineru.log"
PID_FILE="${PID_DIR}/mineru.pid"

# 配置参数
HOST="0.0.0.0"
PORT="8094"
# 设置 VRAM 限制（MB），根据显存大小调整，2080Ti 建议设置为 9000-11000
VRAM="9000"
# 模型源：huggingface / modelscope / local（国内建议用 modelscope）
MODEL_SOURCE="${MINERU_MODEL_SOURCE:-modelscope}"

start_server() {
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "MinerU API 已在运行中 (PID: $PID)"
            return 1
        fi
    fi

    echo "$(date '+%Y-%m-%d %H:%M:%S') 启动 MinerU API 服务..."
    echo "$(date '+%Y-%m-%d %H:%M:%S') Host: $HOST, Port: $PORT, VRAM: ${VRAM}MB, 模型源: $MODEL_SOURCE"

    # 后台启动，设置模型源环境变量
    MINERU_MODEL_SOURCE="$MODEL_SOURCE" \
    nohup /home/tiger/anaconda3/envs/mineru/bin/mineru-api \
        --host "$HOST" \
        --port "$PORT" \
        --vram "$VRAM" \
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
    if [ -f "$PID_FILE" ]; then
        PID=$(cat "$PID_FILE")
        if ps -p "$PID" > /dev/null 2>&1; then
            echo "$(date '+%Y-%m-%d %H:%M:%S') 停止 MinerU API 服务 (PID: $PID)..."
            kill "$PID"
            rm -f "$PID_FILE"
            echo "$(date '+%Y-%m-%d %H:%M:%S') 已停止"
            return 0
        fi
    fi
    echo "$(date '+%Y-%m-%d %H:%M:%S') MinerU API 未运行"
    return 1
}

case "${1:-start}" in
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
        echo "使用方法：$0 {start|stop|restart}"
        exit 1
        ;;
esac
