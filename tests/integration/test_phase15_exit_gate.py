import json
import subprocess
import unittest
from pathlib import Path


class Phase15ExitGateTests(unittest.TestCase):
    def test_installed_operational_exit_passes(self) -> None:
        subprocess.run(
            (".verification-venv/bin/python", "tools/build_phase15_exit_evidence.py"),
            check=True, capture_output=True, text=True,
        )
        report = json.loads(Path("artifacts/product/phase15/phase15-exit.json").read_text())
        self.assertTrue(report["passed"])
        self.assertEqual(report["regression_test_count"], 842)
        self.assertEqual(report["schema_count"], 166)


if __name__ == "__main__":
    unittest.main()
