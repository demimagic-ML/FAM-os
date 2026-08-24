import base64
from datetime import datetime, timezone

from fam_os.core.engineering import (
    DocumentationArtifactKind,
    DocumentationGenerationRequest,
    DocumentationGovernanceBinding,
    DocumentationRequirementSelection,
    DocumentationSource,
    DocumentationStalenessReport,
    GeneratedDocumentationReceipt,
    RequirementTraceabilityRecord,
    RequirementTraceStatus,
    SignedDocumentationRecipe,
)


NOW = datetime(2026, 7, 19, 22, 0, tzinfo=timezone.utc)


def documentation_recipe_schema_value() -> SignedDocumentationRecipe:
    return SignedDocumentationRecipe(
        "fam.documentation.api_reference", "1.0.0",
        DocumentationArtifactKind.API_REFERENCE,
        "fam.documentation.deterministic.v1", "text/markdown",
        64, 2_097_152, 262_144, "release-key", "0" * 64,
        base64.b64encode(b"0" * 64).decode("ascii"),
    )


def documentation_schema_values() -> tuple[object, ...]:
    recipe = documentation_recipe_schema_value()
    source = DocumentationSource("src/api.py", "a" * 64)
    request = DocumentationGenerationRequest(
        "docs-request-1", "task-1", "candidate-1",
        DocumentationArtifactKind.API_REFERENCE, "docs/api.md",
        recipe.coordinate, "CODEOWNERS", "docs/REGENERATE.md",
        (source,), NOW,
    )
    selection = DocumentationRequirementSelection(
        "docs-selection-1", request.task_id, request.candidate_id,
        "fam.documentation.requirements.v1", "f" * 64,
        (DocumentationArtifactKind.API_REFERENCE,), NOW,
    )
    receipt = GeneratedDocumentationReceipt(
        "docs-receipt-1", request.request_id, request.task_id,
        request.candidate_id, request.output_path, "b" * 64,
        request.generator_recipe_id, request.sources, NOW, True,
    )
    binding = DocumentationGovernanceBinding(
        "docs-governance-1", request.request_id, request.task_id,
        request.candidate_id,
        (
            DocumentationSource("CODEOWNERS", "c" * 64),
            DocumentationSource("docs/REGENERATE.md", "d" * 64),
            DocumentationSource("docs/REQUIREMENTS.md", "e" * 64),
        ),
        NOW,
    )
    report = DocumentationStalenessReport(
        "stale-report-1", receipt.receipt_id, receipt.task_id, NOW,
        (), (), False, False,
    )
    trace = RequirementTraceabilityRecord(
        "trace-1", "task-1", "requirement-30.6", "MASTER_PLANv2.md",
        ("src/fam_os/core/engineering/documentation.py",),
        ("tests/unit/test_governed_documentation.py",),
        (receipt.receipt_id,), RequirementTraceStatus.SATISFIED, NOW,
    )
    return selection, request, binding, receipt, report, trace
