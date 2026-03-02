from sym_mcp.security.ast_guard import validate_code


def test_allow_sympy_math_code() -> None:
    code = """
import sympy as sp
from math import sqrt
x = sp.Symbol("x")
print(sp.diff(x**2, x), sqrt(4))
"""
    res = validate_code(code)
    assert res.ok is True


def test_block_bad_import() -> None:
    res = validate_code("import os\nprint('x')")
    assert res.ok is False
    assert "禁止导入模块" in res.message


def test_block_dangerous_builtin() -> None:
    res = validate_code("print(eval('1+1'))")
    assert res.ok is False
    assert "禁止调用 `eval`" in res.message


def test_block_dunder_escape() -> None:
    res = validate_code("print((1).__class__.__mro__)")
    assert res.ok is False
    assert "双下划线" in res.message


def test_allow_import_from_sympy() -> None:
    res = validate_code("from sympy import symbols\nx = symbols('x')\nprint(x)")
    assert res.ok is True


def test_block_blocked_root_name_access() -> None:
    res = validate_code("os = 1\nprint(os)")
    assert res.ok is False
    assert "禁止访问 `os`" in res.message


def test_block_class_def_node() -> None:
    res = validate_code("class A:\n    pass")
    assert res.ok is False
    assert "不允许的语法节点" in res.message
