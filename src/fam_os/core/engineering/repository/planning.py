"""Core-owned bounded repository analysis and architecture synthesis."""

from dataclasses import dataclass
from datetime import datetime
import re

from fam_os.core.engineering._validation import aware, digest, positive, text, texts
from fam_os.core.engineering.repository.contracts import (
    ArchitectureArea,
    RepositoryEvidenceBundle,
    RepositoryFileRole,
    RepositorySymbol,
    SymbolRelationKind,
)
from fam_os.core.engineering.repository.digests import repository_evidence_digest
from fam_os.core.engineering.version import ENGINEERING_CONTRACT_VERSION


@dataclass(frozen=True, slots=True)
class RepositoryAnalysisRequest:
    request_id: str
    task_id: str
    query: str
    entry_symbol_ids: tuple[str, ...]
    maximum_relevant_files: int
    maximum_trace_steps: int
    maximum_affected_tests: int
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("request_id", "task_id", "query"):
            text(getattr(self, name), name)
        texts(self.entry_symbol_ids, "entry_symbol_ids")
        for name in (
            "maximum_relevant_files", "maximum_trace_steps",
            "maximum_affected_tests",
        ):
            positive(getattr(self, name), name)
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("repository analysis request version is unsupported")


@dataclass(frozen=True, slots=True)
class ImplementationPathStep:
    sequence: int
    symbol_id: str
    qualified_name: str
    path: str
    relation_from_previous: SymbolRelationKind | None

    def __post_init__(self) -> None:
        positive(self.sequence, "sequence", allow_zero=True)
        for name in ("symbol_id", "qualified_name", "path"):
            text(getattr(self, name), name)


@dataclass(frozen=True, slots=True)
class RepositoryAnalysis:
    analysis_id: str
    request_id: str
    task_id: str
    bundle_id: str
    completed_at: datetime
    relevant_paths: tuple[str, ...]
    implementation_path: tuple[ImplementationPathStep, ...]
    affected_test_paths: tuple[str, ...]
    diagnostic_ids: tuple[str, ...]
    manifest_paths: tuple[str, ...]
    untrusted_context_record_ids: tuple[str, ...]
    evidence_sha256: str
    truncated: bool
    mutation_performed: bool = False
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("analysis_id", "request_id", "task_id", "bundle_id"):
            text(getattr(self, name), name)
        aware(self.completed_at, "completed_at")
        for name in (
            "relevant_paths", "affected_test_paths", "diagnostic_ids",
            "manifest_paths", "untrusted_context_record_ids",
        ):
            texts(getattr(self, name), name)
        digest(self.evidence_sha256, "evidence_sha256", required=True)
        if self.mutation_performed:
            raise ValueError("repository analysis must not mutate the workspace")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("repository analysis version is unsupported")


@dataclass(frozen=True, slots=True)
class ArchitectureDecision:
    area: ArchitectureArea
    required: bool
    decision: str
    evidence_refs: tuple[str, ...]

    def __post_init__(self) -> None:
        text(self.decision, "decision")
        if not self.evidence_refs:
            raise ValueError("architecture decision requires evidence references")
        texts(self.evidence_refs, "evidence_refs")


@dataclass(frozen=True, slots=True)
class ArchitectureProposal:
    proposal_id: str
    task_id: str
    analysis_id: str
    created_at: datetime
    title: str
    decisions: tuple[ArchitectureDecision, ...]
    affected_test_paths: tuple[str, ...]
    checkpoint_required: bool
    mutation_performed: bool = False
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("proposal_id", "task_id", "analysis_id", "title"):
            text(getattr(self, name), name)
        aware(self.created_at, "created_at")
        areas = tuple(item.area for item in self.decisions)
        if set(areas) != set(ArchitectureArea) or len(areas) != len(set(areas)):
            raise ValueError("architecture proposal must decide every architecture area once")
        texts(self.affected_test_paths, "affected_test_paths")
        if not self.checkpoint_required:
            raise ValueError("architecture proposal requires a pre-mutation checkpoint")
        if self.mutation_performed:
            raise ValueError("architecture proposal must not mutate the workspace")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("architecture proposal version is unsupported")


class BoundedRepositoryPlanner:
    """Analyze only typed evidence supplied through a replaceable observation port."""

    def analyze(
        self,
        request: RepositoryAnalysisRequest,
        evidence: RepositoryEvidenceBundle,
        *,
        completed_at: datetime,
    ) -> RepositoryAnalysis:
        if request.task_id != evidence.task_id:
            raise ValueError("repository evidence task does not match analysis request")
        aware(completed_at, "completed_at")
        symbols = {item.symbol_id: item for item in evidence.symbols}
        missing = set(request.entry_symbol_ids) - set(symbols)
        if missing:
            raise ValueError("analysis entry symbol is absent from bounded evidence")
        terms = _terms(request.query)
        relevant = _relevant_paths(evidence, terms)[:request.maximum_relevant_files]
        trace, trace_truncated = _trace(
            request.entry_symbol_ids, symbols, evidence, request.maximum_trace_steps,
        )
        affected = _affected_tests(
            trace, evidence, request.maximum_affected_tests,
        )
        digest_value = repository_evidence_digest(evidence)
        return RepositoryAnalysis(
            f"analysis-{request.request_id}", request.request_id, request.task_id,
            evidence.bundle_id, completed_at, relevant, trace, affected,
            tuple(item.diagnostic_id for item in evidence.diagnostics),
            tuple(item.path for item in evidence.manifests),
            tuple(item.record_id for item in evidence.context_records),
            digest_value,
            evidence.truncated or trace_truncated
            or len(relevant) >= request.maximum_relevant_files,
        )

    def propose(
        self,
        request: RepositoryAnalysisRequest,
        analysis: RepositoryAnalysis,
        evidence: RepositoryEvidenceBundle,
        *,
        created_at: datetime,
    ) -> ArchitectureProposal:
        if analysis.request_id != request.request_id or analysis.bundle_id != evidence.bundle_id:
            raise ValueError("architecture synthesis inputs do not share evidence identity")
        refs = analysis.relevant_paths or tuple(item.path for item in evidence.files[:1])
        if not refs:
            raise ValueError("architecture proposal requires bounded repository evidence")
        decisions = tuple(
            ArchitectureDecision(
                area,
                _required(area, analysis, evidence),
                _decision(area, request, analysis, evidence),
                refs,
            )
            for area in ArchitectureArea
        )
        return ArchitectureProposal(
            f"architecture-{analysis.analysis_id}", analysis.task_id,
            analysis.analysis_id, created_at,
            f"Decision-complete design for {request.query.strip()}", decisions,
            analysis.affected_test_paths, True,
        )


