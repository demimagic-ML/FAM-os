"""Color-free terminal rendering for persistent memory responses."""

from fam_os.shell.memory_contracts import ShellMemoryOperation, ShellMemoryResponse


def render_memory_response(response: ShellMemoryResponse) -> str:
    if response.operation in {ShellMemoryOperation.LIST, ShellMemoryOperation.INSPECT}:
        return _documents(response)
    if response.operation is ShellMemoryOperation.EXPORT:
        value = response.exported_document
        if value is None:
            raise ValueError("memory export response is empty")
        return "\n".join((
            "Persistent memory export:",
            f"Source: {_safe(value.approval.source_locator)}",
            f"Document: {_safe(value.approval.document_id)}",
            f"Digest: {_safe(value.content_sha256)}",
            "", _safe(value.content, multiline=True),
        ))
    if response.operation is ShellMemoryOperation.RECEIPTS:
        return _receipts(response)
    receipt = response.receipt
    if receipt is None:
        raise ValueError("memory mutation response is empty")
    return "\n".join((
        f"Memory {receipt.operation.value} completed.",
        f"Receipt: {_safe(receipt.receipt_id)}",
        f"Target: {_safe(receipt.target_id)}",
        f"Affected documents: {len(receipt.affected_document_ids)}",
        f"Payload removed: {'yes' if receipt.payload_removed else 'no'}",
        f"Performed: {receipt.performed_at.isoformat()}",
    ))


def _documents(response: ShellMemoryResponse) -> str:
    lines = [
        f"Persistent memory: {len(response.documents)} shown of {response.total_count} "
        f"from offset {response.offset}."
    ]
    if not response.documents:
        lines.append("No retained documents in this page.")
    for item in response.documents:
        approval = item.approval
        lines.extend((
            "", f"[{_safe(approval.document_id)}] {_safe(approval.source_locator)}",
            f"  Digest: {_safe(item.content_sha256)}",
            f"  Size: {item.content_bytes} bytes / {item.chunk_count} chunks",
            f"  Grant: {_safe(approval.grant_id or 'none')}",
            f"  Expires: {approval.expires_at.isoformat() if approval.expires_at else 'none'}",
        ))
    return "\n".join(lines)


def _receipts(response: ShellMemoryResponse) -> str:
    lines = [
        f"Memory receipts: {len(response.receipts)} shown of {response.total_count} "
        f"from offset {response.offset}."
    ]
    if not response.receipts:
        lines.append("No receipts in this page.")
    for receipt in response.receipts:
        lines.extend((
            "", f"[{_safe(receipt.receipt_id)}] {receipt.operation.value}",
            f"  Target: {_safe(receipt.target_id)}",
            f"  Performed: {receipt.performed_at.isoformat()}",
            f"  Tombstone: {_safe(receipt.tombstone_sha256)}",
        ))
    return "\n".join(lines)


def _safe(value: str, multiline=False) -> str:
    rendered = []
    for character in value:
        if character == "\n" and multiline:
            rendered.append(character)
        elif character == "\t":
            rendered.append("    ")
        elif ord(character) < 32 or ord(character) == 127:
            rendered.append("�")
        else:
            rendered.append(character)
    return "".join(rendered)
