"""Restricted verifier process for evaluator-owned Python test cases."""

from __future__ import annotations

import ast
import json
import re
import resource
import sys


_MAX_CANDIDATE_CHARACTERS = 131_072
_MAX_TEST_CHARACTERS = 65_536
_PYTHON_FENCE = re.compile(
    r"```(?:python|py)?\s*\n(.*?)```", flags=re.DOTALL | re.IGNORECASE,
)
_ALLOWED_IMPORTS = frozenset({
    "collections", "dataclasses", "functools", "heapq", "itertools",
    "math", "operator", "statistics", "typing",
})
_FORBIDDEN_CALLS = frozenset({
    "__import__", "breakpoint", "compile", "delattr", "eval", "exec",
    "getattr", "globals", "help", "input", "locals", "open", "setattr",
    "vars",
})


class _SafetyVisitor(ast.NodeVisitor):
    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            if alias.name.split(".", 1)[0] not in _ALLOWED_IMPORTS:
                raise ValueError("candidate import is not allowed")
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = (node.module or "").split(".", 1)[0]
        if node.level or module not in _ALLOWED_IMPORTS:
            raise ValueError("candidate import is not allowed")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> None:
        if isinstance(node.func, ast.Name) and node.func.id in _FORBIDDEN_CALLS:
            raise ValueError("candidate call is not allowed")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> None:
        if node.id == "__builtins__":
            raise ValueError("candidate builtins access is not allowed")
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> None:
        if node.attr.startswith("__"):
            raise ValueError("candidate dunder access is not allowed")
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant) -> None:
        value = node.value
        if isinstance(value, str) and value.startswith("__") and value.endswith("__"):
            raise ValueError("candidate dunder string is not allowed")

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        _reject_decorators(node)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        _reject_decorators(node)
        self.generic_visit(node)

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        _reject_decorators(node)
        self.generic_visit(node)


def verify_document(document: object) -> bool:
    if not isinstance(document, dict) or set(document) != {"candidate", "tests"}:
        raise ValueError("Python evaluation request fields are invalid")
    candidate = _bounded_text(document, "candidate", _MAX_CANDIDATE_CHARACTERS)
    tests = _bounded_text(document, "tests", _MAX_TEST_CHARACTERS)
    source = _sanitize(_extract(candidate))
    namespace = {"__name__": "__fam_evaluation__"}
    exec(compile(source, "<candidate>", "exec"), namespace, namespace)
    exec(compile(tests, "<evaluator-tests>", "exec"), namespace, namespace)
    return True


def main() -> int:
    _limits()
    try:
        document = json.loads(sys.stdin.read(_MAX_CANDIDATE_CHARACTERS + _MAX_TEST_CHARACTERS + 1024))
        passed = verify_document(document)
    except BaseException:
        passed = False
    sys.stdout.write(json.dumps({"passed": passed}, separators=(",", ":")) + "\n")
    return 0


def _extract(content: str) -> str:
    for candidate in _PYTHON_FENCE.findall(content) or (content,):
        source = candidate.strip()
        if not source:
            continue
        try:
            ast.parse(source)
        except SyntaxError:
            continue
        return source
    raise ValueError("model output contains no syntactically valid Python")


def _sanitize(source: str) -> str:
    tree = ast.parse(source)
    _SafetyVisitor().visit(tree)
    retained_types = (ast.Import, ast.ImportFrom, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    retained: list[ast.stmt] = [
        node for node in tree.body if isinstance(node, retained_types)
    ]
    definitions = (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
    if not any(isinstance(node, definitions) for node in retained):
        raise ValueError("candidate contains no definition")
    sanitized = ast.Module(body=retained, type_ignores=[])
    ast.fix_missing_locations(sanitized)
    return ast.unparse(sanitized)


def _reject_decorators(
    node: ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef,
) -> None:
    if node.decorator_list:
        raise ValueError("candidate decorators are not allowed")


def _bounded_text(document: dict, name: str, maximum: int) -> str:
    value = document.get(name)
    if not isinstance(value, str) or not value or len(value) > maximum:
        raise ValueError("Python evaluation text is invalid")
    return value


def _limits() -> None:
    resource.setrlimit(resource.RLIMIT_CPU, (3, 3))
    resource.setrlimit(resource.RLIMIT_AS, (512 * 1024**2, 512 * 1024**2))
    resource.setrlimit(resource.RLIMIT_FSIZE, (0, 0))
    resource.setrlimit(resource.RLIMIT_NOFILE, (32, 32))
    resource.setrlimit(resource.RLIMIT_NPROC, (1, 1))


if __name__ == "__main__":
    raise SystemExit(main())
