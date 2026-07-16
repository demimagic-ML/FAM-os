import unittest
from dataclasses import replace

from fam_os.schemas import (
    ContractReferenceSet,
    CrossContractValidationError,
    find_reference_issues,
    require_valid_references,
)
from tests.contract.schema_core_fixtures import execution_plan, task_request, task_result
from tests.contract.schema_manifest_fixtures import (
    connector_manifest,
    effective_budget,
    expert_manifest,
    host_inventory,
    known_capability_schemas,
    memory_record,
    verifier_manifest,
)


def valid_references() -> ContractReferenceSet:
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


if __name__ == "__main__":
    unittest.main()
