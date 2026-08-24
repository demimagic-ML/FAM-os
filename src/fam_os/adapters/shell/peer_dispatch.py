"""Server-side Shell mapping for the trusted peer management service."""

from fam_os.fabric import PeerManagementRequest, RemoteContextSendRequest
from fam_os.shell.peer_contracts import (
    ShellPeerOperation,
    ShellPeerProbeRequest,
    ShellPeerQuery,
    ShellPeerResponse,
)


class PeerServiceUnavailable(RuntimeError):
    """The installed service has no trusted peer management surface."""


def dispatch_peer(service, command) -> ShellPeerResponse:
    if service is None:
        raise PeerServiceUnavailable
    if isinstance(command, PeerManagementRequest):
        receipt = service.apply_control(command)
        values = service.control_receipts()
        return ShellPeerResponse(
            command.request_id, ShellPeerOperation.RECEIPTS,
            max(0, len(values) - 1), len(values), control_receipts=(receipt,),
        )
    if isinstance(command, RemoteContextSendRequest):
        evidence = service.send_context(command)
        return ShellPeerResponse(
            command.request_id, ShellPeerOperation.CONTEXT, 0, 1,
            context_evidence=(evidence,),
        )
    if isinstance(command, ShellPeerProbeRequest):
        peer = service.probe(command.enrollment_id, command.request_id)
        return ShellPeerResponse(
            command.request_id, ShellPeerOperation.PROBE, 0, 1, peers=(peer,),
        )
    if not isinstance(command, ShellPeerQuery):
        raise ValueError("unsupported Shell peer request")
    values = (
        service.trusted_peers()
        if command.operation is ShellPeerOperation.PEERS
        else service.control_receipts()
        if command.operation is ShellPeerOperation.RECEIPTS
        else service.context_evidence()
    )
    page = values[command.offset:command.offset + command.limit]
    fields = (
        {"peers": page} if command.operation is ShellPeerOperation.PEERS
        else {"control_receipts": page}
        if command.operation is ShellPeerOperation.RECEIPTS
        else {"context_evidence": page}
    )
    return ShellPeerResponse(
        command.request_id, command.operation, command.offset, len(values), **fields,
    )
