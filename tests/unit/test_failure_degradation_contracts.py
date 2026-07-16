import unittest

from fam_os.core.contracts import (
    FAILURE_CONTRACT_VERSION,
    DegradationDisposition,
    DegradationImpact,
    DegradationKind,
    DegradationNotice,
    FailureCategory,
    FailureComponent,
    FailureEnvelope,
    ResultStatus,
    RetryDisposition,
    TaskResult,
)


def _failure(**overrides: object) -> FailureEnvelope:
    values = {
        "error_id": "error-1",
        "category": FailureCategory.UNAVAILABLE,
        "code": "expert.runtime.unavailable",
        "safe_message": "The selected expert is temporarily unavailable.",
        "component": FailureComponent.EXPERT,
        "retry": RetryDisposition.WITH_BACKOFF,
    }
    values.update(overrides)
    return FailureEnvelope(**values)


def _degradation(**overrides: object) -> DegradationNotice:
    values = {
        "degradation_id": "degradation-1",
        "kind": DegradationKind.RESOURCE_CONSTRAINED,
        "code": "scheduler.memory.constrained",
        "safe_message": "The response used a smaller context to preserve system headroom.",
        "component": FailureComponent.SCHEDULER,
        "impact": DegradationImpact.MEDIUM,
        "disposition": DegradationDisposition.CONTINUE,
    }
    values.update(overrides)
    return DegradationNotice(**values)


class FailureEnvelopeTests(unittest.TestCase):
    def test_is_versioned_and_carries_only_safe_evidence_references(self) -> None:
        failure = _failure(evidence_ids=("evidence-1",))
        self.assertEqual(failure.contract_version, FAILURE_CONTRACT_VERSION)
        self.assertEqual(failure.evidence_ids, ("evidence-1",))

    def test_rejects_non_namespaced_code(self) -> None:
        with self.assertRaisesRegex(ValueError, "namespaced"):
            _failure(code="unavailable")

    def test_rejects_multiline_safe_message(self) -> None:
        with self.assertRaisesRegex(ValueError, "one line"):
            _failure(safe_message="safe line\nraw traceback")

    def test_permission_denial_cannot_retry_automatically(self) -> None:
        with self.assertRaisesRegex(ValueError, "requires user action"):
            _failure(
                category=FailureCategory.PERMISSION_DENIED,
                retry=RetryDisposition.IMMEDIATE,
            )


class DegradationNoticeTests(unittest.TestCase):
    def test_fallback_names_original_and_replacement_capabilities(self) -> None:
        notice = _degradation(
            kind=DegradationKind.FALLBACK_USED,
            original_capability_id="editor.semantic.observe",
            replacement_capability_id="filesystem.read",
        )
        self.assertNotEqual(notice.original_capability_id, notice.replacement_capability_id)

    def test_fallback_requires_replacement_capability(self) -> None:
        with self.assertRaisesRegex(ValueError, "original and replacement"):
            _degradation(
                kind=DegradationKind.FALLBACK_USED,
                original_capability_id="editor.semantic.observe",
            )

    def test_quality_reduction_must_declare_impact(self) -> None:
        with self.assertRaisesRegex(ValueError, "declare an impact"):
            _degradation(kind=DegradationKind.QUALITY_REDUCED, impact=DegradationImpact.NONE)


class StructuredTaskResultTests(unittest.TestCase):
    def test_failed_result_requires_structured_failure(self) -> None:
        with self.assertRaisesRegex(ValueError, "structured failure"):
            TaskResult("request-1", ResultStatus.FAILED, None, reason="failed")

    def test_failure_reason_must_be_safe_message(self) -> None:
        with self.assertRaisesRegex(ValueError, "safe_message"):
            TaskResult(
                "request-1",
                ResultStatus.FAILED,
                None,
                reason="raw provider exception",
                failure=_failure(),
            )

    def test_failure_evidence_is_linked_by_result(self) -> None:
        with self.assertRaisesRegex(ValueError, "failure evidence"):
            TaskResult(
                "request-1",
                ResultStatus.FAILED,
                None,
                reason="The selected expert is temporarily unavailable.",
                failure=_failure(evidence_ids=("evidence-1",)),
            )

    def test_success_can_continue_with_visible_degradation(self) -> None:
        result = TaskResult(
            "request-1",
            ResultStatus.COMPLETED,
            "bounded answer",
            degradations=(_degradation(),),
        )
        self.assertEqual(result.degradations[0].impact, DegradationImpact.MEDIUM)

    def test_success_cannot_ignore_withholding_degradation(self) -> None:
        with self.assertRaisesRegex(ValueError, "withholding degradations"):
            TaskResult(
                "request-1",
                ResultStatus.COMPLETED,
                "unsafe answer",
                degradations=(
                    _degradation(disposition=DegradationDisposition.WITHHOLD),
                ),
            )

    def test_withheld_result_can_name_blocking_degradation(self) -> None:
        notice = _degradation(
            kind=DegradationKind.CAPABILITY_UNAVAILABLE,
            safe_message="The required application capability is unavailable.",
            disposition=DegradationDisposition.WITHHOLD,
            original_capability_id="editor.semantic.observe",
        )
        result = TaskResult(
            "request-1",
            ResultStatus.WITHHELD,
            None,
            reason=notice.safe_message,
            degradations=(notice,),
        )
        self.assertIsNone(result.failure)


if __name__ == "__main__":
    unittest.main()
