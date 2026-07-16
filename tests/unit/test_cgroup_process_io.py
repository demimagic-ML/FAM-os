import tempfile
import unittest
from pathlib import Path

from fam_os.adapters.linux.process_io import CgroupProcessIoObserver


class CgroupProcessIoTests(unittest.TestCase):
    def test_aggregates_surviving_process_counters(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            cgroup = root / "cgroup/service"
            cgroup.mkdir(parents=True)
            (cgroup / "cgroup.procs").write_text("10\n11\n12\n")
            proc = root / "proc"
            for pid, read, write in ((10, 100, 20), (11, 300, 40)):
                path = proc / str(pid)
                path.mkdir(parents=True)
                (path / "io").write_text(
                    f"rchar: {read + 5}\nwchar: {write + 7}\nread_bytes: {read}\nwrite_bytes: {write}\n"
                )
            result = CgroupProcessIoObserver(root / "cgroup", proc).observe("/service")
            self.assertEqual(result.physical_read_bytes, 400)
            self.assertEqual(result.physical_write_bytes, 60)
            self.assertEqual(result.logical_read_bytes, 410)
            self.assertEqual(result.process_count, 2)


if __name__ == "__main__":
    unittest.main()
