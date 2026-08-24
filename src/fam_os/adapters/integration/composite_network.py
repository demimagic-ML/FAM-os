"""One broker lease owned by the mixed-backend orchestrator."""

from dataclasses import replace

from fam_os.core.engineering import (
    IntegrationNetworkMode, integration_environment_plan_digest,
)
from fam_os.schemas import loads_document


class CompositeNetworkLifecycle:
    def __init__(self, broker=None): self._broker = broker

    def open(self, plan, permit, state):
        if plan.network_mode is not IntegrationNetworkMode.ALLOWLIST:
            return permit, None
        request = self._request(plan, permit)
        state.record_network_opening()
        lease = self._broker.open(request)
        try: state.record_network_lease(lease)
        except BaseException:
            self._broker.close(lease); raise
        return replace(permit, network_lease=lease), lease

    def permit_from(self, document, permit):
        value = document["network_lease"]
        return permit if value is None else replace(permit, network_lease=loads_document(value))

    def observe(self, lease):
        if lease is None: return None
        usage = self._broker.observe(lease)
        if usage.quota_exceeded:
            raise PermissionError("integration network byte quota was exhausted")
        return usage

    def close(self, document, permit):
        value = document["network_lease"]
        if value is None:
            return (
                self._broker.recover(permit.network_request)
                if document["network_opening"] else None
            )
        lease = loads_document(value)
        try: return self._broker.close(lease)
        except PermissionError: return self._broker.recover(permit.network_request)

    def recover(self, plan, document, permit):
        if (
            plan.network_mode is not IntegrationNetworkMode.ALLOWLIST
            or not document["network_opening"]
        ):
            return None
        self._request(plan, permit)
        return self._broker.recover(permit.network_request)

    def _request(self, plan, permit):
        if self._broker is None or permit.network_request is None:
            raise PermissionError("mixed allowlisted egress broker is unavailable")
        request = permit.network_request
        if (
            request.plan_sha256 != integration_environment_plan_digest(plan)
            or request.destinations != plan.network_hosts
            or request.maximum_network_bytes != plan.resource_impact.max_network_bytes
        ):
            raise PermissionError("mixed integration network request differs from plan")
        return request


def network_evidence(usage):
    return () if usage is None else ("network-finalized:" + usage.enforcement_id,)
