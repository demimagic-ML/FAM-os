import unittest
from datetime import UTC, datetime, timedelta

from fam_os.memory.lifecycle_contracts import (
    MemoryDeletionReason, MemoryDeletionReceipt, MemoryDeletionRequest,
    MemoryExpiryEvaluation, MemoryExpiryState,
)

NOW = datetime(2026, 7, 16, tzinfo=UTC)


class MemoryLifecycleContractTests(unittest.TestCase):
    def test_expiry_state_derives_from_time(self):
        active = MemoryExpiryEvaluation("record", NOW + timedelta(hours=1), NOW, MemoryExpiryState.ACTIVE)
        expired = MemoryExpiryEvaluation("record", NOW, NOW, MemoryExpiryState.EXPIRED)
        self.assertEqual(MemoryExpiryState.ACTIVE, active.state)
        self.assertEqual(MemoryExpiryState.EXPIRED, expired.state)

    def test_inconsistent_expiry_state_is_rejected(self):
        with self.assertRaisesRegex(ValueError, "derive"):
            MemoryExpiryEvaluation("record", NOW + timedelta(hours=1), NOW, MemoryExpiryState.EXPIRED)

    def test_deletion_request_is_owner_and_actor_bound(self):
        request = MemoryDeletionRequest(
            "delete-1", "record-1", "owner-1", "user-1", NOW,
            MemoryDeletionReason.USER_REQUEST,
        )
        self.assertEqual("owner-1", request.owner_id)

    def test_receipt_requires_confirmed_removal_and_digests(self):
        receipt = MemoryDeletionReceipt("delete-1", "record-1", NOW, "a" * 64, "b" * 64, True)
        self.assertTrue(receipt.payload_removed)
        with self.assertRaisesRegex(ValueError, "confirmed"):
            MemoryDeletionReceipt("delete-1", "record-1", NOW, "a" * 64, "b" * 64, False)


if __name__ == "__main__":
    unittest.main()
