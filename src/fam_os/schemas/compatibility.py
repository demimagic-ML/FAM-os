"""Exact-match v1alpha1 schema compatibility admission."""

from __future__ import annotations

from dataclasses import dataclass

from fam_os.schemas.catalog import descriptor_for_schema, family_is_known
from fam_os.schemas.descriptor import SchemaDescriptor
from fam_os.schemas.errors import (
    ContractVersionMismatchError,
    UnknownSchemaError,
    UnsupportedSchemaVersionError,
)


@dataclass(frozen=True, slots=True)
class CompatibilityReport:
    compatible: bool
    schema_id: str
    contract_version: str
    reason_code: str


def compatibility_report(schema_id: str, contract_version: str) -> CompatibilityReport:
    descriptor = descriptor_for_schema(schema_id)
    if descriptor is None:
        family = schema_id.rsplit("/", 1)[0] if "/" in schema_id else schema_id
        reason = "unsupported_schema_version" if family_is_known(family) else "unknown_schema"
        return CompatibilityReport(False, schema_id, contract_version, reason)
    if descriptor.contract_version != contract_version:
        return CompatibilityReport(False, schema_id, contract_version, "contract_version_mismatch")
    return CompatibilityReport(True, schema_id, contract_version, "exact_match")


def require_compatible(schema_id: str, contract_version: str) -> SchemaDescriptor:
    report = compatibility_report(schema_id, contract_version)
    if report.compatible:
        descriptor = descriptor_for_schema(schema_id)
        assert descriptor is not None
        return descriptor
    if report.reason_code == "unsupported_schema_version":
        raise UnsupportedSchemaVersionError("unsupported schema version")
    if report.reason_code == "unknown_schema":
        raise UnknownSchemaError("unknown schema family")
    raise ContractVersionMismatchError("contract version does not match schema")
