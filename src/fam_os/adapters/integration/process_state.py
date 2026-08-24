"""Candidate-local exact unit identity for process integration recovery."""

import json
import os
from pathlib import Path
import tempfile

from fam_os.core.engineering.integration_network import IntegrationNetworkLease
from fam_os.schemas import dumps_document, loads_document


class ProcessEnvironmentState:
    def __init__(self, candidate_root: Path, environment_id: str) -> None:
        self._root = candidate_root / ".fam" / "integration"
        self._path = self._root / f"process-{environment_id}.json"
        self._environment_id = environment_id

    def claim(self) -> None:
        current = self._root
        missing = []
        while not current.exists():
            missing.append(current); current = current.parent
        if current.is_symlink():
            raise PermissionError("process state root cannot traverse a symlink")
        for path in reversed(missing):
            path.mkdir(mode=0o700)
        if self._root.is_symlink():
            raise PermissionError("process state root cannot be symbolic")
        descriptor = os.open(self._path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600)
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            self._dump(stream, self._document(
                "claimed", [], [], False, None, False,
            ))

    def record_unit(self, unit: str) -> None:
        value = self.load(); value["units"].append(unit); value["stage"] = "starting"
        self._write(value)

    def record_secret_root(self, relative_root: str) -> None:
        value = self.load()
        value["secret_roots"].append(relative_root)
        value["stage"] = "secrets_materialized"
        self._write(value)

    def record_network_lease(self, lease: IntegrationNetworkLease) -> None:
        value = self.load()
        if not value["network_opening"] or value["network_lease"] is not None:
            raise PermissionError("process network lease is already recorded")
        value["network_lease"] = dumps_document(lease)
        value["stage"] = "network_attached"
        self._write(value)

    def record_network_opening(self) -> None:
        value = self.load()
        if value["network_opening"]:
            raise PermissionError("process network opening is already recorded")
        value["network_opening"] = True
        value["stage"] = "network_opening"
        self._write(value)

    def finish(self, stage: str) -> None:
        value = self.load(); value["stage"] = stage; value["terminal"] = True
        self._write(value)

    def load(self) -> dict:
        details = self._path.stat(follow_symlinks=False)
        if self._path.is_symlink() or details.st_uid != os.geteuid() or details.st_mode & 0o077:
            raise PermissionError("process environment state ownership is invalid")
        value = json.loads(self._path.read_text("utf-8"))
        legacy = {"environment_id", "stage", "units", "terminal"}
        with_secrets = legacy | {"secret_roots"}
        with_network = legacy | {"network_lease"}
        previous = with_secrets | {"network_lease"}
        current = previous | {"network_opening"}
        if (
            isinstance(value, dict) and legacy <= set(value)
            and set(value) <= current
        ):
            value.setdefault("secret_roots", [])
            value.setdefault("network_lease", None)
            value.setdefault(
                "network_opening", value["network_lease"] is not None,
            )
        if (not isinstance(value, dict) or set(value) != current
                or value["environment_id"] != self._environment_id
                or not isinstance(value["units"], list)
                or not isinstance(value["secret_roots"], list)
                or not isinstance(value["network_opening"], bool)
                or any(
                    not isinstance(item, str) or not item
                    for item in value["units"] + value["secret_roots"]
                )):
            raise ValueError("process environment state is invalid")
        if value["network_lease"] is not None and not isinstance(
            loads_document(value["network_lease"]), IntegrationNetworkLease,
        ):
            raise ValueError("process environment network lease is invalid")
        return value

    def _write(self, value) -> None:
        descriptor, raw = tempfile.mkstemp(prefix=".process-state-", dir=self._root)
        temporary = Path(raw)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                self._dump(stream, value)
            os.replace(temporary, self._path)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _dump(stream, value) -> None:
        json.dump(value, stream, sort_keys=True, separators=(",", ":")); stream.write("\n")
        stream.flush(); os.fsync(stream.fileno())

    def _document(
        self, stage, units, secret_roots, network_opening,
        network_lease, terminal,
    ):
        return {"environment_id": self._environment_id, "stage": stage,
                "units": units, "secret_roots": secret_roots,
                "network_opening": network_opening,
                "network_lease": network_lease, "terminal": terminal}
