"""One shared quota across Linux-namespace and Docker network attachments."""

from datetime import datetime, timezone
import hashlib
import json

from fam_os.adapters.integration.network_enforcement_state import NetworkEnforcementState
from fam_os.supervisor import NetworkEnforcementLease, NetworkUsageSnapshot
from fam_os.supervisor.network_proxy import ProxyUsage


class MultiAttachmentNetworkEnforcementAdapter:
    def __init__(self, state_root, proxy_runtime, resources, clock=None):
        self._root, self._proxy = state_root, proxy_runtime
        self._resources = dict(resources)
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def open(self, spec):
        if any(kind not in self._resources for kind in spec.attachment_kinds):
            raise PermissionError("requested network attachment provider is unavailable")
        state = NetworkEnforcementState(self._root, spec.enforcement_id)
        state.claim(spec)
        resources = []
        try:
            for kind in spec.attachment_kinds:
                provider = self._resources[kind]
                resources.append((provider, provider.for_identity(spec.enforcement_id)))
                resources[-1] = (provider, provider.create(spec))
            state.stage("resources")
            addresses = self._proxy.start_many(
                spec.enforcement_id,
                tuple(resource.bind_host for _provider, resource in resources),
                spec.destinations, spec.maximum_network_bytes, spec.expires_at,
                state.record_usage,
            )
            state.stage("proxy", proxy_addresses=addresses)
            attachments = []
            for (provider, resource), (_host, port) in zip(resources, addresses):
                provider.activate(resource, port)
                attachments.append(provider.attachment(resource, port))
            state.stage("ready")
        except BaseException as open_error:
            errors = []
            try: self._proxy.recover(spec.enforcement_id, _state_usage(state))
            except BaseException as error: errors.append(error)
            try: self._remove(resources)
            except BaseException as error: errors.append(error)
            if errors:
                raise RuntimeError("network enforcement compensation is incomplete") from errors[-1]
            state.stage("recovered")
            raise open_error
        return NetworkEnforcementLease(
            spec.enforcement_id, tuple(attachments), spec.destinations,
            spec.maximum_network_bytes, self._clock(), spec.expires_at,
            _lease_digest(spec, attachments),
        )

    def observe(self, enforcement_id):
        state = NetworkEnforcementState(self._root, enforcement_id)
        if hasattr(self._proxy, "active") and not self._proxy.active(enforcement_id):
            return self.close(enforcement_id)
        usage = self._proxy.snapshot(enforcement_id); state.record_usage(usage)
        if usage.quota_exceeded:
            return self.close(enforcement_id)
        return _snapshot(enforcement_id, state.load(), False, self._clock())

    def close(self, enforcement_id):
        state = NetworkEnforcementState(self._root, enforcement_id)
        document = state.load()
        usage, errors = None, []
        try:
            usage = self._proxy.stop(enforcement_id); state.record_usage(usage)
        except BaseException as error: errors.append(error)
        try: self._remove(self._resources_for(enforcement_id, document))
        except BaseException as error: errors.append(error)
        if errors:
            raise RuntimeError("network enforcement cleanup is incomplete") from errors[-1]
        state.stage("closed")
        return _snapshot(enforcement_id, state.load(), True, self._clock())

    def recover(self, spec):
        state = NetworkEnforcementState(self._root, spec.enforcement_id)
        try:
            document = state.load()
        except FileNotFoundError:
            usage, document = ProxyUsage((), 0, 0, False), None
        else:
            if (
                document["request_digest"] != spec.request_digest
                or tuple(document["attachment_kinds"])
                != tuple(item.value for item in spec.attachment_kinds)
            ):
                raise PermissionError("network recovery request differs from journal")
            usage = _state_usage(state)
        errors = []
        try: usage = self._proxy.recover(spec.enforcement_id, usage)
        except BaseException as error: errors.append(error)
        resources = [
            (self._resources[kind], self._resources[kind].for_identity(spec.enforcement_id))
            for kind in spec.attachment_kinds if kind in self._resources
        ]
        try: self._remove(resources)
        except BaseException as error: errors.append(error)
        if errors:
            raise RuntimeError("network enforcement recovery is incomplete") from errors[-1]
        if document is not None:
            state.record_usage(usage); state.stage("recovered"); document = state.load()
        else:
            document = _fallback_document(spec, usage)
        return _snapshot(spec.enforcement_id, document, True, self._clock())

    def _resources_for(self, identity, document):
        from fam_os.supervisor import NetworkAttachmentKind
        return [
            (self._resources[kind], self._resources[kind].for_identity(identity))
            for kind in (NetworkAttachmentKind(value) for value in document["attachment_kinds"])
        ]

    @staticmethod
    def _remove(resources):
        errors = []
        for provider, resource in reversed(resources):
            try: provider.remove(resource)
            except BaseException as error: errors.append(error)
        if errors:
            raise RuntimeError("network attachment cleanup is incomplete") from errors[-1]


def _state_usage(state):
    value = state.load()
    return ProxyUsage(
        tuple(value["observed_destinations"]), value["transmitted_bytes"],
        value["received_bytes"], value["quota_exceeded"],
    )


def _snapshot(identity, value, finalized, instant):
    return NetworkUsageSnapshot(
        identity, tuple(value["observed_destinations"]), value["transmitted_bytes"],
        value["received_bytes"], value["maximum_network_bytes"],
        value["quota_exceeded"], finalized, instant,
        hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest(),
    )


def _fallback_document(spec, usage):
    return {
        "observed_destinations": list(usage.destinations),
        "transmitted_bytes": usage.transmitted_bytes,
        "received_bytes": usage.received_bytes,
        "maximum_network_bytes": spec.maximum_network_bytes,
        "quota_exceeded": usage.quota_exceeded,
    }


def _lease_digest(spec, attachments):
    values = [spec.request_digest]
    for item in attachments:
        values.extend((item.kind.value, item.attachment_reference, item.proxy_uri))
    return hashlib.sha256("\0".join(values).encode()).hexdigest()
