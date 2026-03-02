from __future__ import annotations

from dataclasses import dataclass
import re

DEFAULT_HINT_LEVEL = "medium"


@dataclass(frozen=True)
class ParsedError:
    code: str
    line: int | None
    err: str
    hint: str


def parse_traceback(tb_text: str, hint_level: str = DEFAULT_HINT_LEVEL) -> ParsedError:
    line = _extract_user_line(tb_text)
    err_text = _extract_error_text(tb_text)
    code = _classify_error(err_text)
    hint = build_hint(code, hint_level=hint_level)
    return ParsedError(code=code, line=line, err=err_text, hint=hint)


def parse_guard_message(message: str, hint_level: str = DEFAULT_HINT_LEVEL) -> ParsedError:
    if message.startswith("语法错误"):
        code = "E_SYNTAX"
        line = _extract_line_from_guard(message)
        err = message
    else:
        code = "E_AST_BLOCK"
        line = _extract_line_from_guard(message)
        err = message
    return ParsedError(code=code, line=line, err=err, hint=build_hint(code, hint_level=hint_level))


def parse_pool_error(message: str, hint_level: str = DEFAULT_HINT_LEVEL) -> ParsedError:
    if "超时" in message:
        code = "E_TIMEOUT"
    else:
        code = "E_WORKER"
    return ParsedError(code=code, line=None, err=message, hint=build_hint(code, hint_level=hint_level))


def parse_internal_error(message: str, hint_level: str = DEFAULT_HINT_LEVEL) -> ParsedError:
    clean = (message or "").strip() or "internal error"
    return ParsedError(code="E_INTERNAL", line=None, err=clean, hint=build_hint("E_INTERNAL", hint_level=hint_level))


def build_hint(code: str, hint_level: str = DEFAULT_HINT_LEVEL) -> str:
    if hint_level == "none":
        return ""
    if hint_level == "short":
        return "根据错误码与行号最小改动后重试。"

    hints = {
        "E_AST_BLOCK": "检测到不安全语句。请仅保留 sympy/math 相关计算代码，并移除系统调用后重试。",
        "E_SYNTAX": "代码存在语法错误。请先修正报错行附近的括号、缩进或符号，再重新执行。",
        "E_TIMEOUT": "计算超时。请减少计算规模、拆分步骤或先做代数化简后再求解。",
        "E_MEMORY": "内存不足。请降低矩阵维度/展开规模，避免一次性构造超大对象。",
        "E_RUNTIME": "运行时错误。请根据行号检查变量类型、零除、未定义变量等问题后重试。",
        "E_WORKER": "执行进程异常。请保持代码简洁后重试；若持续失败请重新发起调用。",
        "E_INTERNAL": "服务内部异常。请重试一次；若仍失败请保留输入代码用于排查。",
    }
    return hints.get(code, hints["E_RUNTIME"])


def _extract_user_line(tb_text: str) -> int | None:
    if not tb_text.strip():
        return None
    lines = tb_text.strip().splitlines()
    for ln in lines:
        s = ln.strip()
        if s.startswith('File "<user_code>", line '):
            try:
                return int(s.split("line ")[1].split(",")[0])
            except (IndexError, ValueError):
                return None
    return None


def _extract_error_text(tb_text: str) -> str:
    default = "RuntimeError: 未知错误"
    if not tb_text.strip():
        return default
    tail = tb_text.strip().splitlines()[-1].strip()
    # 兼容无消息的异常尾行，例如 "MemoryError"
    if ":" not in tail and re.fullmatch(r"[A-Za-z_]\w*", tail):
        return f"{tail}: 未知错误"
    if ":" not in tail:
        return default
    etype, msg = tail.split(":", 1)
    etype = etype.strip() or "RuntimeError"
    msg = msg.strip() or "未知错误"
    return f"{etype}: {msg}"


def _classify_error(err_text: str) -> str:
    etype = err_text.split(":", 1)[0]
    if etype in {"MemoryError"}:
        return "E_MEMORY"
    if etype in {"TimeoutError"}:
        return "E_TIMEOUT"
    return "E_RUNTIME"


def _extract_line_from_guard(message: str) -> int | None:
    m = re.search(r"第\s*(\d+)\s*行", message)
    if not m:
        return None
    try:
        return int(m.group(1))
    except ValueError:
        return None
