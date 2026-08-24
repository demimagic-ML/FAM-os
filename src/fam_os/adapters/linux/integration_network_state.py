"""Root-owned durable state for one Linux network attachment."""

import json
import os
from pathlib import Path
import tempfile
from threading import RLock
import re

from fam_os.supervisor.network_contracts import NetworkEnforcementSpec


class LinuxIntegrationNetworkState:
    def __init__(self, root: Path, identity: str) -> None:
        if not root.is_absolute() or not identity.startswith("fam-network-"):
            raise ValueError("Linux network state identity is invalid")
        self._root, self._path, self._identity = root, root / (identity + ".json"), identity
        self._lock = RLock()

    def claim(self, spec: NetworkEnforcementSpec) -> None:
        self._prepare()
        document = {
            "enforcement_id": self._identity, "request_digest": spec.request_digest,
            "stage": "claimed", "proxy_port": None,
            "allowed_destinations": list(spec.destinations),
            "observed_destinations": [],
            "maximum_network_bytes": spec.maximum_network_bytes,
            "transmitted_bytes": 0, "received_bytes": 0,
            "quota_exceeded": False,
        }
        descriptor = os.open(
            self._path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600,
        )
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            _dump(stream, document)

    def stage(self, value: str, *, proxy_port=None) -> None:
        if value not in {"namespace", "proxy", "ready", "closed", "recovered"}:
            raise ValueError("Linux network state stage is invalid")
        with self._lock:
            document = self.load(); document["stage"] = value
            if proxy_port is not None:
                if not 1 <= proxy_port <= 65535:
                    raise ValueError("Linux network proxy port is invalid")
                document["proxy_port"] = proxy_port
            self._write(document)

    def record_usage(self, usage) -> None:
        with self._lock:
            document = self.load()
            if not set(usage.destinations).issubset(document["allowed_destinations"]):
                raise ValueError("Linux network usage destinations are mismatched")
            document.update(
                observed_destinations=list(usage.destinations),
                transmitted_bytes=usage.transmitted_bytes,
                received_bytes=usage.received_bytes,
                quota_exceeded=usage.quota_exceeded,
            )
            self._write(document)

    def load(self):
        details = self._path.stat(follow_symlinks=False)
        if self._path.is_symlink() or details.st_uid != os.geteuid() or details.st_mode & 0o077:
            raise PermissionError("Linux network state ownership is invalid")
        value = json.loads(self._path.read_text("utf-8"))
        expected = {
            "enforcement_id", "request_digest", "stage", "proxy_port",
            "allowed_destinations", "observed_destinations",
            "maximum_network_bytes", "transmitted_bytes",
            "received_bytes", "quota_exceeded",
        }
        if not isinstance(value, dict) or set(value) != expected:
            raise ValueError("Linux network state shape is invalid")
        if value["enforcement_id"] != self._identity:
            raise ValueError("Linux network state identity is mismatched")
        if not re.fullmatch(r"[0-9a-f]{64}", value["request_digest"]):
            raise ValueError("Linux network request digest is invalid")
        if value["stage"] not in {"claimed", "namespace", "proxy", "ready", "closed", "recovered"}:
            raise ValueError("Linux network state stage is invalid")
        counts = value["transmitted_bytes"], value["received_bytes"]
        if any(isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in counts):
            raise ValueError("Linux network state counts are invalid")
        if sum(counts) > value["maximum_network_bytes"]:
            raise ValueError("Linux network state exceeds its quota")
        if (
            isinstance(value["maximum_network_bytes"], bool)
            or not isinstance(value["maximum_network_bytes"], int)
            or value["maximum_network_bytes"] <= 0
            or not isinstance(value["quota_exceeded"], bool)
            or not all(isinstance(item, str) and item for item in value["allowed_destinations"])
            or not all(isinstance(item, str) and item for item in value["observed_destinations"])
        ):
            raise ValueError("Linux network state values are invalid")
        if not set(value["observed_destinations"]).issubset(value["allowed_destinations"]):
            raise ValueError("Linux network state contains an unapproved destination")
        return value

    def _prepare(self):
        self._root.mkdir(parents=True, exist_ok=True, mode=0o700)
        details = self._root.stat(follow_symlinks=False)
        if self._root.is_symlink() or details.st_uid != os.geteuid() or details.st_mode & 0o077:
            raise PermissionError("Linux network state root ownership is invalid")

    def _write(self, document):
        descriptor, raw = tempfile.mkstemp(prefix=".linux-network-", dir=self._root)
        temporary = Path(raw)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                _dump(stream, document)
            os.replace(temporary, self._path)
        finally:
            temporary.unlink(missing_ok=True)


def _dump(stream, value):
    json.dump(value, stream, sort_keys=True, separators=(",", ":"))
    stream.write("\n"); stream.flush(); os.fsync(stream.fileno())
