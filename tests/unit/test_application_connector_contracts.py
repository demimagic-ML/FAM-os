import unittest
from datetime import datetime, timezone

from fam_os.applications import (
    APPLICATION_CONTRACT_VERSION,
    ActionConfirmation,
    ActionPreparationRequest,
    ActionProposal,
    ActionResult,
    ActionStatus,
    ApplicationAuthority,
    ApplicationFailure,
    ApplicationFailureCategory,
    ApplicationIdentity,
    ApplicationInstance,
    ApplicationRetryDisposition,
    CapabilityDescriptor,
    CapabilityKind,
    CapabilityRegistryEntry,
    ConditionEvidence,
    ConditionRequirement,
    ConfirmationDecision,
    ConfirmationPolicy,
    ConnectorRegistration,
    ConnectorTransportKind,
    ObservationRequest,
    ObservationResult,
    ObservationStatus,
    Reversibility,
)


NOW = datetime(2026, 7, 16, 10, 0, tzinfo=timezone.utc)


class FakeCapabilityRegistry:
    def __init__(self) -> None:
        self._registrations: dict[str, ConnectorRegistration] = {}

    def register(self, registration: ConnectorRegistration) -> None:
        self._registrations[registration.connector_id] = registration

    def unregister(self, connector_id: str) -> None:
        self._registrations.pop(connector_id, None)

    def entries(self, instance_id: str | None = None) -> tuple[CapabilityRegistryEntry, ...]:
        entries = tuple(
            entry
            for registration in self._registrations.values()
            for entry in registration.capabilities
        )
        if instance_id is None:
            return entries
        return tuple(entry for entry in entries if entry.instance_id == instance_id)


class FakeVsCodeConnector:
    def __init__(self, registration: ConnectorRegistration) -> None:
        self._registration = registration
        self.closed = False

    def registration(self) -> ConnectorRegistration:
        return self._registration

    def observe(self, request: ObservationRequest) -> ObservationResult:
        return ObservationResult(
            request.request_id,
            ObservationStatus.OBSERVED,
            NOW,
            {
                "document_uri": "file:///workspace/fam-os/app.py",
                "language_id": "python",
                "selection": {"start": 20, "end": 44},
                "document_version": 7,
            },
            "file:///workspace/fam-os/app.py",
            "document-version-7",
        )

    def prepare_action(self, request: ActionPreparationRequest) -> ActionProposal:
        return ActionProposal(
            "proposal-1",
            request,
            {"diff": "-return old\n+return new"},
            Reversibility.REVERSIBLE,
            ConfirmationPolicy.ALWAYS,
            (
                ConditionRequirement(
                    "document.hash", "sha256", "Applied document matches approved edit"
                ),
                ConditionRequirement(
                    "workspace.tests", "python-tests", "Workspace tests pass"
                ),
            ),
            preconditions=(
                ConditionRequirement(
                    "document.version",
                    "vscode.document-version",
                    "Document is still at the observed version",
                ),
            ),
            reversal_capability_id="vscode.workspace_edit.undo",
        )

    def execute_action(
        self, proposal: ActionProposal, confirmation: ActionConfirmation
    ) -> ActionResult:
        if confirmation.decision is ConfirmationDecision.DENIED:
            return ActionResult(
                proposal.proposal_id,
                ActionStatus.DENIED,
                NOW,
                error=ApplicationFailure(
                    ApplicationFailureCategory.PERMISSION_DENIED,
                    "application.confirmation.denied",
                    confirmation.reason or "The action was denied.",
                    ApplicationRetryDisposition.AFTER_USER_ACTION,
                ),
            )
        return ActionResult(
            proposal.proposal_id,
            ActionStatus.VERIFIED,
            NOW,
            (
                ConditionEvidence("document.hash", "sha256", True, "hash matched"),
                ConditionEvidence("workspace.tests", "python-tests", True, "12 tests passed"),
            ),
            {"applied_edits": 1},
            "document-version-7",
            "document-version-8",
            "vscode-undo-1",
        )

    def close(self) -> None:
        self.closed = True


