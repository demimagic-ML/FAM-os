import copy
import unittest
from pathlib import Path

from fam_os.schemas import (
    ContractVersionMismatchError,
    SchemaValidationError,
    UnknownSchemaError,
    UnsupportedSchemaVersionError,
    compatibility_report,
    decode_document,
    encode_document,
)
from tests.contract.schema_core_fixtures import task_request


FIXTURES = Path("tests/fixtures/schema_compatibility/v1alpha1")


class SchemaCompatibilityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.document = encode_document(task_request())

    def test_current_alpha_schema_requires_exact_match(self) -> None:
        report = compatibility_report(self.document["schema_id"], self.document["contract_version"])
        self.assertTrue(report.compatible)
        self.assertEqual("exact_match", report.reason_code)

    def test_rejects_future_version_of_known_family(self) -> None:
        document = {**self.document, "schema_id": "fam.core.task-request/v1alpha2"}
        with self.assertRaises(UnsupportedSchemaVersionError):
            decode_document(document)

    def test_rejects_unknown_schema_family(self) -> None:
        document = {**self.document, "schema_id": "third.party.unknown/v1alpha1"}
        with self.assertRaises(UnknownSchemaError):
            decode_document(document)

    def test_rejects_contract_version_mismatch(self) -> None:
        document = {**self.document, "contract_version": "fam.core/v1alpha2"}
        with self.assertRaises(ContractVersionMismatchError):
            decode_document(document)

    def test_rejects_unknown_envelope_field(self) -> None:
        document = {**self.document, "unexpected": True}
        with self.assertRaises(SchemaValidationError) as caught:
            decode_document(document)
        self.assertEqual("additionalProperties", caught.exception.keyword)

    def test_rejects_unknown_nested_field(self) -> None:
        document = copy.deepcopy(self.document)
        document["payload"]["unexpected"] = True
        with self.assertRaises(SchemaValidationError) as caught:
            decode_document(document)
        self.assertEqual("additionalProperties", caught.exception.keyword)

    def test_rejects_missing_defaulted_field_for_canonical_shape(self) -> None:
        document = copy.deepcopy(self.document)
        del document["payload"]["verification_required"]
        with self.assertRaises(SchemaValidationError) as caught:
            decode_document(document)
        self.assertEqual("required", caught.exception.keyword)

    def test_rejects_unknown_enum_value(self) -> None:
        from tests.contract.schema_core_fixtures import task_result

        document = encode_document(task_result())
        document["payload"]["status"] = "future_status"
        with self.assertRaises(SchemaValidationError) as caught:
            decode_document(document)
        self.assertEqual("enum", caught.exception.keyword)

    def test_rejects_domain_invalid_value_after_schema_validation(self) -> None:
        document = copy.deepcopy(self.document)
        document["payload"]["prompt"] = " "
        with self.assertRaises(SchemaValidationError) as caught:
            decode_document(document)
        self.assertEqual("domain", caught.exception.keyword)

    def test_fixed_current_fixture_remains_decodable(self) -> None:
        from fam_os.schemas import loads_document

        value = loads_document((FIXTURES / "task-request.valid.json").read_text())
        self.assertEqual("fixture-request-1", value.request_id)

    def test_legacy_expert_fixture_remains_decodable_beside_v1alpha2(self) -> None:
        from fam_os.experts import ExpertManifestV1Alpha1
        from fam_os.schemas import loads_document

        serialized = (FIXTURES / "expert-manifest.valid.json").read_text()
        value = loads_document(serialized)
        self.assertIsInstance(value, ExpertManifestV1Alpha1)
        self.assertEqual(value.contract_version, "fam.expert.manifest/v1alpha1")
        self.assertTrue(
            compatibility_report(
                "fam.expert.manifest/v1alpha2",
                "fam.expert.manifest/v1alpha2",
            ).compatible
        )

    def test_fixed_unknown_field_fixture_remains_rejected(self) -> None:
        from fam_os.schemas import loads_document

        with self.assertRaises(SchemaValidationError):
            loads_document((FIXTURES / "task-request.unknown-field.json").read_text())

    def test_fixed_future_version_fixture_remains_rejected(self) -> None:
        from fam_os.schemas import loads_document

        with self.assertRaises(UnsupportedSchemaVersionError):
            loads_document((FIXTURES / "task-request.future-version.json").read_text())


if __name__ == "__main__":
    unittest.main()
