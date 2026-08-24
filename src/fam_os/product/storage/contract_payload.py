"""Canonical contract encryption helpers for durable repositories."""

from __future__ import annotations

import json

from fam_os.core.contracts import (
    ResultAssurance,
    ResultKind,
    TASK_RESULT_CONTRACT_VERSION,
    TaskResult,
)
from fam_os.product.storage.cipher import CipherContext, ProductPayloadCipher
from fam_os.schemas import SchemaValidationError, dumps_document, loads_document
from fam_os.verification import VerificationDeclaration
from fam_os.verification.legacy_declarations import (
    VerificationDeclaration as VerificationDeclarationV1Alpha1,
    migrate_verification_declaration_v1alpha1,
)


def encrypt_contract(
    cipher: ProductPayloadCipher,
    owner_id: str,
    record_type: str,
    record_id: str,
    value: object,
) -> str:
    context = CipherContext(owner_id, record_type, record_id, "contract")
    return cipher.encrypt(context, dumps_document(value).encode("utf-8"))


def decrypt_contract(
    cipher: ProductPayloadCipher,
    owner_id: str,
    record_type: str,
    record_id: str,
    token: str,
    expected_type: type[object],
) -> object:
    context = CipherContext(owner_id, record_type, record_id, "contract")
    serialized = cipher.decrypt(context, token).decode("utf-8")
    try:
        value = loads_document(serialized)
    except SchemaValidationError:
        value = _migrate_transitional_task_result(serialized, expected_type)
        if value is None:
            raise
    value = _migrate_legacy_contract(value, expected_type)
    if not isinstance(value, expected_type):
        raise TypeError("stored contract has an unexpected type")
    return value


def _migrate_legacy_contract(value, expected_type):
    if expected_type is VerificationDeclaration and isinstance(
        value, VerificationDeclarationV1Alpha1,
    ):
        return migrate_verification_declaration_v1alpha1(value)
    return value


def _migrate_transitional_task_result(serialized: str, expected_type):
    """Recover the exact pre-v1alpha2 result shape once written as v1alpha1."""

    if expected_type is not TaskResult:
        return None
    try:
        document = json.loads(serialized)
    except (TypeError, ValueError):
        return None
    if not _is_transitional_task_result(document):
        return None
    payload = dict(document["payload"])
    assurance = payload.get("assurance")
    payload["contract_version"] = TASK_RESULT_CONTRACT_VERSION
    payload["result_kind"] = (
        ResultKind.CONVERSATION_ANSWER.value
        if assurance == ResultAssurance.UNVERIFIED.value else
        ResultKind.GROUNDED_ANSWER.value
    )
    migrated = {
        "schema_id": "fam.core.task-result/v1alpha2",
        "contract_version": TASK_RESULT_CONTRACT_VERSION,
        "payload": payload,
    }
    return loads_document(json.dumps(migrated, separators=(",", ":")))


def _is_transitional_task_result(document) -> bool:
    if not isinstance(document, dict) or set(document) != {
        "schema_id", "contract_version", "payload",
    }:
        return False
    if (
        document["schema_id"] != "fam.core.task-result/v1alpha1"
        or document["contract_version"] != "fam.core/v1alpha1"
        or not isinstance(document["payload"], dict)
    ):
        return False
    return set(document["payload"]) == {
        "request_id", "status", "content", "verified", "reason", "plan_id",
        "evidence_ids", "failure", "degradations", "contract_version",
        "assurance", "citations",
    }
