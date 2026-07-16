import tempfile
import unittest
from pathlib import Path

from fam_os.product.soak_runner import run_soak


class ProductionSoakTests(unittest.TestCase):
    def test_real_short_soak_verifies_storage_and_crash_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            report = run_soak(Path(directory), 0.05, 0.01)
        self.assertTrue(report.passed, report.failures)
        self.assertGreaterEqual(report.samples, 2)
        self.assertEqual(report.injected_crashes, report.successful_recoveries)
        self.assertGreater(report.storage_bytes_verified, 0)


if __name__ == "__main__":
    unittest.main()
