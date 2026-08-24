"""Repair and bind model-proposed application action parameters."""

from dataclasses import dataclass

from fam_os.core.production.application_parameters import parse_action_parameters
from fam_os.core.production.contracts import (
    InferenceExecutionRecord,
    InferenceExecutionState,
)
from fam_os.core.production.workspace_parameters import (
    WorkspacePatchScopeUnsupported,
    bind_workspace_patch_parameters,
    workspace_parameter_feedback,
)


@dataclass(frozen=True, slots=True)
class ActionParameterResolution:
    inference: InferenceExecutionRecord
    parameters: dict | None = None
    failure_code: str | None = None


def resolve_action_parameters(
    repositories, inference_worker, inference: InferenceExecutionRecord,
    capability_id: str, observations, grounded_context: str,
) -> ActionParameterResolution:
    current = inference
    while True:
        candidate = repositories.final_evidence.candidate(current.candidate_id)
        if candidate is None:
            return ActionParameterResolution(
                current, failure_code="application.candidate.missing",
            )
        try:
            parameters = parse_action_parameters(candidate.content)
            bound = bind_workspace_patch_parameters(
                capability_id, parameters, observations,
            )
            return ActionParameterResolution(current, parameters=bound)
        except WorkspacePatchScopeUnsupported:
            return ActionParameterResolution(
                current, failure_code="application.action.scope_unsupported",
            )
        except ValueError as error:
            escalation = "[workspace-parameter-repair]" in current.verifier_feedback
            exhausted = "[workspace-parameter-escalation]" in current.verifier_feedback
            if exhausted:
                return ActionParameterResolution(
                    current, failure_code="application.action.parameters_invalid",
                )
            feedback = workspace_parameter_feedback(
                error, observations, escalation=escalation,
            )
            regenerated = inference_worker.retry_action_candidate(
                current, grounded_context, feedback, escalation=escalation,
            )
            if (
                regenerated is None
                or regenerated.state is not InferenceExecutionState.CANDIDATE_READY
            ):
                return ActionParameterResolution(
                    current, failure_code="application.action.parameters_invalid",
                )
            current = regenerated
