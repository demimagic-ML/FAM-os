import unittest
from types import SimpleNamespace

from fam_os.applications import WORKSPACE_PATCH_CAPABILITY
from fam_os.core.production.workspace_parameters import (
    WorkspacePatchScopeUnsupported, bind_workspace_patch_parameters,
    workspace_parameter_feedback,
)


class WorkspaceParameterBindingTests(unittest.TestCase):
    def test_explicit_unavailable_object_is_not_treated_as_an_action(self):
        with self.assertRaisesRegex(
            WorkspacePatchScopeUnsupported, "needs a new file",
        ):
            bind_workspace_patch_parameters(
                WORKSPACE_PATCH_CAPABILITY,
                {"unavailable_reason": "needs a new file"}, (),
            )

    def test_empty_or_non_text_changes_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "one to four changes"):
            bind_workspace_patch_parameters(
                WORKSPACE_PATCH_CAPABILITY, {"plan": ["Edit"], "changes": []}, (),
            )
        observations = (SimpleNamespace(payload={
            "documents": [{"path": "app.py", "sha256": "b" * 64}],
        }),)
        with self.assertRaisesRegex(ValueError, "complete UTF-8 text"):
            bind_workspace_patch_parameters(
                WORKSPACE_PATCH_CAPABILITY,
                {"plan": ["Edit"], "changes": [{"path": "app.py", "content": 3}]},
                observations,
            )

    def test_repair_feedback_contains_error_and_authorized_paths(self):
        observations = (SimpleNamespace(payload={
            "documents": [{"path": "src/app.py", "sha256": "c" * 64}],
        }),)
        feedback = workspace_parameter_feedback(
            ValueError("candidate is not JSON"), observations, escalation=False,
        )
        self.assertIn("[workspace-parameter-repair]", feedback)
        self.assertIn("candidate is not JSON", feedback)
        self.assertIn("- src/app.py", feedback)

    def test_model_cannot_name_an_unobserved_file_or_supply_its_own_hash(self):
        observations = (SimpleNamespace(payload={
            "documents": [{"path": "src/app.py", "sha256": "a" * 64}],
        }),)

        with self.assertRaisesRegex(ValueError, "only an observed document"):
            bind_workspace_patch_parameters(
                WORKSPACE_PATCH_CAPABILITY,
                {
                    "plan": ["Change a hidden file."],
                    "changes": [{"path": ".env", "content": "SECRET=changed\n"}],
                },
                observations,
            )

        bound = bind_workspace_patch_parameters(
            WORKSPACE_PATCH_CAPABILITY,
            {
                "plan": ["Change the observed file."],
                "changes": [{"path": "src/app.py", "content": "VALUE = 2\n"}],
            },
            observations,
        )
        self.assertEqual("a" * 64, bound["changes"][0]["expected_sha256"])
        self.assertEqual(
            [
                "Update observed file src/app.py using the approved diff.",
                "Re-observe and verify every changed file after the atomic write.",
            ],
            bound["plan"],
        )
        self.assertEqual(
            {"path", "content", "expected_sha256"},
            set(bound["changes"][0]),
        )


if __name__ == "__main__":
    unittest.main()
