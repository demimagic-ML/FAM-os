import hashlib
import unittest
from dataclasses import replace
from datetime import UTC, datetime, timedelta

from fam_os.memory import (
    MemoryContentDigest, MemoryProvenance, MemoryRecordKind, MemoryRecordManifest,
    MemoryScope, MemorySensitivity, MemorySourceKind,
)
from fam_os.memory.access import MemoryAccessContext
from fam_os.memory.ephemeral_store import BoundedEphemeralMemoryStore
from fam_os.memory.lifecycle_contracts import MemoryDeletionReason, MemoryDeletionRequest

NOW = datetime(2026, 7, 16, tzinfo=UTC)
CONTENT = b"bounded memory"


def manifest(record_id="record-1", kind=MemoryRecordKind.SESSION):
    return MemoryRecordManifest(
        record_id, kind, NOW, "memory.text/v1", "text/plain", len(CONTENT),
        MemoryContentDigest("sha256", hashlib.sha256(CONTENT).hexdigest()),
        MemoryScope("owner", ("assist",), ("app",), ("workspace",), "session"),
        MemoryProvenance(MemorySourceKind.USER, "user", "user", NOW),
        MemorySensitivity.PRIVATE, "session-only", NOW + timedelta(hours=1),
    )


def context(**values):
    fields = dict(owner_id="owner", purpose_id="assist", application_id="app",
                  workspace_id="workspace", session_id="session")
    fields.update(values)
    return MemoryAccessContext(**fields)


class EphemeralMemoryStoreTests(unittest.TestCase):
    def test_put_get_and_inspect_enforce_exact_scope(self):
        store = BoundedEphemeralMemoryStore(2, 100)
        store.put(manifest(), CONTENT)
        self.assertEqual(CONTENT, store.get("record-1", context(), NOW).content)
        self.assertIsNone(store.get("record-1", context(owner_id="other"), NOW))
        self.assertEqual((), store.inspect(context(session_id="other"), NOW))

    def test_digest_and_capacity_fail_closed(self):
        store = BoundedEphemeralMemoryStore(1, len(CONTENT))
        with self.assertRaisesRegex(ValueError, "digest"):
            store.put(replace(manifest(), content_digest=MemoryContentDigest("sha256", "a" * 64)), CONTENT)
        store.put(manifest(), CONTENT)
        with self.assertRaises(MemoryError):
            store.put(manifest("record-2", MemoryRecordKind.WORKING), CONTENT)

    def test_expiry_hides_then_purges_record(self):
        store = BoundedEphemeralMemoryStore(2, 100)
        store.put(manifest(), CONTENT)
        later = NOW + timedelta(hours=2)
        self.assertIsNone(store.get("record-1", context(), later))
        self.assertEqual(("record-1",), store.purge_expired(later))

    def test_delete_removes_payload_before_receipt(self):
        store = BoundedEphemeralMemoryStore(2, 100)
        store.put(manifest(), CONTENT)
        request = MemoryDeletionRequest(
            "delete", "record-1", "owner", "user", NOW, MemoryDeletionReason.USER_REQUEST,
        )
        receipt = store.delete(request, NOW)
        self.assertTrue(receipt.payload_removed)
        self.assertIsNone(store.get("record-1", context(), NOW))


if __name__ == "__main__":
    unittest.main()
