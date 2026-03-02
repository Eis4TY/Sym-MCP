import json

import pytest

import sym_mcp.server as server


@pytest.fixture(autouse=True)
async def _cleanup_pool():
    yield
    if server._POOL is not None:
        await server._POOL.close()
        server._POOL = None


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("code", "expected"),
    [
        ("import sympy as sp\nx=sp.Symbol('x')\nprint(sp.integrate(x,(x,0,1)))", "1/2"),
        ("import sympy as sp\nx=sp.Symbol('x')\nprint(sp.expand((x+1)**5))", "x**5 + 5*x**4 + 10*x**3 + 10*x**2 + 5*x + 1"),
        ("import sympy as sp\nx=sp.Symbol('x')\nprint(sorted(sp.solve(sp.Eq(x**2-5*x+6,0),x)))", "[2, 3]"),
        ("import sympy as sp\nM=sp.Matrix([[1,2],[3,4]])\nprint(M.det())", "-2"),
        ("import sympy as sp\nx,y=sp.symbols('x y')\nsol=sp.solve([sp.Eq(x+y,3),sp.Eq(x-y,1)],[x,y],dict=True)[0]\nprint(sol[x],sol[y])", "2 1"),
        ("import sympy as sp\nx=sp.Symbol('x')\nprint(sp.simplify(sp.sin(x)**2+sp.cos(x)**2))", "1"),
    ],
)
async def test_sympy_tool_math_correctness(code: str, expected: str) -> None:
    out = await server.sympy_tool(code)
    obj = json.loads(out)
    assert obj["ok"] == 1
    assert obj["out"] == expected


@pytest.mark.asyncio
async def test_sympy_tool_math_module_support() -> None:
    out = await server.sympy_tool("from math import sqrt\nprint(sqrt(9))")
    obj = json.loads(out)
    assert obj["ok"] == 1
    assert obj["out"] == "3.0"
