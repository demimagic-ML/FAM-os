"""Deterministic release evidence for completed application actions."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from fam_os.core.contracts import PlanStepKind, StepOutcome
from fam_os.core.lifecycle.contracts import (
    PlanEvidenceKind,
    PlanInstanceSnapshot,
)


_MESSAGES = {
    "os.directory.create": (
        "The approved directory was created and independently verified."
    ),
    "os.directory.remove-empty": (
        "The approved empty-directory reversal completed and was independently "
        "verified."
    ),
    "vscode.workspace_edit.undo": (
        "The approved application action was reversed and independently verified."
    ),
    "os.workspace.patch": (
        "The approved workspace patch completed and was independently verified."
    ),
    "os.workspace.patch.restore": (
        "The approved workspace patch was restored and independently verified."
    ),
}


@dataclass(frozen=True, slots=True)
class VerifiedActionReceipt:
    content: str
    evidence_ids: tuple[str, ...]
    capability_ids: tuple[str, ...]


def verified_action_receipt(
    snapshot: PlanInstanceSnapshot, candidate=None,
) -> VerifiedActionReceipt | None:
    """Require one audited successful execution event for every action step."""

    steps = tuple(
        step for step in snapshot.plan.steps
        if step.kind is PlanStepKind.EXECUTE_ACTION
    )
    if not steps:
        return None
    evidence_ids: list[str] = []
    capability_ids: list[str] = []
    for step in steps:
        events = tuple(
            event for event in snapshot.events
            if event.source_step_id == step.step_id
            and event.outcome is StepOutcome.SUCCEEDED
        )
        if len(events) != 1:
            return None
        event = events[0]
        results = tuple(
            reference for reference in event.evidence_refs
            if reference.kind is PlanEvidenceKind.ACTION_RESULT
        )
        audits = tuple(
            reference for reference in event.evidence_refs
            if reference.kind is PlanEvidenceKind.ACTION_AUDIT
        )
        if len(results) != 1 or not audits:
            return None
        capability_id = results[0].capability_id
        grant_id = results[0].permission_grant_id
        if (
            capability_id not in step.capability_ids
            or grant_id is None
            or any(
                reference.capability_id != capability_id
                or reference.permission_grant_id != grant_id
                for reference in audits
            )
        ):
            return None
        capability_ids.append(capability_id)
        evidence_ids.extend(
            reference.reference_id for reference in (*results, *audits)
        )
    if len(set(evidence_ids)) != len(evidence_ids):
        return None
    capabilities = tuple(capability_ids)
    content = action_receipt_message(capabilities)
    if _is_core_workspace_receipt(snapshot, candidate, capabilities, content):
        content = candidate.content
    return VerifiedActionReceipt(
        content, tuple(evidence_ids), capabilities,
    )


def action_receipt_message(capability_ids: tuple[str, ...]) -> str:
    if len(capability_ids) == 1:
        return _MESSAGES.get(
            capability_ids[0],
            "The approved application action completed and was independently verified.",
        )
    return "The approved application actions completed and were independently verified."


def action_result_receipt_message(capability_id: str, output: Mapping) -> str:
    """Render useful terminal text only from verified provider output."""

    message = action_receipt_message((capability_id,))
    if capability_id not in {"os.workspace.patch", "os.workspace.patch.restore"}:
        return message
    plan = output.get("plan")
    files = output.get("files")
    lines = [message]
    if isinstance(plan, (list, tuple)) and plan and all(
        isinstance(item, str) for item in plan
    ):
        lines.extend(("", "Approved plan:"))
        lines.extend(f"{index}. {item}" for index, item in enumerate(plan, 1))
    paths = tuple(
        item.get("path") for item in files
        if isinstance(item, Mapping) and isinstance(item.get("path"), str)
    ) if isinstance(files, (list, tuple)) else ()
    if paths:
        heading = "Verified restored files:" if capability_id.endswith("restore") else (
            "Verified changed files:"
        )
        lines.extend(("", heading))
        lines.extend(f"- {path}" for path in paths)
    return "\n".join(lines)


def _is_core_workspace_receipt(snapshot, candidate, capabilities, prefix: str) -> bool:
    if candidate is None or capabilities not in {
        ("os.workspace.patch",), ("os.workspace.patch.restore",),
    }:
        return False
    expected_id = f"candidate-{snapshot.plan.request_id}-action-receipt"
    return (
        candidate.candidate_id == expected_id
        and (
            candidate.content == prefix
            or candidate.content.startswith(prefix + "\n")
        )
    )
