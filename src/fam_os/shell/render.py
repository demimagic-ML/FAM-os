"""Color-free terminal rendering for Shell presentation contracts."""

from fam_os.shell.contracts import ShellContext, ShellSessionSnapshot, ShellStepState


STEP_MARKERS = {
    ShellStepState.PENDING: "[ ]",
    ShellStepState.ACTIVE: "[>]",
    ShellStepState.SUCCEEDED: "[x]",
    ShellStepState.FAILED: "[!]",
    ShellStepState.DENIED: "[-]",
    ShellStepState.CANCELLED: "[-]",
    ShellStepState.UNAVAILABLE: "[?]",
    ShellStepState.EXPIRED: "[-]",
}


def render_snapshot(snapshot: ShellSessionSnapshot) -> str:
    lines = [
        f"Request: {_safe(snapshot.request_id)}",
        f"State: {snapshot.state.value}",
        f"Revision: {snapshot.revision}",
    ]
    if snapshot.message:
        lines.append(f"Progress: {_safe(snapshot.message)}")
    if snapshot.steps:
        lines.extend(("", "Plan:"))
        lines.extend(
            f"  {STEP_MARKERS[item.state]} {_safe(item.description)} ({_safe(item.kind)})"
            for item in snapshot.steps
        )
    if snapshot.approval is not None:
        approval = snapshot.approval
        lines.extend((
            "", "Approval required:", f"  {_safe(approval.summary)}",
            f"  Capability: {_safe(approval.capability_id)}",
            f"  Reversible: {'yes' if approval.reversible else 'no'}",
            f"  Expires: {approval.expires_at.isoformat()}",
            "  Enter 'approve' or 'deny'.",
        ))
    if snapshot.result is not None:
        result = snapshot.result
        lines.extend(("", f"Result: {result.status.value}"))
        if result.content is not None:
            lines.append(_safe(result.content, multiline=True))
        else:
            lines.append(f"Reason: {_safe(result.reason)}")
        if result.verified:
            evidence = ", ".join(_safe(item) for item in result.evidence_ids)
            lines.append(f"Verified evidence: {evidence}")
    return "\n".join(lines)


def render_contexts(contexts: tuple[ShellContext, ...]) -> str:
    if not contexts:
        return "No context selected."
    lines = ["Selected context:"]
    lines.extend(
        f"  {_safe(item.context_id)}: {_safe(item.display_name)} [{item.kind.value}]"
        for item in contexts
    )
    return "\n".join(lines)


def _safe(value: str, multiline=False) -> str:
    rendered = []
    for character in value:
        if character == "\n" and multiline:
            rendered.append(character)
        elif character == "\t":
            rendered.append("    ")
        elif ord(character) < 32 or ord(character) == 127:
            rendered.append("�")
        else:
            rendered.append(character)
    return "".join(rendered)
