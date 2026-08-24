"""Deterministic admission and stale-output policy for generated content."""

from datetime import datetime

from fam_os.core.engineering.documentation import (
    DocumentationGenerationRequest,
    DocumentationSource,
    DocumentationStalenessReport,
    GeneratedDocumentationReceipt,
)
from fam_os.core.engineering.transactions import CandidateWorkspace


class GovernedDocumentationService:
    def admit(
        self,
        request: DocumentationGenerationRequest,
        candidate: CandidateWorkspace,
    ) -> None:
        if request.task_id != candidate.task_id or request.candidate_id != candidate.candidate_id:
            raise PermissionError("documentation request targets a different candidate")

    def validate_receipt(
        self,
        request: DocumentationGenerationRequest,
        receipt: GeneratedDocumentationReceipt,
    ) -> None:
        if (
            receipt.request_id != request.request_id
            or receipt.task_id != request.task_id
            or receipt.candidate_id != request.candidate_id
            or receipt.output_path != request.output_path
            or receipt.generator_recipe_id != request.generator_recipe_id
            or receipt.sources != request.sources
        ):
            raise ValueError("generated documentation receipt differs from its request")

    def staleness(
        self,
        receipt: GeneratedDocumentationReceipt,
        current_sources: tuple[DocumentationSource, ...],
        current_output_sha256: str | None,
        *,
        report_id: str,
        observed_at: datetime,
        governance_sources: tuple[DocumentationSource, ...] = (),
    ) -> DocumentationStalenessReport:
        expected = {
            item.path: item.content_sha256
            for item in (*receipt.sources, *governance_sources)
        }
        current = {item.path: item.content_sha256 for item in current_sources}
        missing = tuple(sorted(set(expected) - set(current)))
        stale = tuple(sorted(
            path for path in set(expected) & set(current)
            if expected[path] != current[path]
        ))
        output_modified = current_output_sha256 != receipt.output_sha256
        return DocumentationStalenessReport(
            report_id, receipt.receipt_id, receipt.task_id, observed_at,
            stale, missing, output_modified,
            bool(stale or missing or output_modified),
        )
