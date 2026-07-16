"""Previewed, approved, verified edit through the real VS Code connector."""

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fam_os.adapters.audit import ApplicationJsonlAuditSink
from fam_os.application_acceptance.contracts import IntegrationLevel, ScenarioEvidence
from fam_os.application_acceptance.core_session import AcceptanceCoreSession, plan_factory
from fam_os.application_acceptance.metrics import OperationMeter
from fam_os.application_acceptance.native_vscode import IsolatedVsCodeHost
from fam_os.applications import (
    ActionConfirmation, ApplicationAuthority, ConditionEvidence,
    ConfirmationDecision, PermissionGrant, PermissionScope,
)
from fam_os.core.contracts import (
    PlanStep, PlanStepKind, PlanTransition, StepOutcome, TerminalDisposition,
)
from fam_os.core.lifecycle import (
    ActionExecutionCommand, ActionProposalAcquisition,
    ApplicationActionExecutionService, ApplicationStepService,
    ConfirmationCommand, ConfirmationTransitionService,
    InMemoryActionExecutionReplayRegistry, InMemoryConfirmationReplayRegistry,
    ObservationAcquisition,
)


ACTIVE_CAPABILITY = "vscode.editor.active"
EDIT_CAPABILITY = "vscode.workspace_edit.apply"


