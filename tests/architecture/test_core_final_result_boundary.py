import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
FILES = tuple((ROOT / "src/fam_os/core/lifecycle").glob("final_*.py"))
FORBIDDEN = ("fam_os.adapters", "fam_os.applications", "fam_os.experts", "fam_os.scheduler", "fam_os.supervisor")


class CoreFinalResultBoundaryTests(unittest.TestCase):
    def test_final_policy_depends_only_on_trusted_contracts_and_registry(self):
        violations = []
        for path in FILES:
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                for name in _imports(node):
                    if name.startswith(FORBIDDEN):
                        violations.append(f"{path.name}:{node.lineno}:{name}")
        self.assertEqual([], violations)


def _imports(node):
    if isinstance(node, ast.Import):
        return tuple(alias.name for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        return (node.module or "",)
    return ()


if __name__ == "__main__":
    unittest.main()
