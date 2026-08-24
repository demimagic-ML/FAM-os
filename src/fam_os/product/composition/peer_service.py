"""Installed lifecycle for persistent identity and the authenticated peer listener."""

from __future__ import annotations

import hashlib
import logging
import socket
import ssl
import threading
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from fam_os.fabric import (
    MutualTlsPeerServer,
    PairedPeerTrust,
    PeerTlsServerSettings,
    PersistentDeviceCredentials,
    PersistentDeviceIdentityStore,
)
from fam_os.product.composition.peer_control_handler import PeerControlHandler
from fam_os.fabric.context_evidence import (
    RemoteContextDirection, RemoteContextDisclosureEvidence,
)
from fam_os.schemas import dumps_document

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ProductPeerSettings:
    state_root: Path
    display_name: str
    listen_host: str | None = None
    listen_port: int = 48121

    def __post_init__(self) -> None:
        if not self.display_name.strip() or not 0 <= self.listen_port <= 65535:
            raise ValueError("product peer settings are invalid")
        if self.listen_host is not None and not self.listen_host.strip():
            raise ValueError("product peer listen host is invalid")


@dataclass(frozen=True, slots=True)
class ProductPeerStatus:
    device_id: str
    state: str
    listen_host: str | None
    listen_port: int | None
    active_peer_count: int
    rejected_connection_count: int
    failure: str | None


class ProductPeerService:
    def __init__(
        self, settings: ProductPeerSettings, repository, owner_uid: int,
        capability_source=None, context_repository=None,
        remote_execution=None,
    ) -> None:
        self.settings = settings
        self._repository = repository
        self._owner_uid = owner_uid
        self._credentials: PersistentDeviceCredentials | None = None
        self._server: MutualTlsPeerServer | None = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._listener_stop = threading.Event()
        self._lock = threading.RLock()
        self._capability_source = capability_source or (lambda _credentials, _at: ())
        self._context_repository = context_repository
        self._remote_execution = remote_execution
        self._rejected = 0
        self._failure: str | None = None

    @property
    def credentials(self) -> PersistentDeviceCredentials:
        if self._credentials is None:
            raise RuntimeError("product peer identity is not initialized")
        return self._credentials

    def start(self) -> ProductPeerStatus:
        with self._lock:
            if self._credentials is not None:
                return self.status()
            self._credentials = PersistentDeviceIdentityStore(
                self.settings.state_root / "fabric/identity", self._owner_uid,
            ).resolve(self.settings.display_name)
            self._stop.clear()
            self._start_listener()
            return self.status()

    def reload_trust(self) -> ProductPeerStatus:
        """Close first, then rebuild trust from durable active enrollments."""
        with self._lock:
            if self._credentials is None:
                raise RuntimeError("product peer service is not started")
            self._stop_listener()
            self._failure = None
            self._start_listener()
            return self.status()

    def stop(self) -> None:
        with self._lock:
            self._stop.set()
            self._stop_listener()
            self._credentials = None

    def status(self) -> ProductPeerStatus:
        credentials = self.credentials
        server = self._server
        records = self._repository.active()
        if self._failure is not None:
            state = "failed"
        elif server is not None:
            state = "listening"
        elif self.settings.listen_host is None:
            state = "disabled"
        else:
            state = "awaiting_pairing"
        address = server.address if server is not None else None
        return ProductPeerStatus(
            credentials.identity.device_id, state,
            None if address is None else address.host,
            None if address is None else address.port,
            len(records), self._rejected, self._failure,
        )

    def _start_listener(self) -> None:
        credentials = self.credentials
        records = self._repository.active()
        if self.settings.listen_host is None or not records:
            return
        trust = PairedPeerTrust(
            credentials, tuple(record.approval for record in records), str(self._owner_uid),
        )
        handler = PeerControlHandler(
            credentials.identity.device_id, now=lambda: datetime.now(UTC),
            capabilities=lambda at: self._capability_source(credentials, at),
            peer_active=self._is_active,
            credentials=credentials,
            peer_identity=self._peer_identity,
            context_recorder=self._record_context,
            context_capability=self._context_capable,
            remote_execution=self._execute_remote,
        )
        server = MutualTlsPeerServer(
            PeerTlsServerSettings(self.settings.listen_host, self.settings.listen_port),
            trust, handler,
        )
        server.open()
        self._server = server
        self._listener_stop.clear()
        self._thread = threading.Thread(
            target=self._serve, args=(server,), name="fam-peer-listener", daemon=True,
        )
        self._thread.start()

    def _stop_listener(self) -> None:
        self._listener_stop.set()
        server, self._server = self._server, None
        if server is not None:
            server.close()
        thread, self._thread = self._thread, None
        if thread is not None:
            thread.join(timeout=5)

    def _is_active(self, device_id: str) -> bool:
        return any(
            record.approval.peer_identity.device_id == device_id
            for record in self._repository.active()
        )

    def _peer_identity(self, device_id: str):
        matches = tuple(
            record.approval.peer_identity for record in self._repository.active()
            if record.approval.peer_identity.device_id == device_id
        )
        if len(matches) != 1:
            raise PermissionError("remote context peer is not uniquely active")
        return matches[0]

    def _record_context(self, peer, context, receipt, observed_at) -> None:
        if self._context_repository is None:
            raise PermissionError("remote context evidence repository is unavailable")
        record = next(
            (
                item for item in self._repository.active()
                if item.approval.peer_identity.device_id == peer.device_id
            ), None,
        )
        if record is None:
            raise PermissionError("remote context peer enrollment is inactive")
        evidence_id = "context-inbound-" + hashlib.sha256(
            f"{record.enrollment_id}|{context.request_id}".encode(),
        ).hexdigest()[:32]
        self._context_repository.add(RemoteContextDisclosureEvidence(
            evidence_id, context.request_id,
            hashlib.sha256(dumps_document(context).encode()).hexdigest(),
            record.enrollment_id, peer.device_id,
            RemoteContextDirection.INBOUND, context.context_id,
            context.target_expert_id, context.purpose_id, context.workspace_id,
            context.sensitivity, context.content_bytes, context.content_sha256,
            tuple(item.content_sha256 for item in context.raw_fragments),
            None, None, receipt, (
                "context.signature_valid", "context.bytes_exact",
                "context.capability_valid",
            ),
            observed_at,
        ))

    def _context_capable(self, context, observed_at) -> bool:
        required = set(context.descriptor.capability_ids)
        return any(
            declaration.expert_id == context.target_expert_id
            and required.issubset(declaration.capability_ids)
            and context.content_bytes <= declaration.maximum_context_bytes
            for declaration in self._capability_source(self.credentials, observed_at)
        )

    def _execute_remote(self, peer, request, receipt, observed_at):
        if self._remote_execution is None:
            raise PermissionError("remote execution endpoint is unavailable")
        return self._remote_execution.execute(
            self.credentials, peer, request, receipt, observed_at,
        )

    def _serve(self, server) -> None:
        while not self._stop.is_set() and not self._listener_stop.is_set():
            try:
                server.serve_once()
            except socket.timeout:
                continue
            except (ConnectionError, PermissionError, TypeError, ValueError, ssl.SSLError):
                self._rejected += 1
            except OSError as error:
                if not self._stop.is_set() and not self._listener_stop.is_set():
                    self._failure = f"{type(error).__name__}: {error}"
                    LOGGER.exception("peer listener stopped after an operating-system failure")
                return
            except Exception as error:
                self._failure = f"{type(error).__name__}: {error}"
                LOGGER.exception("peer listener stopped after an unexpected failure")
                return
