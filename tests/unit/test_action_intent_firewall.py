import unittest
from pathlib import Path

from fam_os.applications import WORKSPACE_PATCH_CAPABILITY
from fam_os.core.production.action_intent import (
    ActionIntentFirewall, CREATE_DIRECTORY_CAPABILITY,
    recognize_engineering_authorities,
)
from fam_os.core.engineering import EngineeringAuthority


class ActionIntentFirewallTests(unittest.TestCase):
    def test_named_directory_continues_with_parent_path(self):
        firewall = ActionIntentFirewall()
        first = firewall.inspect(
            "Create a new folder, name it Ivan, no content", "session-a",
        )
        self.assertTrue(first.action_shaped)
        self.assertTrue(first.needs_input)
        self.assertEqual(CREATE_DIRECTORY_CAPABILITY, first.capability_id)

        continued = firewall.inspect("/home/example/Desktop", "session-a")

        self.assertEqual(
            "/home/example/Desktop/Ivan", str(continued.target_path),
        )
        self.assertFalse(continued.needs_input)

    def test_exact_target_is_resolved_without_follow_up(self):
        decision = ActionIntentFirewall().inspect(
            "Please create directory /home/example/Desktop/Ivan", "session-b",
        )
        self.assertEqual(
            "/home/example/Desktop/Ivan", str(decision.target_path),
        )

    def test_other_direct_machine_action_is_fail_closed(self):
        decision = ActionIntentFirewall().inspect(
            "Delete /home/example/Desktop/important.txt", "session-c",
        )
        self.assertTrue(decision.action_shaped)
        self.assertIsNone(decision.capability_id)
        self.assertIn("No action was attempted", decision.safe_message)

    def test_explanation_is_not_mistaken_for_action_authority(self):
        decision = ActionIntentFirewall().inspect(
            "Explain how to create a directory in Python", "session-d",
        )
        self.assertFalse(decision.action_shaped)

    def test_generated_code_request_is_not_a_machine_action(self):
        decision = ActionIntentFirewall().inspect(
            "Write Python code for add", "session-e",
        )
        self.assertFalse(decision.action_shaped)
        benchmark = ActionIntentFirewall().inspect(
            "Implement exactly one Python function named stable_topological_sort(graph). "
            "Return only one complete Python code block under 50 lines.",
            "session-benchmark",
        )
        self.assertFalse(benchmark.action_shaped)

    def test_common_action_paraphrases_cannot_bypass_capability_resolution(self):
        prompts = (
            "Could you please create directory /home/example/New",
            "I would like you to create a folder at /home/example/New",
            "Go ahead and delete /home/example/old.txt",
            "FAM, restart the application",
            "Send an email to the owner",
            "Download the package",
        )
        firewall = ActionIntentFirewall()
        for index, prompt in enumerate(prompts):
            with self.subTest(prompt=prompt):
                decision = firewall.inspect(prompt, f"paraphrase-{index}")
                self.assertTrue(decision.action_shaped)

    def test_content_creation_without_machine_target_remains_inference(self):
        decision = ActionIntentFirewall().inspect(
            "Create a poem about local AI", "session-f",
        )
        self.assertFalse(decision.action_shaped)

    def test_use_interface_wording_without_machine_target_remains_inference(self):
        decision = ActionIntentFirewall().inspect(
            "Use the MCP bridge.", "session-interface",
        )

        self.assertFalse(decision.action_shaped)

    def test_plan_and_implement_resolves_only_to_bounded_workspace_patch(self):
        decision = ActionIntentFirewall().inspect(
            "Create a plan and implement it", "session-workspace",
            Path("/home/example/project"),
        )

        self.assertTrue(decision.action_shaped)
        self.assertEqual(WORKSPACE_PATCH_CAPABILITY, decision.capability_id)
        self.assertIn("preview and owner approval", decision.safe_message)

    def test_explaining_implementation_is_not_a_workspace_action(self):
        decision = ActionIntentFirewall().inspect(
            "Explain how to implement the plan", "session-explain",
            Path("/home/example/project"),
        )

        self.assertFalse(decision.action_shaped)

    def test_every_engineering_authority_is_recognized_without_becoming_a_grant(self):
        prompts = {
            EngineeringAuthority.OBSERVE: "Inspect and read the workspace",
            EngineeringAuthority.PROPOSE: "Draft a plan",
            EngineeringAuthority.MODIFY: "Edit the file",
            EngineeringAuthority.EXECUTE: "Run the test command",
            EngineeringAuthority.NETWORK: "Fetch from the package registry",
            EngineeringAuthority.PUBLISH: "Publish and push the release",
            EngineeringAuthority.RAW_SHELL: "Run this raw shell command",
            EngineeringAuthority.HOST_ADMIN: "Use sudo for host-wide service setup",
            EngineeringAuthority.SECRET_USE: "Use the API key credential",
            EngineeringAuthority.GLOBAL_INSTALL: "Install globally with apt install",
            EngineeringAuthority.PRODUCTION_MUTATE: "Deploy to production",
            EngineeringAuthority.POLICY_CHANGE: "Change the verification policy",
            EngineeringAuthority.PROTECTED_REF_WRITE: "Force-push to a protected branch",
            EngineeringAuthority.SELF_UPDATE: "Update FAM_OS with a self-update",
        }
        for authority, prompt in prompts.items():
            with self.subTest(authority=authority.value):
                self.assertIn(authority, recognize_engineering_authorities(prompt))

    def test_high_risk_intent_is_reported_but_not_resolved_to_a_capability(self):
        decision = ActionIntentFirewall().inspect(
            "Run sudo to force-push to the protected main branch", "session-risk",
        )
        self.assertTrue(decision.action_shaped)
        self.assertIsNone(decision.capability_id)
        self.assertIn(
            EngineeringAuthority.HOST_ADMIN,
            decision.required_engineering_authorities,
        )
        self.assertIn(
            EngineeringAuthority.PROTECTED_REF_WRITE,
            decision.required_engineering_authorities,
        )

    def test_natural_engineering_language_maps_to_exact_non_granting_authorities(self):
        authorities = recognize_engineering_authorities(
            "Analyze this repository, fix the authentication bug, refactor the "
            "session service, and run the tests and type-checker."
        )

        self.assertEqual(
            (
                EngineeringAuthority.OBSERVE,
                EngineeringAuthority.PROPOSE,
                EngineeringAuthority.MODIFY,
                EngineeringAuthority.EXECUTE,
            ),
            authorities,
        )


if __name__ == "__main__":
    unittest.main()
