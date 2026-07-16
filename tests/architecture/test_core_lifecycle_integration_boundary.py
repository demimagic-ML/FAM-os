import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
TARGET = ROOT / "tests/integration/test_core_lifecycle_end_to_end.py"
FORBIDDEN = ("fam_os.adapters", "fam_os.routing.inference", "fam_os.supervisor")


class CoreLifecycleIntegrationBoundaryTests(unittest.TestCase):
    def test_end_to_end_matrix_uses_only_fakes_and_domain_services(self):
        tree = ast.parse(TARGET.read_text(), filename=str(TARGET))
        violations = []
        for node in ast.walk(tree):
            for name in _imports(node):
                if name.startswith(FORBIDDEN):
                    violations.append(f"{node.lineno}:{name}")
        self.assertEqual([], violations)


def _imports(node):
    if isinstance(node, ast.Import):
        return tuple(alias.name for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        return (node.module or "",)
    return ()


if __name__ == "__main__":
    unittest.main()
