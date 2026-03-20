#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
MinerU API 客户端
将 PDF 文件解析为 Markdown 和图片，并打包成 zip 文件

使用方法:
    python mineru_client.py <input_pdf> <output_zip>
    python mineru_client.py "CX560XAB-2W-BT 产品规格书.pdf" "output.zip"
"""

import os
import sys
import subprocess
import requests
import tempfile
import shutil
import logging
from pathlib import Path
from datetime import datetime

# 配置日志
def setup_logging(service_name: str):
    """配置日志，输出到控制台和文件"""
    logs_dir = os.path.expanduser("~/.cache/pi-llm-server/logs")
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

logger = setup_logging("mineru_client")

# API 服务地址
API_BASE_URL = os.getenv("MINERU_API_URL", "http://127.0.0.1:8094")
API_ENDPOINT = f"{API_BASE_URL}/file_parse"


def check_file_exists(file_path: str) -> tuple:
    """使用 subprocess 检查文件是否存在，避免符号链接编码问题"""
    dir_path = os.path.dirname(file_path)
    filename = os.path.basename(file_path)

    result = subprocess.run(['ls', '-1', dir_path], capture_output=True, text=True)
    files_in_dir = result.stdout.strip().split('\n')

    # 精确匹配
    if filename in files_in_dir:
        return True, os.path.join(dir_path, filename)

    # 模糊匹配：移除空格后比较
    filename_no_space = filename.replace(' ', '').replace('-', '-')
    for f in files_in_dir:
        if f.replace(' ', '') == filename_no_space:
            logger.warning(f"提示：找到相似文件 '{f}' (输入文件名中的空格已被移除)")
            return True, os.path.join(dir_path, f)

    return False, None


def call_mineru_api(input_pdf: str, output_zip: str, backend: str = "pipeline"):
    """
    调用 MinerU API 解析 PDF 文件

    Args:
        input_pdf: 输入的 PDF 文件路径
        output_zip: 输出的 zip 文件路径
        backend: 使用的后端，可选：pipeline, hybrid-auto-engine, vlm-auto-engine 等
    """
    # 检查文件是否存在（使用 subprocess 避免编码问题）
    exists, actual_path = check_file_exists(input_pdf)
    if not exists:
        logger.error(f"文件不存在：{input_pdf}")
        sys.exit(1)

    filename = os.path.basename(actual_path)

    logger.info(f"正在处理文件：{filename}")
    logger.info(f"API 地址：{API_ENDPOINT}")
    logger.info(f"后端：{backend}")

    # 准备请求参数
    files = {
        "files": (filename, open(actual_path, "rb"), "application/pdf")
    }

    data = {
        # 核心参数
        "backend": backend,
        "parse_method": "auto",  # auto/txt/ocr
        "lang_list": "ch",  # 语言：ch/en/korean/japan 等

        # 功能开关
        "formula_enable": "true",   # 启用公式解析
        "table_enable": "true",     # 启用表格解析

        # 返回内容控制
        "return_md": "true",           # 返回 markdown
        "return_images": "true",       # 返回提取的图片
        "return_middle_json": "false", # 返回中间 JSON（可选）
        "return_model_output": "false", # 返回模型输出（可选）
        "return_content_list": "false", # 返回内容列表（可选）

        # 关键：以 zip 格式返回
        "response_format_zip": "true",

        # 页码范围
        "start_page_id": "0",
        "end_page_id": "99999",
    }

    try:
        logger.info("发送请求...")
        logger.info("提示：PDF 解析可能需要几分钟，请耐心等待")
        logger.info("超时时间：1800 秒 (30 分钟)")
        response = requests.post(API_ENDPOINT, files=files, data=data, timeout=1800)

        if response.status_code == 200:
            # 保存 zip 文件
            with open(output_zip, "wb") as f:
                f.write(response.content)
            logger.info(f"成功！输出文件：{output_zip}")

            # 显示 zip 文件内容
            logger.info("ZIP 文件内容:")
            import zipfile
            with zipfile.ZipFile(output_zip, 'r') as zf:
                for name in zf.namelist()[:20]:  # 只显示前 20 个
                    logger.info(f"  {name}")
                if len(zf.namelist()) > 20:
                    logger.info(f"  ... 还有 {len(zf.namelist()) - 20} 个文件")

            logger.info(f"文件大小：{os.path.getsize(output_zip) / 1024 / 1024:.2f} MB")
            return True
        else:
            logger.error(f"请求失败，状态码：{response.status_code}")
            logger.error(f"响应内容：{response.text[:500]}")
            return False

    except requests.exceptions.ConnectionError:
        logger.error(f"无法连接到 API 服务 ({API_BASE_URL})")
        logger.error("请确保已启动 MinerU API 服务：./mineru_server.sh start")
        return False
    except requests.exceptions.Timeout:
        logger.error("请求超时，PDF 文件可能过大或处理时间过长")
        return False
    except Exception as e:
        logger.error(f"错误：{e}")
        return False
    finally:
        if 'files' in locals() and files['files'][1]:
            files['files'][1].close()


def main():
    if len(sys.argv) < 2:
        logger.info(__doc__)
        sys.exit(1)

    input_pdf = sys.argv[1]

    # 自动生成输出文件名
    if len(sys.argv) >= 3:
        output_zip = sys.argv[2]
    else:
        base_name = Path(input_pdf).stem
        output_zip = f"{base_name}_output.zip"

    # 可选：从命令行指定 backend
    backend = sys.argv[3] if len(sys.argv) >= 4 else "pipeline"

    success = call_mineru_api(input_pdf, output_zip, backend)
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
