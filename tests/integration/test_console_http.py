import json
import tempfile
import threading
import unittest
import urllib.error
import urllib.request
from pathlib import Path

from fam_os.console.http import ConsoleHttpServer
from fam_os.console.provider import LocalConsoleProvider


class ConsoleHttpTests(unittest.TestCase):
    def test_authenticated_loopback_snapshot_and_static_ui(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            server = ConsoleHttpServer(
                ("127.0.0.1", 0), LocalConsoleProvider(Path(directory), "v1"), "x" * 32,
            )
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            try:
                base = f"http://127.0.0.1:{server.server_port}"
                self.assertIn(b"Your machine, thinking in public", urllib.request.urlopen(base).read())
                with self.assertRaises(urllib.error.HTTPError) as denied:
                    urllib.request.urlopen(base + "/api/v1/snapshot")
                self.assertEqual(denied.exception.code, 401)
                request = urllib.request.Request(base + "/api/v1/snapshot")
                request.add_header("Authorization", "Bearer " + "x" * 32)
                payload = json.loads(urllib.request.urlopen(request).read())
                self.assertEqual(len(payload["sections"]), 6)
            finally:
                server.shutdown()
                server.server_close()
                thread.join()

    def test_non_loopback_binding_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            with self.assertRaisesRegex(ValueError, "loopback"):
                ConsoleHttpServer(
                    ("0.0.0.0", 0), LocalConsoleProvider(Path(directory)), "x" * 32,
                )


if __name__ == "__main__":
    unittest.main()
