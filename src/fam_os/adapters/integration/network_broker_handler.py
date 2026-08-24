"""Translate Core network contracts into audited Supervisor enforcement."""

import hashlib

from fam_os.adapters.integration.network_broker_state import (
    NetworkBrokerStateStore, network_enforcement_id,
)
from fam_os.core.engineering.integration_network import (
    IntegrationNetworkAttachment, IntegrationNetworkAttachmentKind,
    IntegrationNetworkEnforcementRequest,
    IntegrationNetworkLease, IntegrationNetworkUsage,
)
from fam_os.schemas import dumps_document, loads_document
from fam_os.supervisor import (
    NetworkAttachmentKind, NetworkEnforcementSpec, SupervisorCallContext,
)


class IntegrationNetworkBrokerHandler:
    def __init__(
        self, controller, state: NetworkBrokerStateStore, clock, verifier,
        authorities,
    ) -> None:
        self._controller = controller
        self._state = state
        self._clock = clock
        self._verifier = verifier
        self._authorities = authorities

    def open(self, request: IntegrationNetworkEnforcementRequest):
        self._verifier.verify(request)
        identity = self._state.begin(request)
        self._authorities.admit(request, identity)
        context, spec = _supervisor_request(request, identity)
        lease = None
        try:
            lease = self._controller.open(context, spec, self._clock())
            result = _core_lease(request, lease)
        except BaseException as open_error:
            cleanup_error = None
            try:
                if lease is not None:
                    usage = self._controller.close(context, identity)
                    self._state.finalize(
                        identity, _core_usage(request, usage), "compensated",
                    )
            except BaseException as error:
                cleanup_error = error
            finally:
                self._authorities.retire(identity)
            if cleanup_error is not None:
                raise RuntimeError(
                    "network broker open compensation is incomplete"
                ) from cleanup_error
            raise open_error
        try:
            self._state.activate(request, result)
        except BaseException as activation_error:
            try:
                usage = self._controller.close(context, identity)
                self._state.finalize(
                    identity, _core_usage(request, usage), "compensated",
                )
            except BaseException as cleanup_error:
                raise RuntimeError(
                    "network broker activation compensation is incomplete"
                ) from cleanup_error
            finally:
                self._authorities.retire(identity)
            raise activation_error
        return result

    def observe(self, lease: IntegrationNetworkLease):
        document = self._state.require_lease(lease)
        request = _request(document)
        context, _spec = _supervisor_request(request, lease.enforcement_id)
        usage = _core_usage(
            request, self._controller.observe(context, lease.enforcement_id),
        )
        if usage.finalized:
            self._state.finalize(lease.enforcement_id, usage, "closed")
            self._authorities.retire(lease.enforcement_id)
        return usage

    def close(self, lease: IntegrationNetworkLease):
        document = self._state.require_lease(lease)
        request = _request(document)
        context, _spec = _supervisor_request(request, lease.enforcement_id)
        usage = _core_usage(
            request, self._controller.close(context, lease.enforcement_id),
        )
        self._state.finalize(lease.enforcement_id, usage, "closed")
        self._authorities.retire(lease.enforcement_id)
        return usage

    def recover(self, request: IntegrationNetworkEnforcementRequest):
        self._verifier.verify(request)
        identity = network_enforcement_id(request.environment_id)
        self._authorities.admit(request, identity)
        try:
            try:
                document = self._state.load(identity)
            except FileNotFoundError:
                self._state.begin(request)
                document = self._state.load(identity)
            if document["request"] != dumps_document(request):
                raise PermissionError("network recovery request differs from intent")
            if document["state"] in {"closed", "recovered", "compensated"}:
                return _usage(document)
            context, spec = _supervisor_request(request, identity)
            usage = _core_usage(request, self._controller.recover(context, spec))
            self._state.finalize(identity, usage, "recovered")
            return usage
        finally:
            self._authorities.retire(identity)


def _supervisor_request(request, identity):
    context = SupervisorCallContext(
        request.request_id, request.principal_id,
        request.session_id, request.authority_ref,
    )
    kinds = tuple(NetworkAttachmentKind(item.value) for item in request.attachment_kinds)
    digest = hashlib.sha256(dumps_document(request).encode()).hexdigest()
    spec = NetworkEnforcementSpec(
        identity, request.environment_id, kinds, request.destinations,
        request.maximum_network_bytes, request.expires_at, digest,
    )
    return context, spec


def _core_lease(request, lease):
    return IntegrationNetworkLease(
        lease.enforcement_id, request.request_id, request.environment_id,
        request.principal_id, request.session_id, request.authority_ref,
        tuple(IntegrationNetworkAttachment(
            IntegrationNetworkAttachmentKind(item.kind.value),
            item.attachment_reference, item.proxy_uri,
        ) for item in lease.attachments), lease.destinations,
        lease.maximum_network_bytes, lease.issued_at, lease.expires_at,
        lease.evidence_digest,
    )


def _core_usage(request, usage):
    return IntegrationNetworkUsage(
        usage.enforcement_id, request.environment_id, usage.destinations,
        usage.transmitted_bytes, usage.received_bytes,
        usage.maximum_network_bytes, usage.quota_exceeded, usage.finalized,
        usage.observed_at, usage.evidence_digest,
    )


def _request(document):
    value = loads_document(document["request"])
    if not isinstance(value, IntegrationNetworkEnforcementRequest):
        raise ValueError("network broker state request is invalid")
    return value


def _usage(document):
    value = loads_document(document["usage"])
    if not isinstance(value, IntegrationNetworkUsage):
        raise ValueError("network broker terminal usage is invalid")
    return value
