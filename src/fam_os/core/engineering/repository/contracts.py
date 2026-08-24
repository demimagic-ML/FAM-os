"""Typed read-only repository intelligence and architecture contracts."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from fam_os.core.engineering._validation import (
    absolute_path,
    aware,
    digest,
    positive,
    relative_path,
    text,
    texts,
)
from fam_os.core.engineering.version import ENGINEERING_CONTRACT_VERSION


class RepositorySourceKind(StrEnum):
    WORKSPACE_MAP = "workspace_map"
    WORKSPACE_RETRIEVAL = "workspace_retrieval"
    SEMANTIC_SEARCH = "semantic_search"
    LSP = "lsp"
    TREE_SITTER = "tree_sitter"
    CODE_GRAPH = "code_graph"
    COMPILER_DATABASE = "compiler_database"
    EDITOR_API = "editor_api"
    PROJECT_MANIFEST = "project_manifest"
    DEPENDENCY_METADATA = "dependency_metadata"
    GIT = "git"
    REPOSITORY_INSTRUCTION = "repository_instruction"


class RepositoryContextTrust(StrEnum):
    UNTRUSTED_CONTEXT = "untrusted_context"


class RepositoryFileRole(StrEnum):
    SOURCE = "source"
    TEST = "test"
    CONFIGURATION = "configuration"
    MANIFEST = "manifest"
    MIGRATION = "migration"
    DOCUMENTATION = "documentation"
    GENERATED = "generated"
    ASSET = "asset"
    UNKNOWN = "unknown"


class SymbolRelationKind(StrEnum):
    CALLS = "calls"
    IMPORTS = "imports"
    IMPLEMENTS = "implements"
    EXTENDS = "extends"
    REFERENCES = "references"
    TESTS = "tests"


class DiagnosticSeverity(StrEnum):
    ERROR = "error"
    WARNING = "warning"
    INFORMATION = "information"


class ArchitectureArea(StrEnum):
    MODULES = "modules"
    INTERFACES = "interfaces"
    SCHEMAS = "schemas"
    MIGRATIONS = "migrations"
    ADRS = "adrs"
    DEPENDENCY_DIRECTION = "dependency_direction"
    SECURITY_BOUNDARIES = "security_boundaries"
    ROLLOUT = "rollout"
    ACCEPTANCE_CRITERIA = "acceptance_criteria"


@dataclass(frozen=True, slots=True)
class RepositoryObservationBounds:
    maximum_files: int
    maximum_context_records: int
    maximum_symbols: int
    maximum_relations: int
    maximum_diagnostics: int
    maximum_total_text_bytes: int

    def __post_init__(self) -> None:
        for name in (
            "maximum_files", "maximum_context_records", "maximum_symbols",
            "maximum_relations", "maximum_diagnostics",
            "maximum_total_text_bytes",
        ):
            positive(getattr(self, name), name)


@dataclass(frozen=True, slots=True)
class RepositoryFile:
    path: str
    content_sha256: str
    size_bytes: int
    role: RepositoryFileRole
    language: str | None

    def __post_init__(self) -> None:
        relative_path(self.path, "path")
        digest(self.content_sha256, "content_sha256", required=True)
        positive(self.size_bytes, "size_bytes", allow_zero=True)
        if self.language is not None:
            text(self.language, "language")


@dataclass(frozen=True, slots=True)
class RepositoryContextRecord:
    record_id: str
    source_kind: RepositorySourceKind
    path: str
    content_sha256: str
    text: str
    generated: bool
    trust: RepositoryContextTrust = RepositoryContextTrust.UNTRUSTED_CONTEXT

    def __post_init__(self) -> None:
        text(self.record_id, "record_id")
        relative_path(self.path, "path")
        digest(self.content_sha256, "content_sha256", required=True)
        if not self.text.strip() or len(self.text.encode("utf-8")) > 65_536:
            raise ValueError("repository context text is empty or exceeds its bound")
        if self.trust is not RepositoryContextTrust.UNTRUSTED_CONTEXT:
            raise ValueError("repository-derived text is always untrusted context")


@dataclass(frozen=True, slots=True)
class RepositorySymbol:
    symbol_id: str
    qualified_name: str
    kind: str
    path: str
    line: int
    public: bool

    def __post_init__(self) -> None:
        for name in ("symbol_id", "qualified_name", "kind"):
            text(getattr(self, name), name)
        relative_path(self.path, "path")
        positive(self.line, "line")


@dataclass(frozen=True, slots=True)
class RepositorySymbolRelation:
    source_symbol_id: str
    target_symbol_id: str
    kind: SymbolRelationKind
    evidence_path: str

    def __post_init__(self) -> None:
        text(self.source_symbol_id, "source_symbol_id")
        text(self.target_symbol_id, "target_symbol_id")
        relative_path(self.evidence_path, "evidence_path")
        if self.source_symbol_id == self.target_symbol_id:
            raise ValueError("symbol relation cannot be self-referential")


@dataclass(frozen=True, slots=True)
class RepositoryDiagnostic:
    diagnostic_id: str
    path: str
    line: int
    severity: DiagnosticSeverity
    code: str
    message: str
    source_kind: RepositorySourceKind

    def __post_init__(self) -> None:
        for name in ("diagnostic_id", "code", "message"):
            text(getattr(self, name), name)
        relative_path(self.path, "path")
        positive(self.line, "line")


@dataclass(frozen=True, slots=True)
class RepositoryManifest:
    path: str
    ecosystem: str
    project_name: str
    declared_targets: tuple[str, ...]
    content_sha256: str

    def __post_init__(self) -> None:
        relative_path(self.path, "path")
        text(self.ecosystem, "ecosystem")
        text(self.project_name, "project_name")
        texts(self.declared_targets, "declared_targets")
        digest(self.content_sha256, "content_sha256", required=True)


@dataclass(frozen=True, slots=True)
class RepositoryDependencyEdge:
    source: str
    target: str
    direct: bool
    development_only: bool
    source_kind: RepositorySourceKind

    def __post_init__(self) -> None:
        text(self.source, "source")
        text(self.target, "target")
        if self.source == self.target:
            raise ValueError("dependency edge cannot target itself")


@dataclass(frozen=True, slots=True)
class RepositoryGitState:
    branch: str
    head_revision: str
    remotes: tuple[str, ...]
    dirty_paths: tuple[str, ...]
    detached: bool

    def __post_init__(self) -> None:
        text(self.branch, "branch")
        text(self.head_revision, "head_revision")
        texts(self.remotes, "remotes")
        for path in self.dirty_paths:
            relative_path(path, "dirty_paths item")
        texts(self.dirty_paths, "dirty_paths")


@dataclass(frozen=True, slots=True)
class RepositoryArchitectureRule:
    rule_id: str
    source_path: str
    statement: str
    trust: RepositoryContextTrust = RepositoryContextTrust.UNTRUSTED_CONTEXT

    def __post_init__(self) -> None:
        text(self.rule_id, "rule_id")
        relative_path(self.source_path, "source_path")
        text(self.statement, "statement")
        if self.trust is not RepositoryContextTrust.UNTRUSTED_CONTEXT:
            raise ValueError("repository architecture rules are untrusted context")


@dataclass(frozen=True, slots=True)
class RepositoryEvidenceBundle:
    bundle_id: str
    task_id: str
    captured_at: datetime
    workspace_root: str
    workspace_revision: str
    files: tuple[RepositoryFile, ...]
    context_records: tuple[RepositoryContextRecord, ...]
    symbols: tuple[RepositorySymbol, ...]
    relations: tuple[RepositorySymbolRelation, ...]
    diagnostics: tuple[RepositoryDiagnostic, ...]
    manifests: tuple[RepositoryManifest, ...]
    dependencies: tuple[RepositoryDependencyEdge, ...]
    git_state: RepositoryGitState
    architecture_rules: tuple[RepositoryArchitectureRule, ...]
    bounds: RepositoryObservationBounds
    truncated: bool
    mutation_performed: bool = False
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        text(self.bundle_id, "bundle_id")
        text(self.task_id, "task_id")
        aware(self.captured_at, "captured_at")
        absolute_path(self.workspace_root, "workspace_root")
        text(self.workspace_revision, "workspace_revision")
        if self.mutation_performed:
            raise ValueError("repository intelligence evidence must be read-only")
        _unique(self.files, "path", "files")
        _unique(self.context_records, "record_id", "context_records")
        _unique(self.symbols, "symbol_id", "symbols")
        _unique(self.diagnostics, "diagnostic_id", "diagnostics")
        _bounded(self)
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("repository evidence version is unsupported")


def _unique(values: tuple[object, ...], field: str, name: str) -> None:
    identities = tuple(getattr(item, field) for item in values)
    if len(set(identities)) != len(identities):
        raise ValueError(f"{name} identities must be unique")


def _bounded(bundle: RepositoryEvidenceBundle) -> None:
    checks = (
        (len(bundle.files), bundle.bounds.maximum_files),
        (len(bundle.context_records), bundle.bounds.maximum_context_records),
        (len(bundle.symbols), bundle.bounds.maximum_symbols),
        (len(bundle.relations), bundle.bounds.maximum_relations),
        (len(bundle.diagnostics), bundle.bounds.maximum_diagnostics),
        (sum(len(item.text.encode("utf-8")) for item in bundle.context_records),
         bundle.bounds.maximum_total_text_bytes),
    )
    if any(observed > maximum for observed, maximum in checks):
        raise ValueError("repository evidence exceeds declared observation bounds")
