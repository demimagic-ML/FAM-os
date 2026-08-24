"""Root-owned durable journal for multi-attachment network enforcement."""

import json
import os
from pathlib import Path
import tempfile
from threading import RLock
import re


class NetworkEnforcementState:
    def __init__(self, root: Path, identity: str):
        if not root.is_absolute() or not identity.startswith("fam-network-"):
            raise ValueError("network enforcement state identity is invalid")
        self._root, self._path, self._identity = root, root / (identity + ".json"), identity
        self._lock = RLock()

    def claim(self, spec):
        self._prepare()
        document = {
            "enforcement_id": self._identity,
            "request_digest": spec.request_digest,
            "attachment_kinds": [item.value for item in spec.attachment_kinds],
            "stage": "claimed", "proxy_addresses": [],
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

    def stage(self, stage, *, proxy_addresses=None):
        if stage not in {"resources", "proxy", "ready", "closed", "recovered"}:
            raise ValueError("network enforcement state stage is invalid")
        with self._lock:
            document = self.load(); document["stage"] = stage
            if proxy_addresses is not None:
                document["proxy_addresses"] = [list(item) for item in proxy_addresses]
            self._write(document)

    def record_usage(self, usage):
        with self._lock:
            document = self.load()
            if not set(usage.destinations).issubset(document["allowed_destinations"]):
                raise ValueError("network usage destinations differ from request")
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
            raise PermissionError("network enforcement state ownership is invalid")
        value = json.loads(self._path.read_text("utf-8"))
        expected = {
            "enforcement_id", "request_digest", "attachment_kinds", "stage",
            "proxy_addresses", "allowed_destinations", "observed_destinations",
            "maximum_network_bytes", "transmitted_bytes", "received_bytes",
            "quota_exceeded",
        }
        if not isinstance(value, dict) or set(value) != expected:
            raise ValueError("network enforcement state shape is invalid")
        if value["enforcement_id"] != self._identity:
            raise ValueError("network enforcement state identity is mismatched")
        if not re.fullmatch(r"[0-9a-f]{64}", value["request_digest"]):
            raise ValueError("network enforcement request digest is invalid")
        if value["stage"] not in {"claimed", "resources", "proxy", "ready", "closed", "recovered"}:
            raise ValueError("network enforcement state stage is invalid")
        kinds = value["attachment_kinds"]
        if (
            not isinstance(kinds, list) or not kinds or len(set(kinds)) != len(kinds)
            or any(item not in {"linux_namespace", "docker_internal_network"} for item in kinds)
        ):
            raise ValueError("network enforcement attachment state is invalid")
        addresses = value["proxy_addresses"]
        if (
            not isinstance(addresses, list)
            or any(
                not isinstance(item, list) or len(item) != 2
                or not isinstance(item[0], str) or not item[0]
                or isinstance(item[1], bool) or not isinstance(item[1], int)
                or not 1 <= item[1] <= 65535
                for item in addresses
            )
            or (
                value["stage"] in {"proxy", "ready", "closed"}
                and len(addresses) != len(kinds)
            )
        ):
            raise ValueError("network enforcement proxy state is invalid")
        counts = value["transmitted_bytes"], value["received_bytes"]
        if any(isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in counts):
            raise ValueError("network enforcement byte counts are invalid")
        if sum(counts) > value["maximum_network_bytes"]:
            raise ValueError("network enforcement state exceeds quota")
        allowed, observed = value["allowed_destinations"], value["observed_destinations"]
        if (
            isinstance(value["maximum_network_bytes"], bool)
            or not isinstance(value["maximum_network_bytes"], int)
            or value["maximum_network_bytes"] <= 0
            or not isinstance(value["quota_exceeded"], bool)
            or not isinstance(allowed, list) or not allowed
            or len(set(allowed)) != len(allowed)
            or not isinstance(observed, list) or len(set(observed)) != len(observed)
            or any(not isinstance(item, str) or not item for item in allowed + observed)
            or not set(observed).issubset(allowed)
            or value["quota_exceeded"] and sum(counts) != value["maximum_network_bytes"]
        ):
            raise ValueError("network enforcement quota or destination state is invalid")
        return value

    def _prepare(self):
        self._root.mkdir(parents=True, exist_ok=True, mode=0o700)
        details = self._root.stat(follow_symlinks=False)
        if self._root.is_symlink() or details.st_uid != os.geteuid() or details.st_mode & 0o077:
            raise PermissionError("network enforcement state root is unsafe")

    def _write(self, document):
        descriptor, raw = tempfile.mkstemp(prefix=".network-", dir=self._root)
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
