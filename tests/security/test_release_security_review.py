import tempfile
import unittest
from pathlib import Path

from fam_os.security import FindingDisposition, build_review


class ReleaseSecurityReviewTests(unittest.TestCase):
    def test_unresolved_high_finding_blocks_release(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            evidence = Path(directory, "scanner.json")
            evidence.write_text("{}")
            report = build_review("review", (evidence,), (
                FindingDisposition("CVE-1", "high", "open", "upgrade required"),
            ))
        self.assertFalse(report.passed)
        self.assertEqual(report.release_blockers, ("CVE-1",))
        self.assertFalse(report.human_external_review_completed)

    def test_fixed_and_contextual_findings_pass_automated_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            evidence = Path(directory, "scanner.json")
            evidence.write_text("{}")
            report = build_review("review", (evidence,), (
                FindingDisposition("CVE-1", "high", "fixed", "upgraded"),
                FindingDisposition("B108", "medium", "accepted", "namespace path"),
            ))
        self.assertTrue(report.passed)
        self.assertFalse(report.release_blockers)

    def test_missing_scanner_evidence_fails_closed(self) -> None:
        with self.assertRaisesRegex(ValueError, "must exist"):
            build_review("review", (Path("missing"),), ())


if __name__ == "__main__":
    unittest.main()
