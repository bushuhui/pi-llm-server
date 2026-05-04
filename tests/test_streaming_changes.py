"""
测试流式处理和临时文件相关修改

验证:
1. ASR transcribe_audio 使用临时文件且正常清理
2. MinerU parse_pdf_stream 使用 StreamingResponse
3. Server 启动时清理残留临时目录（只删超过1小时的）
4. 守护进程 gateway 监控配置正确加载
"""
import asyncio
import os
import shutil
import tempfile
import time
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, mock_open

import pytest
from fastapi import UploadFile


# ============ ASR 流式测试 ============

class TestASRStreaming:
    """ASR 流式落盘测试"""

    @pytest.fixture
    def asr_service(self):
        from pi_llm_server.config import ServiceConfig
        from pi_llm_server.services.asr import ASRService

        config = ServiceConfig(
            base_url="http://localhost:8092",
            timeout_seconds=300,
            max_retries=1,
        )
        return ASRService(config=config)

    @pytest.mark.asyncio
    async def test_transcribe_audio_uses_temp_file(self, asr_service):
        """验证 ASR 上传时使用临时文件，且请求结束后清理"""
        # 模拟 UploadFile
        fake_content = b"fake audio data" * 100
        upload_file = UploadFile(
            filename="test.wav",
            file=BytesIO(fake_content),
        )

        # mock client 返回成功响应
        mock_response = MagicMock()
        mock_response.json.return_value = {"text": "hello world"}
        mock_response.raise_for_status = MagicMock()
        asr_service.client_long_timeout = MagicMock()
        asr_service.client_long_timeout.post = AsyncMock(return_value=mock_response)

        # 记录创建过的临时目录
        created_dirs = []
        original_mkdtemp = tempfile.mkdtemp

        def tracking_mkdtemp(*args, **kwargs):
            d = original_mkdtemp(*args, **kwargs)
            created_dirs.append(d)
            return d

        with patch("tempfile.mkdtemp", side_effect=tracking_mkdtemp):
            result = await asr_service.transcribe_audio(upload_file, model="test-model")

        assert result == "hello world"

        # 验证临时目录被创建且已清理
        assert len(created_dirs) == 1
        assert not os.path.exists(created_dirs[0]), "临时目录应在请求结束后被清理"

    @pytest.mark.asyncio
    async def test_transcribe_audio_cleanup_on_error(self, asr_service):
        """验证 ASR 请求失败时临时文件仍被清理"""
        fake_content = b"fake audio data" * 100
        upload_file = UploadFile(
            filename="test.wav",
            file=BytesIO(fake_content),
        )

        # mock client 抛出异常
        import httpx
        asr_service.client_long_timeout = MagicMock()
        asr_service.client_long_timeout.post = AsyncMock(
            side_effect=httpx.ConnectError("connection failed")
        )

        created_dirs = []
        original_mkdtemp = tempfile.mkdtemp

        def tracking_mkdtemp(*args, **kwargs):
            d = original_mkdtemp(*args, **kwargs)
            created_dirs.append(d)
            return d

        with patch("tempfile.mkdtemp", side_effect=tracking_mkdtemp):
            from fastapi import HTTPException
            with pytest.raises(HTTPException):
                await asr_service.transcribe_audio(upload_file)

        # 即使失败，临时目录也应被清理
        assert len(created_dirs) == 1
        assert not os.path.exists(created_dirs[0]), "异常时临时目录也应被清理"


# ============ MinerU 流式测试 ============

