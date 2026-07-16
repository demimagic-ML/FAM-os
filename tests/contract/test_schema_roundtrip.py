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
from tests.contract.schema_manifest_fixtures import resource_manifest_schema_values
from tests.contract.schema_shell_fixtures import shell_schema_values
from tests.contract.schema_scheduler_fixtures import scheduler_schema_values


def all_values() -> tuple[object, ...]:
    return (
        core_schema_values()
        + application_schema_values()
        + resource_manifest_schema_values()
        + configuration_schema_values()
        + shell_schema_values()
        + scheduler_schema_values()
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


if __name__ == "__main__":
    unittest.main()
