"""Provider-neutral resource observation port."""

from typing import Protocol

from fam_os.supervisor.contracts import ResourceSnapshot


class ResourceObserver(Protocol):
    def observe(self, service_id: str) -> ResourceSnapshot | None: ...
