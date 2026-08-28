import json
import os
import tempfile
import unittest
from pathlib import Path

from fam_os.product.desktop_permissions import DesktopPermissionStore


class DesktopPermissionStoreTests(unittest.TestCase):
    def test_absent_policy_reports_both_powers_disabled(self):
        with tempfile.TemporaryDirectory() as directory:
            receipt = DesktopPermissionStore(
                Path(directory) / "config/fallbacks.json",
            ).status()
            self.assertFalse(receipt["screen_capture"])
            self.assertFalse(receipt["input_control"])
            self.assertEqual(0, receipt["target_count"])

    def test_toggles_preserve_exact_target_and_other_policy(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config/fallbacks.json"
            path.parent.mkdir()
            path.write_text(json.dumps(_policy()), encoding="utf-8")
            os.chmod(path, 0o600)
            store = DesktopPermissionStore(path)

            enabled = store.update(screen_capture=True, input_control=True)
            self.assertTrue(enabled["screen_capture"])
            self.assertTrue(enabled["input_control"])
            document = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual("0x2a", document["screen_input"]["targets"][0]["window_id"])
            self.assertEqual("click", document["accessibility"]["allowed_actions"][0])

            disabled = store.update(screen_capture=False)
            self.assertFalse(disabled["screen_capture"])
            self.assertFalse(disabled["input_control"])

    def test_cannot_enable_unscoped_capture_or_input_without_capture(self):
        with tempfile.TemporaryDirectory() as directory:
            store = DesktopPermissionStore(Path(directory) / "config/fallbacks.json")
            with self.assertRaisesRegex(ValueError, "owner-approved exact target"):
                store.update(screen_capture=True)
            with self.assertRaisesRegex(ValueError, "requires screen capture"):
                store.update(input_control=True)

    def test_refuses_non_private_or_symlink_configuration(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "fallbacks.json"
            path.write_text(json.dumps(_policy()), encoding="utf-8")
            os.chmod(path, 0o644)
            with self.assertRaises(PermissionError):
                DesktopPermissionStore(path).status()
            path.unlink()
            target = root / "target.json"
            target.write_text(json.dumps(_policy()), encoding="utf-8")
            os.chmod(target, 0o600)
            path.symlink_to(target)
            with self.assertRaises(PermissionError):
                DesktopPermissionStore(path).status()


def _policy():
    return {
        "contract_version": "fam.product.fallbacks/v1alpha1",
        "accessibility": {
            "enabled": False, "privacy_acknowledged": False,
            "include_text": False, "actions_enabled": False,
            "allowed_actions": ["click"], "targets": [],
        },
        "screen_input": {
            "enabled": False, "privacy_acknowledged": False,
            "actions_enabled": False,
            "allowed_kinds": ["pointer_click", "key_chord"],
            "allowed_keys": ["Control_L", "Return"],
            "targets": [{
                "connector_id": "screen.editor",
                "instance_id": "screen-editor",
                "application_id": "org.example.Editor",
                "process_id": 200,
                "window_id": "0x2a",
            }],
        },
    }


if __name__ == "__main__":
    unittest.main()
