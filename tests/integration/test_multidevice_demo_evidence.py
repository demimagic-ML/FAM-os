import json
import unittest
from pathlib import Path

ROOT = Path(__file__).parents[2]


class MultiDeviceDemoEvidenceTests(unittest.TestCase):
    def test_encrypted_remote_and_disconnect_fallback_pass(self):
        raw = json.loads((ROOT / "artifacts/fabric/phase12/multidevice-demo.json").read_text())
        self.assertTrue(raw["passed"])
        self.assertEqual("home-server", raw["remote_device_selected"])
        self.assertEqual(0, raw["unauthorized_context_bytes"])
        self.assertTrue(raw["disconnect_local_fallback_verified"])


if __name__ == "__main__":
    unittest.main()
