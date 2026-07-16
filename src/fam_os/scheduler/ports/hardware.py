"""Read-only hardware discovery port."""

from typing import Protocol

from fam_os.scheduler.hardware import HardwareProfile


class HardwareDiscovery(Protocol):
    def collect(self) -> HardwareProfile: ...

