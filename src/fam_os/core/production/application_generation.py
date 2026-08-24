"""Grounded generation input shared by application inference and repair."""

from fam_os.core.contracts import PlanStepKind
from fam_os.core.production.workspace_parameters import workspace_candidate_instruction
from fam_os.schemas import dumps_document


def application_grounded_context(application, snapshot) -> str:
    selection = []
    if application.resource_uri:
        selection.append(
            "Selected workspace or resource: " + application.resource_uri
        )
    selection.append(
        "Selected application instance: " + application.application_instance_id
    )
    observations = "\n".join(
        dumps_document(item) for item in application.observations
    )
    context = "Authorized selection:\n" + "\n".join(selection)
    if observations:
        context += "\n\nAuthorized observation evidence:\n" + observations
    action_capabilities = tuple(
        item.capability_ids[0] for item in snapshot.plan.steps
        if item.kind is PlanStepKind.PREPARE_ACTION
    )
    if action_capabilities:
        context += "\n" + workspace_candidate_instruction(action_capabilities)
    return context
