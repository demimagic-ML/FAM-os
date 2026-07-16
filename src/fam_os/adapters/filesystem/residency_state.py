"""Private atomic JSON repository for expert residency state."""

from __future__ import annotations

import fcntl
import os
import stat
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from fam_os.scheduler.residency_contracts import ExpertResidencyCatalog
from fam_os.scheduler.residency_ports import ResidencyRevisionConflict
from fam_os.schemas import dumps_document, loads_document


@dataclass(frozen=True, slots=True)
class JsonExpertResidencyRepository:
    path: Path

    def __post_init__(self) -> None:
        if not self.path.is_absolute():
            raise ValueError("residency state path must be absolute")

    def initialize(self, catalog: ExpertResidencyCatalog) -> ExpertResidencyCatalog:
        with self._locked():
            if self.path.exists():
                current = self._read_unlocked()
                if current != catalog:
                    raise ResidencyRevisionConflict("residency state already initialized")
                return current
            self._write_unlocked(catalog)
            return catalog

    def read(self) -> ExpertResidencyCatalog:
        with self._locked():
            return self._read_unlocked()

    def compare_and_swap(
        self, expected_revision: int, replacement: ExpertResidencyCatalog
    ) -> ExpertResidencyCatalog:
        with self._locked():
            current = self._read_unlocked()
            if current.revision != expected_revision:
                raise ResidencyRevisionConflict("residency state revision conflict")
            if replacement.revision != expected_revision + 1:
                raise ResidencyRevisionConflict("replacement residency revision is invalid")
            if replacement.catalog_id != current.catalog_id:
                raise ResidencyRevisionConflict("replacement residency identity changed")
            self._write_unlocked(replacement)
            return replacement

    @contextmanager
    def _locked(self):
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        lock_path = self.path.with_name(self.path.name + ".lock")
        descriptor = os.open(
            lock_path, os.O_RDWR | os.O_CREAT | os.O_NOFOLLOW, 0o600
        )
        try:
            metadata = os.fstat(descriptor)
            if not stat.S_ISREG(metadata.st_mode):
                raise ResidencyRevisionConflict("residency lock is not a regular file")
            if metadata.st_mode & 0o077:
                raise ResidencyRevisionConflict("residency lock permissions are too broad")
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            yield
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)

    def _read_unlocked(self) -> ExpertResidencyCatalog:
        if self.path.is_symlink() or not self.path.is_file():
            raise ResidencyRevisionConflict("residency state is not a regular file")
        if self.path.stat().st_mode & 0o077:
            raise ResidencyRevisionConflict("residency state permissions are too broad")
        value = loads_document(self.path.read_text(encoding="utf-8"))
        if not isinstance(value, ExpertResidencyCatalog):
            raise ResidencyRevisionConflict("residency state document has wrong type")
        return value

    def _write_unlocked(self, catalog: ExpertResidencyCatalog) -> None:
        descriptor, temporary = tempfile.mkstemp(
            prefix=f".{self.path.name}.", dir=self.path.parent
        )
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                stream.write(dumps_document(catalog) + "\n")
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temporary, self.path)
            directory = os.open(self.path.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(directory)
            finally:
                os.close(directory)
        except Exception:
            try:
                os.close(descriptor)
            except OSError:
                pass
            Path(temporary).unlink(missing_ok=True)
            raise
