"""Deterministic requirement-to-change-test-evidence trace generation."""

from __future__ import annotations

import hashlib
from pathlib import PurePosixPath

from fam_os.core.engineering import (
    CandidateEditStatus,
    CandidateOperationKind,
    CandidateVerificationStatus,
    DOCUMENTATION_OUTPUT_PATHS,
    DOCUMENTATION_OWNERSHIP_PATH,
    DOCUMENTATION_REGENERATION_PATH,
    DOCUMENTATION_REQUIREMENTS_PATH,
    RequirementTraceStatus,
    RequirementTraceabilityRecord,
)


class NaturalEngineeringTraceCoordinator:
    def __init__(self, loop) -> None:
        self._loop = loop

    def record(self, owner_id, definition, preparation, edits, verifications):
        changed = tuple(sorted({
            item.operation.path for item in edits
            if item.status is CandidateEditStatus.APPLIED
            and item.operation.kind in _TRACEABLE_FILE_OPERATIONS
            and item.operation.path not in _GOVERNED_PATHS
        }))
        tests = tuple(sorted({
            *preparation.analysis.affected_test_paths,
            *(path for path in changed if _is_test(path)),
        }))
        implementation = tuple(path for path in changed if path not in tests)
        evidence = tuple(sorted({
            item.evidence.evidence_id for item in verifications
            if item.status is CandidateVerificationStatus.COMPLETED
            and item.passed and item.evidence is not None
        }))
        recorded_at = max(
            (
                item.updated_at for item in verifications
                if item.status is CandidateVerificationStatus.COMPLETED
                and item.passed
            ),
            default=definition.created_at,
        )
        status = (
            RequirementTraceStatus.SATISFIED
            if implementation and tests and evidence
            else RequirementTraceStatus.PARTIAL
        )
        identity = _identity(
            definition.task.task_id, definition.task_sha256,
            *implementation, *tests, *evidence,
        )
        trace = RequirementTraceabilityRecord(
            f"requirement-trace-{identity}", definition.task.task_id,
            f"owner-task-{definition.task_sha256[:32]}",
            DOCUMENTATION_REQUIREMENTS_PATH, implementation, tests, evidence,
            status, recorded_at,
        )
        return self._loop.record_requirement_trace(owner_id, trace)


_GOVERNED_PATHS = frozenset({
    *DOCUMENTATION_OUTPUT_PATHS.values(),
    DOCUMENTATION_OWNERSHIP_PATH,
    DOCUMENTATION_REGENERATION_PATH,
    DOCUMENTATION_REQUIREMENTS_PATH,
})

_TRACEABLE_FILE_OPERATIONS = frozenset({
    CandidateOperationKind.CREATE_FILE,
    CandidateOperationKind.PATCH_FILE,
    CandidateOperationKind.MOVE,
    CandidateOperationKind.RESTORE,
    CandidateOperationKind.SET_EXECUTABLE,
})


def _is_test(path: str) -> bool:
    value = PurePosixPath(path)
    name = value.name.casefold()
    return (
        any(part.casefold() in {"test", "tests", "spec", "specs"} for part in value.parts)
        or name.startswith("test_")
        or name.endswith(("_test.py", ".test.js", ".test.ts", ".spec.js", ".spec.ts"))
    )


def _identity(*values: str) -> str:
    return hashlib.sha256("\0".join(values).encode()).hexdigest()[:32]
