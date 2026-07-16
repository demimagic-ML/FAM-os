import tempfile
import unittest
from pathlib import Path

from fam_os.adapters.linux.block_io import (
    ROOT_SOURCE_QUERY,
    parse_block_io,
    query_root_block_io,
)


class FakeRunner:
    def run(self, command: tuple[str, ...], timeout_seconds: float = 10.0) -> str | None:
        return "/dev/testp2" if command == ROOT_SOURCE_QUERY else None


class LinuxBlockIoTests(unittest.TestCase):
    def test_parses_kernel_sector_and_operation_counters(self) -> None:
        reading = parse_block_io("10 0 20 0 30 0 40".split(), 512)
        self.assertEqual(reading.read_bytes, 10_240)
        self.assertEqual(reading.write_bytes, 20_480)
        self.assertEqual(reading.read_operations, 10)
        self.assertEqual(reading.write_operations, 30)

    def test_discovers_root_partition_without_retaining_device_name(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            device = Path(directory) / "testp2"
            (device / "queue").mkdir(parents=True)
            (device / "stat").write_text("1 0 2 0 3 0 4")
            (device / "queue" / "logical_block_size").write_text("512")
            reading = query_root_block_io(FakeRunner(), Path(directory))
        self.assertEqual(reading.storage_id, "storage-root")
        self.assertNotIn("testp2", repr(reading))


if __name__ == "__main__":
    unittest.main()
