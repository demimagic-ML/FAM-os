import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]


class McpIngressBoundaryTests(unittest.TestCase):
    def test_core_ingress_has_no_adapter_or_provider_imports(self):
        self.assertEqual([], _violations(
            ROOT / "src/fam_os/core/ingress", ("fam_os.adapters", "mcp")
        ))

    def test_mcp_ingress_cannot_import_policy_bypass_layers(self):
        self.assertEqual([], _violations(
            ROOT / "src/fam_os/adapters/mcp/ingress",
            ("fam_os.experts", "fam_os.routing", "fam_os.supervisor",
             "fam_os.verification", "fam_os.applications.transport"),
        ))


def _violations(directory, forbidden):
    violations = []
    for path in directory.glob("*.py"):
        tree = ast.parse(path.read_text(), filename=str(path))
        for node in ast.walk(tree):
            for name in _imports(node):
                if name.startswith(forbidden):
                    violations.append(f"{path.name}:{node.lineno}:{name}")
    return violations


def _imports(node):
    if isinstance(node, ast.Import):
        return tuple(alias.name for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        return (node.module or "",)
    return ()


if __name__ == "__main__":
    unittest.main()
