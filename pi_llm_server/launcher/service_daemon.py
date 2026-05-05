#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PI-LLM-Server 服务守护进程

独立进程监控器，定期检查各子服务的健康状态，
使用推理检测验证服务真正可用，而非仅 HTTP 端点响应。

如果检测连续失败超过阈值，自动重启服务。

启动方式:
    # 通过 service_manager 启动
    pi-llm-server services start daemon

    # 或直接运行
    python service_daemon.py

    # 或随 start-all 一并启动
    pi-llm-server start-all
"""

import os
import sys
import time
import signal
import logging
import asyncio
import argparse
import subprocess
import struct
import io
import socket
from pathlib import Path
from datetime import datetime
from typing import Dict, Optional, Any

import httpx
import yaml

# ==================== 日志配置 ====================

LOG_DIR = Path.home() / '.cache' / 'pi-llm-server' / 'logs'
PID_DIR = Path.home() / '.cache' / 'pi-llm-server' / 'pids'
LOG_DIR.mkdir(parents=True, exist_ok=True)
PID_DIR.mkdir(parents=True, exist_ok=True)

LOG_FILE = LOG_DIR / 'daemon.log'
PID_FILE = PID_DIR / 'daemon.pid'


def setup_logging():
    """配置日志"""
    logger = logging.getLogger('daemon')
    logger.setLevel(logging.INFO)

    # 清除已有 handlers
    logger.handlers = []

    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(message)s'
    )

    # 控制台输出
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    # 文件输出
    file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)

    return logger


logger = setup_logging()

# ==================== 配置 ====================

DEFAULT_CONFIG_DIR = Path.home() / '.config' / 'pi-llm-server'
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / 'config.yaml'

# 默认监控配置
DEFAULT_DAEMON_CONFIG = {
    'check_interval': 30,       # 检查间隔（秒）
    'http_timeout': 10,         # HTTP 检查超时（秒）
    'inference_timeout': 5,     # 推理检测超时（秒）
    'unhealthy_threshold': 3,   # 连续失败阈值
    'restart_cooldown': 120,    # 重启后冷却时间（秒）
    'max_restart_attempts': 3,  # 单次最多重启尝试次数
}

# 服务级别默认冷却时间（根据启动时间估算）
SERVICE_COOLDOWN_DEFAULTS = {
    'embedding': 60,    # 模型加载快
    'asr': 180,         # GPU模型加载慢，需要3分钟
    'reranker': 60,     # CPU模型加载较快
    'mineru': 120,      # PDF解析服务启动需要时间
    'gateway': 30,      # 网关无模型，启动快
}

# 子服务端口配置（从配置文件动态读取）
SERVICE_PORTS = {
    'embedding': 8091,
    'asr': 8092,
    'reranker': 8093,
    'mineru': 8094,
    'gateway': 8090,
}

# 推理检测超时配置（服务级别）
INFERENCE_TIMEOUT_DEFAULTS = {
    'embedding': 3,     # 短文本推理快
    'asr': 10,          # 音频转写需要时间
    'reranker': 3,      # 短查询推理快
    'mineru': 60,       # 图片解析需要时间（模型初始化 ~27s + 处理）
    'gateway': 5,       # 仅做 HTTP 检测，无推理
}

# HTTP 检测超时配置（服务级别）
HTTP_TIMEOUT_DEFAULTS = {
    'embedding': 10,
    'asr': 10,
    'reranker': 10,
    'mineru': 30,       # MinerU 处理大文件时可能无法及时响应 /openapi.json
    'gateway': 10,
}

# 连续不健康阈值配置（服务级别）
UNHEALTHY_THRESHOLD_DEFAULTS = {
    'embedding': 3,
    'asr': 3,
    'reranker': 3,
    'mineru': 3,
    'gateway': 3,
}

# MinerU 连续超时专用阈值（更高，避免大文件处理时误杀）
MINERU_TIMEOUT_THRESHOLD = 30


# ==================== 测试数据生成 ====================

def generate_test_audio() -> bytes:
    """
    生成测试音频 WAV 文件

    生成一个 1秒 16kHz 单声道 16bit 的静音 WAV 文件
    手动构建 WAV 格式，不需要外部依赖

    Returns:
        bytes: WAV 文件字节流
    """
    # WAV 参数
    sample_rate = 16000  # 采样率
    num_channels = 1     # 单声道
    bits_per_sample = 16 # 16bit
    duration_seconds = 1 # 1秒

    num_samples = sample_rate * duration_seconds
    byte_rate = sample_rate * num_channels * bits_per_sample // 8
    block_align = num_channels * bits_per_sample // 8
    data_size = num_samples * block_align

    # 静音数据（全零）
    samples = bytes(num_samples * 2)  # 每个 sample 2 bytes

    # 构建 WAV header
    wav_header = struct.pack(
        '<4sI4s4sIHHIIHH4sI',
        b'RIFF',           # ChunkID
        36 + data_size,    # ChunkSize (文件大小 - 8)
        b'WAVE',           # Format
        b'fmt ',           # Subchunk1ID
        16,                # Subchunk1Size (PCM 固定为 16)
        1,                 # AudioFormat (PCM = 1)
        num_channels,      # NumChannels
        sample_rate,       # SampleRate
        byte_rate,         # ByteRate
        block_align,       # BlockAlign
        bits_per_sample,   # BitsPerSample
        b'data',           # Subchunk2ID
        data_size,         # Subchunk2Size
    )

    return wav_header + samples


def generate_test_image() -> bytes:
    """
    生成测试图片 PNG 文件

    生成一个 200x50 像素的白底图片，包含 "test" 文字
    使用 PIL 生成

    Returns:
        bytes: PNG 文件字节流
    """
    try:
        from PIL import Image, ImageDraw

        # 创建 200x50 白底图片
        img = Image.new('RGB', (200, 50), color='white')
        draw = ImageDraw.Draw(img)

        # 绘制文字（使用默认字体）
        draw.text((70, 15), "test", fill='black')

        # 保存为 bytes
        buffer = io.BytesIO()
        img.save(buffer, format='PNG')
        return buffer.getvalue()

    except ImportError:
        logger.warning("PIL 未安装，使用预置的测试图片")
        # 返回一个最小化的 PNG（1x1 白色像素）
        return (
            b'\x89PNG\r\n\x1a\n'
            b'\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x02\x00\x00\x00\x90wS\xde'
            b'\x00\x00\x00\x0cIDATx\x9cc\xf8\x0f\x00\x00\x01\x00\x01\x00\x05\x18\xd8N'
            b'\x00\x00\x00\x00IEND\xaeB`\x82'
        )


# ==================== 服务状态 ====================

class ServiceState:
    """服务状态跟踪"""

    def __init__(self, name: str):
        self.name = name
        self.consecutive_failures = 0
        self.consecutive_timeouts = 0
        self.last_check_time: Optional[datetime] = None
        self.last_restart_time: Optional[datetime] = None
        self.restart_attempts = 0
        self.status = 'unknown'
        self.last_check_type: Optional[str] = None

    def record_success(self, check_type: str = 'http'):
        """记录成功检查"""
        self.consecutive_failures = 0
        self.consecutive_timeouts = 0
        self.restart_attempts = 0
        self.status = 'healthy'
        self.last_check_time = datetime.now()
        self.last_check_type = check_type

    def record_failure(self, check_type: str = 'http', failure_reason: str = 'unknown'):
        """记录失败检查"""
        self.consecutive_failures += 1
        if failure_reason == 'timeout':
            self.consecutive_timeouts += 1
        else:
            self.consecutive_timeouts = 0
        self.status = 'unhealthy'
        self.last_check_time = datetime.now()
        self.last_check_type = check_type

    def is_needs_restart(self, threshold: int, cooldown: int, timeout_threshold: int = None) -> bool:
        """是否需要重启"""
        # 如果当前全是超时，使用超时专用阈值（更宽容）
        if timeout_threshold and self.consecutive_timeouts > 0:
            if self.consecutive_timeouts < timeout_threshold:
                return False
        elif self.consecutive_failures < threshold:
            return False

        if self.last_restart_time:
            cooldown_expired = (
                datetime.now() - self.last_restart_time
            ).total_seconds()
            if cooldown_expired < cooldown:
                return False

        return True

    def record_restart(self):
        """记录重启操作"""
        self.last_restart_time = datetime.now()
        self.restart_attempts += 1
        self.consecutive_failures = 0
        self.consecutive_timeouts = 0


# ==================== 守护进程核心 ====================

class ServiceDaemon:
    """服务守护进程"""

    def __init__(self, config: Dict[str, Any] = None):
        """初始化守护进程"""
        self.config = config or {}
        self.running = False
        self._shutdown_event = asyncio.Event()

        # 守护进程配置
        daemon_cfg = self.config.get('daemon', {})
        self.check_interval = daemon_cfg.get('check_interval', DEFAULT_DAEMON_CONFIG['check_interval'])
        self.http_timeout = daemon_cfg.get('http_timeout', DEFAULT_DAEMON_CONFIG['http_timeout'])
        self.inference_timeout = daemon_cfg.get('inference_timeout', DEFAULT_DAEMON_CONFIG['inference_timeout'])
        self.unhealthy_threshold = daemon_cfg.get('unhealthy_threshold', DEFAULT_DAEMON_CONFIG['unhealthy_threshold'])
        self.restart_cooldown = daemon_cfg.get('restart_cooldown', DEFAULT_DAEMON_CONFIG['restart_cooldown'])
        self.max_restart_attempts = daemon_cfg.get('max_restart_attempts', DEFAULT_DAEMON_CONFIG['max_restart_attempts'])

        # HTTP 客户端（用于 HTTP 检测）
        self.http_client = httpx.AsyncClient(timeout=httpx.Timeout(self.http_timeout))

        # 推理检测客户端（更长超时）
        self.inference_client = httpx.AsyncClient(timeout=httpx.Timeout(60))

        # 服务状态跟踪
        self.service_states: Dict[str, ServiceState] = {}

        # 服务配置
        self.service_cooldowns: Dict[str, int] = {}
        self.service_inference_timeout: Dict[str, int] = {}
        self.service_http_timeout: Dict[str, int] = {}
        self.service_unhealthy_threshold: Dict[str, int] = {}

        # 预生成测试数据
        self._test_audio: bytes = generate_test_audio()
        self._test_image: bytes = generate_test_image()

        logger.info(f"预生成测试音频: {len(self._test_audio)} bytes")
        logger.info(f"预生成测试图片: {len(self._test_image)} bytes")

        # 加载配置
        self._load_service_configs()
        self._load_service_ports()

        logger.info(f"守护进程配置: interval={self.check_interval}s, threshold={self.unhealthy_threshold}")

    def _load_service_configs(self):
        """加载服务级别配置"""
        daemon_cfg = self.config.get('daemon', {})
        default_cooldown = daemon_cfg.get('restart_cooldown', DEFAULT_DAEMON_CONFIG['restart_cooldown'])
        default_http_timeout = daemon_cfg.get('http_timeout', DEFAULT_DAEMON_CONFIG['http_timeout'])
        default_threshold = daemon_cfg.get('unhealthy_threshold', DEFAULT_DAEMON_CONFIG['unhealthy_threshold'])
        services_cfg = daemon_cfg.get('services', {})

        for name in ['embedding', 'asr', 'reranker', 'mineru', 'gateway']:
            if services_cfg and name in services_cfg:
                svc_cfg = services_cfg[name]
                cooldown = svc_cfg.get('restart_cooldown', SERVICE_COOLDOWN_DEFAULTS.get(name, default_cooldown))
                inference_timeout = svc_cfg.get('inference_timeout', INFERENCE_TIMEOUT_DEFAULTS.get(name, self.inference_timeout))
                http_timeout = svc_cfg.get('http_timeout', HTTP_TIMEOUT_DEFAULTS.get(name, default_http_timeout))
                threshold = svc_cfg.get('unhealthy_threshold', UNHEALTHY_THRESHOLD_DEFAULTS.get(name, default_threshold))
            else:
                cooldown = SERVICE_COOLDOWN_DEFAULTS.get(name, default_cooldown)
                inference_timeout = INFERENCE_TIMEOUT_DEFAULTS.get(name, self.inference_timeout)
                http_timeout = HTTP_TIMEOUT_DEFAULTS.get(name, default_http_timeout)
                threshold = UNHEALTHY_THRESHOLD_DEFAULTS.get(name, default_threshold)

            self.service_cooldowns[name] = cooldown
            self.service_inference_timeout[name] = inference_timeout
            self.service_http_timeout[name] = http_timeout
            self.service_unhealthy_threshold[name] = threshold
            logger.info(f"{name}: 冷却时间={cooldown}秒, HTTP超时={http_timeout}秒, 推理超时={inference_timeout}秒, 不健康阈值={threshold}次")

    def _load_service_ports(self):
        """从配置文件加载服务端口"""
        services_cfg = self.config.get('services', {})

        for name in ['embedding', 'asr', 'reranker', 'mineru']:
            svc_cfg = services_cfg.get(name, {})
            if svc_cfg.get('enabled', True) and svc_cfg.get('base_url'):
                import re
                match = re.search(r':(\d+)$', svc_cfg['base_url'])
                if match:
                    port = int(match.group(1))
                    self.service_states[name] = ServiceState(name)
                    logger.info(f"监控服务: {name} (端口 {port})")
            elif name in SERVICE_PORTS:
                self.service_states[name] = ServiceState(name)
                logger.info(f"监控服务: {name} (默认端口 {SERVICE_PORTS[name]})")

        # Gateway 监控（端口从 server 配置读取）
        server_cfg = self.config.get('server', {})
        gateway_port = server_cfg.get('port', SERVICE_PORTS.get('gateway', 8090))
        SERVICE_PORTS['gateway'] = gateway_port
        self.service_states['gateway'] = ServiceState('gateway')
        logger.info(f"监控服务: gateway (端口 {gateway_port})")

    def _get_service_port(self, name: str) -> int:
        """获取服务端口"""
        if name == 'gateway':
            server_cfg = self.config.get('server', {})
            return server_cfg.get('port', SERVICE_PORTS.get('gateway', 8090))

        services_cfg = self.config.get('services', {})
        svc_cfg = services_cfg.get(name, {})
        if svc_cfg.get('base_url'):
            import re
            match = re.search(r':(\d+)$', svc_cfg['base_url'])
            if match:
                return int(match.group(1))
        return SERVICE_PORTS.get(name, 8091)

    # ==================== HTTP 基础检测 ====================

    async def _check_port_open(self, port: int, timeout: float = 2.0) -> bool:
        """快速端口探测：检查端口是否开放（不发送 HTTP 请求）"""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection('127.0.0.1', port),
                timeout=timeout
            )
            writer.close()
            await writer.wait_closed()
            return True
        except asyncio.TimeoutError:
            return False
        except OSError:
            return False

    async def check_http_health(self, name: str, port: int, timeout: int = None) -> tuple[bool, str]:
        """HTTP 基础健康检测，返回 (是否成功, 失败原因)"""
        try:
            # MinerU 没有 /health 端点，使用 /openapi.json
            path = '/openapi.json' if name == 'mineru' else '/health'
            url = f"http://127.0.0.1:{port}{path}"
            t = timeout or self.http_timeout
            response = await self.http_client.get(url, timeout=t)
            if response.status_code == 200:
                return True, "ok"
            return False, "http_error"
        except httpx.TimeoutException:
            logger.warning(f"{name} HTTP 检测超时")
            return False, "timeout"
        except httpx.ConnectError:
            logger.warning(f"{name} 无法连接 (端口 {port})")
            return False, "connect_error"
        except Exception as e:
            logger.warning(f"{name} HTTP 检测异常: {e}")
            return False, "error"

    # ==================== 推理检测 ====================

    async def check_embedding_inference(self, port: int, timeout: int) -> bool:
        """Embedding 推理检测"""
        try:
            url = f"http://127.0.0.1:{port}/v1/embeddings"
            payload = {"model": "test", "input": "hello"}
            response = await self.inference_client.post(url, json=payload, timeout=timeout)
            if response.status_code == 200:
                data = response.json()
                if 'data' in data and len(data['data']) > 0:
                    return True
            return False
        except Exception as e:
            logger.warning(f"embedding 推理检测失败: {e}")
            return False

    async def check_asr_inference(self, port: int, timeout: int) -> bool:
        """ASR 推理检测"""
        try:
            url = f"http://127.0.0.1:{port}/v1/audio/transcriptions"
            files = {'file': ('test.wav', self._test_audio, 'audio/wav')}
            data = {'model': 'test'}
            response = await self.inference_client.post(url, files=files, data=data, timeout=timeout)
            if response.status_code == 200:
                result = response.json()
                if 'text' in result:
                    return True
            return False
        except Exception as e:
            logger.warning(f"asr 推理检测失败: {e}")
            return False

    async def check_reranker_inference(self, port: int, timeout: int) -> bool:
        """Reranker 推理检测"""
        try:
            url = f"http://127.0.0.1:{port}/v1/rerank"
            payload = {"model": "test", "query": "test", "documents": ["hello"]}
            response = await self.inference_client.post(url, json=payload, timeout=timeout)
            if response.status_code == 200:
                data = response.json()
                if 'results' in data and len(data['results']) > 0:
                    return True
            return False
        except Exception as e:
            logger.warning(f"reranker 推理检测失败: {e}")
            return False

    async def check_mineru_inference(self, port: int, timeout: int) -> bool:
        """MinerU 推理检测"""
        try:
            url = f"http://127.0.0.1:{port}/file_parse"
            files = {'files': ('test.png', self._test_image, 'image/png')}
            data = {'backend': 'pipeline', 'parse_method': 'auto', 'lang_list': 'ch'}
            response = await self.inference_client.post(url, files=files, data=data, timeout=timeout)
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"mineru 推理检测失败: {e}")
            return False

    # ==================== 综合健康检测 ====================

    async def check_service_health(self, name: str) -> tuple[bool, str]:
        """综合健康检测：先 HTTP 检测，再推理检测。返回 (是否健康, 失败原因)"""
        port = self._get_service_port(name)
        inference_timeout = self.service_inference_timeout.get(name, 5)
        http_timeout = self.service_http_timeout.get(name, self.http_timeout)

        # MinerU 特殊处理：先快速端口探测，区分"进程死了"和"进程在忙"
        if name == 'mineru':
            port_open = await self._check_port_open(port, timeout=2.0)
            if not port_open:
                logger.warning(f"{name} 端口 {port} 未开放，进程可能已退出")
                return False, "connect_error"
            # 端口通说明进程活着，继续 HTTP 检测确认是否能响应请求
            http_ok, failure_reason = await self.check_http_health(name, port, timeout=http_timeout)
            if not http_ok:
                logger.warning(f"{name} HTTP 检测失败({failure_reason})，端口通但无法响应")
                return False, failure_reason
            return True, "ok"

        # Step 1: HTTP 基础检测
        http_ok, failure_reason = await self.check_http_health(name, port, timeout=http_timeout)
        if not http_ok:
            logger.warning(f"{name} HTTP 检测失败({failure_reason})，跳过推理检测")
            return False, failure_reason

        # Gateway 仅做 HTTP /health 检测，不做推理（推理由各子服务自行检测）
        if name == 'gateway':
            return True, "ok"

        # Step 2: 推理检测
        logger.debug(f"{name} HTTP 检测通过，开始推理检测...")

        inference_ok = False
        try:
            if name == 'embedding':
                inference_ok = await self.check_embedding_inference(port, inference_timeout)
            elif name == 'asr':
                inference_ok = await self.check_asr_inference(port, inference_timeout)
            elif name == 'reranker':
                inference_ok = await self.check_reranker_inference(port, inference_timeout)
            else:
                inference_ok = True
        except Exception as e:
            logger.warning(f"{name} 推理检测异常: {e}")
            inference_ok = False

        if inference_ok:
            logger.debug(f"{name} 推理检测通过")
        else:
            logger.warning(f"{name} 推理检测失败")

        return inference_ok, "inference_error" if not inference_ok else "ok"

    # ==================== 服务重启 ====================

    async def restart_service(self, name: str) -> bool:
        """重启服务"""
        logger.info(f"正在重启服务: {name}")

        try:
            if name == 'gateway':
                # Gateway 由 cli 模块管理，单独处理
                from pi_llm_server.cli import stop_gateway, start_gateway_background
                stop_gateway()
                await asyncio.sleep(1)
                success = start_gateway_background()
            else:
                from pi_llm_server.launcher.service_manager import restart_service
                success = restart_service(name, config=self.config)

            if success:
                state = self.service_states.get(name)
                if state:
                    state.record_restart()
                logger.info(f"{name} 重启成功")
                return True
            else:
                logger.error(f"{name} 重启失败")
                return False

        except Exception as e:
            logger.error(f"重启 {name} 时发生异常: {e}")
            return False

    # ==================== 检测循环 ====================

    async def check_all_services(self):
        """检查所有服务健康状态"""
        for name, state in self.service_states.items():
            # 检查是否需要重置重启计数器（长时间不健康后自动重置，避免永久放弃）
            if state.restart_attempts >= self.max_restart_attempts and state.last_restart_time:
                recovery_window = max(self.restart_cooldown * 5, 600)  # 至少 10 分钟
                if (datetime.now() - state.last_restart_time).total_seconds() > recovery_window:
                    logger.info(f"{name} 超过恢复窗口，重置重启计数器")
                    state.restart_attempts = 0
                    state.consecutive_failures = 0
                    state.consecutive_timeouts = 0

            healthy, failure_reason = await self.check_service_health(name)

            if healthy:
                state.record_success('inference')
                logger.info(f"{name} 健康")
            else:
                state.record_failure('inference', failure_reason=failure_reason)
                logger.warning(
                    f"{name} 不健康 (连续失败 {state.consecutive_failures} 次, "
                    f"连续超时 {state.consecutive_timeouts} 次, 原因: {failure_reason})"
                )

                cooldown = self.service_cooldowns.get(name, self.restart_cooldown)
                threshold = self.service_unhealthy_threshold.get(name, self.unhealthy_threshold)

                # MinerU 特殊处理：纯超时使用更高的阈值，避免大文件处理时误杀
                timeout_threshold = None
                if name == 'mineru' and failure_reason == 'timeout':
                    timeout_threshold = MINERU_TIMEOUT_THRESHOLD

                if state.is_needs_restart(threshold, cooldown, timeout_threshold=timeout_threshold):
                    if state.restart_attempts < self.max_restart_attempts:
                        await self.restart_service(name)
                    else:
                        logger.error(
                            f"{name} 已达到最大重启次数 ({self.max_restart_attempts})，"
                            f"将在 {recovery_window}s 后重置计数器再次尝试"
                        )

    async def run(self):
        """主运行循环"""
        logger.info("守护进程启动")
        self.running = True
        PID_FILE.write_text(str(os.getpid()))

        try:
            while self.running and not self._shutdown_event.is_set():
                try:
                    await self.check_all_services()
                except Exception as e:
                    logger.error(f"检查循环异常: {e}")

                try:
                    await asyncio.wait_for(self._shutdown_event.wait(), timeout=self.check_interval)
                    break
                except asyncio.TimeoutError:
                    pass

        finally:
            await self.http_client.aclose()
            await self.inference_client.aclose()
            logger.info("守护进程停止")

    def shutdown(self):
        """停止守护进程"""
        logger.info("收到停止信号")
        self.running = False
        self._shutdown_event.set()

    def get_status(self) -> Dict:
        """获取守护进程状态"""
        return {
            'running': self.running,
            'check_interval': self.check_interval,
            'services': {
                name: {
                    'status': state.status,
                    'consecutive_failures': state.consecutive_failures,
                    'restart_attempts': state.restart_attempts,
                    'last_check': state.last_check_time.isoformat() if state.last_check_time else None,
                    'last_restart': state.last_restart_time.isoformat() if state.last_restart_time else None,
                    'last_check_type': state.last_check_type,
                }
                for name, state in self.service_states.items()
            }
        }


# ==================== 进程管理函数 ====================

daemon_instance: Optional[ServiceDaemon] = None


def signal_handler(signum, frame):
    """信号处理"""
    logger.info(f"收到信号 {signum}")
    if daemon_instance:
        daemon_instance.shutdown()


def load_config() -> Dict[str, Any]:
    """加载配置文件"""
    if not DEFAULT_CONFIG_FILE.exists():
        logger.warning(f"配置文件不存在: {DEFAULT_CONFIG_FILE}")
        return {}

    try:
        with open(DEFAULT_CONFIG_FILE, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or {}
    except Exception as e:
        logger.error(f"配置文件加载失败: {e}")
        return {}


def is_daemon_running() -> bool:
    """检查守护进程是否运行"""
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            os.kill(pid, 0)
            result = subprocess.run(['ps', '-p', str(pid), '-o', 'args='], capture_output=True, text=True)
            if result.returncode == 0:
                cmd = result.stdout.strip()
                if 'service_daemon.py' in cmd and '--status' not in cmd and '--stop' not in cmd:
                    return True
        except (ValueError, OSError):
            PID_FILE.unlink(missing_ok=True)
    return False


def start_daemon_background(config: Dict[str, Any] = None) -> bool:
    """后台启动守护进程"""
    if is_daemon_running():
        logger.info("守护进程已在运行")
        return True

    config = config or load_config()
    logger.info("正在启动守护进程...")

    with open(LOG_FILE, 'a') as f:
        proc = subprocess.Popen([sys.executable, __file__], stdout=f, stderr=f, start_new_session=True)

    PID_FILE.write_text(str(proc.pid))
    logger.info(f"守护进程已启动 (PID: {proc.pid})")

    time.sleep(2)

    if is_daemon_running():
        logger.info("守护进程启动成功")
        return True
    else:
        logger.error("守护进程启动失败，请查看日志")
        return False


def stop_daemon() -> bool:
    """停止守护进程"""
    if not is_daemon_running():
        logger.info("守护进程未运行")
        return True

    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
            logger.info(f"发送 SIGTERM 到守护进程 (PID: {pid})")
            os.kill(pid, signal.SIGTERM)

            for _ in range(10):
                time.sleep(0.5)
                try:
                    os.kill(pid, 0)
                except OSError:
                    break
            else:
                os.kill(pid, signal.SIGKILL)
                logger.info("发送 SIGKILL 到守护进程")

            PID_FILE.unlink(missing_ok=True)
            logger.info("守护进程已停止")
            return True

        except ProcessLookupError:
            PID_FILE.unlink(missing_ok=True)
            logger.info("守护进程已停止")
            return True
        except Exception as e:
            logger.error(f"停止守护进程失败: {e}")
            return False

    return True


def show_daemon_status():
    """显示守护进程状态"""
    running = is_daemon_running()
    status = "运行中" if running else "已停止"

    pid = None
    if PID_FILE.exists():
        try:
            pid = int(PID_FILE.read_text().strip())
        except ValueError:
            pass

    pid_str = f"(PID: {pid})" if pid else ""
    symbol = "✓" if running else "✗"
    print(f"  {symbol} {'服务守护进程':20s} {status:10s} {pid_str}")


# ==================== 主函数 ====================

def main():
    """主入口"""
    parser = argparse.ArgumentParser(
        description="PI-LLM-Server 服务守护进程",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  python service_daemon.py              # 前台运行
  python service_daemon.py --background # 后台运行
  python service_daemon.py --status     # 查看状态
  python service_daemon.py --stop       # 停止守护进程
        """
    )

    parser.add_argument('--background', '-b', action='store_true', help='后台运行模式')
    parser.add_argument('--stop', action='store_true', help='停止守护进程')
    parser.add_argument('--status', action='store_true', help='查看守护进程状态')
    parser.add_argument('--interval', type=int, default=None, help='检查间隔（秒）')
    parser.add_argument('--threshold', type=int, default=None, help='连续失败阈值')

    args = parser.parse_args()

    if args.status:
        show_daemon_status()
        return

    if args.stop:
        stop_daemon()
        return

    config = load_config()

    if args.interval:
        config.setdefault('daemon', {})['check_interval'] = args.interval
    if args.threshold:
        config.setdefault('daemon', {})['unhealthy_threshold'] = args.threshold

    if args.background:
        start_daemon_background(config)
        return

    global daemon_instance
    daemon_instance = ServiceDaemon(config)

    signal.signal(signal.SIGTERM, signal_handler)
    signal.signal(signal.SIGINT, signal_handler)

    asyncio.run(daemon_instance.run())


if __name__ == '__main__':
    main()