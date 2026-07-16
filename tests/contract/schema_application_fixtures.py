"""Representative Application Fabric schema values."""

from datetime import UTC, datetime

from fam_os.applications import (
    ActionConfirmation,
    ActionAuditStage,
    ActionPreparationRequest,
    ActionProposal,
    ActionResult,
    ActionStatus,
    ApplicationActionAuditIntent,
    ApplicationActionAuditRecord,
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
    ConnectorEvent,
    ConnectorEventKind,
    ConnectorRegistration,
    ConnectorTransportKind,
    ObservationRequest,
    ObservationResult,
    ObservationStatus,
    PermissionGrant,
    PermissionScope,
    Reversibility,
)


NOW = datetime(2026, 7, 16, 10, 0, tzinfo=UTC)


def application_identity() -> ApplicationIdentity:
    return ApplicationIdentity("app.vscode", "Visual Studio Code", "Microsoft", "1.0")


def application_instance() -> ApplicationInstance:
    return ApplicationInstance(
        "instance-1",
        application_identity(),
        "connector-vscode",
        process_id=1234,
        workspace_uris=("file:///workspace",),
    )


def capability() -> CapabilityDescriptor:
    return CapabilityDescriptor(
        capability_id="vscode.workspace_edit.apply",
        display_name="Apply workspace edit",
        description="Apply a reversible workspace edit.",
        kind=CapabilityKind.ACTION,
        required_authority=ApplicationAuthority.MODIFY,
        input_schema_id="capability.vscode.edit-input.v1",
        output_schema_id="capability.vscode.edit-output.v1",
        reversibility=Reversibility.REVERSIBLE,
        confirmation=ConfirmationPolicy.WHEN_REQUIRED,
        postcondition_ids=("document.hash",),
    )


def registry_entry() -> CapabilityRegistryEntry:
    return CapabilityRegistryEntry(
        "entry-1",
        "connector-vscode",
        "instance-1",
        "app.vscode",
        capability(),
        ("file:///workspace",),
    )


def permission_grant() -> PermissionGrant:
    return PermissionGrant(
        "grant-1",
        "user-1",
        (ApplicationAuthority.OBSERVE, ApplicationAuthority.MODIFY),
        PermissionScope(application_ids=("app.vscode",), capability_ids=("vscode.workspace_edit.apply",)),
        NOW,
    )


def observation_request() -> ObservationRequest:
    return ObservationRequest(
        "request-1",
        "instance-1",
        "vscode.editor.active",
        "grant-1",
        {"include_selection": True},
        "file:///workspace/main.py",
    )


def observation_result() -> ObservationResult:
    return ObservationResult(
        "request-1",
        ObservationStatus.OBSERVED,
        NOW,
        {"language": "python", "selection": [0, 10]},
        "file:///workspace/main.py",
        "revision-1",
    )


def action_preparation() -> ActionPreparationRequest:
    return ActionPreparationRequest(
        "request-1",
        "instance-1",
        "vscode.workspace_edit.apply",
        "grant-1",
        "Update main.py",
        {"edits": [{"start": 0, "text": "pass"}]},
        "file:///workspace/main.py",
        "revision-1",
    )


def condition() -> ConditionRequirement:
    return ConditionRequirement("document.hash", "verifier.document-hash", "Hash must match")


def action_proposal() -> ActionProposal:
    return ActionProposal(
        "proposal-1",
        action_preparation(),
        {"summary": "One edit"},
        Reversibility.REVERSIBLE,
        ConfirmationPolicy.WHEN_REQUIRED,
        (condition(),),
        preconditions=(ConditionRequirement("document.revision", "verifier.revision", "Revision must match"),),
        reversal_capability_id="vscode.workspace_edit.undo",
    )


def action_confirmation() -> ActionConfirmation:
    return ActionConfirmation(
        "confirmation-1",
        "proposal-1",
        "grant-1",
        ConfirmationDecision.APPROVED,
        "user-1",
        NOW,
    )


def action_result() -> ActionResult:
    return ActionResult(
        "proposal-1",
        ActionStatus.VERIFIED,
        NOW,
        (ConditionEvidence("document.hash", "verifier.document-hash", True, "Matched"),),
        {"changed": True},
        "revision-1",
        "revision-2",
        "undo-1",
    )


def action_audit_intent() -> ApplicationActionAuditIntent:
    return ApplicationActionAuditIntent(
        "audit-event-1", "action-operation-1", NOW, "request-1", "plan-instance-1",
        "user-1", "session-1", "app.vscode", "instance-1",
        "vscode.workspace_edit.apply", "grant-1", "proposal-1", "confirmation-1",
        ActionAuditStage.VERIFIED, "1" * 64, ("document.hash",),
        ActionStatus.VERIFIED, "vscode.workspace_edit.undo", True,
    )


def action_audit_record() -> ApplicationActionAuditRecord:
    return ApplicationActionAuditRecord(1, "0" * 64, "2" * 64, action_audit_intent())


def connector_registration() -> ConnectorRegistration:
    return ConnectorRegistration(
        "connector-vscode",
        ConnectorTransportKind.NATIVE_LOCAL,
        "fam.native.vscode",
        "1",
        application_instance(),
        (registry_entry(),),
        NOW,
    )


def connector_event() -> ConnectorEvent:
    return ConnectorEvent(
        "event-1",
        "connector-vscode",
        ConnectorEventKind.CAPABILITIES_CHANGED,
        NOW,
        {"generation": 2},
    )


def application_failure() -> ApplicationFailure:
    return ApplicationFailure(
        ApplicationFailureCategory.PERMISSION_DENIED,
        "application.permission_denied",
        "Permission was not granted for this application capability.",
        ApplicationRetryDisposition.AFTER_USER_ACTION,
        ("evidence-app-1",),
    )


def application_schema_values() -> tuple[object, ...]:
    return (
        application_identity(),
        application_instance(),
        capability(),
        registry_entry(),
        permission_grant(),
        observation_request(),
        observation_result(),
        action_preparation(),
        action_proposal(),
        action_confirmation(),
        action_result(),
        action_audit_intent(),
        action_audit_record(),
        connector_registration(),
        connector_event(),
        application_failure(),
    )
