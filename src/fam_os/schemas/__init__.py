"""Public serialized-schema, compatibility, and reference-validation boundary."""

from fam_os.schemas.catalog import SCHEMA_DESCRIPTORS, descriptor_for_schema, descriptor_for_type
from fam_os.schemas.codec import decode_document, dumps_document, encode_document, loads_document
from fam_os.schemas.compatibility import CompatibilityReport, compatibility_report, require_compatible
from fam_os.schemas.descriptor import CompatibilityPolicy, SchemaDescriptor
from fam_os.schemas.errors import (
    ContractSchemaError,
    ContractVersionMismatchError,
    CrossContractValidationError,
    SchemaEncodingError,
    SchemaValidationError,
    UnknownSchemaError,
    UnsupportedSchemaVersionError,
)
from fam_os.schemas.references import (
    ContractReferenceSet,
    ReferenceIssue,
    find_reference_issues,
    require_valid_references,
)
from fam_os.schemas.schema_builder import build_schema

__all__ = [
    "SCHEMA_DESCRIPTORS",
    "CompatibilityPolicy",
    "CompatibilityReport",
    "ContractReferenceSet",
    "ContractSchemaError",
    "ContractVersionMismatchError",
    "CrossContractValidationError",
    "ReferenceIssue",
    "SchemaDescriptor",
    "SchemaEncodingError",
    "SchemaValidationError",
    "UnknownSchemaError",
    "UnsupportedSchemaVersionError",
    "build_schema",
    "compatibility_report",
    "decode_document",
    "descriptor_for_schema",
    "descriptor_for_type",
    "dumps_document",
    "encode_document",
    "find_reference_issues",
    "loads_document",
    "require_compatible",
    "require_valid_references",
]
