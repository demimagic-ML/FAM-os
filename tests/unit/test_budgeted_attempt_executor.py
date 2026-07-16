import unittest

from fam_os.core.execution import AttemptKind, BudgetedAttemptExecutor, GenerationSettings
from fam_os.core.execution.errors import ExecutionConfigurationError
from fam_os.core.lifecycle import GlobalAttemptBudget, InMemoryGlobalAttemptBudgetLedger


class Delegate:
    def __init__(self):
        self.calls = []

    def execute(self, *args):
        self.calls.append(args)
        return "attempt"


class BudgetedAttemptExecutorTests(unittest.TestCase):
    def test_initial_is_free_but_repair_and_escalation_share_global_resources(self):
        delegate = Delegate()
        ledger = InMemoryGlobalAttemptBudgetLedger(GlobalAttemptBudget("plan", 200, 2000, 1, 1))
        executor = BudgetedAttemptExecutor(delegate, ledger, 1000)
        settings = GenerationSettings(100)
        common = (None, None, (), settings)
        self.assertEqual("attempt", executor.execute("initial", AttemptKind.ECONOMICAL, *common))
        self.assertEqual("attempt", executor.execute("repair", AttemptKind.REPAIR, *common))
        self.assertEqual("attempt", executor.execute("escalate", AttemptKind.ESCALATION, *common))
        snapshot = ledger.snapshot()
        self.assertEqual(200, snapshot.consumed_tokens)
        self.assertEqual(2000, snapshot.consumed_wall_milliseconds)

    def test_denied_reservation_never_calls_delegate(self):
        delegate = Delegate()
        ledger = InMemoryGlobalAttemptBudgetLedger(GlobalAttemptBudget("plan", 50, 1000, 1, 0))
        executor = BudgetedAttemptExecutor(delegate, ledger, 1000)
        with self.assertRaises(ExecutionConfigurationError):
            executor.execute("repair", AttemptKind.REPAIR, None, None, (), GenerationSettings(100))
        self.assertEqual([], delegate.calls)


if __name__ == "__main__":
    unittest.main()
