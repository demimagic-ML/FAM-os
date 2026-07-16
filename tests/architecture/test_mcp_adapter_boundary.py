import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
MCP_ADAPTER = ROOT / "src/fam_os/adapters/mcp"


class McpAdapterBoundaryTests(unittest.TestCase):
    def test_sdk_import_is_confined_and_core_model_supervisor_are_absent(self):
        violations = []
        for path in MCP_ADAPTER.glob("*.py"):
            tree = ast.parse(path.read_text(), filename=str(path))
            for node in ast.walk(tree):
                for name in _imports(node):
                    if name.startswith("mcp") and path.name != "sdk.py":
                        violations.append(f"SDK import outside sdk.py: {path.name}:{node.lineno}")
                    if name.startswith((
                        "fam_os.core", "fam_os.experts", "fam_os.routing",
                        "fam_os.supervisor", "fam_os.verification",
                    )):
                        violations.append(f"policy import: {path.name}:{node.lineno}:{name}")
        self.assertEqual([], violations)


def _imports(node):
    if isinstance(node, ast.Import):
        return tuple(alias.name for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        return (node.module or "",)
    return ()


if __name__ == "__main__":
    unittest.main()
