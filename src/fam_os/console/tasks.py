"""Authenticated Console task facade over the same production gateway as Shell."""

from __future__ import annotations

from dataclasses import asdict
from datetime import datetime
from enum import Enum
from uuid import uuid4

from fam_os.shell import (
    ShellAskCommand, ShellCancelCommand, ShellContext, ShellContextKind,
    ShellDecision, ShellDecisionCommand,
    ShellVerifiedAskCommand,
)
from fam_os.console.application_contexts import application_contexts
from fam_os.console.task_activity import task_activity_document
from fam_os.console.verification_document import declaration_from_document
from fam_os.schemas import dumps_document
from fam_os.fabric import RemoteContextSensitivity, RemoteExecutionAuthority


class ConsoleTaskApi:
    def __init__(self, gateway, applications=None) -> None:
        self._gateway = gateway
        self._applications = applications

    def create(self, document: dict, memory_session_id: str | None = None):
        prompt = document.get("prompt")
        if not isinstance(prompt, str):
            raise ValueError("task prompt is required")
        request_id = document.get("request_id") or str(uuid4())
        contexts = tuple(_context(item) for item in document.get("contexts", ()))
        capabilities = tuple(document.get("required_capabilities", ()))
        verification_document = document.get("verification")
        verification = document.get(
            "verification_required", verification_document is not None,
        )
        if not isinstance(verification, bool):
            raise ValueError("verification_required must be boolean")
        remote_authority = _remote_authority(document.get("remote_authority"))
        command = ShellAskCommand(
            request_id, prompt, contexts, capabilities, verification,
            memory_session_id=memory_session_id,
            remote_authority=remote_authority,
        )
        if verification_document is None:
            return self._gateway.ask(command)
        if not verification:
            raise ValueError("a verification declaration requires verification_required")
        declaration = declaration_from_document(request_id, prompt, verification_document)
        return self._gateway.ask_verified(ShellVerifiedAskCommand(
            command, dumps_document(declaration),
        ))

    def snapshot(self, task_id: str):
        return self._gateway.snapshot(task_id)

    def decide(self, task_id: str, document: dict):
        return self._gateway.decide(ShellDecisionCommand(
            task_id, _revision(document), document["approval_id"],
            ShellDecision(document["decision"]),
        ))

    def cancel(self, task_id: str, document: dict):
        return self._gateway.cancel(ShellCancelCommand(task_id, _revision(document)))

    def reversal(self, task_id: str) -> dict:
        return self._reversals().status(task_id)

    def verifications(self, task_id: str) -> list[dict]:
        runs = getattr(self._gateway, "verification_runs", None)
        if runs is None:
            raise ValueError("verification evidence is unavailable")
        return [_json_value(asdict(item)) for item in runs(task_id)]

    def remote_execution(self, task_id: str) -> dict:
        lookup = getattr(self._gateway, "remote_execution_evidence", None)
        if lookup is None:
            raise ValueError("remote execution evidence is unavailable")
        evidence = lookup(task_id)
        return {
            "available": evidence is not None,
            "evidence": None if evidence is None else _json_value(asdict(evidence)),
        }

    def remote_recovery(self, task_id: str) -> dict:
        lookup = getattr(self._gateway, "remote_recovery_evidence", None)
        if lookup is None:
            raise ValueError("remote recovery evidence is unavailable")
        evidence = lookup(task_id)
        return {
            "available": evidence is not None,
            "evidence": None if evidence is None else _json_value(asdict(evidence)),
        }

    def attempt_budget(self, task_id: str) -> dict:
        lookup = getattr(self._gateway, "attempt_budget_evidence", None)
        if lookup is None:
            raise ValueError("attempt budget evidence is unavailable")
        snapshot, reservations = lookup(task_id)
        return {
            "snapshot": _json_value(asdict(snapshot)),
            "reservations": [
                _json_value(asdict(reservation)) for reservation in reservations
            ],
        }

    def activity(self, task_id: str) -> dict:
        lookup = getattr(self._gateway, "application_activity", None)
        if lookup is None:
            return {"available": False, "items": []}
        return task_activity_document(lookup(task_id))

    def reverse(self, task_id: str, document: dict):
        request_id = document.get("request_id") or str(uuid4())
        return self._reversals().start(task_id, request_id, _revision(document))

    def contexts(self) -> list[dict]:
        if self._applications is None:
            return []
        return application_contexts(self._applications.provider.entries())

    def integrations(self) -> list[dict]:
        if self._applications is None:
            return []
        fallbacks = getattr(self._applications, "fallbacks", None)
        return [] if fallbacks is None else fallbacks.status()

    def _reversals(self):
        service = getattr(self._gateway, "reversals", None)
        if service is None:
            raise ValueError("application reversal service is unavailable")
        return service


def task_document(snapshot) -> dict:
    return _json_value(asdict(snapshot))


def _context(value) -> ShellContext:
    if not isinstance(value, dict):
        raise ValueError("task context must be an object")
    return ShellContext(
        value["context_id"], ShellContextKind(value["kind"]),
        value["resource_ref"], value["display_name"],
        tuple(value.get("capability_ids", ())),
    )


def _revision(document: dict) -> int:
    value = document.get("expected_revision")
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError("expected_revision must be a nonnegative integer")
    return value


def _remote_authority(value) -> RemoteExecutionAuthority | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        raise ValueError("remote_authority must be an object")
    expected = {
        "enrollment_id", "expected_privacy_revision", "purpose_id",
        "workspace_id", "sensitivity", "maximum_context_bytes",
        "maximum_output_bytes", "confirmed",
    }
    if set(value) != expected or value.get("confirmed") is not True:
        raise PermissionError(
            "remote authority requires an exact explicitly confirmed scope",
        )
    for name in (
        "expected_privacy_revision", "maximum_context_bytes",
        "maximum_output_bytes",
    ):
        if not isinstance(value[name], int) or isinstance(value[name], bool):
            raise ValueError(f"remote authority {name} must be an integer")
    for name in ("enrollment_id", "purpose_id", "workspace_id", "sensitivity"):
        if not isinstance(value[name], str):
            raise ValueError(f"remote authority {name} must be text")
    return RemoteExecutionAuthority(
        value["enrollment_id"], value["expected_privacy_revision"],
        value["purpose_id"], value["workspace_id"],
        RemoteContextSensitivity(value["sensitivity"]),
        value["maximum_context_bytes"], value["maximum_output_bytes"], True,
    )


def _json_value(value):
    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _json_value(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(item) for item in value]
    return value
