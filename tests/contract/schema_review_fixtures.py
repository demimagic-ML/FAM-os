from datetime import datetime, timezone
import base64

from fam_os.core.engineering import (
    EngineeringFindingDisposition,
    EngineeringFindingSeverity,
    EngineeringReviewCheckpoint,
    EngineeringReviewDiscipline,
    EngineeringReviewFinding,
    EngineeringReviewResolutionReceipt,
    EngineeringReviewSelection,
    EngineeringReviewStatus,
    EngineeringReviewWaiverDecision,
    SignedEngineeringReviewerRecipe,
    review_waiver_consequences_digest,
)


NOW = datetime(2026, 7, 19, 22, 30, tzinfo=timezone.utc)


def review_schema_values() -> tuple[object, ...]:
    finding = EngineeringReviewFinding(
        "finding-1", EngineeringReviewDiscipline.SECURITY,
        EngineeringFindingSeverity.HIGH, "Reject unbounded command",
        "src/runner.py", ("evidence-1",), EngineeringFindingDisposition.OPEN,
    )
    checkpoint = EngineeringReviewCheckpoint(
        "review-1", "task-1", "candidate-1", "a" * 64,
        "producer-1", "reviewer-1", "independence-1",
        (EngineeringReviewDiscipline.CODE, EngineeringReviewDiscipline.SECURITY),
        (finding,), EngineeringReviewStatus.BLOCKED, NOW,
    )
    waiver = EngineeringReviewWaiverDecision(
        "waiver-1", checkpoint.checkpoint_id, finding.finding_id, "owner-1",
        "context-1", review_waiver_consequences_digest(checkpoint, finding),
        "review_waived", NOW,
    )
    selection = EngineeringReviewSelection(
        "selection-1", checkpoint.task_id, checkpoint.candidate_id,
        checkpoint.changeset_sha256, "review-policy-1", "b" * 64,
        checkpoint.required_disciplines, NOW,
    )
    recipe = SignedEngineeringReviewerRecipe(
        "reviewer-recipe-1", "1.0.0", checkpoint.reviewer_id,
        "reviewer-adapter-1", tuple(EngineeringReviewDiscipline), "key-1",
        "c" * 64, base64.b64encode(b"x" * 64).decode("ascii"),
    )
    resolution = EngineeringReviewResolutionReceipt(
        "resolution-1", checkpoint.task_id, checkpoint.candidate_id,
        checkpoint.changeset_sha256, checkpoint.checkpoint_id,
        finding.finding_id, ("edit-1",), ("verification-evidence-1",),
        checkpoint.reviewer_id, checkpoint.reviewer_independence_ref, NOW,
    )
    return checkpoint, waiver, selection, recipe, resolution
