"""Replaceable Linux filesystem locations used for discovery."""

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class LinuxPaths:
    meminfo: Path = Path("/proc/meminfo")
    cpuinfo: Path = Path("/proc/cpuinfo")
    accelerator_directory: Path = Path("/dev/accel")
    storage_root: Path = Path("/")

