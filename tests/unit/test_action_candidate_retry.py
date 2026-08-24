import unittest
from types import SimpleNamespace

from fam_os.core.lifecycle import InMemoryGlobalAttemptBudgetLedger
from fam_os.core.production.action_candidate_retry import ActionCandidateRetry
from fam_os.core.production.contracts import (
    InferenceExecutionRecord,
    InferenceExecutionState,
    ModelIntent,
    RuntimeModelSelection,
)
from fam_os.core.production.model_selection import HostCapacity


class _Executions:
    def __init__(self, record):
        self.record = record

    def replace(self, expected_revision, updated):
        if self.record.revision != expected_revision:
            return False
        self.record = updated
        return True


class _Selector:
    def __init__(self, strong):
        self.strong = strong
        self.calls = []

    def select(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        return self.strong


class ActionCandidateRetryTests(unittest.TestCase):
    def test_escalation_selects_a_different_strong_model_and_is_budgeted(self):
        weak = _selection("weak-7b", "economical")
        strong = _selection("gemma4:26b", "escalation")
        record = InferenceExecutionRecord(
            "instance-1", "request-1", ModelIntent.APPLICATION_MUTATION,
            weak, InferenceExecutionState.CANDIDATE_READY, 3, "candidate-1",
        )
        executions = _Executions(record)
        repositories = SimpleNamespace(
            inference_executions=executions,
            verifications=SimpleNamespace(
                declaration_for_request=lambda request_id: None,
            ),
        )
        selector = _Selector(strong)
        ledgers = {}

        def budget_factory(budget):
            return ledgers.setdefault(
                budget.plan_instance_id, InMemoryGlobalAttemptBudgetLedger(budget),
            )

        retry = ActionCandidateRetry(
            repositories, selector, lambda: HostCapacity(64 * 1024**3),
            lambda: ("weak-7b",), budget_factory,
        )
        prepared = retry.prepare(
            record, "[workspace-parameter-escalation] exact error",
            escalation=True,
        )

        self.assertIsNotNone(prepared)
        assert prepared is not None
        self.assertEqual("gemma4:26b", prepared.record.selection.model_ref)
        self.assertEqual(2048, prepared.maximum_output_tokens)
        self.assertEqual(("weak-7b",), selector.calls[0][1]["excluded_model_refs"])
        self.assertTrue(selector.calls[0][1]["escalation"])
        snapshot = next(iter(ledgers.values())).snapshot()
        self.assertEqual(1, snapshot.escalations)
        self.assertEqual(2048, snapshot.consumed_tokens)


def _selection(model_ref, tier):
    return RuntimeModelSelection(
        f"selection-{model_ref}", "request-1", ModelIntent.APPLICATION_MUTATION,
        model_ref, tier, 1024**3, 64 * 1024**3, 16 * 1024**3,
        ("capability.intent_match",),
    )


if __name__ == "__main__":
    unittest.main()
