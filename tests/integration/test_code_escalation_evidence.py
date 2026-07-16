import hashlib
import unittest
from pathlib import Path

from fam_os.experts import EscalationTraceReport
from fam_os.schemas import loads_document


ROOT = Path(__file__).resolve().parents[2]
CASES = (
    ("laguna", "verified-parity-20260716-191942-680737.json", "laguna-xs.2:q4_K_M"),
    ("gemma", "verified-parity-20260716-192041-127117.json", "gemma4:26b"),
)


class CodeEscalationEvidenceTests(unittest.TestCase):
    def test_small_failure_escalates_to_each_exact_packaged_model_and_passes(self):
        tests_digest = hashlib.sha256((ROOT / "tests/fixtures/verification/stable_topological_sort_tests.py").read_bytes()).hexdigest()
        for directory, raw_name, model_ref in CASES:
            with self.subTest(model=model_ref):
                base = ROOT / f"artifacts/expert_fabric/phase9.3/{directory}"
                trace = loads_document((base / "escalation-trace.json").read_text())
                self.assertIsInstance(trace, EscalationTraceReport)
                self.assertEqual("qwen2.5-coder:7b", trace.economical_model_ref)
                self.assertEqual(model_ref, trace.escalation_model_ref)
                self.assertEqual("failed", trace.verification_statuses[0])
                self.assertEqual("passed", trace.verification_statuses[-1])
                self.assertTrue(trace.verified)
                self.assertEqual(tests_digest, trace.trusted_tests_sha256)
                raw = base / raw_name
                self.assertEqual(hashlib.sha256(raw.read_bytes()).hexdigest(), trace.raw_report_sha256)

    def test_feedback_and_global_reservations_are_bounded_without_requirement_change(self):
        for directory, _, _ in CASES:
            trace = loads_document((ROOT / f"artifacts/expert_fabric/phase9.3/{directory}/escalation-trace.json").read_text())
            self.assertEqual("stable-toposort-v2", trace.acceptance_id)
            self.assertLessEqual(trace.maximum_failure_feedback_characters, 4000)
            self.assertEqual(1, trace.global_budget.escalations)
            self.assertLessEqual(trace.global_budget.repairs, 1)
            self.assertLessEqual(trace.global_budget.consumed_tokens, 3200)
            self.assertEqual(len(trace.attempt_kinds) - 1, len(trace.global_budget.reservation_ids))


if __name__ == "__main__":
    unittest.main()
