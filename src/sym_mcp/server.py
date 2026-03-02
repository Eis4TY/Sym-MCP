from __future__ import annotations

import asyncio
import json
import logging
from typing import Callable, Optional

try:
    from fastmcp import FastMCP
except ImportError:  # pragma: no cover

    class FastMCP:  # type: ignore[override]
        def __init__(self, _: str) -> None:
            self._tools: dict[str, Callable] = {}

        def tool(self, name: str):
            def decorator(func: Callable):
                self._tools[name] = func
                return func

            return decorator

        def run(self) -> None:
            raise RuntimeError("fastmcp 未安装，无法启动 MCP 服务。")

from sym_mcp.config import Settings, load_settings
from sym_mcp.errors.parser import (
    parse_guard_message,
    parse_internal_error,
    parse_pool_error,
    parse_traceback,
)
from sym_mcp.executor.pool import WorkerPool, WorkerPoolError
from sym_mcp.security.ast_guard import validate_code

LOGGER = logging.getLogger(__name__)

settings: Settings = load_settings()
logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))

mcp = FastMCP("SymPy Sandbox MCP")

_POOL: Optional[WorkerPool] = None
_POOL_INIT_LOCK = asyncio.Lock()


async def _get_pool() -> WorkerPool:
    global _POOL
    if _POOL is not None:
        return _POOL
    async with _POOL_INIT_LOCK:
        if _POOL is not None:
            return _POOL
        pool = WorkerPool(
            size=settings.pool_size,
            exec_timeout_sec=settings.exec_timeout_sec,
            queue_wait_sec=settings.queue_wait_sec,
            memory_limit_mb=settings.memory_limit_mb,
        )
        await pool.start()
        _POOL = pool
        LOGGER.info("worker pool initialized")
        return pool


@mcp.tool(name="sympy")
async def sympy_tool(code: str) -> str:
    """SymPy sandbox tool: execute Python/SymPy math code.

    Safety boundaries:
    - Only sympy/math imports and calls are allowed.
    - System calls, file I/O, network access, and dynamic execution are blocked.

    Input rules:
    - Single argument: code (str).
    - You must print() the final answer; otherwise out may be empty.
    - Use multiple print() lines for multiple outputs.

    Recommended workflow:
    1) Define symbols and assumptions.
    2) Derive/solve step by step.
    3) Simplify intermediate expressions (simplify/factor/expand).
    4) Print final results.

    Retry guidance:
    - E_AST_BLOCK: remove unsafe statements and keep pure math code only.
    - E_TIMEOUT: reduce problem size, split steps, simplify before solving.
    - E_MEMORY: reduce dimensions or avoid constructing huge objects at once.
    """
    guard = validate_code(code)
    if not guard.ok:
        parsed = parse_guard_message(guard.message, hint_level=settings.hint_level)
        return _build_error_response(parsed.code, parsed.line, parsed.err, parsed.hint)

    pool = await _get_pool()
    try:
        result = await pool.exec(code)
    except WorkerPoolError as exc:
        parsed = parse_pool_error(str(exc), hint_level=settings.hint_level)
        return _build_error_response(parsed.code, parsed.line, parsed.err, parsed.hint)
    except Exception as exc:
        LOGGER.exception("unexpected pool error")
        parsed = parse_internal_error(str(exc), hint_level=settings.hint_level)
        return _build_error_response(parsed.code, parsed.line, parsed.err, parsed.hint)

    if not result.get("ok", False):
        parsed = parse_pool_error("worker执行失败", hint_level=settings.hint_level)
        return _build_error_response(parsed.code, parsed.line, parsed.err, parsed.hint)

    if result.get("success", False):
        stdout = (result.get("stdout") or "").rstrip()
        out, _ = _truncate(stdout)
        return _json_compact({"out": out})

    tb_text = result.get("traceback", "") or ""
    parsed = parse_traceback(tb_text, hint_level=settings.hint_level)
    return _build_error_response(parsed.code, parsed.line, parsed.err, parsed.hint)


def main() -> None:
    mcp.run()

def _build_error_response(code: str, line: int | None, err: str, hint: str) -> str:
    err, trunc_err = _truncate(err)
    hint, trunc_hint = _truncate(hint)
    if trunc_err and "truncated" not in err:
        err = f"{err}...[truncated]"
    if trunc_hint and "truncated" not in hint:
        hint = f"{hint}...[truncated]"
    return _json_compact(
        {
            "code": code,
            "line": line,
            "err": err,
            "hint": hint,
        }
    )


def _truncate(text: str) -> tuple[str, int]:
    text = text or ""
    max_chars = settings.max_output_chars
    if len(text) <= max_chars:
        return text, 0
    return f"{text[: max_chars - 12]}...[truncated]", 1


def _json_compact(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


if __name__ == "__main__":
    main()
