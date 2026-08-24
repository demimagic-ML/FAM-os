import socket
import unittest

from fam_os.adapters.integration.devtools_client import (
    BoundedDevToolsClient,
    _receive_message,
)


class _ResultClient(BoundedDevToolsClient):
    def __init__(self, result):
        super().__init__(9222, maximum_bytes=32)
        self._result = result

    def _command(self, method, parameters):
        return self._result


class BoundedDevToolsClientTests(unittest.TestCase):
    def test_non_exact_loopback_target_is_rejected_before_connection(self):
        client = BoundedDevToolsClient(9222)

        with self.assertRaisesRegex(PermissionError, "exact loopback"):
            client._connect("ws://localhost:9222/devtools/page/escape")
        with self.assertRaisesRegex(PermissionError, "exact loopback"):
            client._connect("ws://127.0.0.1:9223/devtools/page/escape")

    def test_masked_or_oversized_server_frame_is_rejected(self):
        receiver, sender = socket.socketpair()
        self.addCleanup(receiver.close)
        self.addCleanup(sender.close)

        sender.sendall(b"\x81\x81\x00\x00\x00\x00x")
        with self.assertRaisesRegex(RuntimeError, "invalid or oversized"):
            _receive_message(receiver, 32)

        receiver.close(); sender.close()
        receiver, sender = socket.socketpair()
        self.addCleanup(receiver.close)
        self.addCleanup(sender.close)
        sender.sendall(b"\x81\x21" + b"x" * 33)
        with self.assertRaisesRegex(RuntimeError, "invalid or oversized"):
            _receive_message(receiver, 32)

    def test_fragmented_text_response_is_bounded_and_reassembled(self):
        receiver, sender = socket.socketpair()
        self.addCleanup(receiver.close)
        self.addCleanup(sender.close)

        sender.sendall(b"\x01\x02{}" + b"\x80\x02[]")

        self.assertEqual((1, b"{}[]"), _receive_message(receiver, 32))

    def test_screenshot_requires_strict_bounded_png(self):
        with self.assertRaisesRegex(RuntimeError, "strict base64"):
            _ResultClient({"data": "not base64"}).screenshot_png()
        with self.assertRaisesRegex(RuntimeError, "bounded PNG"):
            _ResultClient({"data": "YWJj"}).screenshot_png()


if __name__ == "__main__":
    unittest.main()