class TestMinerUStreaming:
    """MinerU 流式处理测试"""

    @pytest.fixture
    def mineru_service(self):
        from pi_llm_server.config import ServiceConfig
        from pi_llm_server.services.mineru import MinerUService

        config = ServiceConfig(
            base_url="http://localhost:8094",
            timeout_seconds=600,
            max_retries=1,
        )
        return MinerUService(config=config)

    @pytest.mark.asyncio
    async def test_parse_pdf_stream_returns_streaming_response(self, mineru_service):
        """验证 parse_pdf_stream 返回 StreamingResponse"""
        from fastapi.responses import StreamingResponse

        fake_content = b"%PDF-1.4 fake pdf content" * 100
        upload_file = UploadFile(
            filename="test.pdf",
            file=BytesIO(fake_content),
        )

        # mock httpx stream: 返回支持 async with 的对象
        mock_response = MagicMock()
        mock_response.aiter_bytes = AsyncMock(return_value=async_iter([b"chunk1", b"chunk2"]))
        mock_response.raise_for_status = MagicMock()

        async_cm = MagicMock()
        async_cm.__aenter__ = AsyncMock(return_value=mock_response)
        async_cm.__aexit__ = AsyncMock(return_value=None)
        mineru_service.client.stream = MagicMock(return_value=async_cm)

        result = await mineru_service.parse_pdf_stream(upload_file)

        assert isinstance(result, StreamingResponse)
        assert result.media_type == "application/zip"

    @pytest.mark.asyncio
    async def test_parse_pdf_stream_creates_temp_dir(self, mineru_service):
        """验证 parse_pdf_stream 创建临时目录并在流消费后清理"""
        from fastapi.responses import StreamingResponse

        fake_content = b"%PDF-1.4 fake pdf content" * 100
        upload_file = UploadFile(
            filename="test.pdf",
            file=BytesIO(fake_content),
        )

        mock_response = MagicMock()
        mock_response.aiter_bytes = MagicMock(return_value=async_iter([b"chunk1"]))
        mock_response.raise_for_status = MagicMock()

        async_cm = MagicMock()
        async_cm.__aenter__ = AsyncMock(return_value=mock_response)
        async_cm.__aexit__ = AsyncMock(return_value=None)
        mineru_service.client.stream = MagicMock(return_value=async_cm)

        created_dirs = []
        original_mkdtemp = tempfile.mkdtemp

        def tracking_mkdtemp(*args, **kwargs):
            d = original_mkdtemp(*args, **kwargs)
            created_dirs.append(d)
            return d

        with patch("tempfile.mkdtemp", side_effect=tracking_mkdtemp):
            result = await mineru_service.parse_pdf_stream(upload_file)

        assert isinstance(result, StreamingResponse)
        assert len(created_dirs) == 1
        # 消费完 generator 后目录会被清理
        body = b""
        async for chunk in result.body_iterator:
            body += chunk
        assert not os.path.exists(created_dirs[0]), "StreamingResponse 消费完后临时目录应被清理"

    @pytest.mark.asyncio
    async def test_encrypted_pdf_rejected(self, mineru_service):
        """验证加密 PDF 返回 400 错误"""
        from fastapi import HTTPException
        from unittest.mock import patch

        fake_content = b"%PDF-1.4 fake pdf content" * 100
        upload_file = UploadFile(
            filename="test.pdf",
            file=BytesIO(fake_content),
        )

        with patch(
            "pi_llm_server.services.mineru._check_pdf_encrypted", return_value=True
        ):
            with pytest.raises(HTTPException) as exc_info:
                await mineru_service.parse_pdf_stream(upload_file)

        assert exc_info.value.status_code == 400
        assert "加密" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_large_pdf_batch_processing(self, mineru_service):
        """验证大文件触发分批处理路径"""
        from fastapi.responses import StreamingResponse
        from unittest.mock import patch, AsyncMock
        import zipfile

        fake_content = b"%PDF-1.4 fake pdf content" * 100
        upload_file = UploadFile(
            filename="test.pdf",
            file=BytesIO(fake_content),
        )

        def fake_merge(zip_paths, output_zip_path, output_stem):
            with zipfile.ZipFile(output_zip_path, "w") as zf:
                zf.writestr(f"{output_stem}/{output_stem}.md", "merged content")

        with patch("pi_llm_server.services.mineru._get_pdf_page_count", return_value=100):
            with patch(
                "pi_llm_server.services.mineru._split_pdf_into_chunks"
            ) as mock_split:
                mock_split.return_value = [
                    "/tmp/chunk_0_50.pdf",
                    "/tmp/chunk_50_100.pdf",
                ]
                with patch.object(
                    mineru_service, "_download_mineru_result", new_callable=AsyncMock
                ) as mock_download:
                    with patch(
                        "pi_llm_server.services.mineru._merge_mineru_zip_results",
                        side_effect=fake_merge,
                    ) as mock_merge:
                        result = await mineru_service.parse_pdf_stream(upload_file)

                        assert isinstance(result, StreamingResponse)

                        # 消费完生成器，验证下载和合并都被调用
                        body = b""
                        async for chunk in result.body_iterator:
                            body += chunk

                        # _split_pdf_into_chunks 在子线程中执行，mock.called 不可靠
                        # 通过 download 调用次数间接验证拆分发生了
                        assert mock_download.call_count == 2
                        mock_merge.assert_called_once()
                        assert len(body) > 0


# ============ Server 临时清理测试 ============

