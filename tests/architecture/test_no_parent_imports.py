import ast
import unittest
from pathlib import Path


FAM_ROOT = Path(__file__).parents[2]
ACTIVE_ROOTS = (FAM_ROOT / "src", FAM_ROOT / "tools")
PARENT_MARKER = FAM_ROOT.parent / "PROTOTYPE_READ_ONLY.md"


class ParentPrototypeBoundaryTests(unittest.TestCase):
    def test_active_code_does_not_import_parent_rnf(self) -> None:
        violations: list[str] = []
        for root in ACTIVE_ROOTS:
            for path in root.rglob("*.py"):
                violations.extend(_parent_imports(path))
        self.assertEqual(violations, [], "parent imports found: " + ", ".join(violations))

    def test_read_only_marker_exists(self) -> None:
        self.assertTrue(PARENT_MARKER.is_file())
        marker = PARENT_MARKER.read_text(encoding="utf-8")
        self.assertIn("FAM_OS is the product codebase", marker)


def _parent_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    violations: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            violations.extend(
                _violation(path, node.lineno, alias.name)
                for alias in node.names
                if _is_parent(alias.name)
            )
        elif isinstance(node, ast.ImportFrom) and _is_parent(node.module or ""):
            violations.append(_violation(path, node.lineno, node.module or ""))
        elif _is_dynamic_parent_import(node):
            violations.append(_violation(path, node.lineno, "dynamic rnf import"))
    return violations


def _is_dynamic_parent_import(node: ast.AST) -> bool:
    if not isinstance(node, ast.Call) or not node.args:
        return False
    function = node.func
    name = function.id if isinstance(function, ast.Name) else getattr(function, "attr", "")
    value = node.args[0]
    return (
        name in {"__import__", "import_module"}
        and isinstance(value, ast.Constant)
        and isinstance(value.value, str)
        and _is_parent(value.value)
    )


def _is_parent(module: str) -> bool:
    return module == "rnf" or module.startswith("rnf.")


def _violation(path: Path, line: int, module: str) -> str:
    return f"{path.relative_to(FAM_ROOT)}:{line}:{module}"
