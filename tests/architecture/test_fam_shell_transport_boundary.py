import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
ADAPTER = ROOT / "src/fam_os/adapters/shell"


class FamShellTransportBoundaryTests(unittest.TestCase):
    def test_adapter_does_not_own_core_policy_models_or_supervision(self):
        forbidden = (
            "fam_os.core.admission", "fam_os.core.lifecycle", "fam_os.experts",
            "fam_os.routing", "fam_os.scheduler", "fam_os.supervisor",
            "fam_os.verification", "fam_os.adapters.ollama",
        )
        violations = []
        for path in ADAPTER.glob("*.py"):
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                for name in _imports(node):
                    if name.startswith(forbidden):
                        violations.append(f"{path.name}:{node.lineno}:{name}")
        self.assertEqual([], violations)

    def test_adapter_never_spawns_processes(self):
        violations = []
        for path in ADAPTER.glob("*.py"):
            tree = ast.parse(path.read_text(), filename=str(path))
            if any(name == "subprocess" for node in ast.walk(tree) for name in _imports(node)):
                violations.append(path.name)
        self.assertEqual([], violations)


def _imports(node):
    if isinstance(node, ast.Import):
        return tuple(alias.name for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        return (node.module or "",)
    return ()


if __name__ == "__main__":
    unittest.main()
