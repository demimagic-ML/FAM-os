"""Safe errors raised at serialized contract boundaries."""

from __future__ import annotations


class ContractSchemaError(ValueError):
    """Base error for schema catalog, encoding, and decoding failures."""


class UnknownSchemaError(ContractSchemaError):
    """The document names a schema family unknown to this process."""


class UnsupportedSchemaVersionError(ContractSchemaError):
    """The schema family is known but its version is not supported."""


class ContractVersionMismatchError(ContractSchemaError):
    """The document contract version does not match its schema descriptor."""


class SchemaEncodingError(ContractSchemaError):
    """A domain value cannot be represented as canonical JSON."""


class SchemaValidationError(ContractSchemaError):
    """A serialized document failed structural or domain validation."""

    def __init__(self, message: str, *, path: str = "$", keyword: str = "domain") -> None:
        super().__init__(message)
        self.path = path
        self.keyword = keyword


class CrossContractValidationError(ContractSchemaError):
    """Individually valid documents contain invalid references."""

    def __init__(self, issue_codes: tuple[str, ...]) -> None:
        super().__init__("cross-contract reference validation failed")
        self.issue_codes = issue_codes
