"""Broker-owned network attachment lifecycle for process environments."""

from fam_os.core.engineering.integration_network import (
    IntegrationNetworkAttachmentKind,
)
from fam_os.core.engineering.integration_environment import IntegrationNetworkMode
from fam_os.core.engineering.integration_environment import integration_environment_plan_digest
from fam_os.schemas import loads_document


class ProcessNetworkAttachment:
    def __init__(self, broker=None) -> None:
        self._broker = broker

    @property
    def available(self):
        return self._broker is not None

    def open(self, plan, permit, state):
        if plan.network_mode is not IntegrationNetworkMode.ALLOWLIST:
            return None
        request = self._request(plan, permit)
        state.record_network_opening()
        lease = permit.network_lease or self._broker.open(request)
        attachment = self.attachment(lease)
        try:
            state.record_network_lease(lease)
        except BaseException:
            if permit.network_lease is None:
                self._broker.close(lease)
            raise
        return lease

    def observe(self, lease):
        if lease is None:
            return None
        usage = self._broker.observe(lease)
        if usage.quota_exceeded:
            raise PermissionError("integration network byte quota was exhausted")
        return usage

    def close(self, document, permit):
        lease = self._lease(document)
        if lease is not None:
            if permit.network_lease is not None:
                return self._broker.observe(lease)
            try:
                return self._broker.close(lease)
            except PermissionError:
                if permit.network_request is None:
                    raise
                return self._broker.recover(permit.network_request)
        if permit.network_request is not None and document["network_opening"]:
            return self._broker.recover(permit.network_request)
        return None

    def recover(self, document, permit):
        if permit.network_request is None or not document.get("network_opening", False):
            return None
        if self._broker is None:
            raise PermissionError("integration network broker is unavailable")
        if permit.network_lease is not None:
            return self._broker.observe(permit.network_lease)
        return self._broker.recover(permit.network_request)

    def scope_arguments(self, plan, lease):
        if plan.network_mode is not IntegrationNetworkMode.ALLOWLIST:
            values = ["--property=IPAddressDeny=any"]
            if plan.network_mode is IntegrationNetworkMode.ISOLATED:
                values.append("--property=IPAddressAllow=localhost")
            return tuple(values), ()
        attachment = self.attachment(lease)
        proxy = attachment.proxy_uri
        properties = (
            "--property=NetworkNamespacePath=" + attachment.attachment_reference,
        )
        environment = (
            "--setenv", "HTTP_PROXY", proxy,
            "--setenv", "HTTPS_PROXY", proxy,
            "--setenv", "ALL_PROXY", proxy,
            "--setenv", "NO_PROXY", "localhost,127.0.0.1,::1",
        )
        return properties, environment

    def attachment(self, lease):
        if self._broker is None:
            raise PermissionError("integration network broker is unavailable")
        values = tuple(
            item for item in lease.attachments
            if item.kind is IntegrationNetworkAttachmentKind.LINUX_NAMESPACE
        )
        if len(values) != 1:
            raise PermissionError("process network lease lacks one Linux attachment")
        return values[0]

    def _request(self, plan, permit):
        if self._broker is None or permit.network_request is None:
            raise PermissionError("signed integration network request is unavailable")
        if IntegrationNetworkAttachmentKind.LINUX_NAMESPACE not in (
            permit.network_request.attachment_kinds
        ):
            raise PermissionError("integration network request lacks Linux attachment")
        if (
            (
                permit.network_lease is None
                and permit.network_request.plan_sha256
                != integration_environment_plan_digest(plan)
            )
            or permit.network_request.destinations != plan.network_hosts
            or permit.network_request.maximum_network_bytes
            != plan.resource_impact.max_network_bytes
        ):
            raise PermissionError("integration network request differs from plan")
        return permit.network_request

    @staticmethod
    def _lease(document):
        value = document["network_lease"]
        return None if value is None else loads_document(value)
