import tempfile
import unittest
from dataclasses import fields
from datetime import datetime, timezone
from pathlib import Path

from fam_os.adapters.audit.application_jsonl import ApplicationJsonlAuditSink
from fam_os.applications import (
    ActionAuditStage, ActionStatus, ApplicationActionAuditIntent,
    ApplicationAuditIntegrityError,
)
from fam_os.applications.action_audit_codec import (
    action_audit_record_digest_matches, decode_action_audit_record,
    encode_action_audit_record,
)


NOW = datetime(2026, 7, 16, tzinfo=timezone.utc)


def intent(event_id, stage=ActionAuditStage.REQUESTED):
    terminal = stage is not ActionAuditStage.REQUESTED
    return ApplicationActionAuditIntent(
        event_id, "operation-1", NOW, "request-1", "plan-1", "principal-1",
        "session-1", "app.editor", "instance-1", "app.edit", "grant-1",
        "proposal-1", "confirmation-1", stage, "1" * 64,
        ("document.hash",), ActionStatus.VERIFIED if terminal else None,
        "app.edit.undo", terminal, None,
    )


class ApplicationActionAuditTests(unittest.TestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "actions.jsonl"

    def tearDown(self):
        self.directory.cleanup()

    def test_private_chain_is_durable_canonical_and_verifiable(self):
        sink = ApplicationJsonlAuditSink(self.path)
        first = sink.append(intent("event-1"))
        second = sink.append(intent("event-2", ActionAuditStage.VERIFIED))
        self.assertTrue(action_audit_record_digest_matches(first))
        self.assertEqual(first, decode_action_audit_record(encode_action_audit_record(first)))
        self.assertEqual(first.digest, second.previous_digest)
        verification = sink.verify()
        self.assertTrue(verification.passed)
        self.assertEqual(2, verification.record_count)
        self.assertEqual(0o600, self.path.stat().st_mode & 0o777)

    def test_duplicate_or_tampered_event_is_rejected(self):
        sink = ApplicationJsonlAuditSink(self.path)
        sink.append(intent("event-1"))
        with self.assertRaises(ApplicationAuditIntegrityError):
            sink.append(intent("event-1"))
        encoded = self.path.read_bytes().replace(b'"request_id":"request-1"', b'"request_id":"request-2"')
        self.path.write_bytes(encoded)
        verification = sink.verify()
        self.assertFalse(verification.passed)
        self.assertEqual("digest_mismatch", verification.reason_code)

    def test_contract_excludes_raw_intent_content_resource_and_reversal_token(self):
        names = {item.name for item in fields(ApplicationActionAuditIntent)}
        self.assertTrue({"request_id", "resource_sha256", "reversal_available"} <= names)
        self.assertTrue(names.isdisjoint({
            "prompt", "summary", "parameters", "output", "resource_uri",
            "reversal_token", "safe_message",
        }))


if __name__ == "__main__":
    unittest.main()
