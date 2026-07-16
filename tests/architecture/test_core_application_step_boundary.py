import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
FILES = tuple((ROOT / "src/fam_os/core/lifecycle").glob("application_*.py"))
FORBIDDEN = (
    "fam_os.adapters", "fam_os.experts", "fam_os.memory", "fam_os.scheduler",
    "fam_os.supervisor", "fam_os.verification", "fam_os.routing.inference",
)


class CoreApplicationStepBoundaryTests(unittest.TestCase):
    def test_application_steps_use_contracts_and_ports_not_providers(self):
        violations = []
        for path in FILES:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
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
