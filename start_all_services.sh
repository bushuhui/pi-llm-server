#!/bin/bash
# 启动所有服务的脚本
# 使用方法：./start_all_services.sh

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
LOGS_DIR="${SCRIPT_DIR}/logs"

# 创建日志目录
mkdir -p "$LOGS_DIR"

echo "========================================"
echo "启动所有 AI 服务"
echo "========================================"
echo ""

# 检查子服务是否已运行
check_service() {
    local name=$1
    local port=$2
    if curl -s "http://127.0.0.1:${port}/health" > /dev/null 2>&1; then
        echo "✓ $name 已在运行 (端口 ${port})"
        return 0
    else
        echo "✗ $name 未运行 (端口 ${port})"
        return 1
    fi
}

echo "检查服务状态..."
echo "----------------------------------------"

EMBEDDING_RUNNING=false
ASR_RUNNING=false
RERANKER_RUNNING=false
MINERU_RUNNING=false

check_service "Embedding" "8091" || EMBEDDING_RUNNING=false
check_service "ASR" "8092" || ASR_RUNNING=false
check_service "Reranker" "8093" || RERANKER_RUNNING=false
check_service "MinerU" "8094" || MINERU_RUNNING=false

echo ""
echo "----------------------------------------"
echo "启动未运行的服务..."
echo "----------------------------------------"

# 启动 Embedding 服务
if [ "$EMBEDDING_RUNNING" = false ]; then
    echo "启动 Embedding Server..."
    cd "$SCRIPT_DIR"
    python embedding_server.py > "$LOGS_DIR/embedding.log" 2>&1 &
    sleep 3
    if curl -s "http://127.0.0.1:8091/health" > /dev/null 2>&1; then
        echo "✓ Embedding Server 启动成功"
    else
        echo "✗ Embedding Server 启动失败，请查看日志：$LOGS_DIR/embedding.log"
    fi
else
    echo "跳过 Embedding Server (已运行)"
fi

# 启动 ASR 服务
if [ "$ASR_RUNNING" = false ]; then
    echo "启动 ASR Server..."
    cd "$SCRIPT_DIR"
    python asr_server.py > "$LOGS_DIR/asr.log" 2>&1 &
    sleep 5
    if curl -s "http://127.0.0.1:8092/health" > /dev/null 2>&1; then
        echo "✓ ASR Server 启动成功"
    else
        echo "✗ ASR Server 启动失败，请查看日志：$LOGS_DIR/asr.log"
    fi
else
    echo "跳过 ASR Server (已运行)"
fi

# 启动 Reranker 服务
if [ "$RERANKER_RUNNING" = false ]; then
    echo "启动 Reranker Server..."
    cd "$SCRIPT_DIR"
    python reranker_server.py > "$LOGS_DIR/reranker.log" 2>&1 &
    sleep 3
    if curl -s "http://127.0.0.1:8093/health" > /dev/null 2>&1; then
        echo "✓ Reranker Server 启动成功"
    else
        echo "✗ Reranker Server 启动失败，请查看日志：$LOGS_DIR/reranker.log"
    fi
else
    echo "跳过 Reranker Server (已运行)"
fi

# 启动 MinerU 服务
if [ "$MINERU_RUNNING" = false ]; then
    echo "启动 MinerU Server..."
    cd "$SCRIPT_DIR"
    ./mineru_server.sh start
    sleep 5
    if curl -s "http://127.0.0.1:8094/health" > /dev/null 2>&1; then
        echo "✓ MinerU Server 启动成功"
    else
        echo "✗ MinerU Server 启动失败，请查看日志：$LOGS_DIR/mineru.log"
    fi
else
    echo "跳过 MinerU Server (已运行)"
fi

echo ""
echo "----------------------------------------"
echo "启动 PI-LLM Unified Server..."
echo "----------------------------------------"

# 检查统一服务是否已运行
if curl -s "http://127.0.0.1:8090/health" > /dev/null 2>&1; then
    echo "✓ PI-LLM Server 已在运行"
else
    python "$SCRIPT_DIR/pi-llm-server.py" > "$LOGS_DIR/pi-llm-server.log" 2>&1 &
    sleep 5
    if curl -s "http://127.0.0.1:8090/health" > /dev/null 2>&1; then
        echo "✓ PI-LLM Server 启动成功"
    else
        echo "✗ PI-LLM Server 启动失败，请查看日志：$LOGS_DIR/pi-llm-server.log"
    fi
fi

echo ""
echo "========================================"
echo "所有服务启动完成!"
echo "========================================"
echo ""
echo "服务状态:"
echo "  - Embedding:  http://127.0.0.1:8091"
echo "  - ASR:        http://127.0.0.1:8092"
echo "  - Reranker:   http://127.0.0.1:8093"
echo "  - MinerU:     http://127.0.0.1:8094"
echo "  - Unified:    http://127.0.0.1:8090"
echo ""
echo "API 文档：http://127.0.0.1:8090/docs"
echo "健康检查：http://127.0.0.1:8090/health"
echo ""
