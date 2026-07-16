"""Typed Application Fabric contract messages over the local envelope."""

from fam_os.applications.transport.wire import (
    LocalMessage, LocalMessageKind, message_document,
)
from fam_os.schemas import decode_document, encode_document


def contract_message(
    message_id: str, kind: LocalMessageKind, value: object,
    correlation_id: str | None = None,
) -> LocalMessage:
    return LocalMessage(
        message_id, kind, encode_document(value), correlation_id=correlation_id
    )


def decode_contract_message(message: LocalMessage) -> object:
    document = message_document(message)["payload"]
    return decode_document(document)
