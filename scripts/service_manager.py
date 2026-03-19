#!/usr/bin/env python3
"""
PI-LLM-Server 服务管理工具

支持启动、停止、重启服务，查看服务状态等功能。

使用方法:
    # 启动所有子服务
    python service_manager.py start --all

    # 启动单个服务
    python service_manager.py start embedding

    # 启动子服务 + 统一网关
    python service_manager.py start --with-gateway

    # 停止所有服务
    python service_manager.py stop --all

    # 查看服务状态
    python service_manager.py status

    # 重启服务
    python service_manager.py restart embedding
"""

import argparse
import os
import sys
import signal
import time
import subprocess
from pathlib import Path
from typing import Dict, Optional

# 服务配置
SERVICE_CONFIG = {
    'embedding': {
        'script': 'embedding_server.py',
        'port': 8091,
        'name': 'Embedding Server',
    },
    'asr': {
        'script': 'asr_server.py',
        'port': 8092,
        'name': 'ASR Server',
    },
    'reranker': {
        'script': 'reranker_server.py',
        'port': 8093,
        'name': 'Reranker Server',
    },
    'mineru': {
        'script': 'mineru_server.sh',
        'port': 8094,
        'name': 'MinerU Server',
    },
    'gateway': {
        'script': None,  # 使用 python -m pi_llm_server
        'port': 8090,
        'name': 'PI-LLM Gateway',
    },
}

# 用户目录
LOG_DIR = Path.home() / '.cache' / 'pi-llm-server' / 'logs'
PID_DIR = Path.home() / '.cache' / 'pi-llm-server' / 'pids'

# 确保目录存在
LOG_DIR.mkdir(parents=True, exist_ok=True)
PID_DIR.mkdir(parents=True, exist_ok=True)


def get_log_dir() -> Path:
    """获取日志目录"""
    return LOG_DIR


def get_pid_dir() -> Path:
    """获取 PID 目录"""
    return PID_DIR


def get_pid_file(service_name: str) -> Path:
    """获取服务的 PID 文件路径"""
    return get_pid_dir() / f"{service_name}.pid"


def get_log_file(service_name: str) -> Path:
    """获取服务的日志文件路径"""
    return get_log_dir() / f"{service_name}.log"


def is_service_running(service_name: str) -> bool:
    """检查服务是否正在运行"""
    config = SERVICE_CONFIG.get(service_name)
    if not config:
        return False

    port = config['port']

    # 方法 1: 检查 PID 文件
    pid_file = get_pid_file(service_name)
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, 0)  # 检查进程是否存在
            return True
        except (ValueError, OSError):
            pid_file.unlink(missing_ok=True)

    # 方法 2: 检查端口
    import socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        result = sock.connect_ex(('127.0.0.1', port))
        sock.close()
        return result == 0
    except Exception:
        return False


def get_service_pid(service_name: str) -> Optional[int]:
    """获取服务的 PID"""
    pid_file = get_pid_file(service_name)
    if pid_file.exists():
        try:
            return int(pid_file.read_text().strip())
        except ValueError:
            return None
    return None


def start_service(service_name: str, background: bool = True) -> bool:
    """启动单个服务"""
    config = SERVICE_CONFIG.get(service_name)
    if not config:
        print(f"错误：未知服务 '{service_name}'")
        return False

    if is_service_running(service_name):
        print(f"✓ {config['name']} 已在运行")
        return True

    script_dir = Path(__file__).parent
    log_file = get_log_file(service_name)
    pid_file = get_pid_file(service_name)

    print(f"启动 {config['name']}...", end=" ")

    try:
        if service_name == 'gateway':
            # 网关使用 python -m pi_llm_server 启动
            cmd = [sys.executable, '-m', 'pi_llm_server']
        elif config['script'].endswith('.sh'):
            # Shell 脚本
            cmd = ['bash', script_dir / config['script'], 'start']
        else:
            # Python 脚本
            cmd = [sys.executable, script_dir / config['script']]

        if background:
            # 后台运行
            with open(log_file, 'a') as f:
                proc = subprocess.Popen(
                    cmd,
                    stdout=f,
                    stderr=f,
                    cwd=str(script_dir),
                    start_new_session=True,
                )
            # 写入 PID 文件
            pid_file.write_text(str(proc.pid))
            print(f"进程 ID: {proc.pid}")
        else:
            # 前台运行
            proc = subprocess.Popen(cmd, cwd=str(script_dir))
            pid_file.write_text(str(proc.pid))
            proc.wait()
            return True

        # 等待服务启动
        time.sleep(3)

        if is_service_running(service_name):
            print(f"✓ {config['name']} 启动成功")
            return True
        else:
            print(f"✗ {config['name']} 启动失败，请查看日志：{log_file}")
            return False

    except Exception as e:
        print(f"✗ {config['name']} 启动异常：{e}")
        return False


