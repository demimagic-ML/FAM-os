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
    def test_plain_folder_mutation_does_not_require_git_delivery(self):
        proposal = NaturalLanguageEngineeringPlanner().propose(
            prompt="Create the assistant and run its tests.",
            workspace_root="/workspace/folder", owner_id="owner-1",
            principal_id="owner-1", task_id="task-plain",
            grant_id="grant-plain", toolchains=("python3",), now=NOW,
            git_available=False,
        )

        self.assertIn(
            EngineeringOperation.REPLACE,
            proposal.definition.task.permitted_operations,
        )
        self.assertNotIn(
            EngineeringOperation.GIT_WRITE,
            proposal.definition.task.permitted_operations,
        )

    def test_ask_profile_remains_read_only_even_for_mutating_words(self):
        proposal = NaturalLanguageEngineeringPlanner().propose(
            prompt="Fix app.py, download dependencies, and run the tests.",
            workspace_root="/workspace/project",
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
        self.assertIn(EngineeringAuthority.NETWORK, proposal.grant.authorities)
        self.assertIn(
            EngineeringAuthority.APPLICATION_TEST, proposal.grant.authorities,
        )
        self.assertEqual((), proposal.separately_confirmed_authorities)

    def test_application_test_profile_is_candidate_and_local_app_scoped(self):
        proposal = NaturalLanguageEngineeringPlanner().propose(
            prompt="Test the calculator application in a browser.",
            workspace_root="/workspace/project", owner_id="owner-1",
            principal_id="owner-1", task_id="task-app-test",
            grant_id="grant-app-test", toolchains=("node",), now=NOW,
            authority_profile=AgentAuthorityProfile.APPLICATION_TEST,
        )

        self.assertIn(
            EngineeringAuthority.APPLICATION_TEST, proposal.grant.authorities,
        )
        self.assertIn(EngineeringAuthority.EXECUTE, proposal.grant.authorities)
        self.assertIn(
            EngineeringOperation.RUN_TOOL,
            proposal.definition.task.permitted_operations,
        )
        self.assertNotIn(EngineeringAuthority.HOST_ADMIN, proposal.grant.authorities)
        self.assertNotIn(EngineeringAuthority.RAW_SHELL, proposal.grant.authorities)

    def test_application_test_localhost_and_network_diagnostics_need_no_network_grant(self):
        proposal = NaturalLanguageEngineeringPlanner().propose(
            prompt=(
                "Start http://127.0.0.1:4173, test the calculator, verify there "
                "are no failed network requests, and save a network summary."
            ),
            workspace_root="/workspace/project", owner_id="owner-1",
            principal_id="owner-1", task_id="task-app-local",
            grant_id="grant-app-local", toolchains=("node",), now=NOW,
            authority_profile=AgentAuthorityProfile.APPLICATION_TEST,
        )

        self.assertNotIn(
            EngineeringAuthority.NETWORK,
            proposal.separately_confirmed_authorities,
        )

    def test_finish_the_implementation_is_classified_as_mutation(self):
        proposal = NaturalLanguageEngineeringPlanner().propose(
            prompt=(
                "Analyze the calculator, check what is already done, and continue "
                "to finish the implementation."
            ),
            workspace_root="/workspace/project", owner_id="owner-1",
            principal_id="owner-1", task_id="task-finish",
            grant_id="grant-finish", toolchains=("python",), now=NOW,
            authority_profile=AgentAuthorityProfile.WORKSPACE,
        )

        self.assertIn(EngineeringAuthority.MODIFY, proposal.grant.authorities)
        self.assertIn(
            EngineeringOperation.REPLACE,
            proposal.definition.task.permitted_operations,
        )

    def test_full_os_is_a_complete_execution_profile_without_keyword_routing(self):
        proposal = NaturalLanguageEngineeringPlanner().propose(
            prompt="Continue with the selected project.",
            workspace_root="/workspace/project", owner_id="owner-1",
            principal_id="owner-1", task_id="task-full-os",
            grant_id="grant-full-os", toolchains=("python",), now=NOW,
            authority_profile=AgentAuthorityProfile.FULL_OS,
        )

        self.assertIn(EngineeringAuthority.MODIFY, proposal.grant.authorities)
        self.assertIn(EngineeringAuthority.EXECUTE, proposal.grant.authorities)
        self.assertIn(
            EngineeringOperation.REPLACE,
            proposal.definition.task.permitted_operations,
        )
        self.assertIn(
            EngineeringOperation.RUN_TOOL,
            proposal.definition.task.permitted_operations,
        )

    def test_application_test_external_network_remains_separately_confirmed(self):
        proposal = NaturalLanguageEngineeringPlanner().propose(
            prompt=(
                "Test the local app with network access to "
                "https://api.example.com/v1/status."
            ),
            workspace_root="/workspace/project", owner_id="owner-1",
            principal_id="owner-1", task_id="task-app-external",
            grant_id="grant-app-external", toolchains=("node",), now=NOW,
            authority_profile=AgentAuthorityProfile.APPLICATION_TEST,
        )

        self.assertIn(
            EngineeringAuthority.NETWORK,
            proposal.separately_confirmed_authorities,
        )

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

    def test_filesystem_mutation_does_not_require_repository_toolchain(self):
        proposal = NaturalLanguageEngineeringPlanner().propose(
            prompt="Create a new folder named reports.",
            workspace_root="/workspace/project", owner_id="owner-1",
            principal_id="principal-1", task_id="task-3", grant_id="grant-3",
            toolchains=(), now=NOW, git_available=False,
        )

        self.assertIn(EngineeringAuthority.MODIFY, proposal.grant.authorities)
        self.assertIn(EngineeringAuthority.EXECUTE, proposal.grant.authorities)
        self.assertIn(
            EngineeringOperation.CREATE,
            proposal.definition.task.permitted_operations,
        )
        self.assertEqual((), proposal.definition.task.toolchains)
        self.assertNotIn(
            EngineeringOperation.GIT_WRITE,
            proposal.definition.task.permitted_operations,
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
