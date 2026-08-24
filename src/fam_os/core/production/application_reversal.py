"""Deterministic, approval-bound reversal of a completed application action."""

from __future__ import annotations

import json
from dataclasses import replace

from fam_os.core.ingress.shell_views import accepted_shell_snapshot
from fam_os.core.lifecycle import CandidateEvidenceRecord
from fam_os.core.lifecycle.action_receipt_policy import action_result_receipt_message
from fam_os.core.production.application_admission import ApplicationRequestStarter
from fam_os.core.production.application_contracts import ApplicationExecutionState
from fam_os.core.production.contracts import (
    InferenceExecutionState,
    RuntimeModelSelection,
)
from fam_os.core.production.execution_state import replace_execution
from fam_os.shell import ShellAskCommand, ShellContext, ShellContextKind
from fam_os.applications import (
    WORKSPACE_RESTORE_CAPABILITY, WORKSPACE_RETRIEVE_CAPABILITY,
)


_VSCODE_OBSERVATION_CAPABILITY = "vscode.editor.active"
_DIRECTORY_OBSERVATION_CAPABILITY = "os.directory.inspect"
_REVERSAL_OBSERVATIONS = {
    "vscode.workspace_edit.undo": _VSCODE_OBSERVATION_CAPABILITY,
    "os.directory.remove-empty": _DIRECTORY_OBSERVATION_CAPABILITY,
    WORKSPACE_RESTORE_CAPABILITY: WORKSPACE_RETRIEVE_CAPABILITY,
}


class ApplicationReversalService:
    def __init__(self, repositories, applications, classifier, budget) -> None:
        self._repositories = repositories
        self._applications = applications
        self._classifier = classifier
        self._budget = budget

    def status(self, source_session_id: str) -> dict:
        source = self._source(source_session_id)
        if source is None:
            return _unavailable("application_task_missing")
        application, plan, inference = source
        if (
            application.state is not ApplicationExecutionState.TERMINAL
            or not plan.terminal
            or inference.state is not InferenceExecutionState.TERMINAL
        ):
            return _unavailable("application_task_not_terminal")
        linked = self._linked_reversal(application)
        if linked is not None:
            if linked.state is not ApplicationExecutionState.TERMINAL:
                return _unavailable("reversal_in_progress")
            if linked.action_result is not None and linked.action_result.verified:
                return _unavailable("reversal_already_completed")
        proposal = application.proposal
        result = application.action_result
        if proposal is None or result is None or not result.verified:
            return _unavailable("verified_reversible_action_missing")
        capability_id = proposal.reversal_capability_id
        if capability_id is None or result.reversal_token is None:
            return _unavailable("reversal_not_available")
        if application.resource_uri is None:
            return _unavailable("reversal_resource_missing")
        if self._applications.provider.capability(
            application.application_instance_id, capability_id,
        ) is None:
            return _unavailable("reversal_capability_unavailable")
        observation_capability_id = _REVERSAL_OBSERVATIONS.get(capability_id)
        if observation_capability_id is None:
            return _unavailable("reversal_observation_undefined")
        if self._applications.provider.capability(
            application.application_instance_id, observation_capability_id,
        ) is None:
            return _unavailable("reversal_observation_unavailable")
        return {
            "available": True,
            "reason_code": None,
            "capability_id": capability_id,
            "observation_capability_id": observation_capability_id,
            "source_session_id": source_session_id,
            "expected_revision": plan.revision + 1,
        }

    def start(
        self, source_session_id: str, request_id: str, expected_revision: int,
    ):
        status = self.status(source_session_id)
        if not status["available"]:
            raise ValueError(f"reversal is unavailable: {status['reason_code']}")
        if expected_revision != status["expected_revision"]:
            raise ValueError("reversal source revision is stale")
        application, _, source_inference = self._source(source_session_id)
        capability_id = status["capability_id"]
        command = _reversal_command(
            request_id, application, capability_id,
            status["observation_capability_id"],
        )
        intent = self._classifier.classify(command.prompt, (capability_id,))
        instance_id = f"task-{request_id}"
        claimed = replace(
            application, revision=application.revision + 1,
            reversal_session_id=instance_id,
        )
        if not self._repositories.application_executions.replace(
            application.revision, claimed,
        ):
            raise RuntimeError("reversal source changed before it could be claimed")
        selection = _deterministic_selection(
            request_id, intent, source_inference.selection,
        )
        try:
            ApplicationRequestStarter(
                self._repositories, self._applications, self._classifier,
            ).start(
                command, intent, selection, instance_id,
                reversal_source_session_id=source_session_id,
            )
            self._seed_parameters(instance_id, request_id, claimed)
            self._budget(instance_id)
        except Exception:
            self._release_claim(claimed, application.reversal_session_id)
            raise
        return accepted_shell_snapshot(
            instance_id, request_id,
            "Accepted deterministic reversal; approval is still required.",
        )

    def _seed_parameters(self, instance_id, request_id, source) -> None:
        token = source.action_result.reversal_token
        candidate_id = f"candidate-{request_id}-reversal-parameters"
        candidate = CandidateEvidenceRecord(
            candidate_id, request_id, f"plan-{request_id}",
            json.dumps({"reversal_token": token}, separators=(",", ":")),
        )
        if not self._repositories.final_evidence.add_candidate(candidate):
            raise RuntimeError("reversal parameter evidence already exists")
        inference = self._repositories.inference_executions.get(instance_id)
        if inference is None:
            raise RuntimeError("reversal inference state is missing")
        replace_execution(
            self._repositories, inference,
            state=InferenceExecutionState.CANDIDATE_READY,
            candidate_id=candidate_id,
        )

    def _source(self, session_id: str):
        application = self._repositories.application_executions.get(session_id)
        plan = self._repositories.plans.get(session_id)
        inference = self._repositories.inference_executions.get(session_id)
        if application is None or plan is None or inference is None:
            return None
        return application, plan, inference

    def _linked_reversal(self, source):
        if source.reversal_session_id is None:
            return None
        linked = self._repositories.application_executions.get(
            source.reversal_session_id,
        )
        if linked is None or linked.reversal_source_session_id != source.instance_id:
            raise RuntimeError("reversal linkage is inconsistent")
        return linked

    def _release_claim(self, claimed, previous_session_id) -> None:
        current = self._repositories.application_executions.get(claimed.instance_id)
        if current is None or current.reversal_session_id != claimed.reversal_session_id:
            raise RuntimeError("reversal claim changed before rollback")
        released = replace(
            current, revision=current.revision + 1,
            reversal_session_id=previous_session_id,
        )
        if not self._repositories.application_executions.replace(
            current.revision, released,
        ):
            raise RuntimeError("reversal claim rollback failed")