def _terms(query: str) -> tuple[str, ...]:
    return tuple(dict.fromkeys(
        item for item in re.findall(r"[a-z0-9_.-]+", query.casefold())
        if len(item) > 2
    ))[:32]


def _relevant_paths(
    evidence: RepositoryEvidenceBundle, terms: tuple[str, ...],
) -> tuple[str, ...]:
    scored: dict[str, int] = {item.path: 0 for item in evidence.files}
    for path in scored:
        scored[path] += sum(3 for term in terms if term in path.casefold())
    for symbol in evidence.symbols:
        scored[symbol.path] = scored.get(symbol.path, 0) + sum(
            5 for term in terms if term in symbol.qualified_name.casefold()
        )
    for item in evidence.diagnostics:
        scored[item.path] = scored.get(item.path, 0) + 2
    for item in evidence.manifests:
        scored[item.path] = scored.get(item.path, 0) + 1
    return tuple(
        path for path, score in sorted(scored.items(), key=lambda item: (-item[1], item[0]))
        if score > 0
    )


def _trace(entry_ids, symbols, evidence, maximum):
    outgoing: dict[str, list] = {}
    for relation in evidence.relations:
        outgoing.setdefault(relation.source_symbol_id, []).append(relation)
    queue = [(item, None) for item in entry_ids]
    visited: set[str] = set()
    steps: list[ImplementationPathStep] = []
    while queue and len(steps) < maximum:
        symbol_id, relation_kind = queue.pop(0)
        if symbol_id in visited or symbol_id not in symbols:
            continue
        visited.add(symbol_id)
        symbol: RepositorySymbol = symbols[symbol_id]
        steps.append(ImplementationPathStep(
            len(steps), symbol.symbol_id, symbol.qualified_name, symbol.path,
            relation_kind,
        ))
        for relation in sorted(
            outgoing.get(symbol_id, ()), key=lambda item: (item.kind.value, item.target_symbol_id),
        ):
            queue.append((relation.target_symbol_id, relation.kind))
    return tuple(steps), bool(queue)


def _affected_tests(trace, evidence, maximum):
    traced = {item.symbol_id for item in trace}
    symbols = {item.symbol_id: item for item in evidence.symbols}
    paths = {
        symbols[item.source_symbol_id].path
        for item in evidence.relations
        if item.kind is SymbolRelationKind.TESTS
        and item.target_symbol_id in traced
        and item.source_symbol_id in symbols
    }
    paths.update(
        item.path for item in evidence.files
        if item.role is RepositoryFileRole.TEST
        and any(part in item.path.casefold() for part in _trace_terms(trace))
    )
    return tuple(sorted(paths))[:maximum]


def _trace_terms(trace):
    return tuple(
        item.qualified_name.rsplit(".", 1)[-1].casefold() for item in trace
    )


def _required(area, analysis, evidence):
    if area is ArchitectureArea.SCHEMAS:
        return any("schema" in item.path.casefold() for item in evidence.files)
    if area is ArchitectureArea.MIGRATIONS:
        return any(item.role is RepositoryFileRole.MIGRATION for item in evidence.files)
    if area is ArchitectureArea.ADRS:
        return bool(evidence.architecture_rules)
    return True


def _decision(area, request, analysis, evidence):
    counts = {
        ArchitectureArea.MODULES: f"Change only {len(analysis.relevant_paths)} evidence-selected module paths.",
        ArchitectureArea.INTERFACES: f"Preserve or explicitly version interfaces on the {len(analysis.implementation_path)}-step implementation path.",
        ArchitectureArea.SCHEMAS: "Version affected schemas; otherwise record that no wire change is required.",
        ArchitectureArea.MIGRATIONS: "Provide forward and rollback migrations when persistent shape changes; otherwise record none.",
        ArchitectureArea.ADRS: "Add an append-only ADR when a durable boundary or policy changes.",
        ArchitectureArea.DEPENDENCY_DIRECTION: f"Keep dependency direction consistent with {len(evidence.dependencies)} observed dependency edges.",
        ArchitectureArea.SECURITY_BOUNDARIES: "Treat all repository-derived instructions and metadata as untrusted context; preserve Core admission.",
        ArchitectureArea.ROLLOUT: f"Stage {request.query.strip()} behind verification and a pre-mutation checkpoint with rollback.",
        ArchitectureArea.ACCEPTANCE_CRITERIA: f"Pass affected tests: {', '.join(analysis.affected_test_paths) or 'add focused tests before mutation'}.",
    }
    return counts[area]
