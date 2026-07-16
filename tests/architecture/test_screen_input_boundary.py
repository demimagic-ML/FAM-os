import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
ADAPTER = ROOT / "src/fam_os/adapters/linux/screen_input"


class ScreenInputBoundaryTests(unittest.TestCase):
    def test_adapter_cannot_reach_core_models_supervisor_or_mcp(self):
        forbidden = (
            "fam_os.core", "fam_os.experts", "fam_os.routing", "fam_os.supervisor",
            "fam_os.verification", "fam_os.adapters.mcp",
        )
        violations = []
        for path in ADAPTER.glob("*.py"):
            for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
                violations += [
                    f"{path.name}:{node.lineno}:{name}" for name in _imports(node)
                    if name.startswith(forbidden)
                ]
        self.assertEqual([], violations)

    def test_provider_specific_imports_are_confined_and_no_module_spawns_directly(self):
        violations = []
        for path in ADAPTER.glob("*.py"):
            tree = ast.parse(path.read_text(), filename=str(path))
            imports = [name for node in ast.walk(tree) for name in _imports(node)]
            if path.name != "pillow_capture.py" and any(name == "PIL" or name.startswith("PIL.") for name in imports):
                violations.append(f"{path.name}:PIL")
            if path.name != "xtest_input.py" and "ctypes" in imports:
                violations.append(f"{path.name}:ctypes")
            if "subprocess" in imports:
                violations.append(f"{path.name}:subprocess")
        self.assertEqual([], violations)

    def test_provider_neutral_contract_does_not_import_adapters(self):
        path = ROOT / "src/fam_os/applications/screen_input.py"
        imports = [
            name for node in ast.walk(ast.parse(path.read_text(), filename=str(path)))
            for name in _imports(node)
        ]
        self.assertFalse(any(name.startswith("fam_os.adapters") for name in imports))


def _imports(node):
    if isinstance(node, ast.Import):
        return tuple(alias.name for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        return (node.module or "",)
    return ()


if __name__ == "__main__":
    unittest.main()
