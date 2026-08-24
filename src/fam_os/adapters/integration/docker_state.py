"""Durable replay-resistant ownership claims for Docker environments."""

import json
import os
from pathlib import Path
import tempfile

from fam_os.core.engineering import IntegrationNetworkLease
from fam_os.schemas import dumps_document, loads_document


class DockerEnvironmentState:
    def __init__(self, candidate_root: Path, environment_id: str) -> None:
        self._root = candidate_root / ".fam" / "integration"
        self._path = self._root / f"{environment_id}.json"
        self._environment_id = environment_id

    def claim(self) -> None:
        self._prepare_root()
        document = {
            "environment_id": self._environment_id,
            "stage": "claimed",
            "network_id": None,
            "network_opening": False,
            "network_lease": None,
            "container_ids": [],
            "terminal": False,
        }
        descriptor = os.open(
            self._path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
        )
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            json.dump(document, stream, sort_keys=True, separators=(",", ":"))
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())

    def record_network(self, network_id: str, network_lease=None) -> None:
        document = self.load()
        if network_lease is not None and not document["network_opening"]:
            raise PermissionError("Docker network lease lacks opening intent")
        document["network_id"] = network_id
        document["network_lease"] = (
            None if network_lease is None else dumps_document(network_lease)
        )
        document["stage"] = "network_created"
        self._write(document)

    def record_network_opening(self) -> None:
        document = self.load()
        if document["network_opening"]:
            raise PermissionError("Docker network opening is already recorded")
        document["network_opening"] = True
        document["stage"] = "network_opening"
        self._write(document)

    def record_container(self, container_id: str) -> None:
        document = self.load()
        document["container_ids"].append(container_id)
        document["stage"] = "containers_starting"
        self._write(document)

    def finish(self, stage: str) -> None:
        document = self.load()
        document["stage"] = stage
        document["terminal"] = True
        self._write(document)

    def load(self) -> dict:
        details = self._path.stat(follow_symlinks=False)
        if self._path.is_symlink() or details.st_uid != os.geteuid() or details.st_mode & 0o077:
            raise PermissionError("Docker environment state ownership is invalid")
        document = json.loads(self._path.read_text(encoding="utf-8"))
        legacy = {"environment_id", "stage", "network_id", "container_ids", "terminal"}
        if isinstance(document, dict) and set(document) == legacy:
            document["network_lease"] = None
        previous = legacy | {"network_lease"}
        if isinstance(document, dict) and set(document) == previous:
            document["network_opening"] = document["network_lease"] is not None
        expected = previous | {"network_opening"}
        if (
            not isinstance(document, dict) or set(document) != expected
            or document["environment_id"] != self._environment_id
            or not isinstance(document["container_ids"], list)
            or not isinstance(document["network_opening"], bool)
            or (
                document["network_lease"] is not None
                and not isinstance(loads_document(document["network_lease"]), IntegrationNetworkLease)
            )
        ):
            raise ValueError("Docker environment state is invalid")
        return document

    def _prepare_root(self) -> None:
        current = self._root
        missing = []
        while not current.exists():
            missing.append(current)
            current = current.parent
        if current.is_symlink():
            raise PermissionError("Docker state root cannot traverse a symlink")
        for path in reversed(missing):
            path.mkdir(mode=0o700)
        if self._root.is_symlink():
            raise PermissionError("Docker state root cannot be a symlink")

    def _write(self, document: dict) -> None:
        descriptor, raw = tempfile.mkstemp(prefix=".state-", dir=self._root)
        temporary = Path(raw)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                json.dump(document, stream, sort_keys=True, separators=(",", ":"))
                stream.write("\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self._path)
        finally:
            temporary.unlink(missing_ok=True)
