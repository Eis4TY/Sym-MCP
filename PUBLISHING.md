# Publishing Guide (PyPI)

本文档描述如何将 `sym-mcp` 发布到 PyPI。

## 0. 发布前检查

1. 确认包名可用：
```bash
pip index versions sym-mcp
```

2. 更新版本号（`pyproject.toml` 的 `project.version`）。

3. 执行测试：
```bash
PYTHONPATH=src pytest -q
```

## 1. 构建分发包

```bash
python -m pip install -U build
python -m build
```

产物在 `dist/` 目录下（`.whl` + `.tar.gz`）。

## 2. 校验元数据

```bash
python -m pip install -U twine
twine check dist/*
```

## 3. 上传到 TestPyPI（推荐先试）

```bash
twine upload --repository testpypi dist/*
```

## 4. 上传到 PyPI

```bash
twine upload dist/*
```

## 5. 安装与回归验证

```bash
pip install -U sym-mcp
sym-mcp
```

另开终端验证工具：

```bash
fastmcp list --command "sym-mcp"
fastmcp call --command "sym-mcp" --target sympy --input-json '{"code":"import sympy as sp\nx=sp.Symbol(\"x\")\nprint(sp.factor(x**2-1))"}'
```
