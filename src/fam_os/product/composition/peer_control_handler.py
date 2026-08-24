"""Schema-validated peer control handler behind authenticated transport."""

from fam_os.fabric.peer_control import (
    PeerControlOperation,
    PeerControlRequest,
    PeerControlResponse,
    PeerControlStatus,
)
from fam_os.fabric.tls_trust import AuthenticatedPeer
from fam_os.fabric.context_signing import (
    create_remote_context_receipt, verify_remote_context,
)
from fam_os.fabric.remote_execution import RemoteExecutionRequest
from fam_os.fabric.remote_execution_signing import verify_remote_execution_request
from fam_os.schemas import dumps_document, loads_document


class PeerControlHandler:
    def __init__(
        self, local_device_id: str, *, now, capabilities=None, peer_active=None,
        credentials=None, peer_identity=None, context_recorder=None,
        context_capability=None,
        remote_execution=None,
    ) -> None:
        if not local_device_id.strip():
            raise ValueError("local peer control identity is invalid")
        self._local_device_id = local_device_id
        self._now = now
        self._capabilities = capabilities or (lambda _at: ())
        self._peer_active = peer_active or (lambda _device_id: True)
        self._credentials = credentials
        self._peer_identity = peer_identity
        self._context_recorder = context_recorder
        self._context_capability = context_capability
        self._remote_execution = remote_execution

    def __call__(self, peer: AuthenticatedPeer, payload: bytes) -> bytes:
        value = loads_document(payload.decode("utf-8"))
        if isinstance(value, RemoteExecutionRequest):
            return self._execute(peer, value)
        if not isinstance(value, PeerControlRequest):
            raise TypeError("peer endpoint accepts only control requests")
        if value.sender_device_id != peer.device_id:
            raise PermissionError("peer control sender differs from TLS identity")
        if not self._peer_active(peer.device_id):
            raise PermissionError("peer enrollment is no longer active")
        if value.operation not in {
            PeerControlOperation.HEALTH,
            PeerControlOperation.DESCRIBE,
            PeerControlOperation.CONTEXT,
        }:
            raise ValueError("peer control operation is unsupported")
        observed_at = self._now()
        capabilities = (
            self._capabilities(observed_at)
            if value.operation is PeerControlOperation.DESCRIBE else ()
        )
        context_receipt = None
        if value.operation is PeerControlOperation.CONTEXT:
            context_receipt = self._accept_context(peer, value.context, observed_at)
        response = PeerControlResponse(
            value.request_id, self._local_device_id, PeerControlStatus.READY,
            observed_at, peer.certificate_sha256, capabilities, context_receipt,
        )
        return dumps_document(response).encode("utf-8")

    def _execute(self, peer, request):
        if request.context.sender_device_id != peer.device_id:
            raise PermissionError("remote execution sender differs from TLS identity")
        if not self._peer_active(peer.device_id):
            raise PermissionError("peer enrollment is no longer active")
        if self._remote_execution is None:
            raise PermissionError("remote execution endpoint is unavailable")
        observed_at = self._now()
        identity = self._peer_identity(peer.device_id)
        verify_remote_execution_request(request, identity)
        receipt = self._accept_context(peer, request.context, observed_at)
        result = self._remote_execution(
            peer, request, receipt, observed_at,
        )
        return dumps_document(result).encode("utf-8")

    def _accept_context(self, peer, context, observed_at):
        if (
            context is None or self._credentials is None
            or self._peer_identity is None or self._context_recorder is None
            or self._context_capability is None
        ):
            raise PermissionError("remote context endpoint is unavailable")
        if context.receiver_device_id != self._local_device_id:
            raise PermissionError("remote context targets another device")
        identity = self._peer_identity(peer.device_id)
        verify_remote_context(context, identity, observed_at)
        if not self._context_capability(context, observed_at):
            raise PermissionError("remote context target capability is unavailable")
        receipt = create_remote_context_receipt(
            self._credentials, context, observed_at,
        )
        self._context_recorder(peer, context, receipt, observed_at)
        return receipt
