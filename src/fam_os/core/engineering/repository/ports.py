"""Replaceable observation and persistence ports for repository planning."""

from typing import Protocol

from fam_os.core.engineering.repository.contracts import RepositoryEvidenceBundle
from fam_os.core.engineering.repository.planning import RepositoryAnalysisRequest
from fam_os.core.engineering.repository.task_graph import EngineeringTaskGraphEvent


class RepositoryEvidenceAdapter(Protocol):
    """Adapter boundary for LSP, parser, graph, editor, Git, and build metadata."""

    def observe(self, request: RepositoryAnalysisRequest) -> RepositoryEvidenceBundle: ...


class EngineeringTaskGraphRepository(Protocol):
    def append(
        self, expected_sequence: int, event: EngineeringTaskGraphEvent,
    ) -> bool: ...

    def history(self, graph_id: str) -> tuple[EngineeringTaskGraphEvent, ...]: ...
