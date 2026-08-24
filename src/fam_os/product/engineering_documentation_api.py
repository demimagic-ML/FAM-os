"""Trusted generated-document admission and deterministic staleness policy."""

import hashlib
from datetime import datetime, timezone
from pathlib import Path

from fam_os.core.engineering import (
    DOCUMENTATION_REQUIREMENTS_PATH, DocumentationGenerationRequest,
    DocumentationGovernanceBinding, DocumentationRequirementSelection,
    DocumentationSource,
    GeneratedDocumentationReceipt, GovernedDocumentationService,
    RequirementTraceStatus, RequirementTraceabilityRecord,
)
from fam_os.core.engineering.documentation_policy import (
    DocumentationRequirementPolicy,
)


class ProductEngineeringDocumentationApi:
    def __init__(
        self, owner_id, task_store, preparations, store=None, recipes=None,
    ) -> None:
        self._owner_id = owner_id
        self._tasks = task_store
        self._preparations = preparations
        self._store = store
        self._recipes = recipes
        self._service = GovernedDocumentationService()

    def record_selection(self, owner_id, selection):
        candidate = self._candidate(owner_id, selection.task_id)
        definition = self._tasks.load_task(selection.task_id)
        if definition is None:
            raise KeyError("engineering documentation task definition is unavailable")
        expected_intent = hashlib.sha256(
            definition.task.intent.encode("utf-8")
        ).hexdigest()
        expected_kinds = DocumentationRequirementPolicy().required_kinds(
            definition.task.intent
        )
        if (
            selection.candidate_id != candidate.candidate_id
            or selection.policy_id != DocumentationRequirementPolicy.policy_id
            or selection.intent_sha256 != expected_intent
            or selection.required_kinds != expected_kinds
        ):
            raise PermissionError("documentation requirement selection differs")
        self._require_store()
        self._store.put(selection)
        return selection

    def begin_generation(
        self, owner_id: str, request: DocumentationGenerationRequest,
    ):
        """Persist exact signed-recipe intent before any candidate effect."""
        candidate = self._candidate(owner_id, request.task_id)
        self._service.admit(request, candidate)
        recipe = self._recipe(request.generator_recipe_id)
        if recipe.kind is not request.kind:
            raise PermissionError("documentation recipe kind differs from request")
        root = Path(candidate.candidate_workspace)
        for source in request.sources:
            if _digest_file(root, source.path) != source.content_sha256:
                raise RuntimeError("documentation source changed before intent")
        self._require_store()
        self._store.put(request)
        return request

    def record_generated(
        self, owner_id: str, request: DocumentationGenerationRequest,
        receipt: GeneratedDocumentationReceipt,
    ):
        """Attach output only after a trusted generator adapter returns."""
        candidate = self._candidate(owner_id, request.task_id)
        self._service.admit(request, candidate)
        self._service.validate_receipt(request, receipt)
        self._recipe(request.generator_recipe_id)
        self._require_store()
        if self._store.load(request.request_id) != request:
            raise RuntimeError("documentation generation intent was not recorded")
        root = Path(candidate.candidate_workspace)
        for source in request.sources:
            if _digest_file(root, source.path) != source.content_sha256:
                raise RuntimeError("documentation source changed before admission")
        if _digest_file(root, request.output_path) != receipt.output_sha256:
            raise RuntimeError("generated documentation output digest differs")
        binding = _governance_binding(request, root, receipt.generated_at)
        self._store.put(binding)
        self._store.put(receipt)
        return receipt

    def record_trace(
        self, owner_id: str, trace: RequirementTraceabilityRecord,
        *, trusted_evidence_ids=(),
    ):
        candidate = self._candidate(owner_id, trace.task_id)
        root = Path(candidate.candidate_workspace)
        _required_file(root, trace.requirement_source_path)
        for path in (*trace.implementation_paths, *trace.test_paths):
            _required_file(root, path)
        self._require_store()
        if trace.status is RequirementTraceStatus.SATISFIED:
            records = self._store.for_task(trace.task_id)
            identities = {
                *(_record_id(item) for item in records),
                *tuple(trusted_evidence_ids),
            }
            if not set(trace.evidence_ids).issubset(identities):
                raise PermissionError(
                    "satisfied requirement trace lacks trusted task evidence"
                )
        self._store.put(trace)
        return trace

    def for_task(self, owner_id: str, task_id: str):
        self._require_owner(owner_id)
        if self._store is None:
            return ()
        return self._store.for_task(task_id)

    def require_current(self, owner_id: str, task_id: str):
        candidate = self._candidate(owner_id, task_id)
        if self._store is None:
            return ()
        root = Path(candidate.candidate_workspace)
        records = self._store.for_task(task_id)
        receipts = tuple(
            item for item in records
            if isinstance(item, GeneratedDocumentationReceipt)
            and item.candidate_id == candidate.candidate_id
        )
        bindings = {}
        for item in records:
            if (
                isinstance(item, DocumentationGovernanceBinding)
                and item.candidate_id == candidate.candidate_id
            ):
                if item.request_id in bindings:
                    raise RuntimeError("documentation request has multiple governance bindings")
                bindings[item.request_id] = item
        reports = []
        grouped = {
            path: tuple(item for item in receipts if item.output_path == path)
            for path in sorted({item.output_path for item in receipts})
        }
        for _output_path, candidates in grouped.items():
            current = False
            for receipt in candidates:
                binding = bindings.get(receipt.request_id)
                if binding is None:
                    raise PermissionError(
                        "generated documentation lacks governance binding"
                    )
                _validate_binding(receipt, binding)
                sources = _current_sources(
                    root, (*receipt.sources, *binding.governance_sources),
                )
                output_digest = _optional_digest(root, receipt.output_path)
                report_id = _report_id(receipt, sources, output_digest)
                report = self._store.load(report_id)
                if report is None:
                    report = self._service.staleness(
                        receipt, sources, output_digest,
                        report_id=report_id,
                        observed_at=datetime.now(timezone.utc),
                        governance_sources=binding.governance_sources,
                    )
                    self._store.put(report)
                reports.append(report)
                current = current or not report.stale
            if not current:
                raise PermissionError("generated documentation is stale")
        return tuple(reports)

    def close(self) -> None:
        if self._store is not None:
            self._store.close()

    def _candidate(self, owner_id, task_id):
        self._require_owner(owner_id)
        if self._tasks.load(task_id) is None:
            raise KeyError("engineering documentation task is unavailable")
        preparation = self._preparations.load(task_id)
        if preparation is None:
            raise KeyError("engineering documentation candidate is unavailable")
        return preparation.candidate

    def _require_owner(self, owner_id):
        if owner_id != self._owner_id:
            raise PermissionError("engineering documentation owner is invalid")

    def _require_store(self):
        if self._store is None:
            raise RuntimeError("engineering documentation store was not composed")

    def _recipe(self, coordinate):
        if self._recipes is None:
            raise RuntimeError("installed documentation recipes are unavailable")
        return self._recipes.get(coordinate)


