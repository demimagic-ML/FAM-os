import tempfile
import unittest
import hashlib
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from fam_os.adapters.sqlite import SQLiteEngineeringIncidentStore
from fam_os.core.engineering import (
    EngineeringIncidentEvidenceReceipt, EngineeringIncidentReceiptKind,
    EngineeringIncidentService, EngineeringIncidentStage,
    build_engineering_incident_receipt,
)
from fam_os.product.storage.cipher import ProductPayloadCipher
from fam_os.product.storage.keys import OwnerMasterKey
from fam_os.product.storage.owner_contract_codec import OwnerBoundContractCodec
from fam_os.core.engineering import EngineeringIncidentState


NOW = datetime(2026, 7, 19, 23, 0, tzinfo=timezone.utc)


class EngineeringIncidentServiceTests(unittest.TestCase):
    def test_complete_incident_lifecycle_is_ordered_restart_safe_and_evidenced(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "incidents.sqlite3"
            store = SQLiteEngineeringIncidentStore(path)
            service = EngineeringIncidentService(store)
            state = service.detect(
                "incident-1", "task-1", ("symptom-1",), instant=NOW,
            )
            state = _advance(
                service, state, "preservation-1",
                EngineeringIncidentReceiptKind.PRESERVATION,
                state.symptom_evidence_ids,
            )
            state = _advance(
                service, state, "diagnosis-1",
                EngineeringIncidentReceiptKind.DIAGNOSIS,
                state.preservation_receipt_ids,
            )
            store.close()

            restarted_store = SQLiteEngineeringIncidentStore(path)
            restarted = EngineeringIncidentService(restarted_store)
            state = restarted.inspect("incident-1")
            for receipt_id, kind, sources in (
                ("changeset-1", EngineeringIncidentReceiptKind.REMEDIATION_PROPOSAL, state.diagnosis_receipt_ids),
                ("apply-1", EngineeringIncidentReceiptKind.REMEDIATION, ("changeset-1",)),
                ("monitor-1", EngineeringIncidentReceiptKind.RECOVERY_OBSERVATION, ("apply-1",)),
                ("monitor-2", EngineeringIncidentReceiptKind.RECOVERY_OBSERVATION, ("monitor-1",)),
                ("report-1", EngineeringIncidentReceiptKind.REPORT, ("monitor-2",)),
                ("closure-1", EngineeringIncidentReceiptKind.CLOSURE, ("report-1",)),
            ):
                state = _advance(restarted, state, receipt_id, kind, sources)
            self.assertEqual(EngineeringIncidentStage.CLOSED, state.stage)
            self.assertEqual(("monitor-1", "monitor-2"), state.recovery_observation_ids)
            self.assertEqual(("report-1",), state.post_incident_report_ids)
            receipts = restarted.receipts("incident-1")
            self.assertEqual(8, len(receipts))
            self.assertEqual([
                EngineeringIncidentReceiptKind.PRESERVATION,
                EngineeringIncidentReceiptKind.DIAGNOSIS,
                EngineeringIncidentReceiptKind.REMEDIATION_PROPOSAL,
                EngineeringIncidentReceiptKind.REMEDIATION,
                EngineeringIncidentReceiptKind.RECOVERY_OBSERVATION,
                EngineeringIncidentReceiptKind.RECOVERY_OBSERVATION,
                EngineeringIncidentReceiptKind.REPORT,
                EngineeringIncidentReceiptKind.CLOSURE,
            ], [item.kind for item in receipts])
            restarted_store.close()

    def test_diagnosis_cannot_precede_evidence_preservation(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = SQLiteEngineeringIncidentStore(Path(temporary) / "incident.sqlite3")
            service = EngineeringIncidentService(store)
            service.detect("incident-1", "task-1", ("symptom-1",), instant=NOW)
            with self.assertRaises(ValueError):
                service.advance(
                    "incident-1", EngineeringIncidentStage.DIAGNOSED,
                    "diagnosis-1", instant=NOW,
                )
            store.close()

    def test_wrong_stage_receipt_is_not_persisted_before_transition_denial(self):
        with tempfile.TemporaryDirectory() as temporary:
            store = SQLiteEngineeringIncidentStore(
                Path(temporary) / "incident.sqlite3",
            )
            service = EngineeringIncidentService(store)
            state = service.detect(
                "incident-1", "task-1", ("symptom-1",), instant=NOW,
            )
            first = build_engineering_incident_receipt(
                "preservation-1", state.incident_id, state.task_id,
                EngineeringIncidentReceiptKind.PRESERVATION,
                state.symptom_evidence_ids, "preserved", NOW,
            )
            service.advance_with_receipt(first, instant=NOW)
            duplicate_stage = build_engineering_incident_receipt(
                "preservation-2", state.incident_id, state.task_id,
                EngineeringIncidentReceiptKind.PRESERVATION,
                state.symptom_evidence_ids, "second-preservation", NOW,
            )
            with self.assertRaisesRegex(ValueError, "transition is forbidden"):
                service.advance_with_receipt(duplicate_stage, instant=NOW)
            with self.assertRaises(KeyError):
                service.receipt("preservation-2")
            store.close()

    def test_product_codec_migrates_plaintext_and_indexes_task_lookup(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "incident.sqlite3"
            plain = SQLiteEngineeringIncidentStore(path)
            plain_service = EngineeringIncidentService(plain)
            plain_service.detect(
                "incident-1", "task-1", ("symptom-sensitive-1",), instant=NOW,
            )
            _advance(
                plain_service, plain_service.inspect("incident-1"),
                "preservation-sensitive-1",
                EngineeringIncidentReceiptKind.PRESERVATION,
                ("symptom-sensitive-1",),
            )
            plain.close()

            encrypted = SQLiteEngineeringIncidentStore(path, _owner_codec())
            self.assertEqual(
                "incident-1", encrypted.for_task("task-1")[0].incident_id,
            )
            self.assertEqual((), encrypted.for_task("task-2"))
            encrypted.close()
            connection = sqlite3.connect(path)
            document = connection.execute(
                "SELECT document FROM engineering_incidents WHERE incident_id=?",
                ("incident-1",),
            ).fetchone()[0]
            connection.close()
            self.assertNotIn("symptom-sensitive-1", document)
            self.assertTrue(document.startswith("fam.storage.aes256gcm/v1:"))
            connection = sqlite3.connect(path)
            receipt_document = connection.execute(
                "SELECT document FROM engineering_incident_receipts"
            ).fetchone()[0]
            connection.close()
            self.assertNotIn("symptom-sensitive-1", receipt_document)
            self.assertTrue(receipt_document.startswith("fam.storage.aes256gcm/v1:"))


def _owner_codec():
    key = bytes(range(32))
    key_id = "owner-key-" + hashlib.sha256(key).hexdigest()[:24]
    return OwnerBoundContractCodec(
        ProductPayloadCipher(OwnerMasterKey(key_id, key)), "owner-1",
        "engineering-incident",
        (EngineeringIncidentState, EngineeringIncidentEvidenceReceipt),
    )


def _advance(service, state, receipt_id, kind, sources):
    receipt = build_engineering_incident_receipt(
        receipt_id, state.incident_id, state.task_id, kind, sources,
        f"conclusion-{kind.value}", NOW,
    )
    return service.advance_with_receipt(receipt, instant=NOW)


if __name__ == "__main__":
    unittest.main()
