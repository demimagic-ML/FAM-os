import json
import unittest
from pathlib import Path


class InstalledOperationalEvidenceTests(unittest.TestCase):
    def test_fresh_install_used_real_model_shell_and_console(self) -> None:
        report = json.loads(Path(
            "artifacts/product/phase15/installed-operational-acceptance.json"
        ).read_text())
        self.assertTrue(report["passed"])
        self.assertEqual(report["model_ref"], "qwen3:1.7b")
        self.assertGreater(report["model_accelerator_bytes"], 0)
        self.assertTrue(report["shell_output_nonempty"])
        self.assertTrue(report["console_ui_loaded"])
        self.assertEqual(len(report["console_sections"]), 6)
        self.assertTrue(report["damage_detected"])
        self.assertTrue(report["repair_passed"])
        self.assertTrue(report["complete_removal"])


if __name__ == "__main__":
    unittest.main()
