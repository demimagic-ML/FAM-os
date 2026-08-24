"""Bounded release-owned review of an exact candidate preview."""

from __future__ import annotations

import hashlib
import re

from fam_os.core.engineering.review import (
    EngineeringFindingDisposition,
    EngineeringFindingSeverity,
    EngineeringReviewCheckpoint,
    EngineeringReviewDiscipline,
    EngineeringReviewFinding,
    EngineeringReviewStatus,
)


_SECRET_ASSIGNMENT = re.compile(
    r"(?i)\b(?:api[_-]?key|access[_-]?token|password|client[_-]?secret)\b"
    r"\s*[:=]\s*['\"][^'\"\n]{4,}['\"]"
)
_UNBOUNDED_SHELL = re.compile(
    r"(?i)(?:\bos\.system\s*\(|\bshell\s*=\s*true\b|\beval\s*\(|\bexec\s*\()"
)


class DeterministicEngineeringReviewer:
    adapter_id = "fam.review.deterministic.v1"

    def review(self, recipe, selection, changeset, *, producer_id):
        if recipe.adapter_id != self.adapter_id:
            raise PermissionError("signed reviewer adapter is unsupported")
        findings = []
        if (
            EngineeringReviewDiscipline.CODE in selection.required_disciplines
            and not changeset.preview.verification_evidence_ids
        ):
            findings.append(self._finding(
                selection, EngineeringReviewDiscipline.CODE,
                EngineeringFindingSeverity.HIGH,
                "Passing verification evidence is required", None,
                (selection.selection_id,),
            ))
        if EngineeringReviewDiscipline.SECURITY in selection.required_disciplines:
            for item in changeset.preview.items:
                if "set_executable" in item.risk_codes:
                    findings.append(self._finding(
                        selection, EngineeringReviewDiscipline.SECURITY,
                        EngineeringFindingSeverity.HIGH,
                        "Executable permission change requires explicit disposition",
                        item.path, (selection.selection_id, item.after_sha256 or item.path),
                    ))
                if _SECRET_ASSIGNMENT.search(item.preview):
                    findings.append(self._finding(
                        selection, EngineeringReviewDiscipline.SECURITY,
                        EngineeringFindingSeverity.CRITICAL,
                        "Candidate preview contains secret-like literal material",
                        item.path, (selection.selection_id, item.after_sha256 or item.path),
                    ))
                if _UNBOUNDED_SHELL.search(item.preview):
                    findings.append(self._finding(
                        selection, EngineeringReviewDiscipline.SECURITY,
                        EngineeringFindingSeverity.HIGH,
                        "Candidate preview contains an unbounded execution primitive",
                        item.path, (selection.selection_id, item.after_sha256 or item.path),
                    ))
        if EngineeringReviewDiscipline.ARCHITECTURE in selection.required_disciplines:
            paths = tuple(item.path for item in changeset.preview.items)
            architecture_surface = any(
                path.startswith((
                    "schemas/", "src/fam_os/schemas/",
                    "src/fam_os/product/storage/migrations/",
                ))
                for path in paths
            )
            if architecture_surface and not any(
                path.startswith("docs/decisions/") for path in paths
            ):
                findings.append(self._finding(
                    selection, EngineeringReviewDiscipline.ARCHITECTURE,
                    EngineeringFindingSeverity.MEDIUM,
                    "Architecture-affecting change lacks an accompanying decision record",
                    None, (selection.selection_id,),
                ))
        status = (
            EngineeringReviewStatus.BLOCKED
            if findings else EngineeringReviewStatus.PASSED
        )
        checkpoint_id = _identity(
            "engineering-review", selection.selection_id, recipe.coordinate,
            producer_id, *(item.finding_id for item in findings),
        )
        return EngineeringReviewCheckpoint(
            checkpoint_id, selection.task_id, selection.candidate_id,
            selection.changeset_sha256, producer_id, recipe.reviewer_id,
            f"release-signed:{recipe.coordinate}:{recipe.payload_sha256}",
            selection.required_disciplines, tuple(findings), status,
            selection.selected_at,
        )

    @staticmethod
    def _finding(selection, discipline, severity, title, path, evidence_ids):
        return EngineeringReviewFinding(
            _identity(
                "review-finding", selection.selection_id, discipline.value,
                severity.value, title, path or "",
            ),
            discipline, severity, title, path, tuple(evidence_ids),
            EngineeringFindingDisposition.OPEN,
        )


def _identity(prefix: str, *parts: str) -> str:
    digest = hashlib.sha256("\0".join(parts).encode("utf-8")).hexdigest()[:32]
    return f"{prefix}-{digest}"
