"""
允许通过 python -m pi_llm_server 启动服务

用法:
    # 仅启动统一网关（默认）
    python -m pi_llm_server

    # 启动所有服务（后台服务 + 网关）
    python -m pi_llm_server start-all

    # 停止所有服务
    python -m pi_llm_server stop-all

    # 查看所有服务状态
    python -m pi_llm_server status

    # 管理后台服务
    python -m pi_llm_server services start --all
    python -m pi_llm_server services status

    # 使用 CLI 参数启动网关
    python -m pi_llm_server --port 8090
"""
from pi_llm_server.cli import main

if __name__ == "__main__":
    main()