class VsCodeEditWorkflow:
    def __init__(self, root: Path, workspace: Path, target: Path):
        self.root = root
        self.workspace = workspace
        self.target = target
        self.meter = OperationMeter()
        self.host = IsolatedVsCodeHost(
            Path("/usr/bin/code"), root / "connectors/vscode",
        )
        self.session = None
        self.proposal = None
        self.action_grant = None

    def prepare(self, request_id, prompt):
        active, edit = self._start_host(request_id)
        observation_grant, self.action_grant = self._grants(active, edit)
        self.session = AcceptanceCoreSession.start(
            request_id, prompt, self._plan(request_id),
            (observation_grant, self.action_grant),
        )
        observed = self._observe(request_id, observation_grant)
        self.proposal = self._prepare_proposal(request_id, observed)
        return self.session.lifecycle.repository.get(self.session.plan_instance_id)

    def _start_host(self, request_id):
        self.meter.measure(
            f"{request_id}-native-start", IntegrationLevel.NATIVE,
            ACTIVE_CAPABILITY, lambda: self.host.start(self.workspace, self.target),
            context_selector=lambda host: {
                "connector_id": host.connector_id,
                "capability_ids": tuple(
                    item.capability_id for item in host.registry.entries()
                ),
            },
        )
        active = self.host.capability(self.host.instance_id, ACTIVE_CAPABILITY)
        edit = self.host.capability(self.host.instance_id, EDIT_CAPABILITY)
        if active is None or edit is None:
            raise RuntimeError("native editor capabilities are unavailable")
        return active, edit

    def _observe(self, request_id, observation_grant):
        application = ApplicationStepService(
            self.session.lifecycle, self.host, self.session.permissions,
        )
        observed = self.meter.measure(
            f"{request_id}-native-observe", IntegrationLevel.NATIVE,
            ACTIVE_CAPABILITY,
            lambda: application.acquire_observation(ObservationAcquisition(
                self.session.plan_instance_id, 0, self.session.routed,
                self.host.instance_id, observation_grant.grant_id, {},
                self.target.as_uri(),
            )),
            context_selector=lambda value: value.evidence.payload,
        )
        if observed.rejection is not None:
            raise RuntimeError("native active editor observation failed")
        return observed

    def _prepare_proposal(self, request_id, observed):
        application = ApplicationStepService(
            self.session.lifecycle, self.host, self.session.permissions,
        )
        revision = observed.evidence.revision
        parameters = {
            "document_uri": self.target.as_uri(),
            "edits": ({
                "range": {
                    "start": {"line": 0, "character": 0},
                    "end": {"line": 0, "character": 6},
                },
                "new_text": "After",
            },),
        }
        prepared = self.meter.measure(
            f"{request_id}-native-prepare", IntegrationLevel.NATIVE,
            EDIT_CAPABILITY,
            lambda: application.acquire_action_proposal(ActionProposalAcquisition(
                self.session.plan_instance_id, observed.snapshot.revision,
                self.session.routed, self.host.instance_id,
                self.action_grant.grant_id, "Replace Before with After",
                parameters, self.target.as_uri(), revision,
            )),
            context_selector=lambda value: value.evidence.preview,
        )
        if prepared.rejection is not None:
            raise RuntimeError("native editor proposal failed")
        return prepared.evidence

    def execute(self, request_id, approved):
        confirmation, confirmed = self._confirm(request_id, approved)
        if not approved:
            return self._denied(request_id)
        return self._execute_approved(request_id, confirmation, confirmed)

    def _confirm(self, request_id, approved):
        decision = (
            ConfirmationDecision.APPROVED if approved else ConfirmationDecision.DENIED
        )
        confirmation = ActionConfirmation(
            f"confirmation-{request_id}", self.proposal.proposal_id,
            self.action_grant.grant_id, decision, "local-user",
            datetime.now(timezone.utc), None if approved else "User denied the edit.",
        )
        confirmed = ConfirmationTransitionService(
            self.session.lifecycle, self.session.permissions,
            InMemoryConfirmationReplayRegistry(),
        ).record_confirmation(ConfirmationCommand(
            self.session.plan_instance_id,
            self.session.lifecycle.repository.get(self.session.plan_instance_id).revision,
            self.session.routed, confirmation,
        ))
        if confirmed.rejection is not None:
            raise RuntimeError("native editor confirmation failed")
        return confirmation, confirmed

    def _denied(self, request_id):
        return ScenarioEvidence(
            request_id, False, False, False, "", (ACTIVE_CAPABILITY, EDIT_CAPABILITY),
            ("grant-vscode-observe", "grant-vscode-edit"), (),
            tuple(self.meter.measurements), failure_code="application.action_denied",
        )

    def _execute_approved(self, request_id, confirmation, confirmed):
        audit_dir = self.workspace / ".fam-audit"
        audit_dir.mkdir(mode=0o700, exist_ok=True)
        os.chmod(audit_dir, 0o700)
        service = ApplicationActionExecutionService(
            self.session.lifecycle, self.host, self.session.permissions,
            VsCodeConditionVerifier(self.host, self.target),
            ApplicationJsonlAuditSink((audit_dir / "actions.jsonl").resolve()),
            InMemoryActionExecutionReplayRegistry(),
        )
        result = self.meter.measure(
            f"{request_id}-native-execute", IntegrationLevel.NATIVE,
            EDIT_CAPABILITY,
            lambda: service.execute(ActionExecutionCommand(
                self.session.plan_instance_id, confirmed.snapshot.revision,
                self.session.routed, self.proposal, confirmation,
            )),
            context_selector=lambda value: {
                "status": value.action_result.status.value,
                "output": value.action_result.output,
                "postconditions": tuple(
                    {
                        "condition_id": item.condition_id,
                        "passed": item.passed,
                    }
                    for item in value.action_result.postcondition_evidence
                ),
            },
        )
        verified = result.action_result is not None and result.action_result.verified
        content = ""
        if verified:
            content = (
                "Verified editor-buffer edit: Before -> After on line 1.\n"
                f"Capabilities used: {ACTIVE_CAPABILITY}, {EDIT_CAPABILITY}. "
                "Permission: exact temporary file; reversible: yes."
            )
        return ScenarioEvidence(
            request_id, verified, verified, False, content,
            (ACTIVE_CAPABILITY, EDIT_CAPABILITY),
            ("grant-vscode-observe", "grant-vscode-edit"), (),
            tuple(self.meter.measurements), result.audit_event_ids,
            None if verified else "application.edit_unverified",
        )

    def close(self):
        self.host.stop()

    def _grants(self, active, edit):
        now = datetime.now(timezone.utc)
        expires = now + timedelta(minutes=30)
        scope = dict(
            application_ids=(active.application_id,),
            instance_ids=(active.instance_id,),
            resource_uris=(self.target.as_uri(),),
        )
        observation = PermissionGrant(
            "grant-vscode-observe", "local-user", (ApplicationAuthority.OBSERVE,),
            PermissionScope(capability_ids=(ACTIVE_CAPABILITY,), **scope), now, expires,
        )
        action = PermissionGrant(
            "grant-vscode-edit", "local-user",
            (ApplicationAuthority.PROPOSE, ApplicationAuthority.MODIFY),
            PermissionScope(capability_ids=(EDIT_CAPABILITY,), **scope), now, expires,
        )
        return observation, action

    @staticmethod
    def _plan(request_id):
        capabilities = (ACTIVE_CAPABILITY, EDIT_CAPABILITY)
        steps = (
            PlanStep("observe", PlanStepKind.OBSERVE, "Observe active editor", (ACTIVE_CAPABILITY,)),
            PlanStep("prepare", PlanStepKind.PREPARE_ACTION, "Preview edit", (EDIT_CAPABILITY,)),
            PlanStep("confirm", PlanStepKind.CONFIRM_ACTION, "Approve edit", (EDIT_CAPABILITY,)),
            PlanStep("execute", PlanStepKind.EXECUTE_ACTION, "Apply edit", (EDIT_CAPABILITY,),
                     ("document.hash", "document.version")),
            PlanStep("release", PlanStepKind.FINALIZE, "Release verified edit",
                     terminal_disposition=TerminalDisposition.RELEASE),
            PlanStep("withhold", PlanStepKind.FINALIZE, "Withhold edit result",
                     terminal_disposition=TerminalDisposition.WITHHOLD),
        )
        transitions = (
            PlanTransition("observe", StepOutcome.SUCCEEDED, "prepare"),
            PlanTransition("observe", StepOutcome.FAILED, "withhold"),
            PlanTransition("prepare", StepOutcome.SUCCEEDED, "confirm"),
            PlanTransition("prepare", StepOutcome.FAILED, "withhold"),
            PlanTransition("confirm", StepOutcome.SUCCEEDED, "execute"),
            PlanTransition("confirm", StepOutcome.DENIED, "withhold"),
            PlanTransition("execute", StepOutcome.SUCCEEDED, "release"),
            PlanTransition("execute", StepOutcome.FAILED, "withhold"),
        )
        return plan_factory(f"plan-{request_id}", request_id, capabilities, steps, transitions)


class VsCodeConditionVerifier:
    def __init__(self, host, target):
        self.host = host
        self.target = target

    def verify(self, requirement, proposal, provider_result):
        from fam_os.applications import ObservationRequest
        observation = self.host.observe(ObservationRequest(
            f"verify-{requirement.condition_id}-{datetime.now().timestamp()}",
            self.host.instance_id, ACTIVE_CAPABILITY, "grant-vscode-observe",
            resource_uri=self.target.as_uri(),
        ))
        revision = observation.revision
        if provider_result is None:
            passed = revision == proposal.request.expected_revision
        elif requirement.condition_id == "document.hash":
            passed = revision is not None and revision.endswith(proposal.preview["after_hash"])
        else:
            passed = revision == provider_result.after_revision
        return ConditionEvidence(
            requirement.condition_id, requirement.verifier_id, passed,
            "Trusted editor observation matched." if passed else "Trusted editor observation differed.",
        )
