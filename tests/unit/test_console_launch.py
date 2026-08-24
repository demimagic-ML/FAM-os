import os
import tempfile
import unittest
from pathlib import Path

from fam_os.product.console_launch import ConsoleLaunchService


class _Probe:
    def __init__(self, ready=True):
        self.result = ready
        self.ports = []

    def ready(self, port):
        self.ports.append(port)
        return self.result


class _Browser:
    def __init__(self, opened=True):
        self.result = opened
        self.uris = []

    def open(self, uri):
        self.uris.append(uri)
        return self.result


class ConsoleLaunchTests(unittest.TestCase):
    def test_private_token_opens_fragment_but_never_enters_receipt(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            token = "private_console_token_" + "x" * 32
            token_file = root / "console.token"
            token_file.write_text(token + "\n")
            token_file.chmod(0o600)
            probe = _Probe()
            browser = _Browser()

            receipt = ConsoleLaunchService(probe, browser).launch(root, 8765)

        self.assertEqual([8765], probe.ports)
        self.assertEqual([f"http://127.0.0.1:8765/#token={token}"], browser.uris)
        self.assertEqual("http://127.0.0.1:8765", receipt.base_url)
        self.assertNotIn(token, repr(receipt))

    def test_token_must_be_private_owner_controlled_regular_file(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            token_file = root / "console.token"
            token_file.write_text("x" * 32)
            token_file.chmod(0o644)

            with self.assertRaisesRegex(PermissionError, "private owner file"):
                ConsoleLaunchService(_Probe(), _Browser()).launch(root, 8765)

    def test_symlink_token_is_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            target = root / "target"
            target.write_text("x" * 32)
            target.chmod(0o600)
            os.symlink(target, root / "console.token")

            with self.assertRaises(OSError):
                ConsoleLaunchService(_Probe(), _Browser()).launch(root, 8765)

    def test_dead_console_is_rejected_before_token_is_read(self):
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ConnectionError, "not ready"):
                ConsoleLaunchService(_Probe(False), _Browser()).launch(
                    Path(temporary), 8765,
                )


if __name__ == "__main__":
    unittest.main()
