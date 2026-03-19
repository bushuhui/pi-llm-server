"""
队列管理器测试
"""
import pytest
import asyncio
from pi_llm_server.queue_manager import (
    QueueManager,
    ServiceQueue,
    ServiceQueueConfig,
    init_queue_manager,
)


class TestServiceQueue:
    """服务队列测试"""

    @pytest.mark.asyncio
    async def test_queue_process(self):
        """测试队列处理"""
        config = ServiceQueueConfig(max_concurrent=2, max_size=10, timeout_seconds=5)
        queue = ServiceQueue(config)

        async def dummy_task(x):
            await asyncio.sleep(0.1)
            return x * 2

        result = await queue.process_with_queue(dummy_task, 5)
        assert result == 10

    @pytest.mark.asyncio
    async def test_queue_timeout(self):
        """测试队列超时"""
        config = ServiceQueueConfig(max_concurrent=1, max_size=10, timeout_seconds=1)
        queue = ServiceQueue(config)

        async def slow_task():
            await asyncio.sleep(5)
            return "done"

        with pytest.raises(asyncio.TimeoutError):
            await queue.process_with_queue(slow_task)

    @pytest.mark.asyncio
    async def test_queue_status(self):
        """测试队列状态"""
        config = ServiceQueueConfig(max_concurrent=2, max_size=10, timeout_seconds=5)
        queue = ServiceQueue(config)

        status = queue.get_status()
        assert "pending" in status
        assert "processing" in status
        assert "max_concurrent" in status
        assert "max_size" in status


class TestQueueManager:
    """队列管理器测试"""

    def test_add_queue(self):
        """测试添加队列"""
        qm = QueueManager()
        config = ServiceQueueConfig(max_concurrent=2, max_size=10)
        qm.add_queue("test_service", config)

        queue = qm.get_queue("test_service")
        assert queue is not None
        assert queue.config.max_concurrent == 2

    def test_get_nonexistent_queue(self):
        """测试获取不存在的队列"""
        qm = QueueManager()
        queue = qm.get_queue("nonexistent")
        assert queue is None

    @pytest.mark.asyncio
    async def test_process_request(self):
        """测试处理请求"""
        qm = QueueManager()
        config = ServiceQueueConfig(max_concurrent=2, max_size=10, timeout_seconds=5)
        qm.add_queue("test", config)

        async def dummy_task(x):
            return x + 1

        result = await qm.process_request("test", dummy_task, 10)
        assert result == 11

    def test_queue_status(self):
        """测试队列状态"""
        qm = QueueManager()
        qm.add_queue("test1", ServiceQueueConfig())
        qm.add_queue("test2", ServiceQueueConfig())

        status = qm.get_status()
        assert "test1" in status
        assert "test2" in status


class TestInitQueueManager:
    """初始化队列管理器测试"""

    def test_init_queue_manager(self):
        """测试初始化队列管理器"""
        configs = {
            "embedding": ServiceQueueConfig(max_concurrent=4),
            "asr": ServiceQueueConfig(max_concurrent=1),
        }
        qm = init_queue_manager(configs)

        assert qm.get_queue("embedding") is not None
        assert qm.get_queue("asr") is not None
        assert qm.get_queue("embedding").config.max_concurrent == 4
        assert qm.get_queue("asr").config.max_concurrent == 1
