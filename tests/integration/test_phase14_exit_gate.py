import json
import subprocess
import unittest
from pathlib import Path


class Phase14ExitGateTests(unittest.TestCase):
    def test_checked_exit_evidence_passes_every_gate(self) -> None:
        subprocess.run(
            (".verification-venv/bin/python", "tools/build_phase14_exit_evidence.py"),
            check=True, capture_output=True, text=True,
        )
        report = json.loads(Path("artifacts/product/phase14-exit.json").read_text())
        self.assertTrue(report["passed"])
        self.assertTrue(all(value for key, value in report.items() if key.endswith("_passed")))


if __name__ == "__main__":
    unittest.main()
