from __future__ import annotations

import math
import os
from multiprocessing.connection import Connection
from typing import Any

from sym_mcp.executor.sandbox import execute_user_code

try:
    import resource
except ImportError:  # pragma: no cover
    resource = None  # type: ignore[assignment]


def run_worker(conn: Connection, memory_limit_mb: int, cpu_limit_sec: float) -> None:
    _apply_resource_limits(memory_limit_mb=memory_limit_mb, cpu_limit_sec=cpu_limit_sec)
    _preload_heavy_modules()
    while True:
        msg = conn.recv()
        cmd = msg.get("cmd")
        if cmd == "ping":
            conn.send({"ok": True, "pong": True})
            continue
        if cmd == "stop":
            conn.send({"ok": True, "stopped": True})
            break
        if cmd != "exec":
            conn.send({"ok": False, "error": f"unknown command: {cmd}"})
            continue
        code = msg.get("code", "")
        result = execute_user_code(code)
        conn.send(
            {
                "ok": True,
                "success": result.success,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "traceback": result.traceback_text,
            }
        )


def _preload_heavy_modules() -> None:
    import sympy  # noqa: F401
    import math as _math  # noqa: F401


def _apply_resource_limits(memory_limit_mb: int, cpu_limit_sec: float) -> None:
    if resource is None:
        return

    memory_bytes = memory_limit_mb * 1024 * 1024
    for limit_name in ("RLIMIT_AS", "RLIMIT_DATA"):
        limit = getattr(resource, limit_name, None)
        if limit is None:
            continue
        try:
            resource.setrlimit(limit, (memory_bytes, memory_bytes))
        except (OSError, ValueError):
            pass

    cpu_soft = max(1, math.ceil(cpu_limit_sec))
    cpu_hard = cpu_soft + 1
    try:
        resource.setrlimit(resource.RLIMIT_CPU, (cpu_soft, cpu_hard))
    except (OSError, ValueError):
        pass

    try:
        os.nice(5)
    except OSError:
        pass

