"""Typed Shell contracts for owner engineering secret management."""

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


SHELL_ENGINEERING_SECRET_VERSION = "fam.shell.engineering-secret/v1alpha1"


class ShellEngineeringSecretOperation(StrEnum):
    LIST = "list"
    INSPECT = "inspect"
    AUDIT = "audit"
    PROVISION = "provision"
    ROTATE = "rotate"
    DELETE = "delete"


@dataclass(frozen=True, slots=True)
class ShellEngineeringSecretQuery:
    request_id: str
    operation: ShellEngineeringSecretOperation
    secret_ref: str | None = None
    contract_version: str = SHELL_ENGINEERING_SECRET_VERSION

    def __post_init__(self):
        _text(self.request_id, "request_id")
        if self.operation not in {
            ShellEngineeringSecretOperation.LIST,
            ShellEngineeringSecretOperation.INSPECT,
            ShellEngineeringSecretOperation.AUDIT,
        }:
            raise ValueError("Shell secret query operation is invalid")
        if (self.operation is ShellEngineeringSecretOperation.LIST) != (self.secret_ref is None):
            raise ValueError("Shell secret query identity is invalid")
        if self.secret_ref is not None: _text(self.secret_ref, "secret_ref")
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class ShellEngineeringSecretMutation:
    request_id: str
    operation: ShellEngineeringSecretOperation
    authority_session_id: str
    owner_id: str
    authentication_context_id: str
    secret_ref: str
    tool_key: str | None
    consumer_id: str | None
    value: str | None
    confirmed: bool
    contract_version: str = SHELL_ENGINEERING_SECRET_VERSION

    def __post_init__(self):
        for name in ("request_id", "authority_session_id", "owner_id", "authentication_context_id", "secret_ref"):
            _text(getattr(self, name), name)
        shapes = {
            ShellEngineeringSecretOperation.PROVISION: (
                self.tool_key is not None and self.consumer_id is not None and self.value is not None
            ),
            ShellEngineeringSecretOperation.ROTATE: (
                self.tool_key is None and self.consumer_id is None and self.value is not None
            ),
            ShellEngineeringSecretOperation.DELETE: (
                self.tool_key is None and self.consumer_id is None and self.value is None
            ),
        }
        if self.operation not in shapes or not shapes[self.operation]:
            raise ValueError("Shell secret mutation shape is invalid")
        for value in (self.tool_key, self.consumer_id, self.value):
            if value is not None: _text(value, "mutation value")
        if self.confirmed is not True:
            raise ValueError("Shell secret mutation requires confirmation")
        _version(self.contract_version)


@dataclass(frozen=True, slots=True)
class ShellEngineeringSecretMetadata:
    secret_ref: str
    tool_key: str
    consumer_id: str
    state: str
    generation: int
    created_at: datetime
    updated_at: datetime

    def __post_init__(self):
        for name in ("secret_ref", "tool_key", "consumer_id"): _text(getattr(self, name), name)
        if self.state not in {"active", "deleted"} or self.generation < 1:
            raise ValueError("Shell secret metadata is invalid")
        for value in (self.created_at, self.updated_at):
            if value.tzinfo is None or value.utcoffset() is None:
                raise ValueError("Shell secret metadata time is invalid")


@dataclass(frozen=True, slots=True)
class ShellEngineeringSecretAuditEvent:
    event_id: str
    action: str
    generation: int
    occurred_at: datetime

    def __post_init__(self):
        _text(self.event_id, "event_id")
        if self.action not in {"provisioned", "rotated", "deleted"} or self.generation < 1:
            raise ValueError("Shell secret audit event is invalid")
        if self.occurred_at.tzinfo is None or self.occurred_at.utcoffset() is None:
            raise ValueError("Shell secret audit time is invalid")


@dataclass(frozen=True, slots=True)
class ShellEngineeringSecretResponse:
    request_id: str
    operation: ShellEngineeringSecretOperation
    metadata: ShellEngineeringSecretMetadata | None = None
    items: tuple[ShellEngineeringSecretMetadata, ...] = ()
    events: tuple[ShellEngineeringSecretAuditEvent, ...] = ()
    secret_ref: str | None = None
    contract_version: str = SHELL_ENGINEERING_SECRET_VERSION

    def __post_init__(self):
        _text(self.request_id, "request_id")
        if self.operation is ShellEngineeringSecretOperation.LIST:
            valid = self.metadata is None and not self.events and self.secret_ref is None
        elif self.operation is ShellEngineeringSecretOperation.AUDIT:
            valid = self.metadata is None and not self.items and self.secret_ref is not None
        else:
            valid = self.metadata is not None and not self.items and not self.events and self.secret_ref is None
        if not valid: raise ValueError("Shell secret response shape is invalid")
        _version(self.contract_version)


def _text(value, name):
    if not isinstance(value, str) or not value.strip() or "\0" in value:
        raise ValueError(f"Shell secret {name} is invalid")


def _version(value):
    if value != SHELL_ENGINEERING_SECRET_VERSION:
        raise ValueError("unsupported Shell engineering secret version")
