import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
FILES = (
    "application_discovery.py", "desktop_entries.py", "desktop_environment.py",
    "processes.py", "x11_windows.py",
)


class LinuxApplicationDiscoveryBoundaryTests(unittest.TestCase):
    def test_discovery_has_no_action_model_or_supervisor_imports(self):
        violations = []
        for filename in FILES:
            path = ROOT / "src/fam_os/adapters/linux" / filename
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                for name in _imports(node):
                    if name.startswith((
                        "fam_os.core", "fam_os.experts", "fam_os.routing",
                        "fam_os.supervisor", "fam_os.verification", "fam_os.adapters.mcp",
                    )):
                        violations.append(f"{filename}:{node.lineno}:{name}")
        self.assertEqual([], violations)


def _imports(node):
    if isinstance(node, ast.Import):
        return tuple(alias.name for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        return (node.module or "",)
    return ()


if __name__ == "__main__":
    unittest.main()
