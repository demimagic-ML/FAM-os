"""Durable execution of capability-driven application plan steps."""

from dataclasses import replace

from fam_os.core.contracts import PlanStepKind, StepOutcome
from fam_os.core.lifecycle import (
    AcceptanceEvidenceRecord,
    ActionExecutionCommand,
    ActionProposalAcquisition,
    ObservationAcquisition,
    PlanEvidenceKind,
    PlanEvidenceReference,
    PlanLifecycleService,
)
from fam_os.core.production.application_contracts import ApplicationExecutionState
from fam_os.core.production.application_generation import application_grounded_context
from fam_os.core.production.application_parameter_resolution import (
    resolve_action_parameters,
)
from fam_os.core.production.deterministic_observation import (
    seed_exact_observation_candidate,
)
from fam_os.core.production.application_reversal import (
    release_action_receipt_candidate, seeded_or_generate,
)
from fam_os.core.production.contracts import AssuranceLevel, InferenceExecutionState
from fam_os.core.production.execution_state import terminal_execution
from fam_os.product.restart_recovery import (
    PersistedActionRecord,
    PersistedActionState,
)


class ApplicationTaskWorker:
    def __init__(self, repositories, applications, inference) -> None:
        self._repositories = repositories
        self._applications = applications
        self._inference = inference

    def run(self, instance_id: str) -> None:
        while True:
            application = self._require_application(instance_id)
            snapshot = self._require_plan(instance_id)
            inference = self._require_inference(instance_id)
            if snapshot.terminal:
                self._terminalize(application, inference, snapshot)
                return
            step = next(
                item for item in snapshot.plan.steps
                if item.step_id == snapshot.current_step_id
            )
            if step.kind is PlanStepKind.OBSERVE:
                if not self._observe(
                    application, snapshot, inference, step.capability_ids[0],
                ):
                    return
            elif step.kind is PlanStepKind.INFERENCE:
                if not self._generate(application, snapshot, inference):
                    return
            elif step.kind is PlanStepKind.PREPARE_ACTION:
                self._prepare(application, snapshot, inference)
                return
            elif step.kind is PlanStepKind.CONFIRM_ACTION:
                self._waiting(application)
                return
            elif step.kind is PlanStepKind.EXECUTE_ACTION:
                self._execute(application, snapshot, inference)
            elif step.kind is PlanStepKind.VERIFY:
                self._verify(application, snapshot, inference)
            else:
                self._fail(
                    application, snapshot, inference, "application.step.unsupported",
                )
                return

    def _observe(self, application, snapshot, inference, capability_id):
        parameters = self._applications.provider.observation_parameters(
            application.application_instance_id, capability_id,
            application.routed.admitted.request.prompt,
            application.resource_uri,
        )
        result = self._applications.steps.acquire_observation(ObservationAcquisition(
            application.instance_id, snapshot.revision, application.routed,
            application.application_instance_id, application.permission_grant_id,
            parameters, application.resource_uri,
        ))
        if result.rejection is not None:
            self._fail(application, snapshot, inference, result.rejection)
            return False
        updated = replace(
            application, revision=application.revision + 1,
            observations=application.observations + (result.evidence,),
        )
        self._replace_application(application, updated)
        return True

    def _generate(self, application, snapshot, inference):
        context = application_grounded_context(application, snapshot)
        generated = seed_exact_observation_candidate(
            self._repositories, application, inference,
        )
        if generated is None:
            generated = seeded_or_generate(inference, self._inference, context)
        if generated.state is not InferenceExecutionState.CANDIDATE_READY:
            return False
        target = next(
            transition.target_step_id for transition in snapshot.plan.transitions
            if transition.source_step_id == snapshot.current_step_id
            and transition.outcome is StepOutcome.SUCCEEDED
        )
        references = ()
        if target == "release":
            references = (PlanEvidenceReference(
                generated.candidate_id, PlanEvidenceKind.RELEASE_CANDIDATE, None,
            ),)
        advanced = PlanLifecycleService(self._repositories.plans).advance(
            snapshot.instance_id, snapshot.revision, StepOutcome.SUCCEEDED, references,
        )
        if advanced.rejection is not None:
            raise RuntimeError(
                f"application inference could not advance: {advanced.rejection}"
            )
        return True

    def _prepare(self, application, snapshot, inference):
        step = next(
            item for item in snapshot.plan.steps
            if item.step_id == snapshot.current_step_id
        )
        entry = self._applications.provider.capability(
            application.application_instance_id, step.capability_ids[0],
        )
        if entry is not None and entry.connector_id.startswith("os-tools-"):
            parameters = {}
        else:
            resolution = resolve_action_parameters(
                self._repositories, self._inference, inference,
                step.capability_ids[0], application.observations,
                application_grounded_context(application, snapshot),
            )
            inference = resolution.inference
            if resolution.failure_code is not None:
                self._fail(
                    application, snapshot, inference, resolution.failure_code,
                )
                return
            if resolution.parameters is None:
                raise RuntimeError("application parameter resolution was incomplete")
            parameters = resolution.parameters
        expected = (
            application.observations[-1].revision
            if application.observations else None
        )
        request = self._repositories.requests.get(application.request_id)
        if request is None:
            self._fail(
                application, snapshot, inference, "application.request.missing",
            )
            return
        result = self._applications.steps.acquire_action_proposal(ActionProposalAcquisition(
            application.instance_id, snapshot.revision, application.routed,
            application.application_instance_id, application.permission_grant_id,
            request.prompt,
            parameters, application.resource_uri, expected,
        ))
        if result.rejection is not None:
            self._fail(application, snapshot, inference, result.rejection)
            return
        proposal = result.evidence
        action = PersistedActionRecord(
            f"action-{proposal.proposal_id}", application.instance_id,
            f"{application.request_id}:{proposal.proposal_id}", proposal,
            PersistedActionState.AWAITING_APPROVAL,
        )
        if not self._repositories.actions.create(action):
            raise RuntimeError("application action state already exists")
        self._replace_application(application, replace(
            application, revision=application.revision + 1,
            state=ApplicationExecutionState.WAITING_APPROVAL, proposal=proposal,
        ))

    def _execute(self, application, snapshot, inference):
        if application.proposal is None or application.confirmation is None:
            self._fail(
                application, snapshot, inference, "application.confirmation.missing",
            )
            return
        action_id = f"action-{application.proposal.proposal_id}"
        action = self._repositories.actions.get(action_id)
        if action is None:
            self._fail(
                application, snapshot, inference, "application.action.state_missing",
            )
            return
        invoking = replace(action, state=PersistedActionState.INVOKING)
        if not self._repositories.actions.replace(action.state, invoking):
            raise RuntimeError("application action invocation state changed")
        outcome = self._applications.actions.execute(ActionExecutionCommand(
            application.instance_id, snapshot.revision, application.routed,
            application.proposal, application.confirmation,
        ))
        if outcome.action_result is None:
            uncertain = replace(invoking, state=PersistedActionState.UNCERTAIN)
            self._repositories.actions.replace(invoking.state, uncertain)
            self._fail(application, snapshot, inference, str(outcome.rejection))
            return
        state = (
            PersistedActionState.VERIFIED
            if outcome.action_result.verified else PersistedActionState.FAILED
        )
        self._repositories.actions.replace(invoking.state, replace(
            invoking, state=state, result=outcome.action_result,
        ))
        self._replace_application(application, replace(
            application, revision=application.revision + 1,
            action_result=outcome.action_result,
        ))

    def _verify(self, application, snapshot, inference):
        inference = release_action_receipt_candidate(
            self._repositories, application, inference,
        )
        if inference.candidate_id is None:
            self._fail(
                application, snapshot, inference, "application.grounding.missing",
            )
            return
        step = next(
            item for item in snapshot.plan.steps
            if item.step_id == snapshot.current_step_id
        )
        action_verified = (
            application.action_result is not None
            and application.action_result.verified
        )
        if not action_verified and not application.observations:
            self._fail(
                application, snapshot, inference, "application.grounding.missing",
            )
            return
        evidence_id = f"verification-{application.request_id}-application"
        acceptance = AcceptanceEvidenceRecord(
            evidence_id, inference.candidate_id, step.acceptance_ids, True,
        )
        if not self._repositories.final_evidence.add_acceptance(acceptance):
            raise RuntimeError("application acceptance evidence already exists")
        refs = (
            PlanEvidenceReference(
                inference.candidate_id, PlanEvidenceKind.RELEASE_CANDIDATE, None,
            ),
            PlanEvidenceReference(
                evidence_id, PlanEvidenceKind.VERIFICATION_PASS, None,
            ),
        )
        advanced = PlanLifecycleService(self._repositories.plans).advance(
            snapshot.instance_id, snapshot.revision, StepOutcome.SUCCEEDED, refs,
        )
        if advanced.rejection is not None:
            raise RuntimeError("application verification could not advance")

    def _waiting(self, application):
        if application.state is ApplicationExecutionState.WAITING_APPROVAL:
            return
        self._replace_application(application, replace(
            application, revision=application.revision + 1,
            state=ApplicationExecutionState.WAITING_APPROVAL,
        ))

    def _terminalize(self, application, inference, snapshot):
        if inference.state is not InferenceExecutionState.TERMINAL:
            assurance = (
                AssuranceLevel.VERIFIED
                if application.action_result is not None
                and application.action_result.verified
                else AssuranceLevel.GROUNDED
                if application.observations and inference.candidate_id else
                AssuranceLevel.UNVERIFIED
            )
            terminal_execution(
                self._repositories, inference,
                None if inference.candidate_id else "application.task.failed",
                assurance,
            )
        if application.state is not ApplicationExecutionState.TERMINAL:
            self._replace_application(application, replace(
                application, revision=application.revision + 1,
                state=ApplicationExecutionState.TERMINAL,
            ))

    def _advance_failure(self, snapshot, rejection):
        step = next(
            item for item in snapshot.plan.steps
            if item.step_id == snapshot.current_step_id
        )
        capability_id = (
            step.capability_ids[0]
            if step.capability_ids else "core.application.execution"
        )
        references = (PlanEvidenceReference(
            str(rejection), PlanEvidenceKind.FAILURE_REASON, capability_id,
        ),)
        advanced = PlanLifecycleService(self._repositories.plans).advance(
            snapshot.instance_id, snapshot.revision, StepOutcome.FAILED, references,
        )
        if advanced.rejection is not None:
            raise RuntimeError(f"application rejection could not advance: {rejection}")

    def _fail(self, application, snapshot, inference, code):
        self._advance_failure(snapshot, code)
        terminal_execution(self._repositories, inference, str(code))
        if application.state is not ApplicationExecutionState.TERMINAL:
            self._replace_application(application, replace(
                application, revision=application.revision + 1,
                state=ApplicationExecutionState.TERMINAL,
            ))

    def _replace_application(self, current, updated):
        if not self._repositories.application_executions.replace(
            current.revision, updated,
        ):
            raise RuntimeError("application execution revision conflict")

    def _require_application(self, instance_id):
        value = self._repositories.application_executions.get(instance_id)
        if value is None:
            raise KeyError("application execution does not exist")
        return value

    def _require_plan(self, instance_id):
        value = self._repositories.plans.get(instance_id)
        if value is None:
            raise KeyError("application plan does not exist")
        return value

    def _require_inference(self, instance_id):
        value = self._repositories.inference_executions.get(instance_id)
        if value is None:
            raise KeyError("application inference does not exist")
        return value
