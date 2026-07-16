import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from fam_os.adapters.linux import LinuxHardwareDiscovery, LinuxPaths
from fam_os.adapters.linux.nvidia import NVIDIA_QUERY
from fam_os.scheduler import OperatingSystemProfile, StorageProfile


FIXTURES = Path(__file__).parents[1] / "fixtures" / "linux"


class FakeRunner:
    def __init__(self) -> None:
        self.outputs = {
            NVIDIA_QUERY: (FIXTURES / "nvidia-smi.csv").read_text(),
            ("ollama", "--version"): "ollama version test",
        }

    def run(self, command: tuple[str, ...], timeout_seconds: float = 10.0) -> str | None:
        return self.outputs.get(command)


class FakeHost:
    def captured_at(self) -> datetime:
        return datetime(2026, 7, 16, tzinfo=timezone.utc)

    def hostname(self) -> str:
        return "fam-test-host"

    def operating_system(self) -> OperatingSystemProfile:
        return OperatingSystemProfile("Linux", "test", "x86_64")

    def logical_cpu_count(self) -> int:
        return 2

    def storage(self, root: Path) -> StorageProfile:
        return StorageProfile(2_000, 500, 1_500)


class LinuxHardwareDiscoveryTests(unittest.TestCase):
    def test_composes_complete_profile_from_read_only_probes(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            accel = Path(directory) / "accel"
            accel.mkdir()
            (accel / "accel0").touch()
            paths = LinuxPaths(
                FIXTURES / "proc" / "meminfo",
                FIXTURES / "proc" / "cpuinfo",
                accel,
                Path(directory),
            )
            profile = LinuxHardwareDiscovery(paths, FakeRunner(), FakeHost()).collect()

        self.assertEqual(profile.memory.total_bytes, 16 * 1024**3)
        self.assertEqual(profile.cpu.model, "FAM Test CPU 1.0")
        self.assertEqual(profile.gpus[0].memory_total_bytes, 16 * 1024**3)
        self.assertTrue(profile.npu_device_paths[0].endswith("accel0"))
        self.assertEqual(profile.runtime_version("ollama"), "ollama version test")


if __name__ == "__main__":
    unittest.main()

