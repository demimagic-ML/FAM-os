import json
import unittest
from types import SimpleNamespace

from fam_os.core.agent import (
    AgentAuthorityProfile,
    AgentToolCall,
    AgentToolRegistry,
)
from fam_os.product.agent_application_tools import ApplicationAgentTools


class ApplicationAgentToolsTests(unittest.TestCase):
    def test_discovery_and_observation_use_live_dynamic_provider(self):
        provider = _Provider()
        registry = AgentToolRegistry()
        ApplicationAgentTools(lambda: provider, "owner-1").register(registry)

        listed = registry.invoke(
            AgentToolCall("call-1", "list_application_capabilities", {}, "Discover."),
            AgentAuthorityProfile.ASK,
        )
        observed = registry.invoke(
            AgentToolCall("call-2", "observe_application", {
                "instance_id": "browser-1", "capability_id": "browser.tabs",
                "parameters": {"limit": 5},
            }, "Observe browser tabs."),
            AgentAuthorityProfile.ASK,
        )

        self.assertEqual(1, json.loads(listed.output)["count"])
        self.assertEqual("browser.tabs", json.loads(listed.output)["capabilities"][0]["capability_id"])
        self.assertTrue(json.loads(observed.output)["observed"])
        self.assertEqual({"limit": 5}, dict(provider.observation.parameters))

    def test_application_actions_require_full_os_and_return_receipt(self):
        provider = _Provider()
        registry = AgentToolRegistry()
        ApplicationAgentTools(lambda: provider, "owner-1").register(registry)
        call = AgentToolCall("call-1", "act_on_application", {
            "instance_id": "browser-1", "capability_id": "browser.open",
            "summary": "Open the requested page.",
            "parameters": {"url": "https://example.invalid"},
        }, "Use the registered browser action.")

        denied = registry.invoke(call, AgentAuthorityProfile.WORKSPACE)
        executed = registry.invoke(call, AgentAuthorityProfile.FULL_OS)

        self.assertFalse(denied.succeeded)
        self.assertTrue(executed.succeeded)
        self.assertEqual("verified", json.loads(executed.output)["status"])
        self.assertEqual("owner-1", provider.confirmation.decided_by)


class _Provider:
    def __init__(self):
        self.observation = None
        self.confirmation = None

    def entries(self):
        def value(item):
            return SimpleNamespace(value=item)

        capability = SimpleNamespace(
            display_name="Browser tabs", description="List open browser tabs.",
            kind=value("observation"), required_authority=value("observe"),
            confirmation=value("not_required"), reversibility=value("not_applicable"),
        )
        return (SimpleNamespace(
            instance_id="browser-1", application_id="browser",
            capability_id="browser.tabs", capability=capability,
            resource_scopes=("browser://tabs",),
        ),)

    def observe(self, request):
        self.observation = request
        return {"observed": True, "tabs": ["example"]}

    def prepare_action(self, request):
        self.action = request
        return SimpleNamespace(proposal_id="proposal-1")

    def execute_action(self, _proposal, confirmation):
        self.confirmation = confirmation
        return {"status": "verified", "url": "https://example.invalid"}


if __name__ == "__main__":
    unittest.main()
