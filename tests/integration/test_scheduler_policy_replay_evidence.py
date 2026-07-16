import hashlib
import unittest
from pathlib import Path

from fam_os.scheduler import CachePolicyRequest, CacheTier, SchedulerPolicyKind
from fam_os.schemas import dumps_document, loads_document
from tools.policy_replay.engine import execute_policy


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / "artifacts/scheduler/phase7.9/canonical-policy-replay"


class SchedulerPolicyReplayEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.report = loads_document(
            (EVIDENCE / "policy-replay-report.json").read_text(encoding="utf-8")
        )

    def test_all_fifteen_cases_match_without_current_host_state(self):
        self.assertEqual(len(self.report.records), 15)
        self.assertTrue(self.report.all_matched)
        self.assertTrue(all(item.matched for item in self.report.records))
        self.assertFalse(any(item.current_host_state_consulted for item in self.report.records))

    def test_admission_gpu_and_cache_policies_are_all_replayed(self):
        self.assertEqual(
            {item.policy_kind for item in self.report.records}, set(SchedulerPolicyKind)
        )

    def test_every_actual_policy_still_reproduces_recorded_output(self):
        for record in self.report.records:
            with self.subTest(case_id=record.case_id):
                case = EVIDENCE / record.case_id
                request = loads_document((case / "input.json").read_text(encoding="utf-8"))
                expected = loads_document((case / "recorded-output.json").read_text(encoding="utf-8"))
                replayed, _, _ = execute_policy(expected, request)
                self.assertEqual(dumps_document(replayed), dumps_document(expected))

    def test_record_digests_bind_exact_case_documents(self):
        for record in self.report.records:
            case = EVIDENCE / record.case_id
            self.assertEqual(record.input_digest_sha256, _digest(case / "input.json"))
            self.assertEqual(
                record.recorded_output_digest_sha256,
                _digest(case / "recorded-output.json"),
            )

    def test_cache_snapshot_keeps_resource_tiers_separate(self):
        request = loads_document(
            (EVIDENCE / "cache-host-page-retention/input.json").read_text(encoding="utf-8")
        )
        self.assertIsInstance(request, CachePolicyRequest)
        self.assertEqual({item.tier for item in request.snapshot.entries}, set(CacheTier))
        page = next(
            item for item in request.snapshot.entries
            if item.tier is CacheTier.HOST_PAGE_CACHE
        )
        self.assertGreater(page.observed_bytes, 0)
        self.assertEqual(
            tuple(item.tier for item in request.pressures),
            (CacheTier.HOST_PAGE_CACHE,),
        )


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_text(encoding="utf-8").strip().encode("utf-8")).hexdigest()


if __name__ == "__main__":
    unittest.main()
