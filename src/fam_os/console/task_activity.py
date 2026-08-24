"""Owner-visible projection of real Application Fabric tool evidence."""

from __future__ import annotations

from fam_os.applications.payloads import thaw_payload


def task_activity_document(record) -> dict[str, object]:
    if record is None:
        return {"available": False, "items": []}
    items = [_observation(item) for item in record.observations]
    if record.proposal is not None:
        items.append(_proposal(record.proposal, record.confirmation))
    if record.action_result is not None and record.proposal is not None:
        items.append(_action(record.proposal, record.action_result))
    return {
        "available": True,
        "application_instance_id": record.application_instance_id,
        "resource_uri": record.resource_uri,
        "permission_grant_id": record.permission_grant_id,
        "items": items,
    }


def _observation(value) -> dict[str, object]:
    payload = thaw_payload(value.payload)
    if not isinstance(payload, dict):
        raise ValueError("application observation payload must be an object")
    capability, label = _observation_identity(payload)
    return {
        "kind": "observation",
        "capability_id": capability,
        "label": label,
        "status": value.status.value,
        "resource_uri": value.resource_uri,
        "receipt_id": value.request_id,
        "recorded_at": value.observed_at.isoformat(),
        "output": payload,
    }


def _proposal(value, confirmation) -> dict[str, object]:
    return {
        "kind": "proposal",
        "capability_id": value.request.capability_id,
        "label": f"Preview {value.request.capability_id}",
        "status": (
            "awaiting_approval" if confirmation is None
            else confirmation.decision.value
        ),
        "resource_uri": value.request.resource_uri,
        "receipt_id": value.proposal_id,
        "output": thaw_payload(value.preview),
    }


def _action(proposal, result) -> dict[str, object]:
    return {
        "kind": "action",
        "capability_id": proposal.request.capability_id,
        "label": proposal.request.capability_id,
        "status": result.status.value,
        "resource_uri": proposal.request.resource_uri,
        "receipt_id": result.proposal_id,
        "recorded_at": result.completed_at.isoformat(),
        "output": thaw_payload(result.output),
    }


def _observation_identity(payload: dict) -> tuple[str, str]:
    if "entries" in payload:
        return "os.directory.list", "List directory"
    if "content" in payload:
        return "os.file.read", "Read file"
    if "exists" in payload and "empty" in payload:
        return "os.directory.inspect", "Inspect directory"
    return "application.observe", "Observe application state"
