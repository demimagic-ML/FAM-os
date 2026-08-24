"""Representative transactional candidate-workspace schema documents."""

from datetime import datetime, timezone

from fam_os.core.engineering import (
    CandidateApplyReceipt,
    CandidateApplyStatus,
    CandidateArtifact,
    CandidateArtifactMetadata,
    CandidateBaselineEntry,
    CandidateContentKind,
    CandidateEntryKind,
    CandidateOperation,
    CandidateOperationKind,
    CandidatePreviewItem,
    CandidateTransactionPreview,
    CandidateWorkspace,
    EngineeringSelfUpdatePolicy,
)


NOW = datetime(2026, 7, 18, 18, 0, tzinfo=timezone.utc)


def transaction_schema_values() -> tuple[object, ...]:
    artifact = CandidateArtifact(
        "artifact-1", CandidateContentKind.TEXT, "text/x-python", "b" * 64,
        12, "generated from owner-requested engineering task", "module.py",
        (CandidateArtifactMetadata("language", "python"),),
    )
    operation = CandidateOperation(
        "candidate-operation-1", CandidateOperationKind.PATCH_FILE,
        "src/module.py", "a" * 64, artifact.artifact_id,
    )
    candidate = CandidateWorkspace(
        "candidate-1", "task-1", "baseline-1", "/workspace",
        "/transactions/candidate-1/workspace", NOW, "reflink",
        "c" * 64,
        (CandidateBaselineEntry(
            "src/module.py", CandidateEntryKind.FILE, "a" * 64, 10, False,
        ),),
    )
    preview = CandidateTransactionPreview(
        "transaction-1", candidate.candidate_id, candidate.baseline_tree_sha256,
        NOW,
        (CandidatePreviewItem(
            operation.path, operation.kind, "a" * 64, "b" * 64,
            "text/x-python", 2, "--- before\n+++ after", ("content_change",),
        ),),
        ("verification-1",), "isolated candidate verification passed",
        "restore FAM-owned paths from the durable journal",
    )
    receipt = CandidateApplyReceipt(
        preview.transaction_id, candidate.candidate_id, NOW,
        CandidateApplyStatus.APPLIED, (operation.path,), (), "d" * 64,
        False, "candidate transaction applied",
    )
    policy = EngineeringSelfUpdatePolicy(
        ("source",), ("runtime",), ("trust",),
        ("releases/active",), ("policy/live",),
    )
    return artifact, operation, candidate, preview, receipt, policy
