from __future__ import annotations

import contextlib
import io
import traceback
from dataclasses import dataclass
from typing import Any

import math
import sympy


SAFE_BUILTINS = {
    "abs": abs,
    "all": all,
    "any": any,
    "bool": bool,
    "dict": dict,
    "enumerate": enumerate,
    "float": float,
    "int": int,
    "len": len,
    "list": list,
    "max": max,
    "min": min,
    "pow": pow,
    "print": print,
    "range": range,
    "reversed": reversed,
    "round": round,
    "set": set,
    "sorted": sorted,
    "str": str,
    "sum": sum,
    "tuple": tuple,
    "zip": zip,
}

ALLOWED_IMPORT_ROOTS = {"sympy", "math"}


@dataclass
class ExecResult:
    success: bool
    stdout: str = ""
    stderr: str = ""
    traceback_text: str = ""


def build_exec_globals() -> dict[str, Any]:
    def _safe_import(name: str, globals=None, locals=None, fromlist=(), level=0):
        root = name.split(".")[0]
        if root not in ALLOWED_IMPORT_ROOTS:
            raise ImportError(f"禁止导入模块: {name}")
        return __import__(name, globals, locals, fromlist, level)

    safe_builtins = dict(SAFE_BUILTINS)
    safe_builtins["__import__"] = _safe_import
    return {
        "__builtins__": safe_builtins,
        "sympy": sympy,
        "math": math,
    }


def execute_user_code(code: str) -> ExecResult:
    glb = build_exec_globals()
    loc: dict[str, Any] = {}
    out_buf = io.StringIO()
    err_buf = io.StringIO()
    try:
        compiled = compile(code, "<user_code>", "exec")
        with contextlib.redirect_stdout(out_buf), contextlib.redirect_stderr(err_buf):
            exec(compiled, glb, loc)
    except Exception:
        return ExecResult(
            success=False,
            stdout=out_buf.getvalue(),
            stderr=err_buf.getvalue(),
            traceback_text=traceback.format_exc(),
        )
    return ExecResult(success=True, stdout=out_buf.getvalue(), stderr=err_buf.getvalue())
