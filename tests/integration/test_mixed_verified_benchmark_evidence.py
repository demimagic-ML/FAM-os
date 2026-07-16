import hashlib
import json
import unittest
from pathlib import Path

from fam_os.experts import BenchmarkTaskFamily, MixedBenchmarkReport, MixedBenchmarkSuite, validate_mixed_report
from fam_os.schemas import loads_document


ROOT = Path(__file__).resolve().parents[2]
REPORT = ROOT / "artifacts/expert_fabric/phase9.1/mixed-verified-report.json"
SUITE = ROOT / "configs/benchmarks/mixed-verified-v1.json"


class MixedVerifiedBenchmarkEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.suite = loads_document(SUITE.read_text())
        self.report = loads_document(REPORT.read_text())

    def test_suite_and_report_are_strict_complete_and_passing(self):
        self.assertIsInstance(self.suite, MixedBenchmarkSuite)
        self.assertIsInstance(self.report, MixedBenchmarkReport)
        validate_mixed_report(self.suite, self.report)
        self.assertTrue(self.report.passed)
        self.assertEqual(set(BenchmarkTaskFamily), {case.family for case in self.suite.cases})
        self.assertTrue(next(case for case in self.suite.cases if case.family is BenchmarkTaskFamily.CODE).named_regression)

    def test_laguna_and_gemma_runs_are_independent_digest_bound_and_verified(self):
        expected = {
            "laguna-xs.2:q4_K_M": ROOT / "artifacts/expert_fabric/phase9.1/laguna/workstation-smoke-20260716-191025-334207.json",
            "gemma4:26b": ROOT / "artifacts/expert_fabric/phase9.1/gemma/workstation-smoke-20260716-191142-063424.json",
        }
        for run in self.report.strong_regressions:
            raw = expected[run.model_ref]
            self.assertEqual(run.report_sha256, hashlib.sha256(raw.read_bytes()).hexdigest())
            document = json.loads(raw.read_text())
            self.assertTrue(run.verified)
            self.assertTrue(document["result"]["verified"])
            self.assertEqual(run.package_artifact_sha256, document["package_evidence"]["artifact_digest"])

    def test_kernel_case_used_no_expert_and_every_acceptance_matches(self):
        cases = {case.case_id: case for case in self.suite.cases}
        kernel = next(result for result in self.report.results if cases[result.case_id].family is BenchmarkTaskFamily.KERNEL_ONLY)
        self.assertIsNone(kernel.expert_id)
        for result in self.report.results:
            self.assertTrue(result.passed)
            self.assertEqual(cases[result.case_id].acceptance_id, result.acceptance_id)


if __name__ == "__main__":
    unittest.main()
