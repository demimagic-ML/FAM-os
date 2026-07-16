"""Standard-library host facts kept behind an injectable adapter seam."""

from __future__ import annotations

import os
import platform
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol

from fam_os.scheduler.hardware import OperatingSystemProfile, StorageProfile


class HostProbe(Protocol):
    def captured_at(self) -> datetime: ...
    def hostname(self) -> str: ...
    def operating_system(self) -> OperatingSystemProfile: ...
    def logical_cpu_count(self) -> int | None: ...
    def storage(self, root: Path) -> StorageProfile: ...


class StandardLibraryHostProbe:
    def captured_at(self) -> datetime:
        return datetime.now(timezone.utc)

    def hostname(self) -> str:
        return platform.node()

    def operating_system(self) -> OperatingSystemProfile:
        return OperatingSystemProfile(platform.system(), platform.release(), platform.machine())

    def logical_cpu_count(self) -> int | None:
        return os.cpu_count()

    def storage(self, root: Path) -> StorageProfile:
        usage = shutil.disk_usage(root)
        return StorageProfile(usage.total, usage.used, usage.free)

