# SymPy Sandbox MCP

一个面向 Agent/LLM 的 SymPy 计算沙箱 MCP 服务。  
目标是：在保证安全隔离的前提下，提供低延迟、低 token、可稳定重试的数学计算工具。

## 特性

- 单工具 `sympy`，输入参数仅 `code`
- 预热进程池，避免每次请求重复 `import sympy`
- 双层安全防护：AST 拦截 + 运行时资源限制
- 统一紧凑 JSON 输出，便于程序解析且节省 token
- 错误码标准化，方便 Agent 自动纠错重试

## 适用场景

- 让 LLM 执行代数化简、求导、积分、方程求解、符号推导
- 作为 MCP Tool 接入 Codex / Cursor / Claude Desktop / 自建 MCP Client
- 需要“可控失败 + 低噪声错误信息”的自动化 Agent 工作流

## 快速开始

### 1) 环境要求

- Python 3.11+
- Linux / macOS（推荐 Linux 作为生产环境）

### 2) 安装（清华源优先）

```bash
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -e .
pip install -i https://pypi.tuna.tsinghua.edu.cn/simple -e ".[dev]"
```

### 3) 启动服务（stdio）

```bash
python -m sym_mcp.server
```

### 4) 验证工具可用

```bash
fastmcp list --command 'python -m sym_mcp.server'
```

## 通过 PyPI 安装（推荐给最终用户）

```bash
pip install -U sym-mcp
```

安装后可直接运行：

```bash
sym-mcp
```

或临时运行（不落地安装，推荐给体验用户）：

```bash
uvx sym-mcp
```

## 工具接口（对外契约）

### Tool 名称

- `sympy`

### 输入

- `code: str`

约定：
- 代码必须使用 `print()` 输出最终结果
- 如果不 `print`，`out` 可能为空字符串

### 输出（固定为紧凑 JSON 字符串）

成功：

```json
{"ok":1,"out":"x**2/2","meta":{"trunc":0,"ms":23}}
```

失败：

```json
{"ok":0,"code":"E_RUNTIME","line":3,"err":"ZeroDivisionError: division by zero","hint":"运行时错误。请根据行号检查变量类型、零除、未定义变量等问题后重试。","meta":{"trunc":0,"ms":31}}
```

字段定义：

- `ok`: `1` 成功，`0` 失败
- `out`: 成功输出文本（来自 stdout）
- `code`: 错误码
- `line`: 用户代码报错行号；无则 `null`
- `err`: 精简错误信息（去除 traceback 噪声）
- `hint`: 修复建议（按配置等级生成）
- `meta.trunc`: 是否发生截断（`1/0`）
- `meta.ms`: 执行耗时（毫秒）

## 错误码说明

- `E_AST_BLOCK`: AST 安全拦截（危险导入/调用/双下划线穿透）
- `E_SYNTAX`: 语法错误
- `E_TIMEOUT`: 超时（死循环或计算过慢）
- `E_MEMORY`: 内存限制触发
- `E_RUNTIME`: 一般运行时错误
- `E_WORKER`: Worker 通讯/状态异常
- `E_INTERNAL`: 服务内部异常

## 给 LLM/Agent 的调用规范（建议直接放系统提示）

1. 仅写数学代码，禁止文件、网络、系统调用。
2. 仅导入 `sympy` / `math`。
3. 最终答案必须 `print()`。
4. 多个结果使用多行 `print()`。
5. 收到失败结果时，只修改 `line` 附近最小范围代码并重试。
6. `E_TIMEOUT` 先缩小规模再算；`E_MEMORY` 先减小对象维度；`E_AST_BLOCK` 删除不安全语句。

推荐模板：

```python
import sympy as sp
x = sp.Symbol("x")
expr = (x + 1)**5
print(sp.expand(expr))
```

## 安全模型

### 执行前（AST 白名单）

- 仅允许 `sympy` / `math` 导入
- 禁止 `eval/exec/open/__import__` 等危险能力
- 禁止双下划线属性穿透（如 `__class__`）

### 执行中（OS 资源限制）

- 子进程 CPU 时间限制 + 超时强杀
- 子进程内存限制（`setrlimit`）
- Worker 异常自动重建，不影响主服务

## 架构总览

- `src/sym_mcp/server.py`: MCP 入口与工具注册
- `src/sym_mcp/security/ast_guard.py`: AST 安全校验
- `src/sym_mcp/executor/worker_main.py`: Worker 进程执行循环
- `src/sym_mcp/executor/pool.py`: 异步预热进程池
- `src/sym_mcp/executor/sandbox.py`: 受限执行环境与输出捕获
- `src/sym_mcp/errors/parser.py`: 错误降噪与错误码映射
- `src/sym_mcp/config.py`: 运行配置

## 配置项（环境变量）

- `SYMMCP_POOL_SIZE`：进程池大小，默认 `10`
- `SYMMCP_EXEC_TIMEOUT_SEC`：单次执行超时秒数，默认 `3`
- `SYMMCP_MEMORY_LIMIT_MB`：单 worker 内存上限 MB，默认 `150`
- `SYMMCP_QUEUE_WAIT_SEC`：队列等待超时秒数，默认 `2`
- `SYMMCP_LOG_LEVEL`：日志级别，默认 `INFO`
- `SYMMCP_MAX_OUTPUT_CHARS`：输出截断阈值，默认 `1200`
- `SYMMCP_HINT_LEVEL`：提示等级（`none/short/medium`），默认 `medium`

## 本地开发

### 运行测试

```bash
PYTHONPATH=src pytest -q
```

### 基准压测

```bash
PYTHONPATH=src python scripts/benchmark.py --concurrency 100 --total 500
```

## MCP 客户端接入示例（stdio）

示例命令：

```bash
fastmcp call \
  --command 'python -m sym_mcp.server' \
  --target sympy \
  --input-json '{"code":"import sympy as sp\nx=sp.Symbol(\"x\")\nprint(sp.factor(x**2-1))"}'
```

示例配置（安装为命令 `sym-mcp` 后）：

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

示例配置（使用 `uvx`）：

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

## 常见问题

### 1) 为什么结果为空？

通常是代码未 `print` 最终结果。请显式 `print(...)`。

### 2) 为什么返回 JSON 字符串而不是纯文本？

为便于 Agent 稳定解析并减少 token，返回固定结构化紧凑 JSON。

### 3) macOS 下内存限制有时不稳定？

`setrlimit` 在不同系统语义不同。生产建议优先 Linux。

### 4) 可以支持 HTTP/SSE 吗？

当前主交付是 `stdio`。后续可按 FastMCP 方式扩展 HTTP/SSE 传输层。

## 已知边界

- 当前为“受限 Python 执行”，不是内核虚拟化级别隔离
- 内存限制依赖 OS 层实现，跨平台表现会有差异
- 输出会按阈值截断，请调用方检查 `meta.trunc`

## 贡献建议

- 提交 PR 前先运行 `PYTHONPATH=src pytest -q`
- 新增能力时请同步更新：
  - 错误码文档
  - README 示例
  - 对应单元测试 / 集成测试
- 发布流程见 [PUBLISHING.md](./PUBLISHING.md)
