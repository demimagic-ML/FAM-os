"""Accessible text rendering for trusted peer state and controls."""

from fam_os.shell.peer_contracts import ShellPeerOperation


def render_peer_response(response) -> str:
    if response.operation in {ShellPeerOperation.PEERS, ShellPeerOperation.PROBE}:
        lines = [_peer(item) for item in response.peers]
    elif response.operation is ShellPeerOperation.RECEIPTS:
        lines = [
            f"{item.receipt_id} | {item.operation.value} | "
            f"applied={str(item.applied).lower()} | revision={item.resulting_revision} | "
            f"reasons={','.join(item.reason_codes)}"
            for item in response.control_receipts
        ]
    else:
        lines = [_context(item) for item in response.context_evidence]
    heading = f"Peers {response.operation.value} ({response.offset + len(lines)} of {response.total_count})"
    return "\n".join((heading, *(lines or ["No records."])))


def _peer(item) -> str:
    latency = (
        "unmeasured" if item.latest_performance is None
        else f"{item.latest_performance.round_trip_milliseconds:.2f}ms"
    )
    privacy = "unset-deny-all" if item.privacy is None else f"revision-{item.privacy.revision}"
    models = ",".join(value.model_ref for value in item.capabilities) or "not-probed"
    return (
        f"{item.enrollment_id} | {item.display_name} | {item.endpoint.host}:{item.endpoint.port} | "
        f"trusted=true | enrollment-revision={item.enrollment_revision} | "
        f"models={models} | latency={latency} | privacy={privacy}"
    )


def _context(item) -> str:
    return (
        f"{item.evidence_id} | direction={item.direction.value} | "
        f"peer={item.peer_device_id} | expert={item.target_expert_id} | "
        f"bytes={item.content_bytes} | raw-fragments={len(item.raw_fragment_sha256)} | "
        f"privacy-revision={item.privacy_policy_revision or 'receiver'} | "
        f"reasons={','.join(item.reason_codes)}"
    )
