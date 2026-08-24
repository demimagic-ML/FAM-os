"""Configured permission-filtered MCP ingress owned by the product service."""

from __future__ import annotations

import json
import re
import socket
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Event, Thread
from uuid import uuid4

from fam_os.adapters.mcp.ingress import UnixMcpIngressServer
from fam_os.core.admission import (
    RequestAdmissionService, RequestAuthorityGrant, RequestIdentity,
)
from fam_os.core.ingress import (
    InMemoryIngressCapabilityRegistry, IngressCapability,
    LifecycleCoreIngressGateway,
)
from fam_os.product.composition.mcp_ingress_executor import ProductionMcpTaskExecutor


MCP_INGRESS_CONFIG_VERSION = "fam.product.mcp-ingress/v1alpha1"
_SUPPORTED_CAPABILITIES = {"fam.ask", "fam.ask.verified"}
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:@/-]{0,127}$")


class ProductMcpIngress:
    def __init__(self, server: UnixMcpIngressServer | None) -> None:
        self._server = server
        self._stop = Event()
        self._thread: Thread | None = None
        self.failure: str | None = None

    @classmethod
    def from_file(
        cls, config_path: Path, socket_path: Path, owner_uid: int,
        gateway, repositories,
    ) -> "ProductMcpIngress":
        if not config_path.exists():
            return cls(None)
        _require_private(config_path, owner_uid)
        document = json.loads(config_path.read_text(encoding="utf-8"))
        clients = _configuration(document)
        if not document["enabled"]:
            return cls(None)
        identities = _authorize_clients(clients, repositories)
        capabilities = InMemoryIngressCapabilityRegistry(_capabilities())
        admission = RequestAdmissionService(
            repositories.authorities, repositories.request_replay,
        )
        core_gateway = LifecycleCoreIngressGateway(
            capabilities, repositories.authorities, admission,
            ProductionMcpTaskExecutor(gateway),
        )
        return cls(UnixMcpIngressServer(
            socket_path, owner_uid, identities, core_gateway,
        ))

    @property
    def enabled(self) -> bool:
        return self._server is not None

    def start(self) -> None:
        if self._server is None:
            return
        self._server.open()
        self._thread = Thread(target=self._serve, name="fam-mcp-ingress", daemon=True)
        self._thread.start()

    def close(self) -> None:
        self._stop.set()
        if self._server is not None:
            _wake(self._server.path)
        if self._thread is not None:
            self._thread.join(timeout=5)
            self._thread = None
        if self._server is not None:
            self._server.close()

    def _serve(self) -> None:
        assert self._server is not None
        while not self._stop.is_set():
            try:
                self._server.serve_once()
            except OSError as error:
                if not self._stop.is_set():
                    self.failure = type(error).__name__
                    self._stop.set()


def _configuration(document):
    if not isinstance(document, dict) or set(document) != {
        "contract_version", "enabled", "clients",
    }:
        raise ValueError("MCP ingress configuration fields are invalid")
    if document["contract_version"] != MCP_INGRESS_CONFIG_VERSION:
        raise ValueError("MCP ingress configuration version is unsupported")
    if not isinstance(document["enabled"], bool):
        raise ValueError("MCP ingress enabled flag is invalid")
    clients = document["clients"]
    if not isinstance(clients, list) or len(clients) > 32:
        raise ValueError("MCP ingress client list is invalid")
    parsed = tuple(_client(value) for value in clients)
    if len({item[0] for item in parsed}) != len(parsed):
        raise ValueError("MCP ingress client IDs must be unique")
    if document["enabled"] and not parsed:
        raise ValueError("enabled MCP ingress requires an allowlisted client")
    return parsed


def _client(value):
    if not isinstance(value, dict) or set(value) != {
        "client_id", "principal_id", "capabilities", "session_ttl_seconds",
    }:
        raise ValueError("MCP ingress client fields are invalid")
    client_id, principal_id = value["client_id"], value["principal_id"]
    capabilities = value["capabilities"]
    ttl = value["session_ttl_seconds"]
    if not all(
        isinstance(item, str) and _IDENTIFIER.fullmatch(item)
        for item in (client_id, principal_id)
    ):
        raise ValueError("MCP ingress client identity is invalid")
    if (
        not isinstance(capabilities, list) or not capabilities
        or len(capabilities) != len(set(capabilities))
        or not set(capabilities) <= _SUPPORTED_CAPABILITIES
    ):
        raise ValueError("MCP ingress client capabilities are invalid")
    if not isinstance(ttl, int) or isinstance(ttl, bool) or not 60 <= ttl <= 86_400:
        raise ValueError("MCP ingress session TTL is invalid")
    return client_id, principal_id, tuple(capabilities), ttl


def _authorize_clients(clients, repositories):
    now = datetime.now(timezone.utc)
    identities = {}
    for client_id, principal_id, capabilities, ttl in clients:
        nonce = str(uuid4())
        authority_ref = f"mcp-authority-{client_id}-{nonce}"
        session_id = f"mcp-session-{client_id}-{nonce}"
        grant = RequestAuthorityGrant(
            authority_ref, principal_id, session_id, capabilities,
            now - timedelta(seconds=1), now + timedelta(seconds=ttl),
        )
        if not repositories.authorities.add(grant):
            raise RuntimeError("MCP ingress authority could not be persisted")
        identities[client_id] = (RequestIdentity(
            principal_id, session_id, authority_ref,
        ), 60)
    return identities


def _capabilities():
    prompt = {
        "type": "object", "properties": {
            "prompt": {"type": "string", "minLength": 1, "maxLength": 131072},
        }, "required": ["prompt"], "additionalProperties": False,
    }
    output = {"type": "object"}
    return (
        IngressCapability(
            "fam.ask", "Ask FAM", "Submit a local FAM task.",
            prompt, output, verification_required=False,
        ),
        IngressCapability(
            "fam.ask.verified", "Ask FAM with verification",
            "Submit a local FAM task that must pass declared verification.",
            prompt, output, verification_required=True,
        ),
    )


def _require_private(path: Path, owner_uid: int) -> None:
    details = path.lstat()
    if path.is_symlink() or not path.is_file() or details.st_uid != owner_uid:
        raise PermissionError("MCP ingress configuration must be owner controlled")
    if details.st_mode & 0o077:
        raise PermissionError("MCP ingress configuration must be mode 0600")


def _wake(path: Path) -> None:
    try:
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as stream:
            stream.connect(str(path))
    except OSError:
        pass
