import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
ADAPTER = ROOT / "src/fam_os/adapters/linux/accessibility"


class LinuxAccessibilityBoundaryTests(unittest.TestCase):
    def test_adapter_does_not_import_core_models_or_supervisor(self):
        violations = []
        for path in ADAPTER.glob("*.py"):
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                for name in _imports(node):
                    if name.startswith((
                        "fam_os.core", "fam_os.experts", "fam_os.routing",
                        "fam_os.supervisor", "fam_os.verification", "fam_os.adapters.mcp",
                    )):
                        violations.append(f"{path.name}:{node.lineno}:{name}")
        self.assertEqual([], violations)

    def test_gi_is_confined_to_concrete_provider_and_no_module_spawns_processes(self):
        violations = []
        for path in ADAPTER.glob("*.py"):
            tree = ast.parse(path.read_text(), filename=str(path))
            imports = [name for node in ast.walk(tree) for name in _imports(node)]
            if path.name != "atspi.py" and any(name == "gi" or name.startswith("gi.") for name in imports):
                violations.append(f"{path.name}:gi")
            if any(name == "subprocess" for name in imports):
                violations.append(f"{path.name}:subprocess")
        self.assertEqual([], violations)

    def test_provider_neutral_application_contract_does_not_import_adapters(self):
        path = ROOT / "src/fam_os/applications/accessibility.py"
        tree = ast.parse(path.read_text(), filename=str(path))
        imports = [name for node in ast.walk(tree) for name in _imports(node)]
        self.assertFalse(any(name.startswith("fam_os.adapters") for name in imports))


def _imports(node):
    if isinstance(node, ast.Import):
        return tuple(alias.name for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        return (node.module or "",)
    return ()


if __name__ == "__main__":
    unittest.main()
