"""Replaceable privileged network-enforcement mechanics."""

from typing import Protocol

from fam_os.supervisor.network_contracts import (
    NetworkEnforcementLease, NetworkEnforcementSpec, NetworkUsageSnapshot,
)


class NetworkEnforcementAdapter(Protocol):
    def open(self, spec: NetworkEnforcementSpec) -> NetworkEnforcementLease: ...
    def observe(self, enforcement_id: str) -> NetworkUsageSnapshot: ...
    def close(self, enforcement_id: str) -> NetworkUsageSnapshot: ...
    def recover(self, spec: NetworkEnforcementSpec) -> NetworkUsageSnapshot: ...
