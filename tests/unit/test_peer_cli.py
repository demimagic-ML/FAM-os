import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

from fam_os.product.composition.storage_unit import ProductStorageUnit
from fam_os.product.peer_cli import run_peer_command


class PeerCliTests(unittest.TestCase):
    def test_confirmed_configuration_supplies_offer_endpoint(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            output = io.StringIO()
            with redirect_stdout(output):
                run_peer_command(SimpleNamespace(
                    state_root=root, device_name="Configured device",
                    peer_action="configure", confirm=True,
                    listen_host="0.0.0.0", listen_port=48121,
                    advertised_host="peer.example", advertised_port=48121,
                ))
            self.assertIn("peer-service-configuration", output.getvalue())
            output = io.StringIO()
            with redirect_stdout(output):
                run_peer_command(SimpleNamespace(
                    state_root=root, device_name=None, peer_action="offer",
                    host=None, port=None,
                ))
            self.assertIn("peer.example", output.getvalue())

    def test_offer_code_and_confirmed_approval_persist_enrollment(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            desktop_offer = _offer(root / "desktop", "Desktop", "127.0.0.1", 48121)
            server_offer = _offer(root / "server", "Server", "127.0.0.1", 48122)
            desktop_path = root / "desktop-offer.json"
            server_path = root / "server-offer.json"
            desktop_path.write_text(desktop_offer, encoding="utf-8")
            server_path.write_text(server_offer, encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                result = run_peer_command(SimpleNamespace(
                    state_root=root / "desktop", device_name="Desktop",
                    peer_action="code", local_offer=desktop_path,
                    peer_offer=server_path,
                ))
            self.assertEqual(0, result)
            code = json.loads(output.getvalue())["pairing_code"]

            output = io.StringIO()
            with redirect_stdout(output):
                result = run_peer_command(SimpleNamespace(
                    state_root=root / "desktop", device_name="Desktop",
                    peer_action="approve", local_offer=desktop_path,
                    peer_offer=server_path, code=code, confirm=True,
                ))
            self.assertEqual(0, result)
            self.assertIn("fam.fabric.peer-enrollment/v1alpha1", output.getvalue())

            storage = ProductStorageUnit(root / "desktop", os.geteuid())
            opened = storage.start()
            self.assertFalse(opened.recovery_required)
            records = storage.core.repositories().peer_enrollments.active()
            self.assertEqual(1, len(records))
            self.assertEqual("Server", records[0].approval.peer_identity.display_name)
            storage.stop()

    def test_approval_without_literal_confirmation_stores_nothing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = root / "first.json"
            second = root / "second.json"
            first.write_text(_offer(root / "first", "First", "127.0.0.1", 48121))
            second.write_text(_offer(root / "second", "Second", "127.0.0.1", 48122))
            with self.assertRaisesRegex(PermissionError, "requires --confirm"):
                run_peer_command(SimpleNamespace(
                    state_root=root / "first", device_name="First",
                    peer_action="approve", local_offer=first, peer_offer=second,
                    code="0000-0000-0000", confirm=False,
                ))
            self.assertFalse((root / "first/state/fam.sqlite3").exists())


def _offer(state_root, name, host, port):
    output = io.StringIO()
    with redirect_stdout(output):
        run_peer_command(SimpleNamespace(
            state_root=state_root, device_name=name, peer_action="offer",
            host=host, port=port,
        ))
    return output.getvalue()


if __name__ == "__main__":
    unittest.main()
