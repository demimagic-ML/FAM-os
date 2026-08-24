import unittest
from dataclasses import replace

from fam_os.applications import (
    ApplicationAuthority, CapabilityDescriptor, CapabilityKind,
    CapabilityRegistryEntry, ConfirmationPolicy, Reversibility,
    WORKSPACE_MAP_CAPABILITY, WORKSPACE_PATCH_CAPABILITY,
    WORKSPACE_RETRIEVE_CAPABILITY,
)
from fam_os.core.production.application_intent import ApplicationCapabilityResolver
from fam_os.shell import ShellAskCommand, ShellContext, ShellContextKind
from tests.contract.schema_application_fixtures import connector_registration


class _Provider:
    def __init__(self, entries):
        self.entries = entries

    def capability(self, instance_id, capability_id):
        return next((
            item for item in self.entries
            if (item.instance_id, item.capability_id) == (instance_id, capability_id)
        ), None)


class ApplicationCapabilityResolverTests(unittest.TestCase):
    def test_read_only_prompt_does_not_inherit_action_authority(self):
        registration = connector_registration()
        entries = _entries(registration)
        command = _command(registration, entries)
        resolved = ApplicationCapabilityResolver(
            _Provider(entries),
        ).resolve(command)
        self.assertEqual(
            ("vscode.editor.active",), resolved.required_capabilities,
        )

    def test_mutating_prompt_selects_only_matching_action(self):
        registration = connector_registration()
        entries = _entries(registration)
        command = replace(_command(registration, entries), prompt="Apply this edit")
        resolved = ApplicationCapabilityResolver(
            _Provider(entries),
        ).resolve(command)
        self.assertEqual(
            ("vscode.editor.active", "vscode.workspace_edit.apply"),
            resolved.required_capabilities,
        )

    def test_filesystem_observations_match_folder_or_file_resource(self):
        registration = connector_registration()
        entries = tuple(
            CapabilityRegistryEntry(
                f"entry-{capability_id}", registration.connector_id,
                registration.instance.instance_id,
                registration.instance.application.application_id,
                CapabilityDescriptor(
                    capability_id, capability_id, "Read scoped local state.",
                    CapabilityKind.OBSERVATION, ApplicationAuthority.OBSERVE,
                    f"{capability_id}.input", f"{capability_id}.output",
                ),
            )
            for capability_id in (
                "os.directory.inspect", "os.directory.list", "os.file.read",
            )
        )
        application = ShellContext(
            "filesystem", ShellContextKind.APPLICATION,
            registration.instance.instance_id, "Filesystem",
            tuple(item.capability_id for item in entries),
        )
        resolver = ApplicationCapabilityResolver(_Provider(entries))

        folder = resolver.resolve(ShellAskCommand(
            "folder", "What is here?", (application, ShellContext(
                "folder-uri", ShellContextKind.URI, "file:///home/me/project/", "project",
            )),
        ))
        file = resolver.resolve(ShellAskCommand(
            "file", "Explain this file", (application, ShellContext(
                "file-uri", ShellContextKind.URI, "file:///home/me/project/README.md", "README",
            )),
        ))

        self.assertEqual(
            ("os.directory.inspect", "os.directory.list"),
            folder.required_capabilities,
        )
        self.assertEqual(("os.file.read",), file.required_capabilities)

    def test_workspace_implementation_selects_retrieval_and_exact_patch_only(self):
        registration = connector_registration()
        capabilities = (
            ("os.directory.inspect", CapabilityKind.OBSERVATION),
            ("os.directory.list", CapabilityKind.OBSERVATION),
            (WORKSPACE_MAP_CAPABILITY, CapabilityKind.OBSERVATION),
            (WORKSPACE_RETRIEVE_CAPABILITY, CapabilityKind.OBSERVATION),
            ("os.directory.create", CapabilityKind.ACTION),
            (WORKSPACE_PATCH_CAPABILITY, CapabilityKind.ACTION),
        )
        entries = tuple(
            CapabilityRegistryEntry(
                f"entry-{capability_id}", registration.connector_id,
                registration.instance.instance_id,
                registration.instance.application.application_id,
                CapabilityDescriptor(
                    capability_id, capability_id, "Workspace capability.", kind,
                    ApplicationAuthority.OBSERVE
                    if kind is CapabilityKind.OBSERVATION
                    else ApplicationAuthority.MODIFY,
                    f"{capability_id}.input", f"{capability_id}.output",
                    reversibility=Reversibility.NOT_APPLICABLE
                    if kind is CapabilityKind.OBSERVATION
                    else Reversibility.REVERSIBLE,
                    confirmation=ConfirmationPolicy.NOT_REQUIRED
                    if kind is CapabilityKind.OBSERVATION
                    else ConfirmationPolicy.ALWAYS,
                    postcondition_ids=() if kind is CapabilityKind.OBSERVATION else (
                        "workspace.files-match-proposal",
                    ),
                ),
            )
            for capability_id, kind in capabilities
        )
        application = ShellContext(
            "filesystem", ShellContextKind.APPLICATION,
            registration.instance.instance_id, "Filesystem",
            tuple(item.capability_id for item in entries),
        )
        command = ShellAskCommand(
            "implement", "Create a plan and implement it",
            (application, ShellContext(
                "workspace", ShellContextKind.URI,
                "file:///home/me/project/", "project",
            )),
        )

        resolved = ApplicationCapabilityResolver(_Provider(entries)).resolve(
            command, WORKSPACE_PATCH_CAPABILITY,
        )

        self.assertEqual(
            (WORKSPACE_MAP_CAPABILITY, WORKSPACE_RETRIEVE_CAPABILITY,
             WORKSPACE_PATCH_CAPABILITY),
            resolved.required_capabilities,
        )


def _entries(registration):
    observation = CapabilityDescriptor(
        "vscode.editor.active", "Observe active editor", "Read editor state.",
        CapabilityKind.OBSERVATION, ApplicationAuthority.OBSERVE,
        "vscode.editor.active.input.v1", "vscode.editor.active.output.v1",
    )
    return (
        CapabilityRegistryEntry(
            "entry-observe", registration.connector_id,
            registration.instance.instance_id,
            registration.instance.application.application_id, observation,
        ),
        *registration.capabilities,
    )


def _command(registration, entries):
    return ShellAskCommand(
        "request-resolve", "Explain the active editor",
        (ShellContext(
            "application", ShellContextKind.APPLICATION,
            registration.instance.instance_id, "VS Code",
            tuple(item.capability_id for item in entries),
        ),),
        tuple(item.capability_id for item in entries),
    )


if __name__ == "__main__":
    unittest.main()