def stop_service(service_name: str) -> bool:
    """停止单个服务"""
    config = SERVICE_CONFIG.get(service_name)
    if not config:
        print(f"错误：未知服务 '{service_name}'")
        return False

    if not is_service_running(service_name):
        print(f"✓ {config['name']} 未运行")
        return True

    pid = get_service_pid(service_name)
    if pid:
        try:
            os.kill(pid, signal.SIGTERM)
            print(f"发送 SIGTERM 到 {config['name']} (PID: {pid})")

            # 等待进程终止
            for _ in range(10):
                time.sleep(0.5)
                try:
                    os.kill(pid, 0)
                except OSError:
                    break
            else:
                # 进程仍在运行，强制终止
                os.kill(pid, signal.SIGKILL)
                print(f"发送 SIGKILL 到 {config['name']}")

            # 删除 PID 文件
            pid_file = get_pid_file(service_name)
            pid_file.unlink(missing_ok=True)

            print(f"✓ {config['name']} 已停止")
            return True

        except ProcessLookupError:
            print(f"✓ {config['name']} 已停止")
            return True
        except Exception as e:
            print(f"✗ 停止 {config['name']} 失败：{e}")
            return False
    else:
        # 没有 PID 文件，尝试通过端口检查找到进程
        print(f"警告：未找到 {config['name']} 的 PID 文件")
        return False


def restart_service(service_name: str) -> bool:
    """重启服务"""
    stop_service(service_name)
    time.sleep(1)
    return start_service(service_name)


def show_status():
    """显示所有服务状态"""
    print("=" * 60)
    print("PI-LLM-Server 服务状态")
    print("=" * 60)
    print()

    for name, config in SERVICE_CONFIG.items():
        status = "运行中" if is_service_running(name) else "已停止"
        pid = get_service_pid(name)
        pid_str = f"(PID: {pid})" if pid else ""
        symbol = "✓" if is_service_running(name) else "✗"
        print(f"  {symbol} {config['name']:20s} {status:10s} 端口：{config['port']:5d} {pid_str}")

    print()
    print("=" * 60)

    # 显示目录信息
    print(f"日志目录：{get_log_dir()}")
    print(f"PID 目录：{get_pid_dir()}")


def start_all(with_gateway: bool = False):
    """启动所有服务"""
    print("正在启动所有服务...")
    print()

    # 启动子服务
    for name in ['embedding', 'asr', 'reranker', 'mineru']:
        start_service(name)

    # 启动网关
    if with_gateway:
        print()
        start_service('gateway')


def stop_all():
    """停止所有服务"""
    print("正在停止所有服务...")
    print()

    # 先停止网关
    stop_service('gateway')

    # 停止子服务
    for name in ['embedding', 'asr', 'reranker', 'mineru']:
        stop_service(name)


def main():
    parser = argparse.ArgumentParser(
        description="PI-LLM-Server 服务管理工具",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  %(prog)s start --all           # 启动所有子服务
  %(prog)s start --with-gateway  # 启动所有服务（包括网关）
  %(prog)s start embedding       # 启动单个服务
  %(prog)s stop --all            # 停止所有服务
  %(prog)s stop embedding        # 停止单个服务
  %(prog)s restart embedding     # 重启服务
  %(prog)s status                # 查看服务状态
        """
    )

    subparsers = parser.add_subparsers(dest='command', help='命令')

    # start 命令
    start_parser = subparsers.add_parser('start', help='启动服务')
    start_parser.add_argument('service', nargs='?', help='服务名称 (embedding/asr/reranker/mineru/gateway)')
    start_parser.add_argument('--all', action='store_true', help='启动所有子服务')
    start_parser.add_argument('--with-gateway', action='store_true', help='启动所有服务（包括网关）')

    # stop 命令
    stop_parser = subparsers.add_parser('stop', help='停止服务')
    stop_parser.add_argument('service', nargs='?', help='服务名称')
    stop_parser.add_argument('--all', action='store_true', help='停止所有服务')

    # restart 命令
    restart_parser = subparsers.add_parser('restart', help='重启服务')
    restart_parser.add_argument('service', help='服务名称')

    # status 命令
    status_parser = subparsers.add_parser('status', help='查看服务状态')

    args = parser.parse_args()

    if args.command == 'start':
        if args.all:
            start_all(with_gateway=False)
        elif args.with_gateway:
            start_all(with_gateway=True)
        elif args.service:
            start_service(args.service)
        else:
            start_all(with_gateway=False)

    elif args.command == 'stop':
        if args.all:
            stop_all()
        elif args.service:
            stop_service(args.service)
        else:
            stop_all()

    elif args.command == 'restart':
        if args.service:
            restart_service(args.service)
        else:
            print("错误：restart 命令需要指定服务名称")
            sys.exit(1)

    elif args.command == 'status':
        show_status()

    else:
        parser.print_help()
        sys.exit(1)


if __name__ == '__main__':
    main()
