"""Fail-closed aggregation of independent security scanner output."""

from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class FindingDisposition:
    finding_id: str
    severity: str
    disposition: str
    rationale: str


@dataclass(frozen=True, slots=True)
class SecurityReviewReport:
    review_id: str
    human_external_review_completed: bool
    independent_tools: tuple[str, ...]
    input_digests: tuple[tuple[str, str], ...]
    findings: tuple[FindingDisposition, ...]
    release_blockers: tuple[str, ...]
    passed: bool

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def build_review(
    review_id: str,
    scanner_files: tuple[Path, ...],
    findings: tuple[FindingDisposition, ...],
) -> SecurityReviewReport:
    if not scanner_files or any(not path.is_file() for path in scanner_files):
        raise ValueError("all independent scanner evidence must exist")
    blockers = tuple(
        item.finding_id
        for item in findings
        if item.severity in {"high", "critical"} and item.disposition != "fixed"
    )
    digests = tuple((path.name, _digest(path)) for path in scanner_files)
    tools = tuple(path.stem for path in scanner_files)
    return SecurityReviewReport(
        review_id, False, tools, digests, findings, blockers, not blockers,
    )


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
