import unittest
from dataclasses import replace

from fam_os.experts import (
    BenchmarkTaskFamily, MixedBenchmarkCase, MixedBenchmarkCaseResult,
    MixedBenchmarkReport, MixedBenchmarkSuite, StrongRegressionRunRef,
    validate_mixed_report,
)


def suite():
    return MixedBenchmarkSuite("suite", "1", tuple(
        MixedBenchmarkCase(f"case-{family.value}", family, f"cap.{family.value}", f"accept.{family.value}", "a" * 64)
        for family in BenchmarkTaskFamily
    ))


def report():
    item = suite()
    results = tuple(MixedBenchmarkCaseResult(case.case_id, True, case.acceptance_id, "b" * 64) for case in item.cases)
    strong = (
        StrongRegressionRunRef("laguna-xs.2:q4_K_M", "expert.laguna", "c" * 64, "d" * 64, True),
        StrongRegressionRunRef("gemma4:26b", "expert.gemma", "e" * 64, "f" * 64, False),
    )
    return item, MixedBenchmarkReport("suite", "1", results, strong, True)


class MixedBenchmarkContractTests(unittest.TestCase):
    def test_requires_all_families_and_both_independent_strong_runs(self):
        item, result = report()
        validate_mixed_report(item, result)
        with self.assertRaises(ValueError):
            validate_mixed_report(item, replace(result, strong_regressions=result.strong_regressions[:1]))

    def test_kernel_only_case_cannot_claim_model_use(self):
        item, result = report()
        first = replace(result.results[0], expert_id="expert.x", expert_tier="economical", model_ref="x")
        with self.assertRaises(ValueError):
            validate_mixed_report(item, replace(result, results=(first, *result.results[1:])))


if __name__ == "__main__":
    unittest.main()
