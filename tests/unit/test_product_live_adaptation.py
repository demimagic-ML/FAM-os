import hashlib
import os
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from fam_os.adaptation import VerifiedLearningOutcome
from fam_os.core.ports.inference import InferenceMessage, LoadedModel, MessageRole
from fam_os.core.production.contracts import ModelIntent, RuntimeModelEntry
from fam_os.core.production.model_catalog import RuntimeModelCatalog
from fam_os.core.production.model_selection import HostCapacity
from fam_os.product.live_adaptation import ProductLiveAdaptation
from fam_os.product.storage.database import ProductionDatabase, StorageSettings
from fam_os.product.storage.keys import OwnerKeyStore
from fam_os.product.storage.live_adaptation_repository import (
    SqliteLiveAdaptationRepository,
)
from fam_os.product.storage.adaptation_control_repository import (
    SqliteAdaptationControlRepository,
)
from fam_os.product.storage.secure_store import SecureStorage


class ProductLiveAdaptationTests(unittest.TestCase):
    def test_cold_start_uses_prompt_bound_context_without_truncation(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database, repository = _repository(Path(temporary))
            coordinator = _coordinator(repository, (), _Runtime())
            coordinator.start()

            context = coordinator.context_tokens(
                "cold-request", ModelIntent.CODE, "model-a",
                (InferenceMessage(MessageRole.USER, "short first request"),),
                1024, 32768,
            )

            self.assertEqual(2048, context)
            coordinator.stop()
            database.close()

    def test_new_learning_is_registered_before_terminal_drift_evaluation(self) -> None:
        calls = []
        coordinator = ProductLiveAdaptation.__new__(ProductLiveAdaptation)
        coordinator._control = SimpleNamespace(
            terminal_committed=lambda *_args: calls.append("health"),
        )
        coordinator.learning_committed = lambda _learning: calls.append("learning")

        coordinator.terminal_committed(
            SimpleNamespace(), SimpleNamespace(), SimpleNamespace(),
            SimpleNamespace(),
        )

        self.assertEqual(["learning", "health"], calls)

    def test_live_predictions_drive_context_frequency_transition_and_restart(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            database, repository = _repository(root)
            records = _records(("model-a", "model-b", "model-a", "model-b", "model-a"))
            runtime = _Runtime()
            coordinator = _coordinator(repository, records, runtime)

            coordinator.start()
            self.assertTrue(coordinator.wait_for_idle())

            snapshots = coordinator.snapshots()
            self.assertEqual(1, len(snapshots))
            self.assertEqual("model-a", snapshots[0].frequency_model_refs[0])
            self.assertEqual("model-b", snapshots[0].transition_model_ref)
            self.assertEqual(0.8, snapshots[0].escalation_probability)
            self.assertEqual(["model-b"], runtime.prewarmed)
            self.assertEqual("completed", coordinator.receipts()[0].status.value)
            context = coordinator.context_tokens(
                "request", ModelIntent.CODE, "model-a",
                (InferenceMessage(MessageRole.USER, "short verified repeat"),),
                1024, 32768,
            )
            self.assertEqual(2048, context)
            coordinator.stop()

            restarted_runtime = _Runtime()
            restarted = _coordinator(repository, records, restarted_runtime)
            restarted.start()
            self.assertTrue(restarted.wait_for_idle())
            self.assertEqual(["model-b"], restarted_runtime.prewarmed)
            self.assertEqual(1, len(restarted.snapshots()))
            self.assertEqual(2, len(restarted.receipts()))
            restarted.stop()
            database.close()

    def test_resource_reserve_rejects_prewarm_without_runtime_load(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database, repository = _repository(Path(temporary))
            records = _records(("model-a", "model-b", "model-a", "model-b", "model-a"))
            runtime = _Runtime()
            coordinator = ProductLiveAdaptation(
                _repositories(repository, records), _catalog(), runtime, None,
                lambda: HostCapacity(1024, 0),
            )

            coordinator.start()
            self.assertTrue(coordinator.wait_for_idle())

            self.assertEqual([], runtime.prewarmed)
            receipt = coordinator.receipts()[0]
            self.assertEqual("rejected", receipt.status.value)
            self.assertEqual(0, receipt.reserved_bytes)
            self.assertEqual((), receipt.evicted_model_refs)
            coordinator.stop()
            database.close()

    def test_background_policy_rejects_prewarm_without_runtime_load(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database, repository = _repository(Path(temporary))
            records = _records(("model-a", "model-b", "model-a", "model-b", "model-a"))
            runtime = _Runtime()
            coordinator = ProductLiveAdaptation(
                _repositories(repository, records), _catalog(), runtime, None,
                lambda: HostCapacity(
                    16 * 1024**3, 16 * 1024**3,
                    background_adaptation_allowed=False,
                    reason_codes=("foreground.protect",),
                ),
            )

            coordinator.start()
            self.assertTrue(coordinator.wait_for_idle())

            self.assertEqual([], runtime.prewarmed)
            receipt = coordinator.receipts()[0]
            self.assertEqual("rejected", receipt.status.value)
            self.assertIn("policy.background_adaptation_blocked", receipt.reason_codes)
            self.assertIn("foreground.protect", receipt.reason_codes)
            coordinator.stop()
            database.close()

    def test_images_keep_full_context_instead_of_applying_text_history(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            database, repository = _repository(Path(temporary))
            coordinator = _coordinator(
                repository, _records(("model-a", "model-a")), _Runtime(),
            )
            coordinator.start()

            context = coordinator.context_tokens(
                "image-request", ModelIntent.CODE, "model-a",
                (InferenceMessage(MessageRole.USER, "inspect", (b"image",)),),
                1024, 32768,
            )

            self.assertEqual(32768, context)
            coordinator.stop()
            database.close()


class _Outcomes:
    def __init__(self, records):
        self._records = records

    def learning_records(self):
        return self._records

    def result(self, request_id):
        del request_id
        return None


class _Runtime:
    def __init__(self):
        self.resident = set()
        self.prewarmed = []

    def loaded_models(self):
        return tuple(LoadedModel(model_ref) for model_ref in sorted(self.resident))

    def prewarm(self, model_ref, keep_alive="10m"):
        self.prewarmed.append(model_ref)
        self.resident.add(model_ref)


def _coordinator(repository, records, runtime):
    return ProductLiveAdaptation(
        _repositories(repository, records), _catalog(), runtime, None,
        lambda: HostCapacity(16 * 1024**3, 16 * 1024**3),
    )


def _repositories(repository, records):
    return SimpleNamespace(
        terminal_outcomes=_Outcomes(records),
        live_adaptation=repository.live_adaptation,
        adaptation_controls=repository.adaptation_controls,
    )


def _repository(root):
    database = ProductionDatabase(StorageSettings(root / "fam.sqlite3", os.geteuid()))
    result = SecureStorage(
        database, OwnerKeyStore(root / "master.key", os.geteuid()),
    ).open()
    owner = str(os.geteuid())
    return database, SimpleNamespace(
        live_adaptation=SqliteLiveAdaptationRepository(database, result.cipher, owner),
        adaptation_controls=SqliteAdaptationControlRepository(
            database, result.cipher, owner,
        ),
    )


def _catalog():
    return RuntimeModelCatalog((
        RuntimeModelEntry(
            "model-a", "specialist", (ModelIntent.CODE,), 2 * 1024**3,
            32768, "a" * 64,
        ),
        RuntimeModelEntry(
            "model-b", "escalation", (ModelIntent.CODE,), 4 * 1024**3,
            32768, "b" * 64,
        ),
    ))


def _records(models):
    started = datetime(2026, 1, 1, tzinfo=timezone.utc)
    return tuple(
        VerifiedLearningOutcome(
            f"learning-{index}", "intent:code", "code", model,
            "escalation" if model == "model-b" else "specialist",
            started + timedelta(minutes=index), 2048, index < 4,
            f"acceptance-{index}", f"candidate-{index}",
            hashlib.sha256(f"evidence-{index}".encode()).hexdigest(),
        )
        for index, model in enumerate(models)
    )


if __name__ == "__main__":
    unittest.main()
