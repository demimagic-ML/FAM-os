import unittest

from fam_os.core.contracts import CORE_CONTRACT_VERSION, ResultStatus, TaskRequest, TaskResult


class TaskRequestTests(unittest.TestCase):
    def test_normalizes_capabilities(self) -> None:
        request = TaskRequest("request-1", "Solve it", (" code ",), True)
        self.assertEqual(request.required_capabilities, ("code",))
        self.assertEqual(request.contract_version, CORE_CONTRACT_VERSION)

    def test_rejects_empty_prompt(self) -> None:
        with self.assertRaisesRegex(ValueError, "prompt"):
            TaskRequest("request-1", "  ")


class TaskResultTests(unittest.TestCase):
    def test_accepts_verified_content(self) -> None:
        result = TaskResult(
            "request-1",
            ResultStatus.VERIFIED,
            "answer",
            verified=True,
            evidence_ids=("verification-1",),
        )
        self.assertEqual(result.content, "answer")

    def test_verified_result_requires_evidence(self) -> None:
        with self.assertRaisesRegex(ValueError, "evidence"):
            TaskResult("request-1", ResultStatus.VERIFIED, "answer", verified=True)

    def test_withheld_result_cannot_leak_candidate(self) -> None:
        with self.assertRaisesRegex(ValueError, "cannot expose"):
            TaskResult("request-1", ResultStatus.WITHHELD, "unverified candidate")

    def test_verified_flag_and_status_must_agree(self) -> None:
        with self.assertRaisesRegex(ValueError, "verified status"):
            TaskResult("request-1", ResultStatus.VERIFIED, "answer")

    def test_failed_result_requires_reason(self) -> None:
        with self.assertRaisesRegex(ValueError, "reason"):
            TaskResult("request-1", ResultStatus.FAILED, None)


if __name__ == "__main__":
    unittest.main()
