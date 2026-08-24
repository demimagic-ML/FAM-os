import unittest
from datetime import datetime, timezone

from fam_os.core.engineering import (
    CandidateWorkspace,
    DocumentationArtifactKind,
    DocumentationGenerationRequest,
    DocumentationSource,
    GeneratedDocumentationReceipt,
    GovernedDocumentationService,
    RequirementTraceabilityRecord,
    RequirementTraceStatus,
)


NOW = datetime(2026, 7, 19, 22, 0, tzinfo=timezone.utc)


class GovernedDocumentationTests(unittest.TestCase):
    def setUp(self):
        self.source = DocumentationSource("src/api.py", "a" * 64)
        self.request = DocumentationGenerationRequest(
            "request-1", "task-1", "candidate-1",
            DocumentationArtifactKind.API_REFERENCE, "docs/api.md",
            "signed-recipe-1", "CODEOWNERS", "docs/REGENERATE.md",
            (self.source,), NOW,
        )
        self.receipt = GeneratedDocumentationReceipt(
            "receipt-1", "request-1", "task-1", "candidate-1",
            "docs/api.md", "b" * 64, "signed-recipe-1",
            (self.source,), NOW, True,
        )
        self.candidate = CandidateWorkspace(
            "candidate-1", "task-1", "baseline-1", "/owner/workspace",
            "/candidate/workspace", NOW, "copy", "c" * 64, (),
        )

    def test_generation_is_candidate_bound_and_receipt_exact(self):
        service = GovernedDocumentationService()
        service.admit(self.request, self.candidate)
        service.validate_receipt(self.request, self.receipt)
        with self.assertRaises(PermissionError):
            service.admit(
                self.request,
                CandidateWorkspace(
                    "other", "task-1", "baseline-1", "/owner/workspace",
                    "/candidate/other", NOW, "copy", "c" * 64, (),
                ),
            )

    def test_staleness_detects_source_output_and_missing_source_changes(self):
        service = GovernedDocumentationService()
        current = (DocumentationSource("src/api.py", "d" * 64),)
        report = service.staleness(
            self.receipt, current, "e" * 64,
            report_id="report-1", observed_at=NOW,
        )
        self.assertTrue(report.stale)
        self.assertEqual(("src/api.py",), report.stale_source_paths)
        missing = service.staleness(
            self.receipt, (), self.receipt.output_sha256,
            report_id="report-2", observed_at=NOW,
        )
        self.assertEqual(("src/api.py",), missing.missing_source_paths)

    def test_satisfied_trace_requires_implementation_test_and_evidence(self):
        with self.assertRaises(ValueError):
            RequirementTraceabilityRecord(
                "trace-1", "task-1", "requirement-1", "PLAN.md",
                (), (), (), RequirementTraceStatus.SATISFIED, NOW,
            )


if __name__ == "__main__":
    unittest.main()
