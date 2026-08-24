"""Durable intent-before-effect state for the external network broker."""

import hashlib
import json
import os
from pathlib import Path
import tempfile

from fam_os.core.engineering.integration_network import (
    IntegrationNetworkEnforcementRequest, IntegrationNetworkLease,
    IntegrationNetworkUsage,
)
from fam_os.schemas import dumps_document, loads_document


def network_enforcement_id(environment_id: str) -> str:
    suffix = hashlib.sha256(environment_id.encode("utf-8")).hexdigest()[:24]
    return "fam-network-" + suffix


class NetworkBrokerStateStore:
    def __init__(self, root: Path) -> None:
        if not root.is_absolute():
            raise ValueError("network broker state root must be absolute")
        self._root = root

    def begin(self, request: IntegrationNetworkEnforcementRequest) -> str:
        self._prepare()
        identity = network_enforcement_id(request.environment_id)
        document = self._document(identity, "opening", request, None, None)
        path = self._path(identity)
        descriptor = os.open(
            path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600,
        )
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            _dump(stream, document)
        return identity

    def activate(self, request, lease) -> None:
        document = self._require(request)
        if document["state"] != "opening":
            raise PermissionError("network broker intent is not opening")
        document.update(state="active", lease=dumps_document(lease))
        self._write(document)

    def require_lease(self, lease: IntegrationNetworkLease) -> dict:
        document = self.load(lease.enforcement_id)
        if document["state"] != "active" or document["lease"] != dumps_document(lease):
            raise PermissionError("network broker lease is not exact and active")
        return document

    def finalize(self, identity: str, usage: IntegrationNetworkUsage, state: str) -> None:
        if state not in {"closed", "recovered", "compensated"}:
            raise ValueError("network broker terminal state is invalid")
        document = self.load(identity)
        document.update(state=state, usage=dumps_document(usage))
        self._write(document)

    def load(self, identity: str) -> dict:
        path = self._path(identity)
        details = path.stat(follow_symlinks=False)
        if path.is_symlink() or details.st_uid != os.geteuid() or details.st_mode & 0o077:
            raise PermissionError("network broker state ownership is invalid")
        document = json.loads(path.read_text("utf-8"))
        expected = {"enforcement_id", "state", "request", "lease", "usage"}
        if not isinstance(document, dict) or set(document) != expected:
            raise ValueError("network broker state shape is invalid")
        request = loads_document(document["request"])
        if not isinstance(request, IntegrationNetworkEnforcementRequest):
            raise ValueError("network broker request state is invalid")
        if document["enforcement_id"] != network_enforcement_id(request.environment_id):
            raise ValueError("network broker state identity is invalid")
        state = document["state"]
        if state not in {"opening", "active", "closed", "recovered", "compensated"}:
            raise ValueError("network broker state value is invalid")
        lease = None if document["lease"] is None else loads_document(document["lease"])
        usage = None if document["usage"] is None else loads_document(document["usage"])
        if lease is not None and not isinstance(lease, IntegrationNetworkLease):
            raise ValueError("network broker lease state is invalid")
        if usage is not None and not isinstance(usage, IntegrationNetworkUsage):
            raise ValueError("network broker usage state is invalid")
        if state == "opening" and (lease is not None or usage is not None):
            raise ValueError("opening network state cannot contain evidence")
        if state == "active" and (lease is None or usage is not None):
            raise ValueError("active network state requires only a lease")
        if state in {"closed", "recovered", "compensated"} and (
            usage is None or not usage.finalized
        ):
            raise ValueError("terminal network state requires finalized usage")
        return document

    def _require(self, request):
        document = self.load(network_enforcement_id(request.environment_id))
        if document["request"] != dumps_document(request):
            raise PermissionError("network broker request differs from durable intent")
        return document

    def _prepare(self):
        self._root.mkdir(parents=True, exist_ok=True, mode=0o700)
        details = self._root.stat(follow_symlinks=False)
        if self._root.is_symlink() or details.st_uid != os.geteuid() or details.st_mode & 0o077:
            raise PermissionError("network broker state root ownership is invalid")

    def _path(self, identity):
        if not identity.startswith("fam-network-") or "/" in identity:
            raise ValueError("network enforcement identity is invalid")
        return self._root / (identity + ".json")

    def _write(self, document):
        descriptor, raw = tempfile.mkstemp(prefix=".network-", dir=self._root)
        temporary = Path(raw)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                _dump(stream, document)
            os.replace(temporary, self._path(document["enforcement_id"]))
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _document(identity, state, request, lease, usage):
        return {
            "enforcement_id": identity, "state": state,
            "request": dumps_document(request),
            "lease": None if lease is None else dumps_document(lease),
            "usage": None if usage is None else dumps_document(usage),
        }


def _dump(stream, document):
    json.dump(document, stream, sort_keys=True, separators=(",", ":"))
    stream.write("\n"); stream.flush(); os.fsync(stream.fileno())
