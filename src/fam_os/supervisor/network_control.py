"""Authenticated deterministic admission for integration network enforcement."""

from dataclasses import dataclass
from datetime import datetime

from fam_os.supervisor.access import SupervisorCallContext, SupervisorAuthorizer
from fam_os.supervisor.boundary import SupervisorCapability
from fam_os.supervisor.network_contracts import (
    NetworkEnforcementLease, NetworkEnforcementSpec, NetworkUsageSnapshot,
)
from fam_os.supervisor.ports.network import NetworkEnforcementAdapter


@dataclass(slots=True)
class NetworkEnforcementController:
    authorizer: SupervisorAuthorizer
    adapter: NetworkEnforcementAdapter

    def open(self, context: SupervisorCallContext, spec: NetworkEnforcementSpec, instant: datetime):
        self._require(context, spec.enforcement_id)
        if not instant < spec.expires_at:
            raise PermissionError("network enforcement request is expired")
        lease = self.adapter.open(spec)
        _lease_matches(spec, lease)
        return lease

    def observe(self, context: SupervisorCallContext, enforcement_id: str):
        self._require(context, enforcement_id)
        usage = self.adapter.observe(enforcement_id)
        _usage_matches(enforcement_id, usage)
        return usage

    def close(self, context: SupervisorCallContext, enforcement_id: str):
        self._require(context, enforcement_id)
        usage = self.adapter.close(enforcement_id)
        _usage_matches(enforcement_id, usage)
        if not usage.finalized:
            raise RuntimeError("network close did not finalize accounting")
        return usage

    def recover(self, context: SupervisorCallContext, spec: NetworkEnforcementSpec):
        self._require(context, spec.enforcement_id)
        usage = self.adapter.recover(spec)
        _usage_matches(spec.enforcement_id, usage)
        if not usage.finalized or usage.maximum_network_bytes != spec.maximum_network_bytes:
            raise RuntimeError("network recovery evidence is incomplete")
        if not set(usage.destinations).issubset(spec.destinations):
            raise RuntimeError("network recovery observed an unapproved destination")
        return usage

    def _require(self, context, enforcement_id):
        self.authorizer.require(
            context, SupervisorCapability.ENFORCE_ALLOWLISTED_NETWORK,
            enforcement_id,
        )


def _lease_matches(spec, lease: NetworkEnforcementLease) -> None:
    if (
        lease.enforcement_id != spec.enforcement_id
        or tuple(item.kind for item in lease.attachments) != spec.attachment_kinds
        or lease.destinations != spec.destinations
        or lease.maximum_network_bytes != spec.maximum_network_bytes
        or lease.expires_at > spec.expires_at
    ):
        raise RuntimeError("network adapter returned a substituted lease")


def _usage_matches(enforcement_id, usage: NetworkUsageSnapshot) -> None:
    if usage.enforcement_id != enforcement_id:
        raise RuntimeError("network adapter returned mismatched usage")
