import unittest
from dataclasses import replace

from fam_os.schemas import (
    ContractReferenceSet,
    CrossContractValidationError,
    find_reference_issues,
    require_valid_references,
)
from tests.contract.schema_core_fixtures import execution_plan, task_request, task_result
from tests.contract.schema_engineering_fixtures import (
    engineering_result_schema_values,
    engineering_grant_schema_values,
    engineering_schema_values,
)
from tests.contract.schema_manifest_fixtures import (
    connector_manifest,
    effective_budget,
    expert_manifest,
    host_inventory,
    known_capability_schemas,
    memory_record,
    verifier_manifest,
)
from tests.contract.schema_repository_fixtures import repository_schema_values
from tests.contract.schema_transaction_fixtures import transaction_schema_values
from tests.contract.schema_execution_fixtures import execution_schema_values


def valid_references() -> ContractReferenceSet:
    (
        engineering_task, snapshot, _operation, proposal, recipe, run,
        dependency, design, git, checkpoint, engineering_evidence,
    ) = engineering_schema_values()
    (
        proposal_result, change_receipt, publication_proposal,
        publication_receipt, unavailable,
    ) = engineering_result_schema_values()
    after_snapshot = replace(
        snapshot,
        snapshot_id=change_receipt.after_snapshot_id,
        tree_sha256=change_receipt.after_tree_sha256,
    )
    publication_checkpoint = replace(
        checkpoint,
        decision_id=publication_receipt.checkpoint_decision_id,
        proposal_id=publication_proposal.proposal_id,
    )
    (
        engineering_grant, grant_approval, authorization_request,
        authorization_decision, break_glass_challenge, break_glass_decision,
        execution_record,
    ) = engineering_grant_schema_values()
    (
        repository_bundle, repository_request, repository_analysis,
        architecture_proposal, engineering_graph, engineering_graph_event,
    ) = repository_schema_values()
    repository_task = replace(
        engineering_task, task_id=repository_bundle.task_id,
        intent="Analyze an unfamiliar repository without mutation",
    )
    (
        candidate_artifact, candidate_operation, candidate_workspace,
        candidate_preview, candidate_receipt, _self_update_policy,
    ) = transaction_schema_values()
    (
        signed_recipe, _sandbox_profile, raw_shell, engineering_tool_receipt,
        language_qualification, _polyglot_matrix, dependency_request,
        dependency_receipt, host_change, host_receipt, secret_authorization,
        secret_receipt,
    ) = execution_schema_values()
    return ContractReferenceSet(
        requests=(task_request(),),
        plans=(execution_plan(),),
        results=(task_result(),),
        inventories=(host_inventory(),),
        budgets=(effective_budget(),),
        experts=(expert_manifest(),),
        verifiers=(verifier_manifest(),),
        connectors=(connector_manifest(),),
        memory_records=(memory_record(),),
        engineering_tasks=(engineering_task, repository_task),
        workspace_snapshots=(snapshot, after_snapshot),
        change_sets=(proposal,),
        tool_recipes=(recipe,),
        tool_runs=(run,),
        dependency_plans=(dependency,),
        design_manifests=(design,),
        git_operations=(git,),
        checkpoint_decisions=(checkpoint, publication_checkpoint),
        engineering_evidence=(engineering_evidence,),
        engineering_proposal_results=(proposal_result,),
        verified_change_set_receipts=(change_receipt,),
        publication_proposals=(publication_proposal,),
        publication_receipts=(publication_receipt,),
        unavailable_results=(unavailable,),
        engineering_grants=(engineering_grant,),
        owner_grant_approvals=(grant_approval,),
        engineering_authorization_requests=(authorization_request,),
        engineering_authorization_decisions=(authorization_decision,),
        break_glass_challenges=(break_glass_challenge,),
        break_glass_decisions=(break_glass_decision,),
        engineering_execution_records=(execution_record,),
        repository_evidence_bundles=(repository_bundle,),
        repository_analysis_requests=(repository_request,),
        repository_analyses=(repository_analysis,),
        architecture_proposals=(architecture_proposal,),
        engineering_task_graphs=(engineering_graph,),
        engineering_task_graph_events=(engineering_graph_event,),
        candidate_artifacts=(candidate_artifact,),
        candidate_operations=(candidate_operation,),
        candidate_workspaces=(candidate_workspace,),
        candidate_transaction_previews=(candidate_preview,),
        candidate_apply_receipts=(candidate_receipt,),
        signed_tool_recipes=(signed_recipe,),
        raw_shell_authorizations=(raw_shell,),
        engineering_tool_receipts=(engineering_tool_receipt,),
        language_tool_qualifications=(language_qualification,),
        dependency_resolution_requests=(dependency_request,),
        dependency_resolution_receipts=(dependency_receipt,),
        host_administration_change_sets=(host_change,),
        host_administration_receipts=(host_receipt,),
        secret_use_authorizations=(secret_authorization,),
        secret_use_receipts=(secret_receipt,),
        known_schema_ids=known_capability_schemas(),
    )