def release_action_receipt_candidate(repositories, application, inference):
    proposal = application.proposal
    result = application.action_result
    if proposal is None or result is None or not result.verified:
        return inference
    candidate_id = f"candidate-{application.request_id}-action-receipt"
    message = action_result_receipt_message(
        proposal.request.capability_id, result.output,
    )
    candidate = CandidateEvidenceRecord(
        candidate_id, application.request_id, f"plan-{application.request_id}",
        message,
    )
    if not repositories.final_evidence.add_candidate(candidate):
        existing = repositories.final_evidence.candidate(candidate_id)
        if existing != candidate:
            raise RuntimeError("reversal result evidence identity conflict")
    return replace_execution(repositories, inference, candidate_id=candidate_id)


def seeded_or_generate(inference, worker, context):
    if inference.state is InferenceExecutionState.CANDIDATE_READY:
        return inference
    return worker.generate_candidate(inference, context)


def _deterministic_selection(request_id, intent, source) -> RuntimeModelSelection:
    return RuntimeModelSelection(
        f"selection-{request_id}-reversal", request_id, intent,
        "internal:application-reversal", "deterministic", 0,
        source.available_host_bytes, source.available_vram_bytes,
        ("deterministic_reversal_parameters",),
    )


def _reversal_command(
    request_id, application, capability_id, observation_capability_id,
) -> ShellAskCommand:
    contexts = (
        ShellContext(
            "reversal-application", ShellContextKind.APPLICATION,
            application.application_instance_id, "Application action",
            (observation_capability_id, capability_id),
        ),
        ShellContext(
            "reversal-resource", ShellContextKind.URI,
            application.resource_uri, "Reversible resource",
        ),
    )
    return ShellAskCommand(
        request_id, "Reverse the previously approved application action.",
        contexts, (capability_id,), True,
    )


def _unavailable(reason_code: str) -> dict:
    return {
        "available": False, "reason_code": reason_code, "capability_id": None,
        "source_session_id": None, "expected_revision": None,
        "observation_capability_id": None,
    }
