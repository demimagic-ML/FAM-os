import json
import unittest
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).parents[2]
CONNECTOR = ROOT / "connectors/vscode"
SOURCE = CONNECTOR / "src"


class VsCodeConnectorBoundaryTests(unittest.TestCase):
    def test_modules_are_small_and_vscode_sdk_is_confined_to_editor_adapter(self):
        allowed_vscode = {
            "extension.ts", "provider.ts", "observations.ts", "workspace-actions.ts",
        }
        violations = []
        for path in SOURCE.rglob("*.ts"):
            lines = path.read_text().splitlines()
            if len(lines) > 300:
                violations.append(f"{path.relative_to(SOURCE)}:{len(lines)}")
            if 'from "vscode"' in "\n".join(lines) and path.name not in allowed_vscode:
                violations.append(f"{path.relative_to(SOURCE)}:vscode")
        self.assertEqual([], violations)

    def test_sdk_has_no_model_mcp_process_network_or_shell_escape(self):
        content = "\n".join(path.read_text() for path in (SOURCE / "sdk").glob("*.ts"))
        for forbidden in (
            "child_process", "ollama", "llama", "@modelcontextprotocol", "http.request",
            "https.request", "fetch(", "eval(", "exec(", "spawn(",
        ):
            self.assertNotIn(forbidden, content)

    def test_manifest_exposes_only_narrow_editor_capabilities(self):
        registration = (SOURCE / "editor/registration.ts").read_text()
        for capability in (
            "vscode.editor.active", "vscode.editor.selection",
            "vscode.diagnostics.active", "vscode.workspace_edit.apply",
            "vscode.workspace_edit.undo",
        ):
            self.assertIn(capability, registration)
        for forbidden in ("terminal", "install_extension", "source_control", "network"):
            self.assertNotIn(f'"vscode.{forbidden}', registration)
        package = json.loads((CONNECTOR / "package.json").read_text())
        self.assertEqual({}, package.get("dependencies", {}))
        self.assertEqual({"@types/node", "@types/vscode", "typescript"}, set(package["devDependencies"]))

    def test_connector_owned_schemas_are_valid_and_closed(self):
        paths = tuple((CONNECTOR / "schemas").glob("*.schema.json"))
        self.assertEqual(8, len(paths))
        for path in paths:
            schema = json.loads(path.read_text())
            Draft202012Validator.check_schema(schema)
            branches = schema.get("oneOf", (schema,))
            self.assertTrue(all(branch.get("additionalProperties") is False for branch in branches))

    def test_workspace_edits_are_revision_bound_reversible_and_postchecked(self):
        action = (SOURCE / "editor/workspace-actions.ts").read_text()
        plan = (SOURCE / "editor/edit-plan.ts").read_text()
        for required in (
            "documentRevision", "vscode.workspace.applyEdit", "document.hash",
            "document.version", "ReversalStore", "preconditionResult",
            "verifiedOrPostcondition",
        ):
            self.assertIn(required, action + plan)


if __name__ == "__main__":
    unittest.main()
