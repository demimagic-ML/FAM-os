import os
import stat
import tempfile
import unittest
from pathlib import Path

from fam_os.fabric import PeerEndpoint, PeerServiceConfiguration
from fam_os.product.peer_configuration import PeerConfigurationStore


class PeerConfigurationTests(unittest.TestCase):
    def test_missing_configuration_is_disabled_and_atomic_put_is_private(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "config/peer.json"
            store = PeerConfigurationStore(path, os.geteuid())
            self.assertFalse(store.load().enabled)
            configured = PeerServiceConfiguration(
                True, "Home server", "0.0.0.0", 48121,
                PeerEndpoint("server.example", 48121),
            )
            store.put(configured)
            self.assertEqual(configured, store.load())
            self.assertEqual(0o600, stat.S_IMODE(path.stat().st_mode))
            self.assertEqual(0o700, stat.S_IMODE(path.parent.stat().st_mode))

            replacement = PeerServiceConfiguration(
                True, "Home server", "127.0.0.1", 49121,
                PeerEndpoint("127.0.0.1", 49121),
            )
            store.put(replacement)
            self.assertEqual(replacement, store.load())
            self.assertFalse(path.with_name("peer.json.new").exists())

    def test_symbolic_link_configuration_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "target"
            target.write_text("do-not-replace", encoding="utf-8")
            path = root / "config/peer.json"
            path.parent.mkdir()
            path.symlink_to(target)
            store = PeerConfigurationStore(path, os.geteuid())
            with self.assertRaisesRegex(OSError, "symbolic link"):
                store.put(PeerServiceConfiguration(
                    True, "Device", "127.0.0.1", 48121,
                    PeerEndpoint("127.0.0.1", 48121),
                ))
            self.assertEqual("do-not-replace", target.read_text("utf-8"))


if __name__ == "__main__":
    unittest.main()
