from sym_mcp.errors.parser import parse_guard_message, parse_pool_error, parse_traceback


def test_parse_runtime_error_traceback() -> None:
    tb = """Traceback (most recent call last):
  File "<user_code>", line 3, in <module>
    print(1 / 0)
ZeroDivisionError: division by zero
"""
    parsed = parse_traceback(tb)
    assert parsed.code == "E_RUNTIME"
    assert parsed.line == 3
    assert "ZeroDivisionError: division by zero" == parsed.err
    assert "运行时错误" in parsed.hint


def test_parse_empty_traceback() -> None:
    parsed = parse_traceback("")
    assert parsed.code == "E_RUNTIME"
    assert parsed.line is None


def test_parse_guard_message() -> None:
    parsed = parse_guard_message("安全拦截: 禁止导入模块 `os`。")
    assert parsed.code == "E_AST_BLOCK"
    assert "不安全语句" in parsed.hint


def test_parse_pool_timeout() -> None:
    parsed = parse_pool_error("代码执行超时（超过限制）。")
    assert parsed.code == "E_TIMEOUT"


def test_parse_traceback_memory_error() -> None:
    tb = """Traceback (most recent call last):
  File "<user_code>", line 2, in <module>
MemoryError
"""
    parsed = parse_traceback(tb)
    assert parsed.code == "E_MEMORY"


def test_parse_traceback_timeout_error() -> None:
    tb = """Traceback (most recent call last):
  File "<user_code>", line 1, in <module>
TimeoutError: execution timeout
"""
    parsed = parse_traceback(tb)
    assert parsed.code == "E_TIMEOUT"


def test_parse_guard_message_syntax_line() -> None:
    parsed = parse_guard_message("语法错误: 第 7 行, invalid syntax")
    assert parsed.code == "E_SYNTAX"
    assert parsed.line == 7
