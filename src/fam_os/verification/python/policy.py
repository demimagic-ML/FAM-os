"""Trusted AST policy for generated Python candidates."""

import ast


ALLOWED_IMPORTS = frozenset(
    {
        "collections",
        "dataclasses",
        "functools",
        "heapq",
        "itertools",
        "math",
        "operator",
        "statistics",
        "typing",
    }
)

FORBIDDEN_CALLS = frozenset(
    {
        "__import__",
        "breakpoint",
        "compile",
        "delattr",
        "eval",
        "exec",
        "getattr",
        "globals",
        "help",
        "input",
        "locals",
        "open",
        "setattr",
        "vars",
    }
)


class PythonSafetyVisitor(ast.NodeVisitor):
    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name.split(".", 1)[0] not in ALLOWED_IMPORTS:
                raise ValueError(f"import is not allowed: {alias.name}")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = (node.module or "").split(".", 1)[0]
        if node.level or module not in ALLOWED_IMPORTS:
            raise ValueError(f"import is not allowed: {node.module}")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name) and node.func.id in FORBIDDEN_CALLS:
            raise ValueError(f"call is not allowed: {node.func.id}")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id == "__builtins__":
            raise ValueError("name is not allowed: __builtins__")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr.startswith("__"):
            raise ValueError(f"dunder attribute is not allowed: {node.attr}")
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        value = node.value
        if isinstance(value, str) and value.startswith("__") and value.endswith("__"):
            raise ValueError("dunder string access is not allowed")

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        _reject_decorators(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        _reject_decorators(node)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        _reject_decorators(node)
        self.generic_visit(node)


def sanitize_python_candidate(code: str) -> str:
    tree = ast.parse(code)
    PythonSafetyVisitor().visit(tree)
    retained = tuple(node for node in tree.body if isinstance(node, _RETAINED_NODES))
    if not any(isinstance(node, _DEFINITION_NODES) for node in retained):
        raise ValueError("candidate contains no function or class definition")
    sanitized = ast.Module(body=list(retained), type_ignores=[])
    ast.fix_missing_locations(sanitized)
    return ast.unparse(sanitized)


_DEFINITION_NODES = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
_RETAINED_NODES = (ast.Import, ast.ImportFrom, *_DEFINITION_NODES)


def _reject_decorators(
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
) -> None:
    if node.decorator_list:
        raise ValueError("decorators are not allowed in verified candidate code")
