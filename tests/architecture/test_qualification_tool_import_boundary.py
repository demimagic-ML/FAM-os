"""Qualification tools use one import identity under the repository package."""

import ast
import re
import unittest
from pathlib import Path


_LEGACY_PHASE_IMPORT = re.compile(r"^phase\d+(?:_|$)")


class QualificationToolImportBoundaryTests(unittest.TestCase):
    def test_phase_tools_never_import_sibling_packages_as_top_level_modules(self):
        repository = Path(__file__).resolve().parents[2]
        violations: list[str] = []
        for path in sorted((repository / "tools").rglob("*.py")):
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
            for node in ast.walk(tree):
                names = _imported_modules(node)
                for name in names:
                    if _LEGACY_PHASE_IMPORT.match(name):
                        violations.append(f"{path.relative_to(repository)}:{node.lineno} {name}")
        self.assertEqual([], violations)


def _imported_modules(node: ast.AST) -> tuple[str, ...]:
    if isinstance(node, ast.Import):
        return tuple(alias.name for alias in node.names)
    if isinstance(node, ast.ImportFrom) and node.module is not None:
        return (node.module,)
    return ()


if __name__ == "__main__":
    unittest.main()
