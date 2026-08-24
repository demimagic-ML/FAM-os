import json
import unittest

from jsonschema import Draft202012Validator

from fam_os.schemas import (
    SCHEMA_DESCRIPTORS,
    SchemaValidationError,
    build_schema,
    decode_document,
    dumps_document,
    encode_document,
    loads_document,
)
from tests.contract.schema_application_fixtures import application_schema_values
from tests.contract.schema_configuration_fixtures import configuration_schema_values
from tests.contract.schema_core_fixtures import core_schema_values, task_request
from tests.contract.schema_engineering_fixtures import (
    engineering_result_schema_values,
    engineering_grant_schema_values,
    engineering_schema_values,
)
from tests.contract.schema_manifest_fixtures import resource_manifest_schema_values
from tests.contract.schema_shell_fixtures import shell_schema_values
from tests.contract.schema_scheduler_fixtures import scheduler_schema_values
from tests.contract.schema_repository_fixtures import repository_schema_values
from tests.contract.schema_transaction_fixtures import transaction_schema_values
from tests.contract.schema_execution_fixtures import execution_schema_values
from tests.contract.schema_design_fixtures import design_schema_values
from tests.contract.schema_git_fixtures import git_schema_values
from tests.contract.schema_master_loop_fixtures import master_loop_schema_values
from tests.contract.schema_security_qualification_fixtures import security_qualification_schema_values
from tests.contract.schema_diagnostics_fixtures import diagnostics_schema_values
from tests.contract.schema_diagnostic_qualification_fixtures import diagnostic_qualification_schema_values
from tests.contract.schema_database_engineering_fixtures import (
    database_engineering_schema_values, database_postapply_schema_values,
    postgresql_integration_verification_schema_values,
)
from tests.contract.schema_integration_environment_fixtures import (
    integration_environment_schema_values, integration_network_schema_values,
    natural_integration_declaration_schema_value,
)
from tests.contract.schema_documentation_fixtures import (
    documentation_recipe_schema_value, documentation_schema_values,
)
from tests.contract.schema_review_fixtures import review_schema_values
from tests.contract.schema_incident_fixtures import incident_schema_values
from tests.contract.schema_task_definition_fixtures import task_definition_schema_values
from tests.contract.schema_preparation_fixtures import preparation_schema_values
from tests.contract.schema_candidate_edit_fixtures import candidate_edit_schema_values
from tests.contract.schema_candidate_verification_fixtures import candidate_verification_schema_values
from tests.contract.schema_candidate_changeset_fixtures import candidate_changeset_schema_values
from tests.contract.schema_candidate_generation_fixtures import candidate_generation_schema_values


def all_values() -> tuple[object, ...]:
    return (
        core_schema_values()
        + engineering_schema_values()
        + engineering_result_schema_values()
        + engineering_grant_schema_values()
        + application_schema_values()
        + resource_manifest_schema_values()
        + configuration_schema_values()
        + shell_schema_values()
        + scheduler_schema_values()
        + repository_schema_values()
        + transaction_schema_values()
        + execution_schema_values()
        + design_schema_values()
        + git_schema_values()
        + master_loop_schema_values()
        + security_qualification_schema_values()
        + diagnostics_schema_values()
        + diagnostic_qualification_schema_values()
        + database_engineering_schema_values()
        + database_postapply_schema_values()
        + postgresql_integration_verification_schema_values()
        + integration_environment_schema_values()
        + integration_network_schema_values()
        + (natural_integration_declaration_schema_value(),)
        + (documentation_recipe_schema_value(),)
        + documentation_schema_values()
        + review_schema_values()
        + incident_schema_values()
        + task_definition_schema_values()
        + preparation_schema_values()
        + candidate_edit_schema_values()
        + candidate_verification_schema_values()
        + candidate_changeset_schema_values()
        + candidate_generation_schema_values()
    )


class ContractSchemaRoundTripTests(unittest.TestCase):
    def test_every_registered_root_has_a_representative_round_trip(self) -> None:
        values = all_values()
        self.assertEqual({item.root_type for item in SCHEMA_DESCRIPTORS}, {type(item) for item in values})
        for value in values:
            with self.subTest(root_type=type(value).__name__):
                self.assertEqual(loads_document(dumps_document(value)), value)

    def test_every_generated_schema_is_valid_draft_2020_12(self) -> None:
        for descriptor in SCHEMA_DESCRIPTORS:
            with self.subTest(schema_id=descriptor.schema_id):
                Draft202012Validator.check_schema(build_schema(descriptor))

    def test_canonical_encoding_is_stable(self) -> None:
        serialized = dumps_document(task_request())
        self.assertEqual(serialized, dumps_document(loads_document(serialized)))
        self.assertEqual(serialized, json.dumps(json.loads(serialized), separators=(",", ":"), sort_keys=True))

    def test_decode_document_accepts_mapping_input(self) -> None:
        value = task_request()
        self.assertEqual(decode_document(encode_document(value)), value)

    def test_rejects_non_finite_json_number(self) -> None:
        document = dumps_document(task_request()).replace('"verification_required":false', '"verification_required":NaN')
        with self.assertRaises(SchemaValidationError):
            loads_document(document)

    def test_rejects_duplicate_object_keys_at_any_depth(self) -> None:
        serialized = dumps_document(task_request())
        duplicate_envelope = serialized.replace(
            '"schema_id":', '"schema_id":"duplicate","schema_id":', 1,
        )
        duplicate_payload = serialized.replace(
            '"verification_required":false',
            '"verification_required":true,"verification_required":false',
            1,
        )

        for document in (duplicate_envelope, duplicate_payload):
            with self.subTest(document=document[:80]):
                with self.assertRaisesRegex(
                    SchemaValidationError, "document is not strict JSON",
                ):
                    loads_document(document)


if __name__ == "__main__":
    unittest.main()
