"""Provider-neutral failed-state reset port."""

from typing import Protocol

from fam_os.supervisor.contracts import ServiceStatus


class ServiceFailureReset(Protocol):
    def reset_failed(self, service_id: str) -> ServiceStatus: ...
