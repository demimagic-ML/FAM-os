import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from fam_os.product.network_broker_service_cli import _require_root_installation


class Installation:
    def __init__(self, prefix, keys, *, healthy=True):
        self.prefix, self.keys, self.healthy = prefix, keys, healthy

    def diagnose(self):
        return SimpleNamespace(
            healthy=self.healthy,
            issues=() if self.healthy else ("active_release_unhealthy",),
        )


class NetworkBrokerRootEntrypointTests(unittest.TestCase):
    def test_non_root_and_nonabsolute_prefix_are_rejected_before_diagnosis(self):
        with self.assertRaisesRegex(PermissionError, "host administrator"):
            _require_root_installation(Path("/root-owned"), 1000, Installation)
        with self.assertRaisesRegex(PermissionError, "prefix"):
            _require_root_installation(Path("relative"), 0, Installation)

    def test_unhealthy_signed_installation_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            factory = lambda prefix, keys: Installation(
                prefix, keys, healthy=False,
            )
            with self.assertRaisesRegex(PermissionError, "active_release_unhealthy"):
                _require_root_installation(root, 0, factory)

    def test_healthy_root_installation_is_admitted(self):
        with tempfile.TemporaryDirectory() as temporary:
            _require_root_installation(
                Path(temporary).resolve(), 0, Installation,
            )


if __name__ == "__main__":
    unittest.main()
