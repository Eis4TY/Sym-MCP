# Publishing Guide (PyPI)

本文档描述如何将 `sym-mcp` 发布到 PyPI。

## 0. 发布前检查

1. 确认包名可用：
```bash
pip index versions sym-mcp
```

2. 版本号由 Git Tag 自动生成（`setuptools-scm`），不再手改 `pyproject.toml`。
   - 例如：`v0.1.1` -> 发布版本 `0.1.1`
   - 非 tag 构建会得到开发版号（仅用于本地/CI）

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

## 使用 GitHub Trusted Publisher（推荐）

仓库已包含工作流：

- `.github/workflows/pypi-publish.yml`

发布方式：

1. 在 PyPI 项目中创建 Trusted Publisher，填写：
   - Owner: `Eis4TY`
   - Repository: `Sym-MCP`
   - Workflow: `pypi-publish.yml`
   - Environment: `pypi`

2. 推送版本标签触发发布（版本自动从 tag 推导）：

```bash
git tag v0.1.1
git push origin v0.1.1
```

3. GitHub Actions 会自动完成：
   - 构建
   - `twine check`
   - OIDC 发布到 PyPI
