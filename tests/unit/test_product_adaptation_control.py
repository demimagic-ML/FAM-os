import hashlib
import os
import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

from fam_os.adaptation import (
    AdaptationControlOperation,
    AdaptationHealthSample,
    AdaptationInferenceObservation,
    AdaptationRuntimeHealth,
    LiveAdaptationControlRequest,
    LiveAdaptationSnapshot,
    selection_for,
    VerifiedLearningOutcome,
)
from fam_os.core.contracts import ResultAssurance, ResultStatus, TaskRequest, TaskResult
from fam_os.core.lifecycle import AcceptanceEvidenceRecord, CandidateEvidenceRecord
from fam_os.product.adaptation_control import ProductAdaptationControl
from fam_os.product.composition.core_storage import CoreStorageComposition
from fam_os.product.storage import (
    OwnerKeyStore,
    ProductionDatabase,
    SecureStorage,
    StorageSettings,
)


NOW = datetime(2026, 7, 17, 12, tzinfo=UTC)


class ProductAdaptationControlTests(unittest.TestCase):
    def test_disable_and_reset_survive_restart_without_deleting_terminal_results(self):
        with tempfile.TemporaryDirectory() as temporary:
            database, repositories = _repositories(Path(temporary))
            results, learning = _verified_outcomes(repositories)
            control = ProductAdaptationControl(repositories, lambda: NOW)
            control.start()
            snapshot = _snapshot("baseline", tuple(item.learning_id for item in learning))
            self.assertEqual(snapshot, control.register_snapshot(snapshot))

            disabled = control.control(LiveAdaptationControlRequest(
                "disable-1", AdaptationControlOperation.DISABLE, True,
            ))
            self.assertFalse(disabled.state.enabled)
            self.assertIsNone(control.active_snapshot("intent:code"))
            reset = control.control(LiveAdaptationControlRequest(
                "reset-1", AdaptationControlOperation.RESET, True,
            ))

            self.assertEqual(2, reset.removed_learning_count)
            self.assertEqual(1, reset.removed_snapshot_count)
            self.assertEqual((), repositories.terminal_outcomes.learning_records())
            self.assertEqual(results[0], repositories.terminal_outcomes.result("request-0"))
            self.assertEqual((), repositories.live_adaptation.snapshots())
            self.assertEqual(3, len(control.receipts()))

            restarted = ProductAdaptationControl(repositories, lambda: NOW + timedelta(hours=1))
            restarted.start()
            self.assertFalse(restarted.state().enabled)
            self.assertEqual((), restarted.state().active_selections)
            database.close()

    def test_repeated_quality_latency_thermal_and_policy_drift_restores_known_good(self):
        with tempfile.TemporaryDirectory() as temporary:
            database, repositories = _repositories(Path(temporary))
            control = ProductAdaptationControl(repositories, lambda: NOW)
            control.start()
            baseline = _snapshot("baseline", ("learning-a", "learning-b"))
            candidate = _snapshot("candidate", ("learning-a", "learning-b", "learning-c"))
            control.register_snapshot(baseline)
            _add_health(repositories, baseline, 0, 1, 1, 65, True)
            _add_health(repositories, baseline, 1, 1, 1, 66, True)
            self.assertEqual(candidate, control.register_snapshot(candidate))
            _add_health(repositories, candidate, 2, 0, 2, 91, False)
            _add_health(repositories, candidate, 3, 1, 2, 92, False)

            receipt = control.control(LiveAdaptationControlRequest(
                "evaluate-1", AdaptationControlOperation.EVALUATE, True, "intent:code",
            ))

            state = receipt.state
            active = selection_for(state.active_selections, "intent:code")
            self.assertIsNotNone(active)
            self.assertEqual(baseline.snapshot_id, active.snapshot_id)
            self.assertIn(candidate.snapshot_id, state.drifted_snapshot_ids)
            report = control.reports()[0]
            self.assertTrue(report.drifted)
            self.assertEqual(
                {
                    "verification.quality_regressed", "latency.p95_regressed",
                    "thermal.limit_exceeded", "thermal.regressed",
                    "policy.violation_detected",
                },
                set(report.reason_codes),
            )
            database.close()

    def test_manual_rollback_is_confirmed_and_idempotent(self):
        with tempfile.TemporaryDirectory() as temporary:
            database, repositories = _repositories(Path(temporary))
            control = ProductAdaptationControl(repositories, lambda: NOW)
            control.start()
            baseline = _snapshot("baseline", ("learning-a", "learning-b"))
            candidate = _snapshot("candidate", ("learning-a", "learning-b", "learning-c"))
            control.register_snapshot(baseline)
            _add_health(repositories, baseline, 0, 1, 1, None, True)
            _add_health(repositories, baseline, 1, 1, 1, None, True)
            control.register_snapshot(candidate)
            request = LiveAdaptationControlRequest(
                "rollback-1", AdaptationControlOperation.ROLLBACK, True, "intent:code",
            )

            first = control.control(request)
            second = control.control(request)

            self.assertEqual(first, second)
            self.assertEqual("applied", first.status.value)
            self.assertEqual(1, sum(item.request_id == "rollback-1" for item in control.receipts()))
            with self.assertRaises(PermissionError):
                control.control(LiveAdaptationControlRequest(
                    "disable-denied", AdaptationControlOperation.DISABLE, False,
                ))
            database.close()

    def test_automatic_evaluation_waits_for_two_candidate_samples(self):
        with tempfile.TemporaryDirectory() as temporary:
            database, repositories = _repositories(Path(temporary))
            control = ProductAdaptationControl(repositories, lambda: NOW)
            control.start()
            baseline = _snapshot("baseline", ("learning-a", "learning-b"))
            candidate = _snapshot(
                "candidate", ("learning-a", "learning-b", "learning-c"),
            )
            control.register_snapshot(baseline)
            _add_health(repositories, baseline, 0, 1, 1, 65, True)
            _add_health(repositories, baseline, 1, 1, 1, 66, True)
            control.register_snapshot(candidate)

            _finish_inference(control, repositories, candidate, 2, False, 91)
            state = control.state()
            self.assertEqual(
                candidate.snapshot_id,
                selection_for(state.active_selections, "intent:code").snapshot_id,
            )
            self.assertFalse(any(
                "health_samples_insufficient" in item.reason_codes
                for item in control.receipts()
            ))

            _finish_inference(control, repositories, candidate, 3, False, 92)
            state = control.state()
            self.assertEqual(
                baseline.snapshot_id,
                selection_for(state.active_selections, "intent:code").snapshot_id,
            )
            automatic = tuple(
                item for item in control.receipts()
                if item.request_id.startswith("adaptation-auto-health-")
            )
            self.assertEqual(1, len(automatic))
            self.assertEqual(AdaptationControlOperation.ROLLBACK, automatic[0].operation)
            database.close()