def _required_file(root: Path, relative: str) -> Path:
    resolved = root.resolve(strict=True)
    raw = resolved / relative
    current = raw
    while current != resolved:
        if current.is_symlink():
            raise PermissionError("engineering documentation path uses a symlink")
        current = current.parent
    target = raw.resolve(strict=True)
    if (
        resolved not in target.parents or not target.is_file()
    ):
        raise PermissionError("engineering documentation path escapes candidate")
    return target


def _digest_file(root: Path, relative: str) -> str:
    return hashlib.sha256(_required_file(root, relative).read_bytes()).hexdigest()


def _optional_digest(root: Path, relative: str) -> str | None:
    try:
        return _digest_file(root, relative)
    except (FileNotFoundError, PermissionError):
        return None


def _record_id(value) -> str:
    for name in (
        "receipt_id", "report_id", "trace_id", "binding_id", "selection_id",
        "request_id",
    ):
        if hasattr(value, name):
            return getattr(value, name)
    raise TypeError("engineering documentation record lacks identity")


def _governance_binding(request, root, bound_at):
    paths = tuple(sorted({
        request.ownership_path,
        request.regeneration_instruction_path,
        DOCUMENTATION_REQUIREMENTS_PATH,
    }))
    sources = tuple(
        DocumentationSource(path, _digest_file(root, path)) for path in paths
    )
    digest = hashlib.sha256(request.request_id.encode()).hexdigest()[:32]
    return DocumentationGovernanceBinding(
        f"documentation-governance-{digest}", request.request_id,
        request.task_id, request.candidate_id, sources, bound_at,
    )


def _validate_binding(receipt, binding):
    if (
        binding.request_id != receipt.request_id
        or binding.task_id != receipt.task_id
        or binding.candidate_id != receipt.candidate_id
    ):
        raise PermissionError("documentation governance binding differs")


def _current_sources(root, expected):
    return tuple(
        DocumentationSource(item.path, digest)
        for item in expected
        if (digest := _optional_digest(root, item.path)) is not None
    )


def _report_id(receipt, sources, output_digest):
    digest = hashlib.sha256(
        "\0".join((
            receipt.receipt_id,
            *(f"{item.path}:{item.content_sha256}" for item in sources),
            output_digest or "missing",
        )).encode()
    ).hexdigest()[:32]
    return f"documentation-staleness-{digest}"
