"""Persistence and runtime ports for expert residency lifecycle."""

from typing import Protocol

from fam_os.core.ports.inference import LoadedModel
from fam_os.scheduler.residency_contracts import ExpertResidencyCatalog


class ExpertResidencyRepository(Protocol):
    def initialize(self, catalog: ExpertResidencyCatalog) -> ExpertResidencyCatalog: ...

    def read(self) -> ExpertResidencyCatalog: ...

    def compare_and_swap(
        self, expected_revision: int, replacement: ExpertResidencyCatalog
    ) -> ExpertResidencyCatalog: ...


class ModelResidencyRuntime(Protocol):
    def unload(self, model_ref: str) -> None: ...

    def loaded_models(self) -> tuple[LoadedModel, ...]: ...


class ResidencyRevisionConflict(RuntimeError):
    pass


class ResidencyTransitionError(RuntimeError):
    pass
