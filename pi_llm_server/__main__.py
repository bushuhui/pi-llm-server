"""
允许通过 python -m pi_llm_server 启动服务

用法:
    # 仅启动统一网关（默认）
    python -m pi_llm_server

    # 启动所有后台服务
    python -m pi_llm_server services start --all

    # 启动后台服务 + 网关（一站式启动）
    python -m pi_llm_server start-all

    # 启动单个后台服务
    python -m pi_llm_server services start embedding

    # 查看后台服务状态
    python -m pi_llm_server services status

    # 查看网关 + 后台服务状态
    python -m pi_llm_server status

    # 使用 CLI 参数启动网关
    python -m pi_llm_server --port 8090
"""
import sys
import subprocess
import time
from pathlib import Path


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
        example_config = Path(__file__).parent.parent / "examples" / "config.example.yaml"
        if example_config.exists():
            import shutil
            shutil.copy2(str(example_config), str(DEFAULT_CONFIG_FILE))
            print(f"创建默认配置文件：{DEFAULT_CONFIG_FILE}")
            print("请修改配置文件后重新启动")
            print(f"配置文件位置：{DEFAULT_CONFIG_FILE}")
            sys.exit(1)
        else:
            print("错误：找不到示例配置文件 examples/config.example.yaml")
            sys.exit(1)

    return DEFAULT_CONFIG_FILE


def start_gateway(background: bool = False, config_file: Path = None):
    """启动网关服务"""
    config_file = config_file or ensure_config_exists()

    if background:
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
    else:
        # 前台启动，直接调用 CLI
        from pi_llm_server.cli import main as cli_main
        cli_main()
        return True


def stop_gateway() -> bool:
    """停止网关服务"""
    import signal
    import os

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
    import socket
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
            import os
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
        print(f"  {symbol} {cfg['name']:20s} {status:10s} 端口：{cfg['port']:5d} {pid_str}")

    print()
    print("=" * 60)


def main():
    """主入口函数"""
    # 检查子命令
    if len(sys.argv) > 1:
        if sys.argv[1] == 'services':
            # 传递给 service_manager（只管理后台服务）
            sys.argv.pop(1)
            from pi_llm_server.launcher.service_manager import main as service_main
            service_main()
        elif sys.argv[1] == 'start-all':
            # 一站式启动：后台服务 + 网关
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
            start_gateway(background=True, config_file=config_file)

            print()
            print("=" * 60)
            print("所有服务已启动")
            print("=" * 60)
        elif sys.argv[1] == 'stop-all':
            # 一站式停止：网关 + 后台服务
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
        elif sys.argv[1] == 'status':
            # 显示全部服务状态
            show_full_status()
        else:
            # 默认启动网关
            from pi_llm_server.cli import main as cli_main
            cli_main()
    else:
        # 默认启动网关
        from pi_llm_server.cli import main as cli_main
        cli_main()


if __name__ == "__main__":
    main()
