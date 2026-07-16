import json
import unittest
from dataclasses import FrozenInstanceError
from datetime import datetime, timezone

from fam_os.supervisor import (
    GENESIS_AUDIT_DIGEST,
    SupervisorAuditEmitter,
    SupervisorAuditIntent,
    SupervisorAuditOperation,
    SupervisorAuditOutcome,
    SupervisorCallContext,
)
from fam_os.supervisor.audit_codec import (
    audit_record_digest_matches,
    create_audit_record,
    decode_audit_record,
    encode_audit_record,
)


NOW = datetime(2026, 7, 16, 12, 30, tzinfo=timezone.utc)


def intent(event_id: str = "event-1") -> SupervisorAuditIntent:
    return SupervisorAuditIntent(
        event_id,
        "operation-1",
        NOW,
        "request-1",
        "authority-1",
        "principal-1",
        "session-1",
        "fam-audit-test",
        SupervisorAuditOperation.SERVICE_START,
        SupervisorAuditOutcome.REQUESTED,
        reason_code="admission.requested",
    )


class RecordingSink:
    def __init__(self, error: Exception | None = None) -> None:
        self.intents = []
        self.error = error

    def append(self, value):
        if self.error is not None:
            raise self.error
        self.intents.append(value)
        return create_audit_record(value, len(self.intents), GENESIS_AUDIT_DIGEST)


class SupervisorAuditTests(unittest.TestCase):
    def test_record_is_immutable_canonical_and_digest_bound(self) -> None:
        record = create_audit_record(intent(), 1, GENESIS_AUDIT_DIGEST)
        encoded = encode_audit_record(record)
        self.assertEqual(record, decode_audit_record(encoded))
        self.assertTrue(audit_record_digest_matches(record))
        self.assertNotIn(b" ", encoded)
        with self.assertRaises(FrozenInstanceError):
            record.sequence = 2

    def test_decoder_rejects_noncanonical_or_modified_document(self) -> None:
        record = create_audit_record(intent(), 1, GENESIS_AUDIT_DIGEST)
        document = json.loads(encode_audit_record(record))
        noncanonical = json.dumps(document).encode()
        with self.assertRaisesRegex(ValueError, "canonical"):
            decode_audit_record(noncanonical)
        document["extra"] = True
        encoded = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
        with self.assertRaisesRegex(ValueError, "exact"):
            decode_audit_record(encoded)

    def test_intent_excludes_free_form_or_raw_path_fields(self) -> None:
        with self.assertRaisesRegex(ValueError, "reason"):
            SupervisorAuditIntent(
                "event-1", "operation-1", NOW, "request-1", "authority-1", "principal-1",
                "session-1", "fam-audit-test",
                SupervisorAuditOperation.SERVICE_START,
                SupervisorAuditOutcome.FAILED,
                reason_code="raw exception text is forbidden",
            )
        with self.assertRaisesRegex(ValueError, "resource"):
            SupervisorAuditIntent(
                "event-1", "operation-1", NOW, "request-1", "authority-1", "principal-1",
                "session-1", "fam-audit-test",
                SupervisorAuditOperation.GRANT_FILESYSTEM_ACCESS,
                SupervisorAuditOutcome.REQUESTED,
                resource_id="/home/private",
            )

    def test_emitter_uses_context_clock_and_event_factory(self) -> None:
        sink = RecordingSink()
        emitter = SupervisorAuditEmitter(
            sink, clock=lambda: NOW, event_id_factory=lambda: "event-fixed"
        )
        context = SupervisorCallContext(
            "request-1", "principal-1", "session-1", "authority-1"
        )
        record = emitter.emit(
            context, "fam-audit-test", SupervisorAuditOperation.SERVICE_STOP,
            SupervisorAuditOutcome.SUCCEEDED, "operation-fixed",
            evidence_ref="service.inactive",
        )
        self.assertEqual("event-fixed", record.intent.event_id)
        self.assertEqual(context.request_id, record.intent.request_id)
        self.assertEqual("service.inactive", record.intent.evidence_ref)

    def test_required_sink_failure_propagates(self) -> None:
        emitter = SupervisorAuditEmitter(
            RecordingSink(RuntimeError("sink failed")),
            event_id_factory=lambda: "event-fixed",
        )
        context = SupervisorCallContext(
            "request-1", "principal-1", "session-1", "authority-1"
        )
        with self.assertRaisesRegex(RuntimeError, "sink failed"):
            emitter.emit(
                context, "fam-audit-test",
                SupervisorAuditOperation.SERVICE_START,
                SupervisorAuditOutcome.REQUESTED, "operation-fixed",
            )


if __name__ == "__main__":
    unittest.main()
