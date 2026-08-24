"""Accessible text rendering for live adaptation controls and evidence."""

from fam_os.shell.adaptation_contracts import ShellAdaptationOperation


def render_adaptation_response(response) -> str:
    if response.operation is ShellAdaptationOperation.STATUS:
        return _state(response.state)
    if response.operation is ShellAdaptationOperation.SNAPSHOTS:
        lines = [
            f"{item.snapshot_id} | {item.workflow_id} | observations={item.observation_count} | "
            f"context={item.predicted_context_tokens} | escalation={item.escalation_probability:.2f}"
            for item in response.snapshots
        ]
    elif response.operation is ShellAdaptationOperation.PREWARMS:
        lines = [
            f"{item.receipt_id} | {item.candidate_model_ref} | {item.status.value} | "
            f"source={item.source.value} | resident={str(item.loaded_after).lower()}"
            for item in response.prewarms
        ]
    elif response.operation is ShellAdaptationOperation.HEALTH:
        lines = [
            f"{item.sample_id} | {item.workflow_id} | quality={item.verification_quality:.2f} | "
            f"latency={item.latency_seconds:.3f}s | temperature={_temperature(item)} | "
            f"policy={str(item.policy_conformant).lower()}"
            for item in response.health
        ]
    elif response.operation is ShellAdaptationOperation.DRIFT:
        lines = [
            f"{item.report_id} | {item.workflow_id} | drifted={str(item.drifted).lower()} | "
            f"reasons={','.join(item.reason_codes) or 'none'}"
            for item in response.drift_reports
        ]
    else:
        lines = [
            f"{item.receipt_id} | {item.operation.value} | {item.status.value} | "
            f"revision={item.state.revision} | reasons={','.join(item.reason_codes)}"
            for item in response.control_receipts
        ]
    heading = (
        f"Adaptation {response.operation.value} "
        f"({response.offset + len(lines)} of {response.total_count})"
    )
    return "\n".join((heading, *(lines or ["No records."])))


def _state(state) -> str:
    active = ", ".join(
        f"{item.workflow_id}={item.snapshot_id}" for item in state.active_selections
    ) or "none"
    known = ", ".join(
        f"{item.workflow_id}={item.snapshot_id}" for item in state.known_good_selections
    ) or "none"
    return "\n".join((
        f"Adaptation: {'enabled' if state.enabled else 'disabled'}",
        f"Revision: {state.revision}",
        f"Active: {active}",
        f"Known good: {known}",
        f"Drifted snapshots: {len(state.drifted_snapshot_ids)}",
    ))


def _temperature(sample) -> str:
    return "unavailable" if sample.peak_temperature_c is None else f"{sample.peak_temperature_c:.1f}C"
