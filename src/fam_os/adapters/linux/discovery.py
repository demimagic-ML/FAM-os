"""Composition root for read-only Linux hardware discovery."""

from __future__ import annotations

from fam_os.adapters.linux.command import CommandRunner, SubprocessCommandRunner
from fam_os.adapters.linux.host import HostProbe, StandardLibraryHostProbe
from fam_os.adapters.linux.nvidia import query_nvidia_gpus
from fam_os.adapters.linux.paths import LinuxPaths
from fam_os.adapters.linux.procfs import read_cpu_model, read_meminfo
from fam_os.scheduler.hardware import CpuProfile, HardwareProfile, MemoryProfile, RuntimeVersion


class LinuxHardwareDiscovery:
    def __init__(
        self,
        paths: LinuxPaths | None = None,
        runner: CommandRunner | None = None,
        host: HostProbe | None = None,
    ) -> None:
        self._paths = paths or LinuxPaths()
        self._runner = runner or SubprocessCommandRunner()
        self._host = host or StandardLibraryHostProbe()

    def collect(self) -> HardwareProfile:
        memory = read_meminfo(self._paths.meminfo)
        npu_paths = tuple(
            sorted(str(path) for path in self._paths.accelerator_directory.glob("accel*"))
        )
        return HardwareProfile(
            schema_version=1,
            captured_at=self._host.captured_at(),
            hostname=self._host.hostname(),
            operating_system=self._host.operating_system(),
            cpu=CpuProfile(read_cpu_model(self._paths.cpuinfo), self._host.logical_cpu_count()),
            memory=MemoryProfile(
                memory.get("MemTotal"),
                memory.get("MemAvailable"),
                memory.get("SwapTotal"),
                memory.get("SwapFree"),
            ),
            storage=self._host.storage(self._paths.storage_root),
            gpus=query_nvidia_gpus(self._runner),
            npu_device_paths=npu_paths,
            runtimes=(RuntimeVersion("ollama", self._runner.run(("ollama", "--version"))),),
        )

