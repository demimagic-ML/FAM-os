import unittest
from concurrent.futures import ThreadPoolExecutor

from fam_os.core.lifecycle import (
    AttemptBudgetReservation, AttemptKind, GlobalAttemptBudget,
    InMemoryGlobalAttemptBudgetLedger,
)


class GlobalAttemptBudgetTests(unittest.TestCase):
    def setUp(self):
        self.ledger = InMemoryGlobalAttemptBudgetLedger(
            GlobalAttemptBudget("plan-1", 1000, 5000, 2, 1)
        )

    def reserve(self, number, kind=AttemptKind.REPAIR, tokens=300, millis=1000):
        return self.ledger.reserve(AttemptBudgetReservation(
            f"reservation-{number}", "plan-1", f"attempt-{number}", kind, tokens, millis,
        ))

    def test_repairs_and_escalation_share_time_and_token_ceiling(self):
        self.assertIsNotNone(self.reserve(1))
        self.assertIsNotNone(self.reserve(2, AttemptKind.ESCALATION, 500, 2000))
        self.assertIsNone(self.reserve(3, tokens=300, millis=1000))
        snapshot = self.ledger.snapshot()
        self.assertEqual(800, snapshot.consumed_tokens)
        self.assertEqual(3000, snapshot.consumed_wall_milliseconds)

    def test_attempt_identity_cannot_reset_budget_by_changing_reservation(self):
        self.assertIsNotNone(self.reserve(1))
        replay = AttemptBudgetReservation(
            "reservation-other", "plan-1", "attempt-1", AttemptKind.ESCALATION, 1, 1,
        )
        self.assertIsNone(self.ledger.reserve(replay))

    def test_concurrent_reservations_cannot_oversubscribe(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = tuple(pool.map(lambda number: self.reserve(number, tokens=600), range(8)))
        self.assertEqual(1, sum(result is not None for result in results))
        self.assertEqual(600, self.ledger.snapshot().consumed_tokens)


if __name__ == "__main__":
    unittest.main()