class CrossContractReferenceTests(unittest.TestCase):
    def test_accepts_complete_reference_set(self) -> None:
        self.assertEqual((), find_reference_issues(valid_references()))
        require_valid_references(valid_references())

    def test_reports_missing_core_request_and_plan(self) -> None:
        references = replace(valid_references(), requests=(), plans=())
        codes = {item.code for item in find_reference_issues(references)}
        self.assertEqual({"core.result.request_missing", "core.result.plan_missing"}, codes)

    def test_reports_budget_resource_not_present_in_inventory(self) -> None:
        inventory = replace(host_inventory(), accelerators=())
        references = replace(valid_references(), inventories=(inventory,))
        self.assertIn(
            "hardware.budget.accelerator_missing",
            {item.code for item in find_reference_issues(references)},
        )

    def test_reports_missing_verifier_and_capability_schemas(self) -> None:
        references = replace(valid_references(), verifiers=(), known_schema_ids=frozenset())
        codes = {item.code for item in find_reference_issues(references)}
        self.assertIn("expert.verifier_missing", codes)
        self.assertIn("connector.schema_missing", codes)
        self.assertIn("memory.content_schema_missing", codes)

    def test_reports_duplicate_cross_document_identity(self) -> None:
        request = task_request()
        references = replace(valid_references(), requests=(request, request))
        self.assertIn(
            "core.request.duplicate",
            {item.code for item in find_reference_issues(references)},
        )

    def test_require_valid_references_raises_stable_codes(self) -> None:
        references = replace(valid_references(), inventories=())
        with self.assertRaises(CrossContractValidationError) as caught:
            require_valid_references(references)
        self.assertEqual(("hardware.budget.inventory_missing",), caught.exception.issue_codes)

    def test_reports_missing_engineering_task_and_snapshot(self) -> None:
        references = replace(valid_references(), engineering_tasks=(), workspace_snapshots=())
        codes = {item.code for item in find_reference_issues(references)}
        self.assertIn("engineering.task.missing", codes)
        self.assertIn("engineering.change_set.snapshot_missing", codes)

    def test_reports_missing_recipe_and_evidence_links(self) -> None:
        references = replace(
            valid_references(), tool_recipes=(), checkpoint_decisions=(),
        )
        codes = {item.code for item in find_reference_issues(references)}
        self.assertIn("engineering.tool_run.recipe_missing", codes)
        self.assertIn("engineering.evidence.checkpoint_missing", codes)

    def test_reports_missing_result_proposals_and_publication_checkpoint(self) -> None:
        references = replace(
            valid_references(), change_sets=(), checkpoint_decisions=(),
        )
        codes = {item.code for item in find_reference_issues(references)}
        self.assertIn("engineering.proposal_result.change_set_missing", codes)
        self.assertIn("engineering.change_receipt.proposal_missing", codes)
        self.assertIn("engineering.publication_receipt.checkpoint_missing", codes)

    def test_reports_missing_grant_challenge_and_authorization_references(self) -> None:
        references = replace(
            valid_references(), engineering_grants=(), break_glass_challenges=(),
            engineering_authorization_requests=(),
        )
        codes = {item.code for item in find_reference_issues(references)}
        self.assertIn("engineering.grant_approval.grant_missing", codes)
        self.assertIn("engineering.break_glass_decision.challenge_missing", codes)
        self.assertIn("engineering.authorization_decision.request_missing", codes)
        self.assertIn("engineering.execution.grant_missing", codes)

    def test_reports_missing_repository_bundle_analysis_and_graph(self) -> None:
        references = replace(
            valid_references(), repository_evidence_bundles=(),
            engineering_task_graphs=(),
        )
        codes = {item.code for item in find_reference_issues(references)}
        self.assertIn("engineering.repository_analysis.bundle_missing", codes)
        without_analysis = replace(valid_references(), repository_analyses=())
        codes.update(item.code for item in find_reference_issues(without_analysis))
        self.assertIn("engineering.architecture.analysis_missing", codes)
        self.assertIn("engineering.task_graph_event.graph_missing", codes)

    def test_reports_missing_candidate_artifact_workspace_and_preview(self) -> None:
        references = replace(
            valid_references(), candidate_artifacts=(), candidate_workspaces=(),
            candidate_transaction_previews=(),
        )
        codes = {item.code for item in find_reference_issues(references)}
        self.assertEqual({
            "engineering.candidate_operation.artifact_missing",
            "engineering.candidate_receipt.preview_missing",
            "engineering.tool_receipt.candidate_missing",
        }, codes)


if __name__ == "__main__":
    unittest.main()
