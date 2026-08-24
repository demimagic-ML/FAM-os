"""Core-facing provider over the live connector registry and broker."""


class LiveApplicationProvider:
    def __init__(self, registry, broker, local_transports=()) -> None:
        self._registry = registry
        self._broker = broker
        self._local_transports = (
            (local_transports,)
            if hasattr(local_transports, "transport") else tuple(local_transports)
        )

    def capability(self, instance_id: str, capability_id: str):
        entry = self._registry.lookup(instance_id, capability_id)
        return entry if entry is not None and entry.available else None

    def entries(self):
        return tuple(item for item in self._registry.entries() if item.available)

    def observe(self, request):
        connector_id = self._connector(request.instance_id)
        transport = self._local_transport(connector_id)
        if transport is not None:
            return transport.observe(request)
        return self._broker.observe(connector_id, request)

    def observation_parameters(
        self, instance_id: str, capability_id: str, prompt: str,
        resource_uri: str | None,
    ) -> dict[str, object]:
        connector_id = self._connector(instance_id)
        transport = self._local_transport(connector_id)
        if transport is not None and hasattr(transport, "observation_parameters"):
            return transport.observation_parameters(
                capability_id, prompt, resource_uri,
            )
        if capability_id == "vscode.editor.selection":
            return {"maximum_characters": 16_384}
        return {}

    def prepare_action(self, request):
        connector_id = self._connector(request.instance_id)
        transport = self._local_transport(connector_id)
        if transport is not None:
            return transport.prepare_action(request)
        return self._broker.prepare_action(connector_id, request)

    def execute_action(self, proposal, confirmation):
        if confirmation.proposal_id != proposal.proposal_id:
            raise ValueError("action confirmation does not match proposal")
        connector_id = self._connector(proposal.request.instance_id)
        transport = self._local_transport(connector_id)
        if transport is not None:
            return transport.execute_action(proposal, confirmation)
        return self._broker.execute_action(connector_id, confirmation)

    def _local_transport(self, connector_id: str):
        for lifecycle in self._local_transports:
            transport = lifecycle.transport(connector_id)
            if transport is not None:
                return transport
        return None

    def _connector(self, instance_id: str) -> str:
        entries = self._registry.entries(instance_id)
        available = tuple(item for item in entries if item.available)
        connector_ids = {item.connector_id for item in available}
        if len(connector_ids) != 1:
            raise RuntimeError("application instance has no unique live connector")
        return next(iter(connector_ids))
