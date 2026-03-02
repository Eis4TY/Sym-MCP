from __future__ import annotations

import asyncio
import logging
import multiprocessing as mp
import time
from dataclasses import dataclass
from multiprocessing.connection import Connection
from typing import Any

from sym_mcp.executor.worker_main import run_worker

LOGGER = logging.getLogger(__name__)


class WorkerPoolError(RuntimeError):
    """Errors from worker pool."""


@dataclass
class Worker:
    worker_id: int
    process: mp.Process
    conn: Connection


class WorkerPool:
    def __init__(
        self,
        size: int,
        exec_timeout_sec: float,
        queue_wait_sec: float,
        memory_limit_mb: int,
    ) -> None:
        self._size = size
        self._exec_timeout_sec = exec_timeout_sec
        self._queue_wait_sec = queue_wait_sec
        self._memory_limit_mb = memory_limit_mb
        self._ctx = mp.get_context("spawn")
        self._queue: asyncio.Queue[Worker] = asyncio.Queue(maxsize=size)
        self._workers: dict[int, Worker] = {}
        self._lock = asyncio.Lock()
        self._started = False
        self.timeout_count = 0
        self.rebuild_count = 0
        self.reject_count = 0

    async def start(self) -> None:
        async with self._lock:
            if self._started:
                return
            for i in range(self._size):
                worker = self._spawn_worker(worker_id=i)
                await self._wait_worker_ready(worker)
                await self._queue.put(worker)
                self._workers[worker.worker_id] = worker
            self._started = True
            LOGGER.info("Worker pool started with size=%s", self._size)

    async def close(self) -> None:
        async with self._lock:
            workers = list(self._workers.values())
            self._workers.clear()
            self._started = False
            while not self._queue.empty():
                self._queue.get_nowait()

        for worker in workers:
            await self._shutdown_worker(worker)

    async def exec(self, code: str) -> dict[str, Any]:
        if not self._started:
            raise WorkerPoolError("worker pool not started")
        borrow_start = time.perf_counter()
        try:
            worker = await asyncio.wait_for(self._queue.get(), timeout=self._queue_wait_sec)
        except TimeoutError as exc:
            self.reject_count += 1
            raise WorkerPoolError("执行排队超时，请稍后重试。") from exc
        borrow_ms = (time.perf_counter() - borrow_start) * 1000
        LOGGER.debug("borrow worker=%s cost=%.2fms", worker.worker_id, borrow_ms)

        try:
            result = await self._exec_on_worker(worker, code)
        finally:
            if self._is_alive(worker):
                await self._queue.put(worker)
            else:
                await self._replace_worker(worker)
        return result

    async def health_check(self) -> None:
        for worker in list(self._workers.values()):
            if not self._is_alive(worker):
                await self._replace_worker(worker)
                continue
            try:
                await self._request(worker, {"cmd": "ping"}, timeout=1.0)
            except Exception:
                await self._replace_worker(worker)

    def _spawn_worker(self, worker_id: int) -> Worker:
        parent_conn, child_conn = self._ctx.Pipe(duplex=True)
        proc = self._ctx.Process(
            target=run_worker,
            args=(child_conn, self._memory_limit_mb, self._exec_timeout_sec),
            daemon=True,
            name=f"sym-worker-{worker_id}",
        )
        proc.start()
        child_conn.close()
        return Worker(worker_id=worker_id, process=proc, conn=parent_conn)

    async def _replace_worker(self, old_worker: Worker) -> None:
        self.rebuild_count += 1
        LOGGER.warning("replace dead worker=%s", old_worker.worker_id)
        await self._shutdown_worker(old_worker)
        new_worker = self._spawn_worker(old_worker.worker_id)
        await self._wait_worker_ready(new_worker)
        self._workers[new_worker.worker_id] = new_worker
        await self._queue.put(new_worker)

    async def _shutdown_worker(self, worker: Worker) -> None:
        try:
            if self._is_alive(worker):
                await self._request(worker, {"cmd": "stop"}, timeout=0.5)
        except Exception:
            pass
        try:
            if self._is_alive(worker):
                worker.process.terminate()
                await asyncio.to_thread(worker.process.join, 0.5)
            if self._is_alive(worker):
                worker.process.kill()
                await asyncio.to_thread(worker.process.join, 0.5)
        finally:
            if worker.worker_id in self._workers and self._workers[worker.worker_id] is worker:
                self._workers.pop(worker.worker_id, None)
            try:
                worker.conn.close()
            except OSError:
                pass

    async def _exec_on_worker(self, worker: Worker, code: str) -> dict[str, Any]:
        start = time.perf_counter()
        try:
            result = await self._request(worker, {"cmd": "exec", "code": code}, timeout=self._exec_timeout_sec)
            exec_ms = (time.perf_counter() - start) * 1000
            LOGGER.debug("exec worker=%s cost=%.2fms", worker.worker_id, exec_ms)
            return result
        except TimeoutError as exc:
            self.timeout_count += 1
            LOGGER.warning("worker=%s timeout, terminate", worker.worker_id)
            await self._kill_worker(worker)
            raise WorkerPoolError("代码执行超时（超过限制）。") from exc
        except (EOFError, BrokenPipeError, ConnectionError, OSError) as exc:
            LOGGER.warning("worker=%s communication broken, terminate", worker.worker_id)
            await self._kill_worker(worker)
            raise WorkerPoolError("执行进程异常，请重试。") from exc

    async def _kill_worker(self, worker: Worker) -> None:
        if self._is_alive(worker):
            worker.process.terminate()
            await asyncio.to_thread(worker.process.join, 0.5)
        if self._is_alive(worker):
            worker.process.kill()
            await asyncio.to_thread(worker.process.join, 0.5)

    async def _request(self, worker: Worker, payload: dict[str, Any], timeout: float) -> dict[str, Any]:
        worker.conn.send(payload)
        ready = await asyncio.wait_for(asyncio.to_thread(worker.conn.poll, timeout), timeout=timeout + 0.2)
        if not ready:
            raise TimeoutError("worker response timeout")
        return worker.conn.recv()

    async def _wait_worker_ready(self, worker: Worker) -> None:
        startup_timeout = max(15.0, self._exec_timeout_sec * 5)
        await self._request(worker, {"cmd": "ping"}, timeout=startup_timeout)

    @staticmethod
    def _is_alive(worker: Worker) -> bool:
        return worker.process.is_alive()
