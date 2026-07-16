import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
LIFECYCLE_ROOT = ROOT / "src/fam_os/core/lifecycle"
GENERIC_FILES = ("contracts.py", "ports.py", "repository.py", "service.py")
FORBIDDEN = (
    "fam_os.adapters", "fam_os.applications", "fam_os.experts", "fam_os.memory",
    "fam_os.routing.inference", "fam_os.scheduler", "fam_os.supervisor",
    "fam_os.verification",
)


class CorePlanLifecycleBoundaryTests(unittest.TestCase):
    def test_state_machine_has_no_provider_or_external_boundary_imports(self):
        violations = []
        for name in GENERIC_FILES:
            path = LIFECYCLE_ROOT / name
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
