import unittest

from fam_os.verification import VerificationReport, VerificationRequest, VerificationStatus


class VerificationReportTests(unittest.TestCase):
    def test_request_requires_candidate(self) -> None:
        with self.assertRaisesRegex(ValueError, "candidate"):
            VerificationRequest("verification-0", "")

    def test_passed_is_derived_from_status(self) -> None:
        report = VerificationReport(
            "verification-1",
            "python-tests-v1",
            VerificationStatus.PASSED,
            "tests",
            "all deterministic tests passed",
            0.05,
        )
        self.assertTrue(report.passed)

    def test_failure_is_not_passing(self) -> None:
        report = VerificationReport(
            "verification-2",
            "python-tests-v1",
            VerificationStatus.FAILED,
            "tests",
            "assertion failed",
            0.05,
        )
        self.assertFalse(report.passed)


if __name__ == "__main__":
    unittest.main()
