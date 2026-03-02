from __future__ import annotations

import ast
from dataclasses import dataclass


ALLOWED_MODULES = {"sympy", "math"}
BLOCKED_NAMES = {
    "eval",
    "exec",
    "open",
    "compile",
    "input",
    "globals",
    "locals",
    "vars",
    "getattr",
    "setattr",
    "delattr",
    "__import__",
    "help",
    "dir",
    "type",
    "super",
}
BLOCKED_ROOT_NAMES = {"os", "sys", "subprocess", "pathlib", "socket", "importlib", "builtins"}

ALLOWED_NODES = {
    ast.Module,
    ast.Expr,
    ast.Assign,
    ast.AugAssign,
    ast.Name,
    ast.Load,
    ast.Store,
    ast.Call,
    ast.BinOp,
    ast.UnaryOp,
    ast.Compare,
    ast.BoolOp,
    ast.If,
    ast.For,
    ast.While,
    ast.Break,
    ast.Continue,
    ast.Pass,
    ast.Return,
    ast.List,
    ast.Tuple,
    ast.Dict,
    ast.Set,
    ast.Subscript,
    ast.Slice,
    ast.Constant,
    ast.Import,
    ast.ImportFrom,
    ast.alias,
    ast.FunctionDef,
    ast.arguments,
    ast.arg,
    ast.keyword,
    ast.IfExp,
    ast.ListComp,
    ast.SetComp,
    ast.DictComp,
    ast.GeneratorExp,
    ast.comprehension,
    ast.Attribute,
    ast.Try,
    ast.ExceptHandler,
    ast.Raise,
    ast.Assert,
    ast.Lambda,
    ast.NamedExpr,
    ast.JoinedStr,
    ast.FormattedValue,
    ast.Delete,
    ast.With,
    ast.withitem,
    ast.Starred,
    ast.And,
    ast.Or,
    ast.Not,
    ast.Add,
    ast.Sub,
    ast.Mult,
    ast.Div,
    ast.FloorDiv,
    ast.Mod,
    ast.Pow,
    ast.MatMult,
    ast.USub,
    ast.UAdd,
    ast.Eq,
    ast.NotEq,
    ast.Lt,
    ast.LtE,
    ast.Gt,
    ast.GtE,
    ast.Is,
    ast.IsNot,
    ast.In,
    ast.NotIn,
}


@dataclass(frozen=True)
class GuardResult:
    ok: bool
    message: str = ""


class SecurityViolation(ValueError):
    """Code failed AST security validation."""


def validate_code(code: str) -> GuardResult:
    try:
        tree = ast.parse(code, mode="exec")
    except SyntaxError as exc:
        return GuardResult(ok=False, message=f"语法错误: 第 {exc.lineno} 行, {exc.msg}")

    try:
        _AstValidator().visit(tree)
    except SecurityViolation as exc:
        return GuardResult(ok=False, message=str(exc))

    return GuardResult(ok=True)


class _AstValidator(ast.NodeVisitor):
    def generic_visit(self, node: ast.AST) -> None:
        if type(node) not in ALLOWED_NODES:
            raise SecurityViolation(f"安全拦截: 不允许的语法节点 `{type(node).__name__}`。")
        super().generic_visit(node)

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            root = alias.name.split(".")[0]
            if root not in ALLOWED_MODULES:
                raise SecurityViolation(f"安全拦截: 禁止导入模块 `{alias.name}`。")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = (node.module or "").split(".")[0]
        if module not in ALLOWED_MODULES:
            raise SecurityViolation(f"安全拦截: 禁止从模块 `{node.module}` 导入。")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        name = node.id
        self._check_identifier(name, node.lineno)
        if name in BLOCKED_ROOT_NAMES:
            raise SecurityViolation(f"安全拦截: 第 {node.lineno} 行禁止访问 `{name}`。")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        self._check_identifier(node.attr, node.lineno)
        root = _root_name(node)
        if root in BLOCKED_ROOT_NAMES:
            raise SecurityViolation(f"安全拦截: 第 {node.lineno} 行禁止访问 `{root}`。")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        func_name = _callable_name(node.func)
        if func_name and func_name in BLOCKED_NAMES:
            raise SecurityViolation(f"安全拦截: 第 {node.lineno} 行禁止调用 `{func_name}`。")
        self.generic_visit(node)

    @staticmethod
    def _check_identifier(name: str, lineno: int) -> None:
        if "__" in name:
            raise SecurityViolation(f"安全拦截: 第 {lineno} 行出现双下划线标识符。")


def _root_name(node: ast.AST) -> str | None:
    cur = node
    while isinstance(cur, ast.Attribute):
        cur = cur.value
    if isinstance(cur, ast.Name):
        return cur.id
    return None


def _callable_name(node: ast.AST) -> str | None:
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    return None
