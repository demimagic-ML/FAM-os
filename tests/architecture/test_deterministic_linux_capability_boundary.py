import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
FILES = (
    "bounded_command.py", "dbus_calls.py", "desktop_portal.py",
    "deterministic_catalog.py", "deterministic_result.py", "mime_types.py",
    "scoped_files.py", "tools.py",
)


class DeterministicLinuxCapabilityBoundaryTests(unittest.TestCase):
    def test_adapters_do_not_import_core_models_or_supervisor(self):
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

    def test_only_bounded_command_module_may_spawn_processes(self):
        violations = []
        for filename in FILES:
            if filename == "bounded_command.py":
                continue
            path = ROOT / "src/fam_os/adapters/linux" / filename
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                if any(name == "subprocess" for name in _imports(node)):
                    violations.append(filename)
        self.assertEqual([], violations)


def _imports(node):
    if isinstance(node, ast.Import):
        return tuple(alias.name for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        return (node.module or "",)
    return ()


if __name__ == "__main__":
    unittest.main()
