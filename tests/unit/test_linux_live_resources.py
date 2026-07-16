import tempfile
import unittest
from pathlib import Path

from fam_os.adapters.linux.live_resources import (
    CacheDirectory,
    DirectoryStorageRuntimeObserver,
    NvidiaAcceleratorRuntimeObserver,
)


class FakeRunner:
    def run(self, command):
        return "0, NVIDIA Test, 1024, 256, 50, 999.1\n"


class LinuxLiveResourceAdapterTests(unittest.TestCase):
    def test_nvidia_observer_maps_stable_inventory_identifier(self):
        readings = NvidiaAcceleratorRuntimeObserver(FakeRunner()).observe_accelerators()
        self.assertEqual(readings[0].device_id, "gpu-0")
        self.assertEqual(readings[0].current_memory_bytes, 256 * 1024 * 1024)
        self.assertEqual(readings[0].utilization_fraction, 0.5)

    def test_cache_observer_counts_regular_files_but_not_symlink_targets(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "nested").mkdir()
            (root / "one").write_bytes(b"123")
            (root / "nested" / "two").write_bytes(b"4567")
            (root / "link").symlink_to(root / "nested" / "two")
            observer = DirectoryStorageRuntimeObserver((CacheDirectory("ssd", root),))

            self.assertEqual(observer.observe_storage()[0].current_cache_bytes, 7)

    def test_cache_observer_is_entry_bounded(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "one").write_bytes(b"1")
            (root / "two").write_bytes(b"2")
            observer = DirectoryStorageRuntimeObserver(
                (CacheDirectory("ssd", root),), maximum_entries=1
            )
            with self.assertRaisesRegex(ValueError, "entry limit"):
                observer.observe_storage()

    def test_cache_observer_rejects_symbolic_link_root(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            target = root / "target"
            target.mkdir()
            link = root / "link"
            link.symlink_to(target)
            observer = DirectoryStorageRuntimeObserver((CacheDirectory("ssd", link),))
            with self.assertRaisesRegex(ValueError, "symbolic link"):
                observer.observe_storage()

    def test_missing_cache_directory_is_empty_not_unavailable(self):
        observer = DirectoryStorageRuntimeObserver((
            CacheDirectory("ssd", Path("/definitely/missing/fam-cache")),
        ))
        self.assertEqual(observer.observe_storage()[0].current_cache_bytes, 0)


if __name__ == "__main__":
    unittest.main()
