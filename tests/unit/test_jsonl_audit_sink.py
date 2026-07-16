import json
import os
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from fam_os.adapters.audit import JsonlHashChainAuditSink
from fam_os.supervisor import (
    AuditEmissionError,
    AuditIntegrityError,
    GENESIS_AUDIT_DIGEST,
    SupervisorAuditIntent,
    SupervisorAuditOperation,
    SupervisorAuditOutcome,
)


NOW = datetime(2026, 7, 16, 12, 30, tzinfo=timezone.utc)


def intent(index: int) -> SupervisorAuditIntent:
    return SupervisorAuditIntent(
        f"event-{index}", f"operation-{index}", NOW,
        f"request-{index}", "authority-1",
        "principal-1", "session-1", "fam-audit-test",
        SupervisorAuditOperation.SERVICE_START,
        SupervisorAuditOutcome.SUCCEEDED,
    )


class JsonlHashChainAuditSinkTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.path = Path(self.temporary.name) / "supervisor-audit.jsonl"
        self.sink = JsonlHashChainAuditSink(self.path)

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_appends_durable_private_hash_chain(self) -> None:
        first = self.sink.append(intent(1))
        second = self.sink.append(intent(2))
        verification = self.sink.verify()
        self.assertEqual(1, first.sequence)
        self.assertEqual(GENESIS_AUDIT_DIGEST, first.previous_digest)
        self.assertEqual(first.digest, second.previous_digest)
        self.assertTrue(verification.passed)
        self.assertEqual(2, verification.record_count)
        self.assertEqual(second.digest, verification.head_digest)
        self.assertEqual(0o600, self.path.stat().st_mode & 0o777)
        self.assertEqual(2, len(self.path.read_bytes().splitlines()))

    def test_tamper_is_reported_and_blocks_next_append(self) -> None:
        self.sink.append(intent(1))
        document = json.loads(self.path.read_text())
        document["event"]["outcome"] = "failed"
        self.path.write_text(
            json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n"
        )
        verification = self.sink.verify()
        self.assertFalse(verification.passed)
        self.assertEqual(1, verification.failure_sequence)
        self.assertEqual("digest_mismatch", verification.reason_code)
        with self.assertRaises(AuditIntegrityError):
            self.sink.append(intent(2))
        self.assertEqual(1, len(self.path.read_bytes().splitlines()))

    def test_tamper_reports_the_last_verified_prefix(self) -> None:
        first = self.sink.append(intent(1))
        self.sink.append(intent(2))
        lines = self.path.read_text().splitlines()
        document = json.loads(lines[1])
        document["event"]["outcome"] = "failed"
        lines[1] = json.dumps(document, sort_keys=True, separators=(",", ":"))
        self.path.write_text("\n".join(lines) + "\n")

        verification = self.sink.verify()

        self.assertFalse(verification.passed)
        self.assertEqual(1, verification.record_count)
        self.assertEqual(first.digest, verification.head_digest)
        self.assertEqual(2, verification.failure_sequence)

    def test_duplicate_event_id_is_rejected(self) -> None:
        self.sink.append(intent(1))

        with self.assertRaises(AuditIntegrityError):
            self.sink.append(intent(1))

        verification = self.sink.verify()
        self.assertTrue(verification.passed)
        self.assertEqual(1, verification.record_count)

    def test_truncated_record_is_detected(self) -> None:
        self.sink.append(intent(1))
        encoded = self.path.read_bytes()
        self.path.write_bytes(encoded[:-1])
        verification = self.sink.verify()
        self.assertFalse(verification.passed)
        self.assertEqual("unterminated_record", verification.reason_code)

    def test_symlink_and_broad_permissions_are_rejected(self) -> None:
        target = Path(self.temporary.name) / "target"
        target.write_text("")
        self.path.symlink_to(target)
        with self.assertRaises(AuditEmissionError):
            self.sink.append(intent(1))
        self.path.unlink()
        self.sink.append(intent(1))
        os.chmod(self.path, 0o640)
        with self.assertRaises(AuditEmissionError):
            self.sink.verify()

    def test_insecure_or_symlinked_parent_is_rejected(self) -> None:
        os.chmod(self.temporary.name, 0o777)
        try:
            with self.assertRaisesRegex(AuditEmissionError, "parent"):
                self.sink.append(intent(1))
        finally:
            os.chmod(self.temporary.name, 0o700)

        real = Path(self.temporary.name) / "real"
        real.mkdir(mode=0o700)
        linked = Path(self.temporary.name) / "linked"
        linked.symlink_to(real, target_is_directory=True)
        sink = JsonlHashChainAuditSink(linked / "audit.jsonl")
        with self.assertRaisesRegex(AuditEmissionError, "parent"):
            sink.append(intent(1))

    def test_concurrent_appends_remain_one_valid_chain(self) -> None:
        with ThreadPoolExecutor(max_workers=8) as pool:
            records = tuple(pool.map(lambda index: self.sink.append(intent(index)), range(20)))
        verification = self.sink.verify()
        self.assertTrue(verification.passed)
        self.assertEqual(20, verification.record_count)
        self.assertEqual(set(range(1, 21)), {record.sequence for record in records})


if __name__ == "__main__":
    unittest.main()
