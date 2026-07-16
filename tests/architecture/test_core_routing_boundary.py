import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
ROUTING_ROOT = ROOT / "src/fam_os/core/routing"
FORBIDDEN = (
    "fam_os.adapters", "fam_os.applications", "fam_os.experts", "fam_os.memory",
    "fam_os.routing.inference", "fam_os.scheduler", "fam_os.supervisor",
    "fam_os.verification",
)


class CoreRoutingBoundaryTests(unittest.TestCase):
    def test_lifecycle_depends_only_on_routing_contract_and_port(self):
        violations = []
        for path in ROUTING_ROOT.rglob("*.py"):
            violations.extend(_violations(path))
        self.assertEqual([], violations)


def _violations(path):
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    found = []
    for node in ast.walk(tree):
        for name in _imports(node):
            if name.startswith(FORBIDDEN):
                found.append(f"{path.relative_to(ROOT)}:{node.lineno}:{name}")
    return found


def _imports(node):
    if isinstance(node, ast.Import):
        return tuple(alias.name for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        return (node.module or "",)
    return ()


if __name__ == "__main__":
    unittest.main()
