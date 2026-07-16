import json
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


class VerificationFabricEvidenceTests(unittest.TestCase):
    def load(self, relative):
        return json.loads((ROOT / relative).read_text())

    def test_multiple_families_have_positive_and_withheld_negative_evidence(self):
        language = self.load("artifacts/verification/phase8.4/language-verifier-packages.json")
        math = self.load("artifacts/verification/phase8.5/math-verifiers.json")
        retrieval = self.load("artifacts/verification/phase8.6/retrieval-verifier.json")
        self.assertTrue(language["acceptance"])
        for report in language["reports"].values():
            self.assertTrue(all(gate["status"] == "passed" for gate in report["positive"]["gates"]))
            self.assertTrue(any(gate["status"] != "passed" for gate in report["negative"]["gates"]))
        self.assertTrue(math["identity"]["passed"])
        self.assertFalse(math["wrong"]["passed"])
        self.assertTrue(retrieval["accepted"]["passed"])
        self.assertFalse(retrieval["tampered"]["passed"])

    def test_isolated_python_passes_all_gates_and_global_budget_rejects(self):
        python = self.load("artifacts/verification/phase8.3/python-quality-verifiers.json")
        budget = self.load("artifacts/verification/phase8.8/global-attempt-budget.json")
        self.assertFalse(python["release_withheld_without_isolation"])
        self.assertTrue(all(
            python["good"][name]["status"] == "passed"
            for name in ("syntax", "unit_tests", "typing", "static_analysis")
        ))
        self.assertTrue(budget["over_budget_rejected"])
        self.assertTrue(budget["attempt_replay_rejected"])


if __name__ == "__main__":
    unittest.main()