def _repositories(root: Path):
    database = ProductionDatabase(StorageSettings(root / "fam.sqlite3", os.geteuid()))
    storage = SecureStorage(
        database, OwnerKeyStore(root / "master.key", os.geteuid()),
    ).open()
    repositories = CoreStorageComposition(
        database, storage.cipher, str(os.geteuid()),
    ).repositories()
    return database, repositories


def _verified_outcomes(repositories):
    results, learning = [], []
    for index in range(2):
        request = TaskRequest(f"request-{index}", f"prompt-{index}", (), True)
        candidate = CandidateEvidenceRecord(
            f"candidate-{index}", request.request_id, f"plan-{index}", "READY",
        )
        acceptance = AcceptanceEvidenceRecord(
            f"acceptance-{index}", candidate.candidate_id, ("exact",), True,
        )
        result = TaskResult(
            request.request_id, ResultStatus.VERIFIED, "READY", True,
            plan_id=f"plan-{index}",
            evidence_ids=(candidate.candidate_id, acceptance.evidence_id),
            assurance=ResultAssurance.VERIFIED,
        )
        outcome = VerifiedLearningOutcome(
            f"learning-{index}", "intent:code", "code", "code:model", "specialist",
            NOW + timedelta(minutes=index), 512, False,
            acceptance.evidence_id, candidate.candidate_id,
            hashlib.sha256(f"evidence-{index}".encode()).hexdigest(),
        )
        repositories.requests.add(request, "running")
        repositories.final_evidence.add_candidate(candidate)
        repositories.final_evidence.add_acceptance(acceptance)
        repositories.terminal_outcomes.finalize(request, result, outcome)
        results.append(result)
        learning.append(outcome)
    return tuple(results), tuple(learning)


def _snapshot(name: str, learning_ids: tuple[str, ...]):
    return LiveAdaptationSnapshot(
        f"snapshot-{name}", "intent:code", NOW, len(learning_ids), 2048,
        .5, False, ("code:model",), None, None, learning_ids,
        hashlib.sha256(name.encode()).hexdigest(),
    )


def _add_health(repositories, snapshot, index, quality, latency, temperature, policy):
    sample = AdaptationHealthSample(
        f"sample-{snapshot.snapshot_id}-{index}", f"observation-{index}",
        hashlib.sha256(f"request-{index}".encode()).hexdigest(),
        snapshot.snapshot_id, snapshot.workflow_id, "code:model",
        NOW + timedelta(minutes=index), quality, latency, temperature, policy,
        ("policy.runtime_bounds_satisfied" if policy else "policy.test_violation",),
    )
    repositories.adaptation_controls.finalize_health(sample)


def _finish_inference(control, repositories, snapshot, index, verified, temperature):
    request_id = f"candidate-request-{index}"
    observation_id = f"candidate-observation-{index}"
    repositories.adaptation_controls.add_inference(AdaptationInferenceObservation(
        observation_id, request_id, snapshot.snapshot_id, snapshot.workflow_id,
        "code:model", NOW + timedelta(minutes=index), 2, 0, 8, 4, 2048, 8192,
        AdaptationRuntimeHealth(
            temperature, False,
            ("thermal.limit_exceeded", "policy.thermal_limit_violated"),
        ),
    ))
    result = TaskResult(
        request_id, ResultStatus.VERIFIED if verified else ResultStatus.COMPLETED,
        "result", verified, assurance=(
            ResultAssurance.VERIFIED if verified else ResultAssurance.UNVERIFIED
        ),
    )
    control.terminal_committed(SimpleNamespace(instance_id=observation_id), result, None)


if __name__ == "__main__":
    unittest.main()
