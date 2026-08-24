"""Fail-closed outbound minimum-context transfer to an authenticated peer."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime
from collections.abc import Sequence

from cryptography.hazmat.primitives import hashes

from fam_os.fabric.context_evidence import (
    RemoteContextDirection,
    RemoteContextDisclosureEvidence,
    RemoteContextSendRequest,
)
from fam_os.fabric.context import RemoteContextEnvelope, RemoteContextReceipt
from fam_os.fabric.enrollment import PeerEnrollmentRecord
from fam_os.fabric.context_signing import (
    create_remote_context,
    verify_remote_context_receipt,
)
from fam_os.fabric.peer_control import (
    PeerControlOperation,
    PeerControlRequest,
    PeerControlResponse,
    PeerControlStatus,
)
from fam_os.fabric.privacy import (
    RemoteContextRequest,
    RemotePrivacyEvaluator,
)
from fam_os.fabric.peer_state import (
    PeerCapabilityDeclaration,
    PeerPrivacyPolicyRecord,
)
from fam_os.fabric.tls_transport import MutualTlsPeerClient
from fam_os.fabric.tls_trust import PairedPeerTrust
from fam_os.schemas import dumps_document, loads_document


@dataclass(frozen=True, slots=True)
class PreparedRemoteContextTransfer:
    request: RemoteContextSendRequest
    request_sha256: str
    enrollment: PeerEnrollmentRecord
    privacy: PeerPrivacyPolicyRecord
    declaration: PeerCapabilityDeclaration
    context: RemoteContextEnvelope


class ProductPeerContextService:
    """Authorize, send, authenticate, and record a context disclosure."""

    def __init__(
        self, enrollments, peer_state, context_evidence, peer_service,
        owner_id: str, *, clock=None, client_factory=None,
    ) -> None:
        if not owner_id.strip():
            raise ValueError("peer context owner is invalid")
        self._enrollments = enrollments
        self._peer_state = peer_state
        self._evidence = context_evidence
        self._peer_service = peer_service
        self._owner_id = owner_id
        self._clock = clock or (lambda: datetime.now(UTC))
        self._client_factory = client_factory or MutualTlsPeerClient
        self._privacy = RemotePrivacyEvaluator()

    def send(
        self, request: RemoteContextSendRequest,
    ) -> RemoteContextDisclosureEvidence:
        request_sha256 = self.request_sha256(request)
        existing = self._evidence.for_request(
            RemoteContextDirection.OUTBOUND, request.request_id,
        )
        if existing is not None:
            if existing.request_sha256 != request_sha256:
                raise ValueError("remote context request identity was reused")
            return existing

        prepared = self.prepare(request)
        enrollment = prepared.enrollment
        peer_device_id = enrollment.approval.peer_identity.device_id
        issued_at = prepared.context.issued_at

        trust = PairedPeerTrust(
            self._peer_service.credentials,
            tuple(item.approval for item in self._enrollments.active()),
            self._owner_id,
        )
        control = PeerControlRequest(
            request.request_id, self._peer_service.credentials.identity.device_id,
            PeerControlOperation.CONTEXT, issued_at, prepared.context,
        )
        authenticated, raw = self._client_factory(trust).request(
            peer_device_id, dumps_document(control).encode("utf-8"),
        )
        response = loads_document(raw.decode("utf-8"))
        receipt = self._verified_receipt(
            request, prepared.context, response, authenticated, enrollment,
        )
        return self.record(prepared, receipt, (
            "privacy.approved", "capability.signed_and_current",
            "context.bytes_exact", "context.receipt_verified",
        ))

    def prepare(
        self, request: RemoteContextSendRequest,
    ) -> PreparedRemoteContextTransfer:
        request_sha256 = self.request_sha256(request)
        enrollment = self._active_enrollment(request.enrollment_id)
        peer_device_id = enrollment.approval.peer_identity.device_id
        privacy = self._privacy_record(request)
        declaration = self._capability(request, peer_device_id)
        issued_at = self._clock()
        context = create_remote_context(
            self._peer_service.credentials,
            context_id=_context_id(request.enrollment_id, request_sha256),
            request_id=request.request_id,
            receiver_device_id=peer_device_id,
            target_expert_id=request.target_expert_id,
            purpose_id=request.purpose_id,
            workspace_id=request.workspace_id,
            sensitivity=request.sensitivity,
            descriptor=request.descriptor,
            raw_fragments=request.raw_fragments,
            issued_at=issued_at,
        )
        self._authorize(request, context, privacy.policy, peer_device_id)
        if context.content_bytes > declaration.maximum_context_bytes:
            raise PermissionError("remote context exceeds signed capability ceiling")
        return PreparedRemoteContextTransfer(
            request, request_sha256, enrollment, privacy, declaration, context,
        )

    def record(
        self,
        prepared: PreparedRemoteContextTransfer,
        receipt: RemoteContextReceipt,
        reason_codes: Sequence[str],
    ) -> RemoteContextDisclosureEvidence:
        request = prepared.request
        peer_device_id = prepared.enrollment.approval.peer_identity.device_id
        evidence = RemoteContextDisclosureEvidence(
            _evidence_id(request.enrollment_id, request.request_id), request.request_id,
            prepared.request_sha256, request.enrollment_id, peer_device_id,
            RemoteContextDirection.OUTBOUND, prepared.context.context_id,
            request.target_expert_id, request.purpose_id, request.workspace_id,
            request.sensitivity, prepared.context.content_bytes,
            prepared.context.content_sha256,
            tuple(item.content_sha256 for item in request.raw_fragments),
            prepared.privacy.revision, prepared.declaration.declaration_id, receipt,
            tuple(reason_codes), self._clock(),
        )
        existing = self._evidence.for_request(
            RemoteContextDirection.OUTBOUND, request.request_id,
        )
        if existing is not None:
            if existing.request_sha256 != prepared.request_sha256:
                raise ValueError("remote context request identity was reused")
            return existing
        self._evidence.add(evidence)
        return evidence

    @staticmethod
    def request_sha256(request: RemoteContextSendRequest) -> str:
        return hashlib.sha256(
            dumps_document(request).encode("utf-8"),
        ).hexdigest()

    def evidence(self) -> tuple[RemoteContextDisclosureEvidence, ...]:
        return self._evidence.all()

    def _active_enrollment(self, enrollment_id):
        record = self._enrollments.get(enrollment_id)
        if record is None or not record.active:
            raise PermissionError("remote context requires active enrollment")
        return record

    def _privacy_record(self, request):
        record = self._peer_state.privacy(request.enrollment_id)
        if record is None:
            raise PermissionError("remote context disclosure defaults to denied")
        if record.revision != request.expected_privacy_revision:
            raise RuntimeError("remote context privacy revision changed")
        return record

    def _capability(self, request, peer_device_id):
        matches = tuple(
            declaration for declaration in self._peer_state.capabilities(
                request.enrollment_id, self._clock(),
            )
            if declaration.declaration_id == request.capability_declaration_id
        )
        if len(matches) != 1:
            raise PermissionError("remote context capability is unavailable")
        declaration = matches[0]
        required = set(request.descriptor.capability_ids)
        if (
            declaration.device_id != peer_device_id
            or declaration.expert_id != request.target_expert_id
            or not required.issubset(declaration.capability_ids)
        ):
            raise PermissionError("remote context differs from signed capability")
        return declaration

    def _authorize(self, request, context, policy, peer_device_id) -> None:
        decision = self._privacy.decide(policy, RemoteContextRequest(
            self._owner_id, peer_device_id, request.purpose_id,
            request.workspace_id, request.sensitivity, context.content_bytes,
            context.contains_raw_content,
        ))
        if not decision.allowed:
            raise PermissionError(
                "remote context disclosure denied: " + ",".join(decision.reason_codes),
            )

    def _verified_receipt(
        self, request, context, response, authenticated, enrollment,
    ):
        if not isinstance(response, PeerControlResponse):
            raise TypeError("remote context returned an unexpected contract")
        local_fingerprint = self._peer_service.credentials.tls_certificate.fingerprint(
            hashes.SHA256(),
        ).hex()
        if (
            response.request_id != request.request_id
            or response.responder_device_id != authenticated.device_id
            or authenticated.device_id
            != enrollment.approval.peer_identity.device_id
            or response.status is not PeerControlStatus.READY
            or response.peer_certificate_sha256 != local_fingerprint
            or response.capabilities
            or response.context_receipt is None
        ):
            raise PermissionError("remote context response identity is invalid")
        verify_remote_context_receipt(
            response.context_receipt, context,
            enrollment.approval.peer_identity,
        )
        return response.context_receipt


def _context_id(enrollment_id: str, request_sha256: str) -> str:
    value = hashlib.sha256(
        f"{enrollment_id}|{request_sha256}".encode("utf-8"),
    ).hexdigest()[:32]
    return "remote-context-" + value


def _evidence_id(enrollment_id: str, request_id: str) -> str:
    value = hashlib.sha256(
        f"{enrollment_id}|{request_id}".encode("utf-8"),
    ).hexdigest()[:32]
    return "context-outbound-" + value
