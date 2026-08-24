"""Durable backend progress for restart-safe mixed integration environments."""

import json
import os
from pathlib import Path
import tempfile

from fam_os.core.engineering import IntegrationNetworkLease
from fam_os.schemas import dumps_document, loads_document


class CompositeEnvironmentState:
    def __init__(self, candidate_root: Path, environment_id: str) -> None:
        self._root = candidate_root / ".fam" / "integration"
        self._path = self._root / f"composite-{environment_id}.json"
        self._environment_id = environment_id

    def claim(self, backends) -> None:
        self._prepare_root()
        document = self._document(
            "claimed", list(backends), [], {}, False, False, None, [],
        )
        descriptor = os.open(
            self._path,
            os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
            0o600,
        )
        with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
            self._dump(stream, document)

    def record_launched(self, backend) -> None:
        document = self.load()
        if backend in document["launched_backends"]:
            raise RuntimeError("composite backend launch was already recorded")
        document["launched_backends"].append(backend)
        document["stage"] = "launching"
        self._write(document)

    def record_network_lease(self, lease) -> None:
        document = self.load()
        if not document["network_opening"] or document["network_lease"] is not None:
            raise RuntimeError("composite network lease was already recorded")
        document["network_lease"] = dumps_document(lease)
        document["stage"] = "network_attached"
        self._write(document)

    def record_network_opening(self) -> None:
        document = self.load()
        if document["network_opening"]:
            raise RuntimeError("composite network opening was already recorded")
        document["network_opening"] = True
        document["stage"] = "network_opening"
        self._write(document)

    def record_network_cleaned(self, evidence_ids) -> None:
        document = self.load()
        if document["network_cleanup_evidence"]:
            raise RuntimeError("composite network cleanup was already recorded")
        if not evidence_ids:
            raise RuntimeError("composite network cleanup lacks evidence")
        document["network_cleanup_evidence"] = list(evidence_ids)
        document["stage"] = "cleaning"
        self._write(document)

    def record_cleaned(self, backend, evidence_ids) -> None:
        document = self.load()
        if backend not in document["launched_backends"]:
            raise RuntimeError("unlaunched composite backend cannot be cleaned")
        if backend in document["cleanup_evidence"]:
            raise RuntimeError("composite backend cleanup was already recorded")
        if not evidence_ids:
            raise RuntimeError("composite backend cleanup lacks evidence")
        document["cleanup_evidence"][backend] = list(evidence_ids)
        document["stage"] = "cleaning"
        self._write(document)

    def finish(self, stage, *, terminal) -> None:
        document = self.load()
        document["stage"] = stage
        document["terminal"] = terminal
        self._write(document)

    def load(self):
        details = self._path.stat(follow_symlinks=False)
        if (
            self._path.is_symlink() or details.st_uid != os.geteuid()
            or details.st_mode & 0o077
        ):
            raise PermissionError("composite environment state ownership is invalid")
        document = json.loads(self._path.read_text(encoding="utf-8"))
        legacy = {
            "environment_id", "stage", "backend_order", "launched_backends",
            "cleanup_evidence", "terminal",
        }
        if isinstance(document, dict) and set(document) == legacy:
            document.update(
                network_opening=False, network_lease=None,
                network_cleanup_evidence=[],
            )
        previous = legacy | {"network_lease", "network_cleanup_evidence"}
        if isinstance(document, dict) and set(document) == previous:
            document["network_opening"] = document["network_lease"] is not None
        expected = previous | {"network_opening"}
        lists = ("backend_order", "launched_backends")
        if (
            not isinstance(document, dict) or set(document) != expected
            or document["environment_id"] != self._environment_id
            or not isinstance(document["stage"], str) or not document["stage"]
            or not isinstance(document["terminal"], bool)
            or any(not isinstance(document[name], list) for name in lists)
            or any(
                item not in {"docker", "process"}
                for name in lists for item in document[name]
            )
            or len(set(document["backend_order"])) != len(document["backend_order"])
            or len(set(document["launched_backends"])) != len(document["launched_backends"])
            or not isinstance(document["cleanup_evidence"], dict)
            or not isinstance(document["network_cleanup_evidence"], list)
            or not isinstance(document["network_opening"], bool)
            or any(
                not isinstance(item, str) or not item
                for item in document["network_cleanup_evidence"]
            )
            or (
                document["network_lease"] is not None
                and not isinstance(loads_document(document["network_lease"]), IntegrationNetworkLease)
            )
            or any(
                name not in {"docker", "process"}
                or not isinstance(values, list) or not values
                or any(not isinstance(item, str) or not item for item in values)
                for name, values in document["cleanup_evidence"].items()
            )
            or not set(document["launched_backends"]) <= set(document["backend_order"])
            or not set(document["cleanup_evidence"]) <= set(document["launched_backends"])
        ):
            raise ValueError("composite environment state is invalid")
        return document

    def _prepare_root(self) -> None:
        current, missing = self._root, []
        while not current.exists():
            missing.append(current); current = current.parent
        if current.is_symlink():
            raise PermissionError("composite state root cannot traverse a symlink")
        for path in reversed(missing):
            path.mkdir(mode=0o700)
        if self._root.is_symlink():
            raise PermissionError("composite state root cannot be symbolic")

    def _write(self, document) -> None:
        descriptor, raw = tempfile.mkstemp(prefix=".composite-state-", dir=self._root)
        temporary = Path(raw)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                self._dump(stream, document)
            os.replace(temporary, self._path)
        finally:
            temporary.unlink(missing_ok=True)

    @staticmethod
    def _dump(stream, document) -> None:
        json.dump(document, stream, sort_keys=True, separators=(",", ":"))
        stream.write("\n"); stream.flush(); os.fsync(stream.fileno())

    def _document(
        self, stage, order, launched, evidence, terminal,
        network_opening, network_lease, network_cleanup_evidence,
    ):
        return {
            "environment_id": self._environment_id, "stage": stage,
            "backend_order": order, "launched_backends": launched,
            "cleanup_evidence": evidence, "terminal": terminal,
            "network_opening": network_opening,
            "network_lease": network_lease,
            "network_cleanup_evidence": network_cleanup_evidence,
        }
