"""Owner ceremony and presentation for blocking engineering review findings."""

import hashlib

from fam_os.core.engineering import (
    EngineeringFindingDisposition,
    EngineeringReviewStatus,
    EngineeringReviewWaiverDecision,
    review_waiver_consequences_digest,
)


class NaturalEngineeringReviewGovernance:
    def __init__(self, loop, authentication, clock) -> None:
        self._loop = loop
        self._authentication = authentication
        self._clock = clock

    def attach_blocked(self, task: dict, reviews) -> None:
        blocked = tuple(
            item for item in reviews
            if item.status is EngineeringReviewStatus.BLOCKED
        )
        if not blocked:
            return
        checkpoint = blocked[-1]
        finding = next(
            item for item in checkpoint.findings
            if item.disposition is EngineeringFindingDisposition.OPEN
        )
        task["outcome"] = "independent_review_blocked"
        task["review_waiver_checkpoint"] = review_waiver_view(
            checkpoint, finding,
        )

    def waive(
        self, owner_id, task_id, checkpoint_id, finding_id,
        consequences_sha256, transport_session_id,
    ):
        checkpoint, finding = self._finding(
            owner_id, task_id, checkpoint_id, finding_id,
        )
        expected = review_waiver_consequences_digest(checkpoint, finding)
        if consequences_sha256 != expected:
            raise PermissionError("engineering review waiver consequences changed")
        decision_id = _identity(
            "review-waiver", task_id, checkpoint_id, finding_id, expected,
        )
        prior = next((
            item for item in self._loop.review_evidence_for_task(
                owner_id, task_id,
            )
            if isinstance(item, EngineeringReviewWaiverDecision)
            and item.decision_id == decision_id
        ), None)
        if prior is None:
            context = self._authentication.issue(
                owner_id, "engineering-review-waiver", expected,
                transport_session_id=transport_session_id,
            )
            if not self._authentication.belongs_to_session(
                context.context_id, transport_session_id,
            ):
                raise PermissionError("review waiver authentication session failed")
            prior = EngineeringReviewWaiverDecision(
                decision_id, checkpoint_id, finding_id, owner_id,
                context.context_id, expected,
                _truthful_assurance(checkpoint), self._clock(),
            )
        updated = self._loop.waive_review_finding(owner_id, prior)
        return prior, updated

    def _finding(self, owner_id, task_id, checkpoint_id, finding_id):
        checkpoints = tuple(
            item for item in self._loop.reviews_for_task(owner_id, task_id)
            if item.checkpoint_id == checkpoint_id
        )
        if len(checkpoints) != 1:
            raise KeyError("engineering review checkpoint is unavailable")
        findings = tuple(
            item for item in checkpoints[0].findings
            if item.finding_id == finding_id
        )
        if len(findings) != 1:
            raise KeyError("engineering review finding is unavailable")
        if findings[0].disposition is not EngineeringFindingDisposition.OPEN:
            raise PermissionError("engineering review finding is already closed")
        return checkpoints[0], findings[0]


def review_waiver_view(checkpoint, finding) -> dict:
    return {
        "checkpoint_id": checkpoint.checkpoint_id,
        "finding_id": finding.finding_id,
        "discipline": finding.discipline.value,
        "severity": finding.severity.value,
        "title": finding.title,
        "path": finding.path,
        "consequences_sha256": review_waiver_consequences_digest(
            checkpoint, finding,
        ),
        "truthful_assurance_after_waiver": _truthful_assurance(checkpoint),
    }


def _truthful_assurance(checkpoint) -> str:
    open_count = sum(
        item.disposition is EngineeringFindingDisposition.OPEN
        for item in checkpoint.findings
    )
    return "review_waived" if open_count == 1 else "partially_reviewed"


def _identity(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()[:32]
    return f"{prefix}-{digest}"