class VsCodeConnectorContractTests(unittest.TestCase):
    def test_register_observe_prepare_confirm_execute_and_verify(self) -> None:
        connector = FakeVsCodeConnector(_registration())
        registry = FakeCapabilityRegistry()
        registry.register(connector.registration())
        self.assertEqual(len(registry.entries("vscode-instance-1")), 2)

        observation = connector.observe(
            ObservationRequest(
                "observe-1",
                "vscode-instance-1",
                "vscode.editor.active",
                "grant-1",
            )
        )
        self.assertEqual(observation.payload["language_id"], "python")

        proposal = connector.prepare_action(_preparation_request())
        confirmation = ActionConfirmation(
            "confirm-1",
            proposal.proposal_id,
            "grant-1",
            ConfirmationDecision.APPROVED,
            "user-1",
            NOW,
        )
        result = connector.execute_action(proposal, confirmation)
        self.assertTrue(result.verified)
        self.assertEqual(result.after_revision, "document-version-8")

    def test_registration_rejects_capability_from_other_instance(self) -> None:
        registration = _registration()
        wrong = CapabilityRegistryEntry(
            "wrong-entry",
            registration.connector_id,
            "another-instance",
            registration.instance.application.application_id,
            registration.capabilities[0].capability,
        )
        with self.assertRaisesRegex(ValueError, "instance"):
            ConnectorRegistration(
                registration.connector_id,
                registration.transport_kind,
                registration.protocol_id,
                registration.protocol_version,
                registration.instance,
                (wrong,),
                NOW,
            )

    def test_registration_is_versioned_and_protocol_neutral(self) -> None:
        registration = _registration()
        self.assertEqual(registration.contract_version, APPLICATION_CONTRACT_VERSION)
        self.assertEqual(registration.transport_kind, ConnectorTransportKind.NATIVE_LOCAL)
        self.assertEqual(registration.protocol_id, "fam.native-connector")


def _registration() -> ConnectorRegistration:
    application = ApplicationIdentity("com.microsoft.vscode", "Visual Studio Code")
    instance = ApplicationInstance(
        "vscode-instance-1",
        application,
        "fam-vscode-connector",
        42,
        ("file:///workspace/fam-os",),
    )
    entries = (
        _entry(instance, "vscode.editor.active", _observation_capability()),
        _entry(instance, "vscode.workspace_edit.apply", _action_capability()),
    )
    return ConnectorRegistration(
        "fam-vscode-connector",
        ConnectorTransportKind.NATIVE_LOCAL,
        "fam.native-connector",
        "1",
        instance,
        entries,
        NOW,
    )


def _entry(
    instance: ApplicationInstance, suffix: str, capability: CapabilityDescriptor
) -> CapabilityRegistryEntry:
    return CapabilityRegistryEntry(
        f"vscode-instance-1:{suffix}",
        instance.connector_id,
        instance.instance_id,
        instance.application.application_id,
        capability,
        instance.workspace_uris,
    )


def _observation_capability() -> CapabilityDescriptor:
    return CapabilityDescriptor(
        "vscode.editor.active",
        "Observe active editor",
        "Observe active document, selection, language, and revision",
        CapabilityKind.OBSERVATION,
        ApplicationAuthority.OBSERVE,
        "vscode.editor.active.input.v1",
        "vscode.editor.active.output.v1",
    )


def _action_capability() -> CapabilityDescriptor:
    return CapabilityDescriptor(
        "vscode.workspace_edit.apply",
        "Apply workspace edit",
        "Apply a previewed and reversible workspace edit",
        CapabilityKind.ACTION,
        ApplicationAuthority.MODIFY,
        "vscode.workspace_edit.input.v1",
        "vscode.workspace_edit.output.v1",
        Reversibility.REVERSIBLE,
        ConfirmationPolicy.ALWAYS,
        ("document.hash", "workspace.tests"),
    )


def _preparation_request() -> ActionPreparationRequest:
    return ActionPreparationRequest(
        "action-1",
        "vscode-instance-1",
        "vscode.workspace_edit.apply",
        "grant-1",
        "Replace the selected function body",
        {"new_text": "return new"},
        "file:///workspace/fam-os/app.py",
        "document-version-7",
    )


if __name__ == "__main__":
    unittest.main()
