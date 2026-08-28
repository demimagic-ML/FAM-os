import json
import tempfile
import unittest
from pathlib import Path

from fam_os.product.omarchy_session_bridge import OmarchySessionBridge


class OmarchySessionRecoveryTests(unittest.TestCase):
    def test_session_checkpoint_is_atomic_and_restart_readable(self):
        with tempfile.TemporaryDirectory() as directory:
            bridge = OmarchySessionBridge(poll_seconds=0.01)
            bridge.state_file = Path(directory) / "omarchy-session.json"
            bridge._write("recovering", "hyprland-disconnected", 2)
            first = json.loads(bridge.state_file.read_text(encoding="utf-8"))
            bridge._write("connected", "hyprland", 0)
            second = json.loads(bridge.state_file.read_text(encoding="utf-8"))
        self.assertEqual(first["recoveryAttempts"], 2)
        self.assertEqual(second["status"], "connected")
        self.assertEqual(second["contractVersion"], "fam.omarchy.session/v1")


if __name__ == "__main__":
    unittest.main()
