import stat
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path

from fam_os.adaptation.preferences import (
    FilePreferenceStore, PreferenceKey, UserPreference, UserPreferenceProfile,
)

NOW = datetime(2026, 7, 16, tzinfo=UTC)


class PreferenceAdapterTests(unittest.TestCase):
    def test_inspect_persist_and_reset(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "preferences.json"
            store = FilePreferenceStore(path, "owner")
            profile = UserPreferenceProfile("owner", (
                UserPreference(PreferenceKey.QUALITY_PRIORITY, .8, NOW),
            ))
            store.save(profile)
            self.assertEqual(profile, store.inspect("owner"))
            self.assertEqual(0o600, stat.S_IMODE(path.stat().st_mode))
            receipt = store.reset("owner", NOW)
            self.assertEqual((PreferenceKey.QUALITY_PRIORITY,), receipt.removed_keys)
            self.assertEqual((), store.inspect("owner").preferences)

    def test_cross_owner_access_is_denied(self):
        with tempfile.TemporaryDirectory() as directory:
            store = FilePreferenceStore(Path(directory) / "p.json", "owner")
            with self.assertRaises(PermissionError):
                store.inspect("other")


if __name__ == "__main__":
    unittest.main()
