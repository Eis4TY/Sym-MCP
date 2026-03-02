from __future__ import annotations

import asyncio
import os
import time

import pytest

from sym_mcp.config import load_settings
from sym_mcp.executor.pool import WorkerPool


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = max(0, min(len(ordered) - 1, int(round((p / 100.0) * (len(ordered) - 1)))))
    return ordered[idx]


@pytest.mark.asyncio
@pytest.mark.skipif(os.getenv("SYMMCP_RUN_PERF") != "1", reason="set SYMMCP_RUN_PERF=1 to run perf guardrail test")
async def test_worker_pool_perf_guardrails() -> None:
    settings = load_settings()
    total = int(os.getenv("SYMMCP_PERF_TOTAL", "120"))
    concurrency = int(os.getenv("SYMMCP_PERF_CONCURRENCY", "24"))
    p95_limit_ms = float(os.getenv("SYMMCP_PERF_P95_MS_MAX", "800"))
    p99_limit_ms = float(os.getenv("SYMMCP_PERF_P99_MS_MAX", "1200"))
    timeout_rate_max = float(os.getenv("SYMMCP_PERF_TIMEOUT_RATE_MAX", "0.02"))
    reject_rate_max = float(os.getenv("SYMMCP_PERF_REJECT_RATE_MAX", "0.02"))

    pool = WorkerPool(
        size=settings.pool_size,
        exec_timeout_sec=settings.exec_timeout_sec,
        queue_wait_sec=settings.queue_wait_sec,
        memory_limit_mb=settings.memory_limit_mb,
    )
    await pool.start()

    durations: list[float] = []
    sem = asyncio.Semaphore(concurrency)

    async def one_call() -> None:
        async with sem:
            start = time.perf_counter()
            result = await pool.exec("print(2+2)")
            if not result.get("success", False):
                raise AssertionError(f"worker returned failure in perf test: {result}")
            durations.append((time.perf_counter() - start) * 1000)

    try:
        await asyncio.gather(*(one_call() for _ in range(total)))
    finally:
        await pool.close()

    p95 = _percentile(durations, 95)
    p99 = _percentile(durations, 99)
    timeout_rate = pool.timeout_count / total if total else 0.0
    reject_rate = pool.reject_count / total if total else 0.0

    assert p95 <= p95_limit_ms, f"p95={p95:.2f}ms exceeds limit={p95_limit_ms:.2f}ms"
    assert p99 <= p99_limit_ms, f"p99={p99:.2f}ms exceeds limit={p99_limit_ms:.2f}ms"
    assert timeout_rate <= timeout_rate_max, f"timeout_rate={timeout_rate:.4f} exceeds {timeout_rate_max:.4f}"
    assert reject_rate <= reject_rate_max, f"reject_rate={reject_rate:.4f} exceeds {reject_rate_max:.4f}"
