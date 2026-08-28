import unittest

from fam_os.core.agent import AgentAuthorityProfile, AgentToolRegistry
from fam_os.product.agent_application_tools import ApplicationAgentTools


class _Provider:
    def entries(self):
        return ()


class ApplicationTestAuthorityTests(unittest.TestCase):
    def test_application_test_profile_receives_scoped_action_tool(self):
        registry = AgentToolRegistry()
        ApplicationAgentTools(
            lambda: _Provider(), "owner",
            profile=AgentAuthorityProfile.APPLICATION_TEST,
        ).register(registry)
        names = {item.tool_id for item in registry.descriptors(AgentAuthorityProfile.APPLICATION_TEST)}
        self.assertIn("act_on_application", names)


if __name__ == "__main__":
    unittest.main()
