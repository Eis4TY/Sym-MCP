from __future__ import annotations

import argparse
import asyncio
import statistics
import time
from typing import Any

from sym_mcp.config import load_settings
from sym_mcp.executor.pool import WorkerPool


def _percentile(durations: list[float], p: float) -> float:
    if not durations:
        return 0.0
    ordered = sorted(durations)
    idx = max(0, min(len(ordered) - 1, int(round((p / 100.0) * (len(ordered) - 1)))))
    return ordered[idx]


async def benchmark_stats(concurrency: int, total: int) -> dict[str, Any]:
    settings = load_settings()
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
                raise RuntimeError(f"benchmark exec failed: {result}")
            durations.append((time.perf_counter() - start) * 1000)

    try:
        await asyncio.gather(*(one_call() for _ in range(total)))
    finally:
        await pool.close()

    p50 = _percentile(durations, 50)
    p95 = _percentile(durations, 95)
    p99 = _percentile(durations, 99)
    avg = statistics.mean(durations) if durations else 0.0
    timeout_rate = (pool.timeout_count / total) if total > 0 else 0.0
    reject_rate = (pool.reject_count / total) if total > 0 else 0.0
    return {
        "total": total,
        "concurrency": concurrency,
        "latency_ms": {"avg": avg, "p50": p50, "p95": p95, "p99": p99},
        "timeouts": pool.timeout_count,
        "rejects": pool.reject_count,
        "rebuilds": pool.rebuild_count,
        "rates": {"timeout": timeout_rate, "reject": reject_rate},
    }


async def run_benchmark(concurrency: int, total: int) -> None:
    stats = await benchmark_stats(concurrency=concurrency, total=total)
    print(f"total={total}, concurrency={concurrency}")
    print(
        "latency_ms "
        f"avg={stats['latency_ms']['avg']:.2f}, "
        f"p50={stats['latency_ms']['p50']:.2f}, "
        f"p95={stats['latency_ms']['p95']:.2f}, "
        f"p99={stats['latency_ms']['p99']:.2f}"
    )
    print(
        "pool "
        f"timeouts={stats['timeouts']}, "
        f"rejects={stats['rejects']}, "
        f"rebuilds={stats['rebuilds']}"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Worker pool benchmark")
    parser.add_argument("--concurrency", type=int, default=100)
    parser.add_argument("--total", type=int, default=500)
    args = parser.parse_args()
    asyncio.run(run_benchmark(concurrency=args.concurrency, total=args.total))


if __name__ == "__main__":
    main()
