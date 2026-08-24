import unittest
from pathlib import Path

from fam_os.adapters.integration.docker_client import DockerCommandClient


class DockerCommandClientInputTests(unittest.TestCase):
    def test_streams_bounded_input_without_a_shell(self):
        client = DockerCommandClient(
            executable=Path("/usr/bin/cat"),
            maximum_output_bytes=64,
            maximum_input_bytes=64,
        )
        result = client.run_with_input(("-",), b"bounded-input\n")
        self.assertEqual(0, result.exit_code)
        self.assertEqual(b"bounded-input\n", result.output)

    def test_rejects_input_above_constructor_bound(self):
        client = DockerCommandClient(
            executable=Path("/usr/bin/cat"),
            maximum_input_bytes=3,
        )
        with self.assertRaisesRegex(ValueError, "input exceeds"):
            client.run_with_input(("-",), b"four")


if __name__ == "__main__":
    unittest.main()
