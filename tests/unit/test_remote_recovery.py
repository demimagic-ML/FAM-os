import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from fam_os.core.lifecycle import AttemptBudgetReservation
from fam_os.core.lifecycle.attempt_contracts import AttemptKind
from fam_os.core.production.remote_recovery import (
    classify_remote_failure,
    local_retry_allowed,
)
from fam_os.fabric import (
    RemoteAttemptFailure,
    RemoteRecoveryDisposition,
    RemoteRecoveryEvidence,
)


NOW = datetime(2026, 7, 17, tzinfo=UTC)


class RemoteRecoveryTests(unittest.TestCase):
    def test_failure_classification_allows_only_loss_or_signed_provider_failure(self):
        cases = (
            (ConnectionError("closed"), RemoteAttemptFailure.DISCONNECTED, True),
            (
                ConnectionError("closed before a complete frame"),
                RemoteAttemptFailure.PARTIAL_RESULT,
                True,
            ),
            (TimeoutError("timed out"), RemoteAttemptFailure.TIMEOUT, True),
            (
                RuntimeError("remote.execution.provider_failed"),
                RemoteAttemptFailure.REMOTE_PROVIDER_FAILED,
                True,
            ),
            (
                PermissionError("TLS peer identity changed"),
                RemoteAttemptFailure.AUTHENTICATION_FAILED,
                False,
            ),
            (
                ValueError("invalid signed result"),
                RemoteAttemptFailure.INVALID_RESULT,
                False,
            ),
        )
        for error, expected, allowed in cases:
            with self.subTest(error=error):
                failure = classify_remote_failure(error)
                self.assertEqual(expected, failure)
                self.assertEqual(allowed, local_retry_allowed(failure))

    def test_recovery_evidence_is_content_free_and_one_way(self):
        pending = recovery_evidence()
        recovered = pending.recovered("candidate-local", NOW + timedelta(seconds=1))
        self.assertEqual(RemoteRecoveryDisposition.RECOVERED, recovered.disposition)
        with self.assertRaisesRegex(ValueError, "not awaiting"):
            recovered.recovered("candidate-other", NOW + timedelta(seconds=2))
        with self.assertRaisesRegex(ValueError, "content-free"):
            replace(pending, partial_output_retained=True)
        with self.assertRaisesRegex(ValueError, "comparison"):
            replace(pending, observed_contract_sha256="b" * 64)

    def test_remote_and_local_recovery_reservations_bind_acceptance(self):
        reservation = AttemptBudgetReservation(
            "budget-1", "instance-1", "attempt-1",
            AttemptKind.LOCAL_RECOVERY, 1024, 300_000,
            "a" * 64, "remote-plan-1",
        )
        self.assertEqual("a" * 64, reservation.acceptance_sha256)
        self.assertEqual("remote-plan-1", reservation.route_plan_id)
        with self.assertRaisesRegex(ValueError, "acceptance digest"):
            replace(reservation, acceptance_sha256="bad")


def recovery_evidence() -> RemoteRecoveryEvidence:
    return RemoteRecoveryEvidence(
        "remote-recovery-1", "instance-1", "request-1", "remote-plan-1",
        "budget-remote", "attempt-remote", RemoteAttemptFailure.DISCONNECTED,
        "a" * 64, "a" * 64, True, True,
        "selection-local", "local:q4", "economical",
        "budget-local", "attempt-local", None,
        RemoteRecoveryDisposition.LOCAL_RETRY_PENDING,
        ("remote.disconnected", "acceptance.unchanged", "fallback.local"),
        NOW, None,
    )


if __name__ == "__main__":
    unittest.main()
