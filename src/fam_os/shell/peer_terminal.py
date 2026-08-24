"""Explicit owner commands for trusted peer inspection and control."""

from fam_os.fabric import (
    PeerManagementOperation, RemoteContextSensitivity, RemotePrivacyPolicy,
)
from fam_os.shell.peer_contracts import ShellPeerOperation
from fam_os.shell.peer_render import render_peer_response


def execute_peer_command(controller, values: list[str]) -> str:
    if not values:
        raise ValueError("peer subcommand is required")
    command, arguments = values[0].casefold(), values[1:]
    if command in {"list", "receipts"}:
        offset, limit = _page(arguments)
        operation = (
            ShellPeerOperation.PEERS if command == "list" else ShellPeerOperation.RECEIPTS
        )
        return render_peer_response(controller.peer_query(operation, offset, limit))
    if command == "context-evidence":
        offset, limit = _page(arguments)
        return render_peer_response(controller.peer_query(
            ShellPeerOperation.CONTEXT_EVIDENCE, offset, limit,
        ))
    if command == "probe" and len(arguments) == 1:
        return render_peer_response(controller.peer_probe(arguments[0]))
    if command == "revoke":
        if len(arguments) != 4 or arguments[-1] != "--confirm":
            raise ValueError("peer revoke requires ENROLLMENT REVISION REASON --confirm")
        response = controller.peer_control(
            PeerManagementOperation.REVOKE, arguments[0], int(arguments[1]),
            True, arguments[2],
        )
        return render_peer_response(response)
    if command == "privacy":
        return _privacy(controller, arguments)
    if command == "context":
        return _context(controller, arguments)
    raise ValueError("invalid peer command or missing --confirm")


def _privacy(controller, arguments: list[str]) -> str:
    if len(arguments) != 9 or arguments[-1] != "--confirm":
        raise ValueError(
            "peer privacy requires ENROLLMENT REVISION BYTES SENSITIVITIES PURPOSES "
            "WORKSPACES RAW_BOOL REASON --confirm"
        )
    enrollment, revision, maximum, sensitivities, purposes, workspaces, raw, reason = arguments[:8]
    entry = next(
        item for item in controller.peer_query(ShellPeerOperation.PEERS).peers
        if item.enrollment_id == enrollment
    )
    policy = RemotePrivacyPolicy(
        controller.owner_id, (entry.device_id,), _csv(purposes), _csv(workspaces),
        int(maximum), tuple(RemoteContextSensitivity(item) for item in _csv(sensitivities)),
        _boolean(raw),
    )
    return render_peer_response(controller.peer_control(
        PeerManagementOperation.SET_PRIVACY, enrollment, int(revision), True, reason, policy,
    ))


def _context(controller, arguments: list[str]) -> str:
    if len(arguments) != 11:
        raise ValueError(
            "peer context requires ENROLLMENT EXPERT DECLARATION POLICY_REV PURPOSE "
            "WORKSPACE SENSITIVITY INTENT CAPABILITIES ASSURANCE MAX_OUTPUT"
        )
    return render_peer_response(controller.peer_context(
        arguments[0], arguments[1], arguments[2], int(arguments[3]),
        arguments[4], arguments[5], RemoteContextSensitivity(arguments[6]),
        arguments[7], _csv(arguments[8]), arguments[9], int(arguments[10]),
    ))


def _csv(value: str) -> tuple[str, ...]:
    values = tuple(item for item in value.split(",") if item)
    if not values:
        raise ValueError("peer privacy lists cannot be empty")
    return values


def _boolean(value: str) -> bool:
    if value not in {"true", "false"}:
        raise ValueError("peer privacy raw flag must be true or false")
    return value == "true"


def _page(arguments: list[str]) -> tuple[int, int]:
    if len(arguments) > 2:
        raise ValueError("peer page accepts OFFSET and LIMIT")
    return (
        int(arguments[0]) if arguments else 0,
        int(arguments[1]) if len(arguments) == 2 else 100,
    )
