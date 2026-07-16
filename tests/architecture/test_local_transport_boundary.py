import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
TRANSPORT = ROOT / "src/fam_os/applications/transport"
FORBIDDEN = (
    "fam_os.adapters", "fam_os.core", "fam_os.experts", "fam_os.routing",
    "fam_os.supervisor", "fam_os.verification",
)


class LocalTransportBoundaryTests(unittest.TestCase):
    def test_transport_primitives_have_no_policy_or_provider_imports(self):
        violations = []
        for path in TRANSPORT.glob("*.py"):
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
