import json
import inspect

import pytest

import sym_mcp.server as server


@pytest.fixture(autouse=True)
async def _cleanup_pool():
    yield
    if server._POOL is not None:
        await server._POOL.close()
        server._POOL = None


@pytest.mark.asyncio
async def test_sympy_tool_success() -> None:
    out = await server.sympy_tool("import sympy as sp\nx=sp.Symbol('x')\nprint(sp.integrate(x, x))")
    obj = json.loads(out)
    assert "x**2/2" in obj["out"]
    assert "code" not in obj


def test_sympy_tool_signature_only_code() -> None:
    sig = inspect.signature(server.sympy_tool)
    assert list(sig.parameters.keys()) == ["code"]


@pytest.mark.asyncio
async def test_sympy_tool_ast_reject() -> None:
    out = await server.sympy_tool("import os\nprint(os.listdir('.'))")
    obj = json.loads(out)
    assert obj["code"] == "E_AST_BLOCK"
    assert "安全拦截" in obj["err"]


@pytest.mark.asyncio
async def test_sympy_tool_runtime_error_noise_reduced() -> None:
    out = await server.sympy_tool("a=1/0\nprint(a)")
    obj = json.loads(out)
    assert obj["code"] == "E_RUNTIME"
    assert obj["line"] == 1
    assert "ZeroDivisionError" in obj["err"]


@pytest.mark.asyncio
async def test_sympy_tool_truncate_output() -> None:
    old = server.settings.max_output_chars
    server.settings = server.settings.__class__(**{**server.settings.__dict__, "max_output_chars": 120})
    try:
        out = await server.sympy_tool("print('x'*500)")
        obj = json.loads(out)
        assert obj["out"].endswith("[truncated]")
    finally:
        server.settings = server.settings.__class__(**{**server.settings.__dict__, "max_output_chars": old})


@pytest.mark.asyncio
async def test_sympy_tool_syntax_error() -> None:
    out = await server.sympy_tool("for")
    obj = json.loads(out)
    assert obj["code"] == "E_SYNTAX"
    assert obj["line"] == 1


@pytest.mark.asyncio
async def test_sympy_tool_no_print_output() -> None:
    out = await server.sympy_tool("import sympy as sp\nx = sp.Symbol('x')\ny = sp.expand((x+1)**3)")
    obj = json.loads(out)
    assert obj["out"] == ""


@pytest.mark.asyncio
async def test_sympy_tool_multiline_output() -> None:
    out = await server.sympy_tool("print(1)\nprint(2)")
    obj = json.loads(out)
    assert obj["out"] == "1\n2"


@pytest.mark.asyncio
async def test_sympy_tool_hint_level_none() -> None:
    old = server.settings
    server.settings = server.settings.__class__(**{**server.settings.__dict__, "hint_level": "none"})
    try:
        out = await server.sympy_tool("a=1/0")
        obj = json.loads(out)
        assert obj["code"] == "E_RUNTIME"
        assert obj["hint"] == ""
    finally:
        server.settings = old


@pytest.mark.asyncio
async def test_sympy_tool_hint_level_short() -> None:
    old = server.settings
    server.settings = server.settings.__class__(**{**server.settings.__dict__, "hint_level": "short"})
    try:
        out = await server.sympy_tool("a=1/0")
        obj = json.loads(out)
        assert obj["code"] == "E_RUNTIME"
        assert obj["hint"] == "根据错误码与行号最小改动后重试。"
    finally:
        server.settings = old
