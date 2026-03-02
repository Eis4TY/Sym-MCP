import asyncio
import sys

import pytest

from sym_mcp.executor.pool import WorkerPool, WorkerPoolError


@pytest.mark.asyncio
async def test_pool_exec_success() -> None:
    pool = WorkerPool(size=1, exec_timeout_sec=2.0, queue_wait_sec=1.0, memory_limit_mb=128)
    await pool.start()
    try:
        result = await pool.exec("print(1+2)")
        assert result["ok"] is True
        assert result["success"] is True
        assert result["stdout"].strip() == "3"
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_pool_timeout_and_rebuild() -> None:
    pool = WorkerPool(size=1, exec_timeout_sec=1.0, queue_wait_sec=1.0, memory_limit_mb=128)
    await pool.start()
    try:
        with pytest.raises(Exception):
            await pool.exec("while True:\n    pass")
        await asyncio.sleep(0.2)
        result = await pool.exec("print(42)")
        assert result["success"] is True
        assert result["stdout"].strip() == "42"
        assert pool.rebuild_count >= 1
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_pool_memory_limit() -> None:
    pool = WorkerPool(size=1, exec_timeout_sec=2.0, queue_wait_sec=1.0, memory_limit_mb=64)
    await pool.start()
    try:
        result = await pool.exec("a = 'x' * (200 * 1024 * 1024)\nprint(len(a))")
        if sys.platform.startswith("linux"):
            assert result["success"] is False
        else:
            # macOS 下 RLIMIT_AS/RLIMIT_DATA 语义不稳定，允许该用例仅做兼容性验证。
            assert "success" in result
    finally:
        await pool.close()


@pytest.mark.asyncio
async def test_pool_queue_wait_timeout() -> None:
    pool = WorkerPool(size=1, exec_timeout_sec=2.0, queue_wait_sec=0.1, memory_limit_mb=128)
    await pool.start()
    try:
        busy_task = asyncio.create_task(pool.exec("while True:\n    pass"))
        await asyncio.sleep(0.05)
        with pytest.raises(WorkerPoolError, match="执行排队超时"):
            await pool.exec("print(1)")
        with pytest.raises(WorkerPoolError, match="超时|异常"):
            await busy_task
        assert pool.reject_count >= 1
    finally:
        await pool.close()
