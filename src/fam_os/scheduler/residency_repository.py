"""In-memory compare-and-swap residency repository."""

from dataclasses import dataclass, field
from threading import RLock

from fam_os.scheduler.residency_contracts import ExpertResidencyCatalog
from fam_os.scheduler.residency_ports import ResidencyRevisionConflict


@dataclass(slots=True)
class InMemoryExpertResidencyRepository:
    _catalog: ExpertResidencyCatalog | None = None
    _lock: object = field(init=False, repr=False)

    def __post_init__(self) -> None:
        self._lock = RLock()

    def initialize(self, catalog: ExpertResidencyCatalog) -> ExpertResidencyCatalog:
        with self._lock:
            if self._catalog is None:
                self._catalog = catalog
            elif self._catalog != catalog:
                raise ResidencyRevisionConflict("residency repository already initialized")
            return self._catalog

    def read(self) -> ExpertResidencyCatalog:
        with self._lock:
            if self._catalog is None:
                raise ResidencyRevisionConflict("residency repository is not initialized")
            return self._catalog

    def compare_and_swap(
        self, expected_revision: int, replacement: ExpertResidencyCatalog
    ) -> ExpertResidencyCatalog:
        with self._lock:
            current = self.read()
            if current.revision != expected_revision:
                raise ResidencyRevisionConflict("residency repository revision conflict")
            if replacement.revision != expected_revision + 1:
                raise ResidencyRevisionConflict("replacement residency revision is invalid")
            if replacement.catalog_id != current.catalog_id:
                raise ResidencyRevisionConflict("replacement residency catalog identity changed")
            self._catalog = replacement
            return replacement
