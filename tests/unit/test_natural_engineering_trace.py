import unittest
from datetime import datetime, timezone
from types import SimpleNamespace

from fam_os.core.engineering import (
    CandidateEditStatus, CandidateOperationKind,
    CandidateVerificationStatus, RequirementTraceStatus,
)
from fam_os.product.natural_engineering_trace import (
    NaturalEngineeringTraceCoordinator,
)


NOW = datetime(2026, 7, 19, 16, 0, tzinfo=timezone.utc)


class NaturalEngineeringTraceTests(unittest.TestCase):
    def test_trace_excludes_directory_and_deleted_path_operations(self):
        loop = _Loop()
        coordinator = NaturalEngineeringTraceCoordinator(loop)
        definition = SimpleNamespace(
            task=SimpleNamespace(task_id="task-1"),
            task_sha256="a" * 64,
            created_at=NOW,
        )
        preparation = SimpleNamespace(analysis=SimpleNamespace(
            affected_test_paths=("tests/test_readme.py",),
        ))
        edits = (
            _edit(CandidateOperationKind.CREATE_DIRECTORY, "tests"),
            _edit(CandidateOperationKind.PATCH_FILE, "README.md"),
            _edit(CandidateOperationKind.DELETE, "obsolete.md"),
            _edit(CandidateOperationKind.CREATE_FILE, "tests/test_readme.py"),
        )
        verifications = (SimpleNamespace(
            status=CandidateVerificationStatus.COMPLETED,
            passed=True,
            evidence=SimpleNamespace(evidence_id="evidence-1"),
            updated_at=NOW,
        ),)

        trace = coordinator.record(
            "owner-1", definition, preparation, edits, verifications,
        )

        self.assertEqual(("README.md",), trace.implementation_paths)
        self.assertEqual(("tests/test_readme.py",), trace.test_paths)
        self.assertEqual(("evidence-1",), trace.evidence_ids)
        self.assertEqual(RequirementTraceStatus.SATISFIED, trace.status)
        self.assertEqual(trace, loop.recorded)


class _Loop:
    def record_requirement_trace(self, owner_id, trace):
        self.owner_id = owner_id
        self.recorded = trace
        return trace


def _edit(kind, path):
    return SimpleNamespace(
        status=CandidateEditStatus.APPLIED,
        operation=SimpleNamespace(kind=kind, path=path),
    )


if __name__ == "__main__":
    unittest.main()
