"""Ports consumed when orchestration resolves expert identities."""

from typing import Protocol

from fam_os.experts.contracts import ExpertDescriptor
from fam_os.experts.manifest import ExpertManifest
from fam_os.experts.routing_metadata import ExpertRoutingEmbedding
from fam_os.experts.benchmark_metadata import ExpertBenchmarkRun


class ExpertCatalog(Protocol):
    def get(self, expert_id: str) -> ExpertDescriptor | None: ...


class ExpertManifestSource(Protocol):
    def load(self) -> tuple[ExpertManifest, ...]: ...


class ExpertRoutingEmbeddingSource(Protocol):
    def load(self) -> tuple[ExpertRoutingEmbedding, ...]: ...


class ExpertBenchmarkSource(Protocol):
    def load(self) -> tuple[ExpertBenchmarkRun, ...]: ...
