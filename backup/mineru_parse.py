#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MinerU API 一键调用脚本
自动启动 API 服务并调用，完成后关闭服务

使用方法:
    ./mineru_parse.py <PDF 文件> [输出 ZIP 文件] [backend]

示例:
    ./mineru_parse.py "CX560XAB-2W-BT 产品规格书.pdf"
    ./mineru_parse.py "CX560XAB-2W-BT 产品规格书.pdf" output.zip pipeline
"""

import os
import sys
import subprocess
import time
import signal
import atexit
import logging
from pathlib import Path
from datetime import datetime

# 配置日志
def setup_logging(service_name: str):
    """配置日志，输出到控制台和文件"""
    script_dir = os.path.dirname(os.path.abspath(__file__))
    logs_dir = os.path.join(script_dir, "logs")
    os.makedirs(logs_dir, exist_ok=True)

    log_file = os.path.join(logs_dir, f"{service_name}.log")

    # 创建 logger
    logger = logging.getLogger()
    logger.setLevel(logging.INFO)

    # 清除已有的 handlers
    logger.handlers = []

    # 创建 formatter
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    # 控制台 handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件 handler
    file_handler = logging.FileHandler(log_file, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger

logger = setup_logging("mineru_parse")

# 配置
API_HOST = "127.0.0.1"
API_PORT = "8094"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PID_FILE = os.path.join(BASE_DIR, ".mineru_api.pid")

# 颜色输出
class Colors:
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    RED = '\033[91m'
    END = '\033[0m'

def print_info(msg):
    logger.info(msg)
    print(f"{Colors.GREEN}[INFO]{Colors.END} {msg}")

def print_warn(msg):
    logger.warning(msg)
    print(f"{Colors.YELLOW}[WARN]{Colors.END} {msg}")

def print_error(msg):
    logger.error(msg)
    print(f"{Colors.RED}[ERROR]{Colors.END} {msg}")

# 清理函数
def cleanup():
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, 'r') as f:
                pid = int(f.read().strip())
            os.kill(pid, signal.SIGTERM)
            print_info("已停止 MinerU API 服务")
        except (ValueError, ProcessLookupError, FileNotFoundError):
            pass
        finally:
            os.remove(PID_FILE)

def find_actual_file(file_path):
    """查找实际文件（处理符号链接和编码问题）"""
    dir_path = os.path.dirname(os.path.abspath(file_path))
    filename = os.path.basename(file_path)

    result = subprocess.run(['ls', '-1', dir_path], capture_output=True, text=True)
    files = result.stdout.strip().split('\n')

    # 精确匹配
    if filename in files:
        return os.path.join(dir_path, filename)

    # 模糊匹配（移除空格）
    filename_no_space = filename.replace(' ', '')
    for f in files:
        if f.replace(' ', '') == filename_no_space:
            print_warn(f"使用文件 '{f}' 替代 '{filename}'")
            return os.path.join(dir_path, f)

    return None

def start_api_server():
    """启动 API 服务"""
    if os.path.exists(PID_FILE):
        try:
            with open(PID_FILE, 'r') as f:
                pid = int(f.read().strip())
            os.kill(pid, 0)  # 检查进程是否存在
            logger.info("MinerU API 已在运行")
            print_info("MinerU API 已在运行")
            return True
        except (ValueError, ProcessLookupError, FileNotFoundError):
            os.remove(PID_FILE)

    logger.info("启动 MinerU API 服务...")
    log_file = os.path.join(BASE_DIR, "logs/mineru.log")

    cmd = [
        "/home/tiger/anaconda3/envs/mineru/bin/mineru-api",
        "--host", API_HOST,
        "--port", API_PORT,
        "--vram", "9000"
    ]

    with open(log_file, 'a') as log:
        proc = subprocess.Popen(cmd, stdout=log, stderr=log, start_new_session=True)

    with open(PID_FILE, 'w') as f:
        f.write(str(proc.pid))

    time.sleep(3)

    try:
        os.kill(proc.pid, 0)
        logger.info(f"API 服务已启动 (PID: {proc.pid})")
        print_info(f"API 服务已启动 (PID: {proc.pid})")
        print_info(f"文档地址：http://{API_HOST}:{API_PORT}/docs")
        return True
    except ProcessLookupError:
        logger.error("API 服务启动失败")
        print_error("API 服务启动失败")
        return False

def call_api(input_pdf, output_zip, backend="pipeline"):
    """调用 API 处理 PDF"""
    actual_path = find_actual_file(input_pdf)
    if not actual_path:
        logger.error(f"文件不存在：{input_pdf}")
        print_error(f"文件不存在：{input_pdf}")
        return False

    filename = os.path.basename(actual_path)
    logger.info(f"处理文件：{filename}")
    print_info(f"处理文件：{filename}")

    # 构建 Python 脚本调用 API
    script = os.path.join(BASE_DIR, "mineru_api_call.py")
    cmd = [
        "/home/tiger/anaconda3/envs/mineru/bin/python3",
        script,
        actual_path,
        output_zip,
        backend
    ]

    result = subprocess.run(cmd, capture_output=False)
    return result.returncode == 0

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(1)

    input_pdf = sys.argv[1]
    output_zip = sys.argv[2] if len(sys.argv) >= 3 else Path(input_pdf).stem + "_output.zip"
    backend = sys.argv[3] if len(sys.argv) >= 4 else "pipeline"

    # 注册清理函数
    atexit.register(cleanup)

    # 启动 API 服务
    if not start_api_server():
        sys.exit(1)

    # 调用 API
    logger.info(f"使用后端：{backend}")
    print_info(f"使用后端：{backend}")
    success = call_api(input_pdf, output_zip, backend)

    if success:
        logger.info(f"完成！输出文件：{output_zip}")
        print_info(f"完成！输出文件：{output_zip}")
    else:
        logger.error("处理失败")
        print_error("处理失败")

    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
