import unittest

from fam_os.product.composition.live_application_provider import LiveApplicationProvider
from tests.contract.schema_application_fixtures import (
    action_confirmation,
    action_proposal,
    connector_registration,
    observation_request,
    observation_result,
)


class _Registry:
    def __init__(self, registration):
        self.registration = registration

    def lookup(self, instance_id, capability_id):
        return next((
            entry for entry in self.registration.capabilities
            if (entry.instance_id, entry.capability_id) == (instance_id, capability_id)
        ), None)

    def entries(self, instance_id=None):
        return tuple(
            entry for entry in self.registration.capabilities
            if instance_id is None or entry.instance_id == instance_id
        )


class _Broker:
    def __init__(self):
        self.calls = []

    def observe(self, connector_id, request):
        self.calls.append(("observe", connector_id, request))
        return observation_result()

    def prepare_action(self, connector_id, request):
        self.calls.append(("prepare", connector_id, request))
        return action_proposal()

    def execute_action(self, connector_id, confirmation):
        self.calls.append(("execute", connector_id, confirmation))
        return object()


class _McpClients:
    def __init__(self, connector_id, transport):
        self.connector_id = connector_id
        self.transport_value = transport

    def transport(self, connector_id):
        return self.transport_value if connector_id == self.connector_id else None


class _McpTransport:
    def __init__(self):
        self.calls = []

    def observe(self, request):
        self.calls.append(("observe", request))
        return observation_result()

    def observation_parameters(self, capability_id, prompt, resource_uri):
        self.calls.append(("parameters", capability_id, prompt, resource_uri))
        return {"query": prompt}

    def prepare_action(self, request):
        self.calls.append(("prepare", request))
        return action_proposal()

    def execute_action(self, proposal, confirmation):
        self.calls.append(("execute", proposal, confirmation))
        return object()


class LiveApplicationProviderTests(unittest.TestCase):
    def test_routes_all_operations_to_registered_instance_connector(self):
        registration = connector_registration()
        broker = _Broker()
        provider = LiveApplicationProvider(_Registry(registration), broker)
        request = observation_request()
        action = action_proposal()
        self.assertIsNotNone(provider.capability(
            action.request.instance_id, action.request.capability_id,
        ))
        self.assertEqual(observation_result(), provider.observe(request))
        provider.prepare_action(action.request)
        provider.execute_action(action, action_confirmation())
        self.assertEqual(
            ["connector-vscode"] * 3,
            [call[1] for call in broker.calls],
        )

    def test_routes_mcp_entries_to_the_mcp_transport_not_native_broker(self):
        registration = connector_registration()
        broker = _Broker()
        transport = _McpTransport()
        provider = LiveApplicationProvider(
            _Registry(registration), broker,
            _McpClients(registration.connector_id, transport),
        )
        action = action_proposal()
        parameters = provider.observation_parameters(
            action.request.instance_id, action.request.capability_id,
            "search terms", None,
        )
        self.assertEqual({"query": "search terms"}, parameters)
        provider.observe(observation_request())
        provider.prepare_action(action.request)
        provider.execute_action(action, action_confirmation())
        self.assertEqual([], broker.calls)
        self.assertEqual(["parameters", "observe", "prepare", "execute"], [
            call[0] for call in transport.calls
        ])

    def test_native_defaults_do_not_disclose_prompt_to_broker(self):
        registration = connector_registration()
        broker = _Broker()
        provider = LiveApplicationProvider(_Registry(registration), broker)
        entry = registration.capabilities[0]
        parameters = provider.observation_parameters(
            entry.instance_id, entry.capability_id, "private prompt", None,
        )
        self.assertEqual({}, parameters)
        self.assertEqual([], broker.calls)


if __name__ == "__main__":
    unittest.main()
