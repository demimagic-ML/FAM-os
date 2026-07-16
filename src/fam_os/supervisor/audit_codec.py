"""Canonical JSON and SHA-256 encoding for Supervisor audit records."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone

from fam_os.supervisor.audit_contracts import (
    AUDIT_CONTRACT_VERSION,
    SupervisorAuditIntent,
    SupervisorAuditOperation,
    SupervisorAuditOutcome,
    SupervisorAuditRecord,
)


_RECORD_KEYS = frozenset(("sequence", "previous_digest", "digest", "event"))
_EVENT_KEYS = frozenset((
    "contract_version", "event_id", "operation_id", "occurred_at", "request_id",
    "authority_ref", "principal_id", "session_id", "service_id",
    "operation", "outcome", "resource_id", "reason_code", "evidence_ref",
))


def create_audit_record(
    intent: SupervisorAuditIntent, sequence: int, previous_digest: str
) -> SupervisorAuditRecord:
    digest = hashlib.sha256(
        _canonical_json(_unsigned_document(intent, sequence, previous_digest))
    ).hexdigest()
    return SupervisorAuditRecord(sequence, previous_digest, digest, intent)


def encode_audit_record(record: SupervisorAuditRecord) -> bytes:
    document = _unsigned_document(
        record.intent, record.sequence, record.previous_digest
    )
    document["digest"] = record.digest
    return _canonical_json(document)


def decode_audit_record(encoded: bytes) -> SupervisorAuditRecord:
    try:
        document = json.loads(encoded.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("audit record is not canonical JSON") from error
    if type(document) is not dict or set(document) != _RECORD_KEYS:
        raise ValueError("audit record fields are not exact")
    event = document["event"]
    if type(event) is not dict or set(event) != _EVENT_KEYS:
        raise ValueError("audit event fields are not exact")
    intent = _decode_intent(event)
    record = SupervisorAuditRecord(
        _exact_int(document["sequence"]),
        _exact_str(document["previous_digest"]),
        _exact_str(document["digest"]),
        intent,
    )
    if encode_audit_record(record) != encoded:
        raise ValueError("audit record encoding is not canonical")
    return record


def audit_record_digest_matches(record: SupervisorAuditRecord) -> bool:
    expected = create_audit_record(
        record.intent, record.sequence, record.previous_digest
    )
    return expected.digest == record.digest


def _unsigned_document(
    intent: SupervisorAuditIntent, sequence: int, previous_digest: str
) -> dict[str, object]:
    return {
        "event": _event_document(intent),
        "previous_digest": previous_digest,
        "sequence": sequence,
    }


def _event_document(intent: SupervisorAuditIntent) -> dict[str, object]:
    return {
        "authority_ref": intent.authority_ref,
        "contract_version": intent.contract_version,
        "event_id": intent.event_id,
        "operation_id": intent.operation_id,
        "evidence_ref": intent.evidence_ref,
        "occurred_at": _format_instant(intent.occurred_at),
        "operation": intent.operation.value,
        "outcome": intent.outcome.value,
        "principal_id": intent.principal_id,
        "reason_code": intent.reason_code,
        "request_id": intent.request_id,
        "resource_id": intent.resource_id,
        "service_id": intent.service_id,
        "session_id": intent.session_id,
    }


def _decode_intent(event: dict[str, object]) -> SupervisorAuditIntent:
    return SupervisorAuditIntent(
        _exact_str(event["event_id"]),
        _exact_str(event["operation_id"]),
        _parse_instant(_exact_str(event["occurred_at"])),
        _exact_str(event["request_id"]),
        _exact_str(event["authority_ref"]),
        _exact_str(event["principal_id"]),
        _exact_str(event["session_id"]),
        _exact_str(event["service_id"]),
        SupervisorAuditOperation(_exact_str(event["operation"])),
        SupervisorAuditOutcome(_exact_str(event["outcome"])),
        _optional_str(event["resource_id"]),
        _optional_str(event["reason_code"]),
        _optional_str(event["evidence_ref"]),
        _exact_version(event["contract_version"]),
    )


def _canonical_json(document: dict[str, object]) -> bytes:
    return json.dumps(
        document, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def _format_instant(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(
        timespec="microseconds"
    ).replace("+00:00", "Z")


def _parse_instant(value: str) -> datetime:
    if not value.endswith("Z"):
        raise ValueError("audit timestamp is not canonical UTC")
    return datetime.fromisoformat(value[:-1] + "+00:00")


def _exact_str(value: object) -> str:
    if type(value) is not str:
        raise ValueError("audit field must be a string")
    return value


def _exact_int(value: object) -> int:
    if type(value) is not int:
        raise ValueError("audit sequence must be an integer")
    return value


def _optional_str(value: object) -> str | None:
    if value is None:
        return None
    return _exact_str(value)


def _exact_version(value: object) -> str:
    version = _exact_str(value)
    if version != AUDIT_CONTRACT_VERSION:
        raise ValueError("unsupported audit contract version")
    return version
