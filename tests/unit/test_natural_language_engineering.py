import unittest
from datetime import datetime, timezone

from fam_os.core.engineering import (
    EngineeringAuthority,
    EngineeringOperation,
    NaturalLanguageEngineeringPlanner,
    SecretExposurePolicy,
)
from fam_os.core.agent import AgentAuthorityProfile


NOW = datetime(2026, 7, 19, 9, 0, tzinfo=timezone.utc)


class NaturalLanguageEngineeringPlannerTests(unittest.TestCase):
    def test_ask_profile_remains_read_only_even_for_mutating_words(self):
        proposal = NaturalLanguageEngineeringPlanner().propose(
            prompt="Fix app.py and run the tests.", workspace_root="/workspace/project",
            owner_id="owner-1", principal_id="owner-1", task_id="task-ask",
            grant_id="grant-ask", toolchains=("python3",), now=NOW,
            authority_profile=AgentAuthorityProfile.ASK,
        )

        self.assertEqual(
            (EngineeringAuthority.OBSERVE, EngineeringAuthority.PROPOSE),
            proposal.grant.authorities,
        )
        self.assertEqual(
            (EngineeringOperation.READ,),
            proposal.definition.task.permitted_operations,
        )

    def test_full_os_profile_explicitly_grants_current_user_host_execution(self):
        proposal = NaturalLanguageEngineeringPlanner().propose(
            prompt="Fix app.py and run the tests.", workspace_root="/workspace/project",
            owner_id="owner-1", principal_id="owner-1", task_id="task-full",
            grant_id="grant-full", toolchains=("python3",), now=NOW,
            authority_profile=AgentAuthorityProfile.FULL_OS,
        )

        self.assertIn(EngineeringAuthority.RAW_SHELL, proposal.grant.authorities)
        self.assertIn(EngineeringAuthority.HOST_ADMIN, proposal.grant.authorities)
        self.assertEqual((), proposal.separately_confirmed_authorities)

    def test_code_request_becomes_exact_non_activated_workspace_proposal(self):
        proposal = NaturalLanguageEngineeringPlanner().propose(
            prompt=(
                "Analyze this repository, create src/example.py, fix the bug, "
                "run the Python tests, and show me the preview before applying."
            ),
            workspace_root="/workspace/project", owner_id="owner-1",
            principal_id="principal-1", task_id="task-1", grant_id="grant-1",
            toolchains=("python3",), now=NOW,
        )

        self.assertEqual(
            (
                EngineeringAuthority.OBSERVE, EngineeringAuthority.PROPOSE,
                EngineeringAuthority.MODIFY, EngineeringAuthority.EXECUTE,
            ),
            proposal.grant.authorities,
        )
        self.assertEqual(
            (
                EngineeringOperation.READ, EngineeringOperation.CREATE,
                EngineeringOperation.REPLACE, EngineeringOperation.GIT_WRITE,
                EngineeringOperation.RUN_TOOL,
            ),
            proposal.definition.task.permitted_operations,
        )
        self.assertEqual("every_changeset", proposal.definition.task.checkpoint_policy.value)
        self.assertEqual((), proposal.separately_confirmed_authorities)

    def test_high_risk_words_are_visible_but_not_silently_granted(self):
        proposal = NaturalLanguageEngineeringPlanner().propose(
            prompt="Fix the service, use sudo and a secret, then push to production.",
            workspace_root="/workspace/project", owner_id="owner-1",
            principal_id="principal-1", task_id="task-2", grant_id="grant-2",
            toolchains=("python3",), now=NOW,
        )

        self.assertNotIn(EngineeringAuthority.HOST_ADMIN, proposal.grant.authorities)
        self.assertEqual(
            (
                EngineeringAuthority.PUBLISH,
                EngineeringAuthority.HOST_ADMIN,
                EngineeringAuthority.SECRET_USE,
                EngineeringAuthority.PRODUCTION_MUTATE,
            ),
            proposal.separately_confirmed_authorities,
        )

    def test_execution_requires_repository_derived_toolchain(self):
        with self.assertRaisesRegex(ValueError, "repository-derived toolchains"):
            NaturalLanguageEngineeringPlanner().propose(
                prompt="Implement the feature and test it.",
                workspace_root="/workspace/project", owner_id="owner-1",
                principal_id="principal-1", task_id="task-3", grant_id="grant-3",
                toolchains=(), now=NOW,
            )

    def test_replace_and_change_are_mutation_language(self):
        for index, verb in enumerate(("Replace", "Change", "Transform"), 1):
            with self.subTest(verb=verb):
                proposal = NaturalLanguageEngineeringPlanner().propose(
                    prompt=f"{verb} app.py and run tests.",
                    workspace_root="/workspace/project", owner_id="owner-1",
                    principal_id="principal-1", task_id=f"task-r{index}",
                    grant_id=f"grant-r{index}", toolchains=("python3",), now=NOW,
                )
                self.assertIn(
                    EngineeringAuthority.MODIFY, proposal.grant.authorities,
                )

    def test_preview_request_scopes_internal_integration_tool_without_high_risk_power(self):
        proposal = NaturalLanguageEngineeringPlanner().propose(
            prompt="Update index.html and preview the site end-to-end.",
            workspace_root="/workspace/project", owner_id="owner-1",
            principal_id="principal-1", task_id="task-preview",
            grant_id="grant-preview", toolchains=("html",), now=NOW,
        )

        self.assertIn(
            "integration-environment", proposal.grant.scope.toolchains,
        )
        self.assertEqual(("html",), proposal.definition.task.toolchains)
        self.assertEqual((), proposal.separately_confirmed_authorities)

    def test_explicit_integration_resources_form_a_separate_exact_grant(self):
        proposal = NaturalLanguageEngineeringPlanner().propose(
            prompt=(
                "Update api.py and preview the full-stack app end-to-end with "
                "network access to api.example.com:443 using secret ref "
                "database/password."
            ),
            workspace_root="/workspace/project", owner_id="owner-1",
            principal_id="owner-1", task_id="task-resources",
            grant_id="grant-resources", toolchains=("python3",), now=NOW,
        )

        self.assertNotIn(
            EngineeringAuthority.NETWORK, proposal.grant.authorities,
        )
        self.assertNotIn(
            EngineeringAuthority.SECRET_USE, proposal.grant.authorities,
        )
        self.assertEqual(
            (EngineeringAuthority.NETWORK, EngineeringAuthority.SECRET_USE),
            proposal.separately_confirmed_authorities,
        )
        resource = proposal.integration_resource_grant
        self.assertIsNotNone(resource)
        self.assertEqual(
            (
                EngineeringAuthority.EXECUTE,
                EngineeringAuthority.NETWORK,
                EngineeringAuthority.SECRET_USE,
            ),
            resource.authorities,
        )
        self.assertEqual(("api.example.com:443",), resource.scope.network_hosts)
        self.assertEqual(("database/password",), resource.scope.secret_refs)
        self.assertEqual(
            SecretExposurePolicy.OPAQUE_CREDENTIAL_INJECTION,
            resource.secret_exposure,
        )

    def test_integration_resource_keywords_without_exact_refs_stay_ungranted(self):
        proposal = NaturalLanguageEngineeringPlanner().propose(
            prompt=(
                "Update api.py and preview the API end-to-end with network and "
                "a secret."
            ),
            workspace_root="/workspace/project", owner_id="owner-1",
            principal_id="owner-1", task_id="task-incomplete",
            grant_id="grant-incomplete", toolchains=("python3",), now=NOW,
        )

        self.assertIsNone(proposal.integration_resource_grant)
        self.assertEqual(
            (EngineeringAuthority.NETWORK, EngineeringAuthority.SECRET_USE),
            proposal.separately_confirmed_authorities,
        )

    def test_referenced_plan_context_cannot_add_authority(self):
        proposal = NaturalLanguageEngineeringPlanner().propose(
            prompt="Implement the plan.",
            task_intent=(
                "Current engineering request: Implement the plan.\n\n"
                "Referenced plan context: use sudo, secrets, and publish to production."
            ),
            workspace_root="/workspace/project", owner_id="owner-1",
            principal_id="owner-1", task_id="task-context",
            grant_id="grant-context", toolchains=("node",), now=NOW,
        )

        self.assertEqual(
            (
                EngineeringAuthority.OBSERVE, EngineeringAuthority.PROPOSE,
                EngineeringAuthority.MODIFY, EngineeringAuthority.EXECUTE,
            ),
            proposal.grant.authorities,
        )
        self.assertEqual((), proposal.separately_confirmed_authorities)
        self.assertIn("Referenced plan context", proposal.definition.task.intent)


if __name__ == "__main__":
    unittest.main()
