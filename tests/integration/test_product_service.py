import json
import tempfile
import unittest
import urllib.request
from pathlib import Path

from fam_os.adapters.shell import UnixShellClientConfiguration, UnixShellCoreClient
from fam_os.product.service import LocalProductService, ProductServiceSettings
from fam_os.shell import ShellAskCommand


class _Response:
    content = "Operational local response"


class _Runtime:
    def chat(self, request):
        return _Response()

    def unload(self, model_ref):
        return None

    def loaded_models(self):
        return ()


class ProductServiceTests(unittest.TestCase):
    def test_one_service_answers_shell_and_console_then_stops(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            service = LocalProductService(
                ProductServiceSettings(root / "state", root / "runtime", console_port=0),
                _Runtime(),
            )
            service.start()
            try:
                client = UnixShellCoreClient(UnixShellClientConfiguration(
                    root / "runtime" / "shell.sock", 5,
                ))
                accepted = client.ask(ShellAskCommand("request", "hello"))
                result = client.snapshot(accepted.session_id)
                self.assertEqual(result.result.content, "Operational local response")
                token = (root / "runtime" / "console.token").read_text().strip()
                port = service.console_server.server_port
                request = urllib.request.Request(f"http://127.0.0.1:{port}/api/v1/snapshot")
                request.add_header("Authorization", f"Bearer {token}")
                payload = json.loads(urllib.request.urlopen(request).read())
                self.assertEqual(len(payload["sections"]), 6)
            finally:
                service.stop()
            self.assertFalse((root / "runtime" / "shell.sock").exists())


if __name__ == "__main__":
    unittest.main()
