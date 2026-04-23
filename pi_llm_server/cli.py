#!/usr/bin/env python3
"""
PI-LLM-Server 命令行入口 - 统一网关 + 后台服务一站式启动
"""
import argparse
import sys
import os
import time
import subprocess
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
        # 从包内复制示例配置
        script_dir = Path(__file__).parent
        example_config = script_dir / "examples" / "config.example.yaml"
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


def start_gateway_background(config_file: Path = None):
    """后台启动网关服务"""
    config_file = config_file or ensure_config_exists()

    log_dir = Path.home() / ".cache" / "pi-llm-server" / "logs"
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "gateway.log"

    pid_dir = Path.home() / ".cache" / "pi-llm-server" / "pids"
    pid_dir.mkdir(parents=True, exist_ok=True)
    pid_file = pid_dir / "gateway.pid"

    with open(log_file, 'a') as f:
        proc = subprocess.Popen(
            [sys.executable, '-m', 'pi_llm_server', '--config', str(config_file)],
            stdout=f,
            stderr=f,
            start_new_session=True,
        )
    pid_file.write_text(str(proc.pid))
    print(f"✓ 网关已启动 (PID: {proc.pid})")
    time.sleep(2)
    return True


def stop_gateway() -> bool:
    """停止网关服务"""
    import signal
    import socket

    pid_dir = Path.home() / ".cache" / "pi-llm-server" / "pids"
    pid_file = pid_dir / "gateway.pid"

    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, signal.SIGTERM)
            print(f"发送 SIGTERM 到网关 (PID: {pid})")

            # 等待进程终止
            for _ in range(10):
                time.sleep(0.5)
                try:
                    os.kill(pid, 0)
                except OSError:
                    break
            else:
                os.kill(pid, signal.SIGKILL)
                print(f"发送 SIGKILL 到网关")

            pid_file.unlink()
            print("✓ 网关已停止")
            return True

        except ProcessLookupError:
            pid_file.unlink(missing_ok=True)
            print("✓ 网关已停止")
            return True
        except Exception as e:
            print(f"✗ 停止网关失败：{e}")
            return False

    # 尝试通过端口检查
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        result = sock.connect_ex(('127.0.0.1', 8090))
        sock.close()
        if result == 0:
            print("⚠ 网关在运行但没有 PID 文件，请手动停止")
            return False
    except Exception:
        pass

    print("✓ 网关未运行")
    return True


def is_gateway_running() -> bool:
    """检查网关是否正在运行"""
    import socket

    # 方法 1: 检查 PID 文件
    pid_dir = Path.home() / ".cache" / "pi-llm-server" / "pids"
    pid_file = pid_dir / "gateway.pid"

    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, 0)
            return True
        except (ValueError, OSError):
            pid_file.unlink(missing_ok=True)

    # 方法 2: 检查端口
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        result = sock.connect_ex(('127.0.0.1', 8090))
        sock.close()
        return result == 0
    except Exception:
        return False


def show_full_status():
    """显示网关 + 后台服务状态"""
    print("=" * 60)
    print("PI-LLM-Server 全部服务状态")
    print("=" * 60)
    print()

    # 网关状态
    gateway_status = "运行中" if is_gateway_running() else "已停止"
    gateway_symbol = "✓" if is_gateway_running() else "✗"
    print(f"  {gateway_symbol} {'统一网关':20s} {gateway_status:10s} 端口：8090")

    # 后台服务状态
    from pi_llm_server.launcher.service_manager import SERVICE_CONFIG, is_service_running, get_service_pid

    for name, cfg in SERVICE_CONFIG.items():
        status = "运行中" if is_service_running(name) else "已停止"
        pid = get_service_pid(name)
        pid_str = f"(PID: {pid})" if pid else ""
        symbol = "✓" if is_service_running(name) else "✗"

        # 守护进程没有端口
        if cfg['port']:
            print(f"  {symbol} {cfg['name']:20s} {status:10s} 端口：{cfg['port']:5d} {pid_str}")
        else:
            print(f"  {symbol} {cfg['name']:20s} {status:10s} {pid_str}")

    print()
    print("=" * 60)


def start_all_services():
    """一站式启动：后台服务 + 网关"""
    print("=" * 60)
    print("启动所有服务（后台服务 + 网关）")
    print("=" * 60)
    print()

    # 确保配置文件存在
    config_file = ensure_config_exists()

    # 启动后台服务
    from pi_llm_server.launcher.service_manager import start_all
    start_all()

    print()
    print("-" * 60)
    print()

    # 启动网关
    start_gateway_background(config_file=config_file)

    print()
    print("=" * 60)
    print("所有服务已启动")
    print("=" * 60)


def stop_all_services():
    """一站式停止：网关 + 后台服务"""
    print("=" * 60)
    print("停止所有服务")
    print("=" * 60)
    print()

    # 先停止网关
    stop_gateway()

    print()

    # 停止后台服务
    from pi_llm_server.launcher.service_manager import stop_all
    stop_all()

    print()
    print("=" * 60)
    print("所有服务已停止")
    print("=" * 60)


def run_gateway():
    """运行网关服务（前台模式）"""
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


def main():
    """主函数 - 支持一站式启动命令"""
    # 检查子命令
    if len(sys.argv) > 1:
        if sys.argv[1] == 'start-all':
            # 一站式启动：后台服务 + 网关
            start_all_services()
        elif sys.argv[1] == 'stop-all':
            # 一站式停止：网关 + 后台服务
            stop_all_services()
        elif sys.argv[1] == 'status':
            # 显示全部服务状态
            show_full_status()
        elif sys.argv[1] == 'services':
            # 传递给 service_manager（只管理后台服务）
            sys.argv.pop(0)  # 移除 'pi-llm-server' 或脚本名
            from pi_llm_server.launcher.service_manager import main as service_main
            service_main()
        elif sys.argv[1] in ('-h', '--help'):
            print("""
PI-LLM-Server - 统一 LLM 服务网关

用法:
  pi-llm-server [命令] [选项]

命令:
  start-all     启动所有服务（后台服务 + 网关）
  stop-all      停止所有服务（网关 + 后台服务）
  status        查看所有服务状态（网关 + 后台服务）
  services      后台服务管理（start/stop/restart/status）
  <无命令>      仅启动统一网关（默认行为）

示例:
  pi-llm-server start-all              # 一站式启动所有服务
  pi-llm-server stop-all               # 一站式停止所有服务
  pi-llm-server status                 # 查看所有服务状态
  pi-llm-server services start --all   # 仅启动后台服务
  pi-llm-server --port 8090            # 仅启动网关，指定端口
            """)
        else:
            # 默认启动网关
            run_gateway()
    else:
        # 默认启动网关
        run_gateway()


if __name__ == "__main__":
    main()
