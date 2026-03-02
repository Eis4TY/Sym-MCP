# SymPy Sandbox MCP

English | [中文版](README.zh.md)

A production-focused MCP service that lets agents/LLMs run SymPy safely and efficiently.
It combines AST policy checks, runtime resource limits, and prewarmed workers to deliver low-noise, parse-friendly results.

## Features

- Single tool: `sympy` (input only requires `code`)
- Prewarmed worker pool to avoid repeated `import sympy`
- Two-layer safety: AST guard + runtime resource limits
- Compact structured JSON output for low token overhead
- Standardized error codes for reliable auto-retry workflows

## Typical Use Cases

- Symbolic algebra, differentiation, integration, equation solving
- MCP tool integration for Codex / Cursor / Claude Desktop / custom MCP clients
- Agent workflows that need controllable failures and clean error signals

## Recommended Integration (MCP client via stdio)

Call example:

```bash
fastmcp call \
  --command 'python -m sym_mcp.server' \
  --target sympy \
  --input-json '{"code":"import sympy as sp\\nx=sp.Symbol(\"x\")\\nprint(sp.factor(x**2-1))"}'
```

Client config (`python -m`, recommended):

```json
{
  "mcpServers": {
    "sympy-sandbox": {
      "command": "python",
      "args": ["-m", "sym_mcp.server"]
    }
  }
}
```

Client config (installed as `sym-mcp`):

```json
{
  "mcpServers": {
    "sympy-sandbox": {
      "command": "sym-mcp",
      "args": []
    }
  }
}
```

Client config (`uvx`):

```json
{
  "mcpServers": {
    "sympy-sandbox": {
      "command": "uvx",
      "args": ["sym-mcp"]
    }
  }
}
```

## Quick Start

### 1) Requirements

- Python 3.11+
- Linux / macOS (Linux recommended for production)

### 2) Install (Tsinghua mirror first)

```bash
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -e .
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -e ".[dev]"
```

### 3) Run server (stdio)

```bash
python -m sym_mcp.server
```

### 4) Verify tool

```bash
fastmcp list --command 'python -m sym_mcp.server'
```

## Tool Contract

### Tool name

- `sympy`

### Input

- `code: str`

Notes:
- You must `print()` final outputs.
- If nothing is printed, `out` may be empty.

### Output (always compact JSON string)

Success:

```json
{"out":"x**2/2"}
```

Failure:

```json
{"code":"E_RUNTIME","line":3,"err":"ZeroDivisionError: division by zero","hint":"Runtime error. Check variable types, division-by-zero, or undefined names near the reported line."}
```

Field definitions:

- `out`: stdout text on success
- `code`: error code
- `line`: user code error line, or `null`
- `err`: compact error message (traceback noise removed)
- `hint`: fix hint (based on configured hint level)
- If `out` / `err` / `hint` is too long, it will be truncated with `...[truncated]`

## Error Codes

- `E_AST_BLOCK`: blocked by AST safety policy
- `E_SYNTAX`: syntax error
- `E_TIMEOUT`: timeout
- `E_MEMORY`: memory limit triggered
- `E_RUNTIME`: general runtime error
- `E_WORKER`: worker communication/state failure
- `E_INTERNAL`: internal server error

## Recommended Agent Prompt Rules

1. Use math-only Python code.
2. Only import `sympy` or `math`.
3. Always `print()` final answers.
4. For multiple outputs, use multiple `print()` lines.
5. On failure, patch minimally near `line` and retry.
6. For `E_TIMEOUT`, reduce scale first; for `E_MEMORY`, reduce object size/dimension; for `E_AST_BLOCK`, remove unsafe statements.

Example:

```python
import sympy as sp
x = sp.Symbol("x")
expr = (x + 1)**5
print(sp.expand(expr))
```

## Security Model

### Before execution (AST policy)

- Only `sympy` / `math` imports are allowed
- Dangerous capabilities are blocked (`eval`, `exec`, `open`, `__import__`, etc.)
- Dunder attribute traversal is blocked (e.g. `__class__`)

### During execution (OS resource limits)

- Per-task CPU time limit + timeout kill
- Per-worker memory limit via `setrlimit`
- Worker auto-rebuild on failure to keep server healthy

## Architecture

- `src/sym_mcp/server.py`: MCP entrypoint and tool registration
- `src/sym_mcp/security/ast_guard.py`: AST validation
- `src/sym_mcp/executor/worker_main.py`: worker loop
- `src/sym_mcp/executor/pool.py`: async prewarmed process pool
- `src/sym_mcp/executor/sandbox.py`: restricted execution and stdout capture
- `src/sym_mcp/errors/parser.py`: error normalization and code mapping
- `src/sym_mcp/config.py`: runtime configuration

## Configuration (Environment Variables)

- `SYMMCP_POOL_SIZE`: worker pool size, default `10`
- `SYMMCP_EXEC_TIMEOUT_SEC`: per execution timeout (sec), default `3`
- `SYMMCP_MEMORY_LIMIT_MB`: memory cap per worker (MB), default `150`
- `SYMMCP_QUEUE_WAIT_SEC`: queue wait timeout (sec), default `2`
- `SYMMCP_LOG_LEVEL`: log level, default `INFO`
- `SYMMCP_MAX_OUTPUT_CHARS`: output truncation threshold, default `1200`
- `SYMMCP_HINT_LEVEL`: hint level (`none/short/medium`), default `medium`

## FAQ

### Why is `out` empty?

Most likely the code does not `print()` the final result.

### Why return compact JSON string?

It is easier for agents to parse reliably and reduces token cost.

### Is memory limiting always stable on macOS?

`setrlimit` behavior differs by OS. Linux is preferred for production.

### Does it support HTTP/SSE?

Current primary delivery is `stdio`. HTTP/SSE can be added later via FastMCP transport extensions.

## Known Limits

- This is restricted Python execution, not VM/container-grade isolation
- Memory limit behavior is OS-dependent
- Output is truncated at threshold, with `...[truncated]` suffix

## Development

### Run tests

```bash
PYTHONPATH=src pytest -q
```

### Benchmark

```bash
PYTHONPATH=src python scripts/benchmark.py --concurrency 100 --total 500
```

## Contributing

- Run `PYTHONPATH=src pytest -q` before submitting PRs
- When adding new capabilities, update:
  - error code docs
  - README examples
  - related unit/integration tests
- Publishing process: [PUBLISHING.md](./PUBLISHING.md)
