import ast
import unittest
from pathlib import Path


ROOT = Path(__file__).parents[2]
LIFECYCLE = ROOT / "src/fam_os/core/lifecycle"


class CoreActionExecutionBoundaryTests(unittest.TestCase):
    def test_execution_policy_has_no_adapter_model_supervisor_or_shell_imports(self):
        names = (
            "action_execution_service.py", "action_execution_validation.py",
            "action_result_policy.py", "action_audit_policy.py",
        )
        forbidden = (
            "fam_os.adapters", "fam_os.experts", "fam_os.routing",
            "fam_os.supervisor", "fam_os.shell",
        )
        violations = []
        for name in names:
            path = LIFECYCLE / name
            for node in ast.walk(ast.parse(path.read_text(), filename=str(path))):
                violations += [
                    f"{name}:{node.lineno}:{value}" for value in _imports(node)
                    if value.startswith(forbidden)
                ]
        self.assertEqual([], violations)

    def test_application_audit_contract_does_not_import_core_or_adapters(self):
        paths = (
            ROOT / "src/fam_os/applications/action_audit.py",
            ROOT / "src/fam_os/applications/action_audit_ports.py",
        )
        imports = [
            value for path in paths
            for node in ast.walk(ast.parse(path.read_text(), filename=str(path)))
            for value in _imports(node)
        ]
        self.assertFalse(any(value.startswith(("fam_os.core", "fam_os.adapters")) for value in imports))

    def test_jsonl_audit_adapter_has_no_core_or_supervisor_dependency(self):
        path = ROOT / "src/fam_os/adapters/audit/application_jsonl.py"
        imports = [
            value for node in ast.walk(ast.parse(path.read_text(), filename=str(path)))
            for value in _imports(node)
        ]
        self.assertFalse(any(value.startswith(("fam_os.core", "fam_os.supervisor")) for value in imports))


def _imports(node):
    if isinstance(node, ast.Import):
        return tuple(alias.name for alias in node.names)
    if isinstance(node, ast.ImportFrom):
        return (node.module or "",)
    return ()


if __name__ == "__main__":
    unittest.main()
