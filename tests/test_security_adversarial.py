import json

import pytest

import sym_mcp.server as server


@pytest.fixture(autouse=True)
async def _cleanup_pool():
    yield
    if server._POOL is not None:
        await server._POOL.close()
        server._POOL = None


_ADVERSARIAL_CASES = [
    "import os\nprint(os.listdir('.'))",
    "from os import system\nprint(system('echo hacked'))",
    "import subprocess\nprint(subprocess.run(['echo','x']))",
    "import importlib\nprint(importlib.import_module('os'))",
    "import pathlib\nprint(list(pathlib.Path('.').iterdir()))",
    "print(eval('1+1'))",
    "exec('print(1)')",
    "print(open('x.txt', 'w'))",
    "print(__import__('os'))",
    "print((1).__class__.__mro__)",
    "print(globals())",
    "print(vars())",
    "print(getattr(1, 'real'))",
    "print(type(1))",
]


@pytest.mark.asyncio
@pytest.mark.parametrize("code", _ADVERSARIAL_CASES)
async def test_sympy_tool_blocks_adversarial_payloads(code: str) -> None:
    out = await server.sympy_tool(code)
    obj = json.loads(out)
    assert obj["ok"] == 0
    assert obj["code"] == "E_AST_BLOCK"
    assert "安全拦截" in obj["err"]
