import os
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

from fam_os.product.owned_root import OwnedProductRoot
from fam_os.product.removal import CompleteProductRemoval


class CompleteProductRemovalTests(unittest.TestCase):
    def test_confirmed_removal_stops_services_and_removes_every_owned_surface(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prefix = root / "prefix"
            state = root / "state"
            runtime = root / "runtime"
            extensions = root / "extensions"
            for path in (prefix, state, runtime, extensions):
                path.mkdir(mode=0o700)
            OwnedProductRoot(state, "state", os.geteuid()).initialize()
            OwnedProductRoot(runtime, "runtime", os.geteuid()).initialize()
            installation = Mock(prefix=prefix)
            installation.remove.side_effect = lambda: prefix.rmdir()
            connector = Mock()
            connector.status.return_value = SimpleNamespace(installed=True)
            connector.remove.return_value = SimpleNamespace(
                installed=False, path=str(extensions),
            )
            calls = []

            receipt = CompleteProductRemoval(
                installation, connector, state, runtime,
                root / "units", lambda *args, **kwargs: calls.append((args, kwargs)),
            ).remove(confirmed=True)

            self.assertFalse(prefix.exists())
            self.assertFalse(state.exists())
            self.assertFalse(runtime.exists())
            self.assertTrue(receipt.connector_removed)
            installation.remove_user_unit.assert_called_once_with(root / "units")
            self.assertIn((("disable", "--now", "fam-os.service"), {"check": False}), calls)
            self.assertIn((("disable", "--now", "fam-ollama.service"), {"check": False}), calls)
            self.assertIn((("reset-failed", "fam-ollama.service"), {"check": False}), calls)

    def test_missing_confirmation_changes_nothing(self):
        installation = Mock(prefix=Path("/tmp/fam-prefix"))
        connector = Mock()
        removal = CompleteProductRemoval(
            installation, connector, Path("/tmp/fam-state"),
            Path("/tmp/fam-runtime"), Path("/tmp/fam-units"), Mock(),
        )

        with self.assertRaisesRegex(PermissionError, "--confirm"):
            removal.remove(confirmed=False)
        installation.remove.assert_not_called()
        connector.remove.assert_not_called()

    def test_unmarked_state_refuses_before_any_service_mutation(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            prefix, state, runtime = root / "prefix", root / "state", root / "runtime"
            for path in (prefix, state, runtime):
                path.mkdir(mode=0o700)
            OwnedProductRoot(runtime, "runtime", os.geteuid()).initialize()
            installation = Mock(prefix=prefix)
            systemctl = Mock()
            removal = CompleteProductRemoval(
                installation, Mock(), state, runtime, root / "units", systemctl,
            )

            with self.assertRaisesRegex(FileNotFoundError, "marker"):
                removal.remove(confirmed=True)
            systemctl.assert_not_called()
            installation.remove.assert_not_called()


if __name__ == "__main__":
    unittest.main()
