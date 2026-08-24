"""Core repository intelligence, architecture, and task-graph interfaces."""

from fam_os.core.engineering.repository.contracts import (
    ArchitectureArea,
    DiagnosticSeverity,
    RepositoryArchitectureRule,
    RepositoryContextRecord,
    RepositoryContextTrust,
    RepositoryDependencyEdge,
    RepositoryDiagnostic,
    RepositoryEvidenceBundle,
    RepositoryFile,
    RepositoryFileRole,
    RepositoryGitState,
    RepositoryManifest,
    RepositoryObservationBounds,
    RepositorySourceKind,
    RepositorySymbol,
    RepositorySymbolRelation,
    SymbolRelationKind,
)
from fam_os.core.engineering.repository.planning import (
    ArchitectureDecision,
    ArchitectureProposal,
    BoundedRepositoryPlanner,
    ImplementationPathStep,
    RepositoryAnalysis,
    RepositoryAnalysisRequest,
)
from fam_os.core.engineering.repository.ports import (
    EngineeringTaskGraphRepository,
    RepositoryEvidenceAdapter,
)
from fam_os.core.engineering.repository.task_graph import (
    EngineeringTaskBudget,
    EngineeringTaskGraph,
    EngineeringTaskGraphEvent,
    EngineeringTaskGraphEventKind,
    EngineeringTaskGraphService,
    EngineeringTaskGraphStep,
    EngineeringTaskStepKind,
    EngineeringTaskStepState,
)

__all__ = [name for name in globals() if not name.startswith("_")]
