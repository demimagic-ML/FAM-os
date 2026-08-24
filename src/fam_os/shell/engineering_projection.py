"""Model-free terminal projection of strict engineering outcomes."""

from fam_os.core.engineering import (
    EngineeringCapabilityUnavailable,
    EngineeringExecutionRecord,
    EngineeringProposalResult,
    EngineeringPublicationProposal,
    EngineeringPublicationReceipt,
    VerifiedChangeSetReceipt,
)


EngineeringProjectionSource = (
    EngineeringProposalResult
    | VerifiedChangeSetReceipt
    | EngineeringPublicationProposal
    | EngineeringPublicationReceipt
    | EngineeringCapabilityUnavailable
    | EngineeringExecutionRecord
)


def render_engineering_result(value: EngineeringProjectionSource) -> str:
    """Render policy-owned state without turning proposal text into a receipt."""

    lines = [f"Engineering result: {value.result_kind.value}"]
    if isinstance(value, EngineeringProposalResult):
        lines.extend((
            "State: proposed; no workspace mutation is claimed.",
            f"Task: {_safe(value.task_id)}",
            f"Change set: {_safe(value.change_set_proposal_id)}",
        ))
    elif isinstance(value, VerifiedChangeSetReceipt):
        lines.extend((
            "State: independently verified workspace mutation.",
            f"Task: {_safe(value.task_id)}",
            f"Receipt: {_safe(value.receipt_id)}",
            f"Verifier runs: {len(value.verifier_run_ids)}",
            f"Evidence records: {len(value.evidence_ids)}",
        ))
    elif isinstance(value, EngineeringPublicationProposal):
        lines.extend((
            "State: publication proposed; nothing external is claimed published.",
            f"Task: {_safe(value.task_id)}",
            f"Publication proposal: {_safe(value.proposal_id)}",
            f"Checkpoint: {_safe(value.checkpoint_id)}",
        ))
    elif isinstance(value, EngineeringPublicationReceipt):
        lines.extend((
            "State: publication observed and postcondition-verified.",
            f"Task: {_safe(value.task_id)}",
            f"Publication receipt: {_safe(value.receipt_id)}",
            f"Remote revision: {_safe(value.observed_remote_revision)}",
            f"Evidence records: {len(value.evidence_ids)}",
        ))
    elif isinstance(value, EngineeringCapabilityUnavailable):
        lines.extend((
            "State: capability unavailable; no effect is claimed.",
            f"Task: {_safe(value.task_id)}",
            f"Capability: {_safe(value.capability_id)}",
            f"Reason code: {_safe(value.reason_code)}",
        ))
    elif isinstance(value, EngineeringExecutionRecord):
        lines.extend((
            f"State: {value.assurance.value}.",
            f"Task: {_safe(value.task_id)}",
            f"Execution record: {_safe(value.record_id)}",
            f"Effect applied: {'yes' if value.effect_applied else 'no'}",
            f"Evidence records: {len(value.evidence_ids)}",
        ))
    else:
        raise TypeError("engineering result projection source is unsupported")
    return "\n".join(lines)


def _safe(value: str) -> str:
    return "".join(
        character if ord(character) >= 32 and ord(character) != 127 else "�"
        for character in value
    )
