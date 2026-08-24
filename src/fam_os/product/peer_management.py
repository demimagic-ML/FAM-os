"""Authoritative owner service for trusted peer discovery, probing, and control."""

from __future__ import annotations

import time
from datetime import UTC, datetime
from uuid import uuid4

from fam_os.fabric import (
    MutualTlsPeerClient,
    PairedPeerTrust,
    PeerControlOperation,
    PeerControlRequest,
    PeerControlResponse,
    PeerControlStatus,
    PeerManagementOperation,
    PeerPerformanceObservation,
)
from fam_os.fabric.peer_directory import TrustedPeerDirectoryEntry
from fam_os.schemas import dumps_document, loads_document


class ProductPeerManagement:
    def __init__(
        self, enrollments, state, peer_service, owner_id: str, *, clock=None,
        monotonic=None, context=None,
    ) -> None:
        if not owner_id.strip():
            raise ValueError("peer management owner is invalid")
        self._enrollments = enrollments
        self._state = state
        self._peer_service = peer_service
        self._owner_id = owner_id
        self._clock = clock or (lambda: datetime.now(UTC))
        self._monotonic = monotonic or time.perf_counter
        self._context = context

    def trusted_peers(self) -> tuple[TrustedPeerDirectoryEntry, ...]:
        """Project only active enrollments; this method can never enroll a device."""
        now = self._clock()
        return tuple(self._entry(record, now) for record in self._enrollments.active())

    @property
    def owner_id(self) -> str:
        return self._owner_id

    def peer(self, enrollment_id: str) -> TrustedPeerDirectoryEntry:
        for item in self.trusted_peers():
            if item.enrollment_id == enrollment_id:
                return item
        raise KeyError(f"trusted peer does not exist: {enrollment_id}")

    def probe(
        self, enrollment_id: str, request_id: str | None = None,
    ) -> TrustedPeerDirectoryEntry:
        record = self._active(enrollment_id)
        trust = PairedPeerTrust(
            self._peer_service.credentials,
            tuple(item.approval for item in self._enrollments.active()),
            self._owner_id,
        )
        issued = self._clock()
        request = PeerControlRequest(
            request_id or "peer-probe-" + uuid4().hex,
            self._peer_service.credentials.identity.device_id,
            PeerControlOperation.DESCRIBE, issued,
        )
        payload = dumps_document(request).encode()
        started = self._monotonic()
        authenticated, raw = MutualTlsPeerClient(trust).request(
            record.approval.peer_identity.device_id, payload,
        )
        elapsed_ms = (self._monotonic() - started) * 1_000
        response = loads_document(raw.decode())
        if not isinstance(response, PeerControlResponse):
            raise TypeError("peer probe returned an unexpected contract")
        if (
            response.request_id != request.request_id
            or response.responder_device_id != authenticated.device_id
            or response.status is not PeerControlStatus.READY
        ):
            raise PermissionError("peer probe response identity is invalid")
        observed = self._clock()
        for declaration in response.capabilities:
            self._state.put_capability(enrollment_id, declaration, observed)
        self._state.add_performance(PeerPerformanceObservation(
            "peer-performance-" + uuid4().hex, enrollment_id,
            authenticated.device_id, elapsed_ms, len(raw), observed,
            authenticated.certificate_sha256,
            tls_version=authenticated.tls_version,
        ))
        return self.peer(enrollment_id)

    def apply_control(self, request):
        receipt = self._state.apply_control(request, self._clock())
        if receipt.applied and receipt.operation is PeerManagementOperation.REVOKE:
            self._peer_service.reload_trust()
        return receipt

    def control_receipts(self):
        return self._state.receipts()

    def send_context(self, request):
        if self._context is None:
            raise PermissionError("peer context transfer is unavailable")
        return self._context.send(request)

    def context_evidence(self):
        if self._context is None:
            return ()
        return self._context.evidence()

    def _active(self, enrollment_id):
        record = self._enrollments.get(enrollment_id)
        if record is None or not record.active:
            raise KeyError("active peer enrollment does not exist")
        return record

    def _entry(self, record, now):
        performance = self._state.performance(record.enrollment_id)
        approval = record.approval
        return TrustedPeerDirectoryEntry(
            record.enrollment_id, record.revision,
            approval.peer_identity.device_id, approval.peer_identity.display_name,
            approval.peer_endpoint,
            self._state.capabilities(record.enrollment_id, now),
            performance[0] if performance else None,
            self._state.privacy(record.enrollment_id),
        )
