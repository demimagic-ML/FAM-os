import unittest

from fam_os.applications import (
    ApplicationAuthority,
    ApplicationIdentity,
    ApplicationInstance,
    CapabilityDescriptor,
    CapabilityKind,
    CapabilityRegistryEntry,
    ConfirmationPolicy,
    Reversibility,
)


class ApplicationIdentityTests(unittest.TestCase):
    def test_describes_vscode_instance_without_vscode_types(self) -> None:
        identity = ApplicationIdentity(
            "com.microsoft.vscode", "Visual Studio Code", "Microsoft", "1.0"
        )
        instance = ApplicationInstance(
            "vscode-instance-1",
            identity,
            "fam-vscode-connector",
            process_id=42,
            workspace_uris=("file:///workspace/fam-os",),
        )
        self.assertEqual(instance.application.application_id, "com.microsoft.vscode")
        self.assertEqual(instance.workspace_uris, ("file:///workspace/fam-os",))

    def test_rejects_invalid_instance_process(self) -> None:
        identity = ApplicationIdentity("com.microsoft.vscode", "VS Code")
        with self.assertRaisesRegex(ValueError, "process_id"):
            ApplicationInstance("vscode-1", identity, "connector-1", process_id=0)


class CapabilityDescriptorTests(unittest.TestCase):
    def test_observation_requires_observe_authority(self) -> None:
        with self.assertRaisesRegex(ValueError, "observe authority"):
            CapabilityDescriptor(
                "vscode.editor.active",
                "Observe active editor",
                "Return active editor state",
                CapabilityKind.OBSERVATION,
                ApplicationAuthority.MODIFY,
                "vscode.editor.active.input.v1",
                "vscode.editor.active.output.v1",
            )

    def test_action_requires_deterministic_postcondition(self) -> None:
        with self.assertRaisesRegex(ValueError, "postconditions"):
            CapabilityDescriptor(
                "vscode.workspace_edit.apply",
                "Apply workspace edit",
                "Apply a previewed edit",
                CapabilityKind.ACTION,
                ApplicationAuthority.MODIFY,
                "vscode.workspace_edit.input.v1",
                "vscode.workspace_edit.output.v1",
                Reversibility.REVERSIBLE,
                ConfirmationPolicy.WHEN_REQUIRED,
            )

    def test_irreversible_action_requires_confirmation(self) -> None:
        with self.assertRaisesRegex(ValueError, "always require confirmation"):
            CapabilityDescriptor(
                "vscode.command.external",
                "External command",
                "Run an irreversible external command",
                CapabilityKind.ACTION,
                ApplicationAuthority.EXECUTE,
                "vscode.command.input.v1",
                "vscode.command.output.v1",
                Reversibility.IRREVERSIBLE,
                ConfirmationPolicy.WHEN_REQUIRED,
                ("command.exit_code",),
            )

    def test_registry_entry_retains_resource_scope(self) -> None:
        capability = _workspace_edit_capability()
        entry = CapabilityRegistryEntry(
            "vscode-1:workspace-edit",
            "fam-vscode-connector",
            "vscode-instance-1",
            "com.microsoft.vscode",
            capability,
            ("file:///workspace/fam-os",),
        )
        self.assertEqual(entry.capability_id, "vscode.workspace_edit.apply")


def _workspace_edit_capability() -> CapabilityDescriptor:
    return CapabilityDescriptor(
        "vscode.workspace_edit.apply",
        "Apply workspace edit",
        "Apply a previewed and reversible workspace edit",
        CapabilityKind.ACTION,
        ApplicationAuthority.MODIFY,
        "vscode.workspace_edit.input.v1",
        "vscode.workspace_edit.output.v1",
        Reversibility.REVERSIBLE,
        ConfirmationPolicy.WHEN_REQUIRED,
        ("document.hash", "workspace.tests"),
    )


if __name__ == "__main__":
    unittest.main()
