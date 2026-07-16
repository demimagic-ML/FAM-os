import urllib.error
import unittest
from unittest.mock import MagicMock, patch

from fam_os.adapters.ollama.errors import OllamaTransportError
from fam_os.adapters.ollama.transport import UrllibJsonTransport


class UrllibJsonTransportTests(unittest.TestCase):
    @patch("fam_os.adapters.ollama.transport.urllib.request.urlopen")
    def test_sends_json_without_using_a_shell(self, urlopen: MagicMock) -> None:
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b'{"models":[]}'
        urlopen.return_value = response

        result = UrllibJsonTransport().request("POST", "http://localhost/api/test", {"x": 1}, 5)

        request = urlopen.call_args.args[0]
        self.assertEqual(result, {"models": []})
        self.assertEqual(request.method, "POST")
        self.assertEqual(request.data, b'{"x": 1}')

    @patch("fam_os.adapters.ollama.transport.urllib.request.urlopen")
    def test_translates_connection_failure(self, urlopen: MagicMock) -> None:
        urlopen.side_effect = urllib.error.URLError("offline")
        with self.assertRaisesRegex(OllamaTransportError, "request failed"):
            UrllibJsonTransport().request("GET", "http://localhost/api/ps", None, 5)

    @patch("fam_os.adapters.ollama.transport.urllib.request.urlopen")
    def test_rejects_non_object_json(self, urlopen: MagicMock) -> None:
        response = MagicMock()
        response.__enter__.return_value.read.return_value = b"[]"
        urlopen.return_value = response
        with self.assertRaisesRegex(OllamaTransportError, "JSON object"):
            UrllibJsonTransport().request("GET", "http://localhost/api/ps", None, 5)


if __name__ == "__main__":
    unittest.main()

