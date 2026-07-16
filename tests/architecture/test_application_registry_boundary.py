import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
TARGET = ROOT / "src/fam_os/applications/registry.py"
FORBIDDEN = (
    "fam_os.adapters", "fam_os.core", "fam_os.routing", "fam_os.supervisor",
    "fam_os.verification",
)


class ApplicationRegistryBoundaryTests(unittest.TestCase):
    def test_registry_is_transport_and_core_independent(self):
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
