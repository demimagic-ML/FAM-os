"""Canonical encoding and digest binding for application-action audit records."""

import hashlib
import json

from fam_os.applications.action_audit import (
    ApplicationActionAuditIntent, ApplicationActionAuditRecord,
)
from fam_os.schemas import dumps_document, loads_document


def create_action_audit_record(
    intent: ApplicationActionAuditIntent, sequence: int, previous_digest: str,
) -> ApplicationActionAuditRecord:
    digest = hashlib.sha256(_digest_payload(intent, sequence, previous_digest)).hexdigest()
    return ApplicationActionAuditRecord(sequence, previous_digest, digest, intent)


def encode_action_audit_record(record: ApplicationActionAuditRecord) -> bytes:
    return dumps_document(record).encode("utf-8")


def decode_action_audit_record(encoded: bytes) -> ApplicationActionAuditRecord:
    value = loads_document(encoded.decode("utf-8"))
    if not isinstance(value, ApplicationActionAuditRecord):
        raise ValueError("document is not an application action audit record")
    return value


def action_audit_record_digest_matches(record: ApplicationActionAuditRecord) -> bool:
    expected = hashlib.sha256(
        _digest_payload(record.intent, record.sequence, record.previous_digest)
    ).hexdigest()
    return record.digest == expected


def _digest_payload(intent, sequence, previous_digest):
    value = {
        "intent": json.loads(dumps_document(intent)),
        "previous_digest": previous_digest,
        "sequence": sequence,
    }
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("utf-8")