class TestServerTempCleanup:
    """Server 启动时残留临时目录清理测试"""

    def test_cleanup_old_directories(self):
        """验证超过1小时的残留目录被清理"""
        from pi_llm_server.server import _cleanup_service_temp_residuals

        tmp = tempfile.gettempdir()
        old_dir = tempfile.mkdtemp(prefix="mineru_", dir=tmp)
        new_dir = tempfile.mkdtemp(prefix="mineru_", dir=tmp)
        old_asr_dir = tempfile.mkdtemp(prefix="asr_", dir=tmp)
        other_dir = tempfile.mkdtemp(prefix="other_", dir=tmp)

        try:
            # 把 old_dir 和 old_asr_dir 的修改时间设为2小时前
            old_time = time.time() - 7200
            os.utime(old_dir, (old_time, old_time))
            os.utime(old_asr_dir, (old_time, old_time))

            # new_dir 保持当前时间

            _cleanup_service_temp_residuals()

            assert not os.path.exists(old_dir), "超过1小时的 mineru_ 目录应被清理"
            assert not os.path.exists(old_asr_dir), "超过1小时的 asr_ 目录应被清理"
            assert os.path.exists(new_dir), "新创建的 mineru_ 目录不应被清理"
            assert os.path.exists(other_dir), "非 mineru_/asr_ 前缀的目录不应被清理"
        finally:
            # 确保测试后清理
            for d in [old_dir, new_dir, old_asr_dir, other_dir]:
                if os.path.exists(d):
                    shutil.rmtree(d, ignore_errors=True)

    def test_cleanup_ignores_files(self):
        """验证不删除同名普通文件"""
        from pi_llm_server.server import _cleanup_service_temp_residuals

        tmp = tempfile.gettempdir()
        # 创建一个普通文件（不是目录）
        fake_file = os.path.join(tmp, "mineru_should_not_touch")
        Path(fake_file).touch()

        try:
            old_time = time.time() - 7200
            os.utime(fake_file, (old_time, old_time))

            _cleanup_service_temp_residuals()

            assert os.path.exists(fake_file), "普通文件不应被清理"
        finally:
            if os.path.exists(fake_file):
                os.remove(fake_file)


# ============ 守护进程 Gateway 测试 ============

class TestDaemonGateway:
    """守护进程 gateway 监控配置测试"""

    def test_service_ports_includes_gateway(self):
        """验证 SERVICE_PORTS 包含 gateway"""
        from pi_llm_server.launcher.service_daemon import SERVICE_PORTS
        assert "gateway" in SERVICE_PORTS
        assert SERVICE_PORTS["gateway"] == 8090

    def test_load_service_configs_includes_gateway(self):
        """验证 _load_service_configs 加载 gateway"""
        from pi_llm_server.launcher.service_daemon import ServiceDaemon

        mock_config = {
            "server": {"port": 8090},
            "services": {
                "embedding": {"enabled": True, "base_url": "http://localhost:8091"},
                "gateway": {"enabled": True},
            },
        }

        daemon = ServiceDaemon(config=mock_config)
        assert "gateway" in daemon.service_states
        assert daemon.service_states["gateway"].name == "gateway"

    def test_get_service_port_for_gateway(self):
        """验证 _get_service_port 对 gateway 返回配置端口"""
        from pi_llm_server.launcher.service_daemon import ServiceDaemon

        mock_config = {"server": {"port": 9000}}
        daemon = ServiceDaemon(config=mock_config)
        port = daemon._get_service_port("gateway")
        assert port == 9000

    def test_check_service_health_skips_inference_for_gateway(self):
        """验证 gateway 跳过推理检测"""
        from pi_llm_server.launcher.service_daemon import ServiceDaemon

        mock_config = {"server": {"port": 8090}}
        daemon = ServiceDaemon(config=mock_config)

        # mock HTTP 检测为成功
        daemon.check_http_health = AsyncMock(return_value=True)
        # mock 各推理检测方法
        daemon.check_embedding_inference = AsyncMock(return_value=True)
        daemon.check_asr_inference = AsyncMock(return_value=True)
        daemon.check_reranker_inference = AsyncMock(return_value=True)
        daemon.check_mineru_inference = AsyncMock(return_value=True)

        healthy = asyncio.run(daemon.check_service_health("gateway"))

        assert healthy is True
        # gateway 不应调用任何推理检测
        daemon.check_embedding_inference.assert_not_called()
        daemon.check_asr_inference.assert_not_called()
        daemon.check_reranker_inference.assert_not_called()
        daemon.check_mineru_inference.assert_not_called()


def test_convert_to_pdf_file_passes_timeout():
    """验证 convert_to_pdf_file 正确传递超时参数"""
    import asyncio
    from unittest.mock import patch
    from pi_llm_server.services.mineru import convert_to_pdf_file, _convert_to_pdf_sync

    async def _test():
        with patch(
            "pi_llm_server.services.mineru.asyncio.to_thread"
        ) as mock_to_thread:
            mock_to_thread.return_value = "/tmp/output.pdf"
            result = await convert_to_pdf_file(
                "/tmp/input.docx", "/tmp/out", "test.docx", timeout_seconds=900
            )
            mock_to_thread.assert_called_once_with(
                _convert_to_pdf_sync,
                "/tmp/input.docx",
                "/tmp/out",
                "test.docx",
                900,
            )
            assert result == "/tmp/output.pdf"

    asyncio.run(_test())


# ============ 辅助函数 ============

async def async_iter(items):
    """辅助：将列表转为异步迭代器"""
    for item in items:
        yield item
