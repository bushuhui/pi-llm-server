#!/usr/bin/env python3
"""
PI-LLM-Server 命令行入口
"""
import argparse
import sys
import os
from pathlib import Path

# 导入 FastAPI 应用和配置
from pi_llm_server.server import app, initialize_services
from pi_llm_server.config import init_config, ConfigManager
from pi_llm_server.utils.logging import init_default_logging
import uvicorn

# 默认配置目录
DEFAULT_CONFIG_DIR = Path.home() / ".config" / "pi-llm-server"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.yaml"


def ensure_config_exists() -> Path:
    """确保配置文件存在，不存在则自动创建"""
    if not DEFAULT_CONFIG_DIR.exists():
        DEFAULT_CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        print(f"创建配置目录：{DEFAULT_CONFIG_DIR}")

    if not DEFAULT_CONFIG_FILE.exists():
        # 从项目目录复制示例配置
        script_dir = Path(__file__).parent
        example_config = script_dir.parent.parent / "examples" / "config.example.yaml"
        if example_config.exists():
            import shutil
            shutil.copy2(example_config, DEFAULT_CONFIG_FILE)
            print(f"创建默认配置文件：{DEFAULT_CONFIG_FILE}")
            print("请修改配置文件后重新启动")
            print(f"配置文件位置：{DEFAULT_CONFIG_FILE}")
            sys.exit(1)
        else:
            print("错误：找不到示例配置文件 examples/config.example.yaml")
            sys.exit(1)

    return DEFAULT_CONFIG_FILE


def main():
    """主函数"""
    parser = argparse.ArgumentParser(
        description="PI-LLM Server - 统一 LLM 服务网关",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例用法:
  # 使用默认配置文件（~/.config/pi-llm-server/config.yaml）
  pi-llm-server

  # 指定配置文件
  pi-llm-server --config /path/to/config.yaml

  # 指定端口和日志级别
  pi-llm-server --port 8090 --log-level debug

  # 使用 python -m 方式启动
  python -m pi_llm_server --port 8090
        """
    )

    parser.add_argument(
        "--config", "-c",
        default=None,
        help=f"配置文件路径（默认：{DEFAULT_CONFIG_FILE}）"
    )

    parser.add_argument(
        "--host",
        default=None,
        help="服务主机地址（默认：从配置文件读取）"
    )

    parser.add_argument(
        "--port", "-p",
        type=int,
        default=None,
        help="服务端口（默认：从配置文件读取）"
    )

    parser.add_argument(
        "--log-level",
        default=None,
        choices=["debug", "info", "warning", "error"],
        help="日志级别（默认：从配置文件读取）"
    )

    args = parser.parse_args()

    # 确定配置文件路径
    if args.config:
        config_path = Path(args.config)
    else:
        config_path = ensure_config_exists()

    # 检查配置文件是否存在
    if not config_path.exists():
        print(f"错误：配置文件不存在：{config_path}")
        print("请复制 config.example.yaml 并修改配置")
        sys.exit(1)

    # 初始化日志
    log_level = args.log_level or "info"
    log_dir = Path.home() / ".cache" / "pi-llm-server" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    init_default_logging("pi-llm-server", log_level, str(log_dir))

    import logging
    logger = logging.getLogger(__name__)

    # 加载配置
    try:
        config_manager = init_config(str(config_path))
        logger.info(f"配置文件加载成功：{config_path}")
    except Exception as e:
        logger.error(f"配置文件加载失败：{e}")
        sys.exit(1)

    # 命令行参数覆盖配置文件
    host = args.host or config_manager.config.server.host
    port = args.port or config_manager.config.server.port
    if args.log_level:
        config_manager.config.server.log_level = args.log_level

    # 初始化服务
    initialize_services(config_manager)

    # 启动服务
    logger.info(f"启动服务：http://{host}:{port}")

    # 当 workers > 1 时，uvicorn 要求传递 import string 而不是 app 对象
    # 但多 worker 模式下，每个 worker 会重新导入模块，无法共享 config_manager
    # 因此建议生产环境使用反向代理（如 nginx）实现多进程，而非 uvicorn workers
    workers = config_manager.config.server.workers
    if workers > 1:
        logger.warning(f"多 worker 模式 ({workers}) 下配置管理器无法在 worker 间共享，建议使用反向代理实现多进程。")
        logger.warning("临时使用单 worker 模式启动，如需多 worker 请使用 nginx 等反向代理")
        workers = 1  # 临时降级为单 worker

    # 单 worker 模式，直接传递 app 对象
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level=config_manager.config.server.log_level,
        workers=workers,
    )


if __name__ == "__main__":
    main()
