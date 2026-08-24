"""Bounded Unix transport to the deterministic integration egress broker."""

import socket
from pathlib import Path

from fam_os.core.engineering.integration_network import (
    IntegrationNetworkEnforcementRequest,
    IntegrationNetworkLease,
    IntegrationNetworkUsage,
    validate_integration_network_lease,
)
from fam_os.schemas import dumps_document, loads_document


class UnixIntegrationNetworkBroker:
    def __init__(
        self, socket_path: Path, *, maximum_message_bytes: int = 1_048_576,
        timeout_seconds: int = 30,
    ) -> None:
        if not socket_path.is_absolute():
            raise ValueError("integration network broker socket must be absolute")
        if maximum_message_bytes <= 0 or timeout_seconds <= 0:
            raise ValueError("integration network broker bounds must be positive")
        self._path = socket_path
        self._limit = maximum_message_bytes
        self._timeout = timeout_seconds

    def open(self, request: IntegrationNetworkEnforcementRequest):
        lease = self._exchange("open", request, IntegrationNetworkLease)
        validate_integration_network_lease(request, lease)
        return lease

    def observe(self, lease: IntegrationNetworkLease):
        usage = self._exchange("observe", lease, IntegrationNetworkUsage)
        self._validate_usage(lease, usage, finalized=False)
        return usage

    def close(self, lease: IntegrationNetworkLease):
        usage = self._exchange("close", lease, IntegrationNetworkUsage)
        self._validate_usage(lease, usage, finalized=True)
        return usage

    def recover(self, request: IntegrationNetworkEnforcementRequest):
        usage = self._exchange("recover", request, IntegrationNetworkUsage)
        if usage.environment_id != request.environment_id or not usage.finalized:
            raise ValueError("network recovery returned mismatched evidence")
        if usage.maximum_network_bytes != request.maximum_network_bytes:
            raise ValueError("network recovery returned a substituted byte limit")
        if not set(usage.destinations).issubset(request.destinations):
            raise ValueError("network recovery returned an unapproved destination")
        return usage

    def _exchange(self, operation, document, expected):
        request = (operation + "\n" + dumps_document(document) + "\n").encode()
        if len(request) > self._limit:
            raise ValueError("integration network broker request exceeds bound")
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as stream:
            stream.settimeout(self._timeout)
            stream.connect(str(self._path))
            stream.sendall(request)
            stream.shutdown(socket.SHUT_WR)
            response = self._receive(stream)
        value = loads_document(response.decode("utf-8"))
        if not isinstance(value, expected):
            raise TypeError("integration network broker returned wrong contract")
        return value

    def _receive(self, stream):
        response = bytearray()
        while len(response) <= self._limit:
            part = stream.recv(min(65_536, self._limit + 1 - len(response)))
            if not part:
                break
            response.extend(part)
        if len(response) > self._limit:
            raise ValueError("integration network broker response exceeds bound")
        return bytes(response)

    @staticmethod
    def _validate_usage(lease, usage, *, finalized):
        if usage.enforcement_id != lease.enforcement_id:
            raise ValueError("network usage enforcement identity is mismatched")
        if usage.environment_id != lease.environment_id:
            raise ValueError("network usage environment identity is mismatched")
        if usage.maximum_network_bytes != lease.maximum_network_bytes:
            raise ValueError("network usage byte limit is mismatched")
        if not set(usage.destinations).issubset(lease.destinations):
            raise ValueError("network usage contains an unapproved destination")
        if finalized and not usage.finalized:
            raise ValueError("network close did not finalize accounting")
