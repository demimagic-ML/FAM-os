import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
SHELL = ROOT / "src/fam_os/shell"


class FamShellBoundaryTests(unittest.TestCase):
    def test_shell_is_an_unprivileged_client_not_a_policy_or_runtime_owner(self):
        forbidden = (
            "fam_os.adapters", "fam_os.experts", "fam_os.routing",
            "fam_os.scheduler", "fam_os.supervisor", "fam_os.verification",
            "fam_os.core.admission", "fam_os.core.lifecycle",
        )
        violations = []
        for path in SHELL.glob("*.py"):
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                for name in _imports(node):
                    if name.startswith(forbidden):
                        violations.append(f"{path.name}:{node.lineno}:{name}")
        self.assertEqual([], violations)

    def test_shell_does_not_spawn_processes_or_own_model_clients(self):
        forbidden = {"subprocess", "ollama", "llama_cpp", "torch"}
        violations = []
        for path in SHELL.glob("*.py"):
            tree = ast.parse(path.read_text(), filename=str(path))
            imports = {name for node in ast.walk(tree) for name in _imports(node)}
            if imports & forbidden:
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
