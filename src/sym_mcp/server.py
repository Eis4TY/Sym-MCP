from __future__ import annotations

import asyncio
import json
import logging
import time
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
    """SymPy 计算沙箱工具（单入参，紧凑 JSON 输出）。

    用途:
    - 执行 Python/SymPy 数学计算代码，返回标准输出中的关键结论。
    - 仅用于数学推导、化简、求解、积分、微分、代数运算。

    重要边界:
    - 只允许 sympy/math 相关导入与调用。
    - 禁止系统调用、文件读写、网络访问、动态执行等危险行为。

    输入规范:
    - 唯一参数: code (str)。
    - 必须使用 print() 输出最终答案；不 print 则 out 可能为空。
    - 多个结果请分多行 print。
    - 避免打印超大对象（如超大矩阵/超长表达式）以减少 token。

    推荐模板:
    1) 定义符号与条件
    2) 分步推导/求解
    3) 对中间式做 simplify/factor/expand
    4) print 最终结果

    返回协议（固定紧凑 JSON 字符串）:
    - 成功: {"ok":1,"out":"...","meta":{"trunc":0,"ms":23}}
    - 失败: {"ok":0,"code":"E_RUNTIME","line":12,"err":"...","hint":"...","meta":{"trunc":0,"ms":31}}

    字段说明:
    - ok: 1 成功 / 0 失败
    - out: 结果文本（成功时）
    - code: 错误码（失败时）
    - line: 报错行号（失败时，可为 null）
    - err: 精简错误信息
    - hint: 中等长度修复提示
    - meta.trunc: 1 表示输出被截断
    - meta.ms: 执行耗时毫秒

    错误码:
    - E_AST_BLOCK / E_SYNTAX / E_TIMEOUT / E_MEMORY / E_RUNTIME / E_WORKER / E_INTERNAL

    失败重试建议:
    - 仅修改 line 对应附近代码，不要整体重写。
    - E_AST_BLOCK: 删除危险语句，仅保留纯数学代码。
    - E_TIMEOUT: 减少规模、分步计算、先简化再求解。
    - E_MEMORY: 降低维度或避免一次性构造大对象。
    """
    start = time.perf_counter()

    guard = validate_code(code)
    if not guard.ok:
        parsed = parse_guard_message(guard.message, hint_level=settings.hint_level)
        return _build_error_response(parsed.code, parsed.line, parsed.err, parsed.hint, start)

    pool = await _get_pool()
    try:
        result = await pool.exec(code)
    except WorkerPoolError as exc:
        parsed = parse_pool_error(str(exc), hint_level=settings.hint_level)
        return _build_error_response(parsed.code, parsed.line, parsed.err, parsed.hint, start)
    except Exception as exc:
        LOGGER.exception("unexpected pool error")
        parsed = parse_internal_error(str(exc), hint_level=settings.hint_level)
        return _build_error_response(parsed.code, parsed.line, parsed.err, parsed.hint, start)

    if not result.get("ok", False):
        parsed = parse_pool_error("worker执行失败", hint_level=settings.hint_level)
        return _build_error_response(parsed.code, parsed.line, parsed.err, parsed.hint, start)

    if result.get("success", False):
        stdout = (result.get("stdout") or "").rstrip()
        out, trunc = _truncate(stdout)
        return _json_compact(
            {
                "ok": 1,
                "out": out,
                "meta": {
                    "trunc": trunc,
                    "ms": _elapsed_ms(start),
                },
            }
        )

    tb_text = result.get("traceback", "") or ""
    parsed = parse_traceback(tb_text, hint_level=settings.hint_level)
    return _build_error_response(parsed.code, parsed.line, parsed.err, parsed.hint, start)


def main() -> None:
    mcp.run()

def _build_error_response(code: str, line: int | None, err: str, hint: str, start: float) -> str:
    err, trunc_err = _truncate(err)
    hint, trunc_hint = _truncate(hint)
    return _json_compact(
        {
            "ok": 0,
            "code": code,
            "line": line,
            "err": err,
            "hint": hint,
            "meta": {
                "trunc": 1 if (trunc_err or trunc_hint) else 0,
                "ms": _elapsed_ms(start),
            },
        }
    )


def _truncate(text: str) -> tuple[str, int]:
    text = text or ""
    max_chars = settings.max_output_chars
    if len(text) <= max_chars:
        return text, 0
    return f"{text[: max_chars - 12]}...[truncated]", 1


def _elapsed_ms(start: float) -> int:
    return int((time.perf_counter() - start) * 1000)


def _json_compact(data: dict) -> str:
    return json.dumps(data, ensure_ascii=False, separators=(",", ":"))


if __name__ == "__main__":
    main()
