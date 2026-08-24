"""Broker-owned allowlisted attachment lifecycle for Docker environments."""

from fam_os.core.engineering import (
    IntegrationNetworkAttachmentKind, IntegrationNetworkMode,
    integration_environment_plan_digest,
)
from fam_os.schemas import loads_document


class DockerNetworkAttachment:
    def __init__(self, broker=None): self._broker = broker

    @property
    def available(self): return self._broker is not None

    def open(self, plan, permit, state):
        if plan.network_mode is not IntegrationNetworkMode.ALLOWLIST:
            return None, None, ()
        request = self._request(plan, permit)
        state.record_network_opening()
        lease = permit.network_lease or self._broker.open(request)
        attachment = self.attachment(lease)
        try:
            state.record_network(attachment.attachment_reference, lease)
        except BaseException:
            if permit.network_lease is None: self._broker.close(lease)
            raise
        environment = (
            "HTTP_PROXY=" + attachment.proxy_uri,
            "HTTPS_PROXY=" + attachment.proxy_uri,
            "ALL_PROXY=" + attachment.proxy_uri,
            "NO_PROXY=localhost,127.0.0.1,::1",
        )
        return lease, attachment.attachment_reference, environment

    def observe(self, lease):
        if lease is None: return None
        usage = self._broker.observe(lease)
        if usage.quota_exceeded:
            raise PermissionError("integration network byte quota was exhausted")
        return usage

    def close(self, document, permit):
        lease = self._lease(document)
        if lease is None:
            return (
                self._broker.recover(permit.network_request)
                if permit.network_request is not None and document["network_opening"]
                else None
            )
        if permit.network_lease is not None:
            return self._broker.observe(lease)
        try: return self._broker.close(lease)
        except PermissionError: return self._broker.recover(permit.network_request)

    def recover(self, document, permit):
        if permit.network_request is None or not document.get("network_opening", False):
            return None
        if self._broker is None:
            raise PermissionError("integration network broker is unavailable")
        if permit.network_lease is not None:
            return self._broker.observe(permit.network_lease)
        return self._broker.recover(permit.network_request)

    def attachment(self, lease):
        values = tuple(
            item for item in lease.attachments
            if item.kind is IntegrationNetworkAttachmentKind.DOCKER_INTERNAL_NETWORK
        )
        if len(values) != 1:
            raise PermissionError("Docker network lease lacks one internal attachment")
        return values[0]

    def _request(self, plan, permit):
        if self._broker is None or permit.network_request is None:
            raise PermissionError("signed integration network request is unavailable")
        request = permit.network_request
        if IntegrationNetworkAttachmentKind.DOCKER_INTERNAL_NETWORK not in request.attachment_kinds:
            raise PermissionError("integration network request lacks Docker attachment")
        if (
            (permit.network_lease is None and request.plan_sha256 != integration_environment_plan_digest(plan))
            or request.destinations != plan.network_hosts
            or request.maximum_network_bytes != plan.resource_impact.max_network_bytes
        ):
            raise PermissionError("integration network request differs from plan")
        return request

    @staticmethod
    def _lease(document):
        value = document["network_lease"]
        return None if value is None else loads_document(value)


def docker_network_evidence(document, network_id, usage, action):
    if document["network_lease"] is None:
        return () if not network_id else (f"{action}-network:{network_id}",)
    if usage is None:
        return ()
    prefix = "network-finalized:" if usage.finalized else "network-observed:"
    return (prefix + usage.enforcement_id,)
