"""Exercise installed Console and Shell persistent-memory management."""

from __future__ import annotations

import hashlib
import urllib.request

from tools.phase20_management_exit.console_client import MemoryConsoleClient
from tools.phase20_management_exit.shell_client import run_installed_shell

ORIGINAL_NONCE = "PHASE20_MANAGEMENT_ORIGINAL_NONCE retained source"
SHELL_CORRECTED_NONCE = "PHASE20_MANAGEMENT_SHELL_CORRECTED_NONCE"
CONSOLE_CORRECTED_NONCE = "PHASE20_MANAGEMENT_CONSOLE_CORRECTED_NONCE"
DELETE_NONCE = "PHASE20_MANAGEMENT_DELETE_NONCE"
EXPIRY_NONCE = "PHASE20_MANAGEMENT_EXPIRY_NONCE"


def first_process_scenario(
    installation, service, primary_file, folder, replacement_file,
) -> dict:
    client = _client(service)
    before = client.documents()
    primary_index = client.create_index({
        "path": str(primary_file), "kind": "file", "recursive": False,
        "allowed_extensions": [".md"], "expires_in_hours": 24,
        "confirmed": True,
    })
    folder_index = client.create_index({
        "path": str(folder), "kind": "folder", "recursive": False,
        "allowed_extensions": [".txt"], "expires_in_hours": 24,
        "confirmed": True,
    })
    documents = client.documents()
    primary = _document(documents, primary_file.name)
    deleted = _document(documents, "delete.txt")
    expiring = _document(documents, "expire.txt")
    denied = _denied_delete(client, deleted)
    shell = run_installed_shell(installation, service, (
        "/memory list",
        f"/memory inspect {primary['approval']['document_id']}",
        f"/memory export {primary['approval']['document_id']}",
        f"/memory correct {primary['approval']['document_id']} "
        f"{primary['content_sha256']} {replacement_file}",
        f"/memory correct {primary['approval']['document_id']} "
        f"{primary['content_sha256']} {replacement_file} --confirm",
        "/memory receipts",
    ))
    shell_corrected = client.inspect(primary["approval"]["document_id"])
    console_content = CONSOLE_CORRECTED_NONCE
    console_digest = _digest(console_content)
    console_correction = client.correct(
        primary["approval"]["document_id"], "console-correct",
        shell_corrected["content_sha256"], console_content, console_digest, True,
    )
    deletion = client.delete(
        deleted["approval"]["document_id"], "console-delete",
        deleted["content_sha256"], True,
    )
    expiration = client.expire(
        folder_index["grant_id"], "console-expire", True,
    )
    final_documents = client.documents()
    final_export = client.export(primary["approval"]["document_id"])
    shell_export = run_installed_shell(installation, service, (
        f"/memory export {primary['approval']['document_id']}",
        "/memory receipts",
    ))
    return {
        "before": before,
        "primary_index": primary_index,
        "folder_index": folder_index,
        "initial_document_count": len(documents),
        "explicit_confirmation_denied": denied,
        "installed_shell": shell,
        "shell_corrected_digest": shell_corrected["content_sha256"],
        "console_correction": console_correction,
        "console_deletion": deletion,
        "console_expiration": expiration,
        "remaining_document_ids": [
            item["approval"]["document_id"] for item in final_documents
        ],
        "primary_document_id": primary["approval"]["document_id"],
        "primary_grant_id": primary_index["grant_id"],
        "final_export": final_export,
        "receipts": client.receipts(),
        "installed_shell_export": shell_export,
        "console_assets": _console_assets(service),
        "expired_document_removed": all(
            item["approval"]["document_id"] != expiring["approval"]["document_id"]
            for item in final_documents
        ),
    }


def restarted_process_scenario(installation, service, first: dict) -> dict:
    client = _client(service)
    document_id = first["primary_document_id"]
    documents = client.documents()
    exported = client.export(document_id)
    before_receipts = client.receipts()
    shell = run_installed_shell(installation, service, (
        f"/memory inspect {document_id}",
        f"/memory export {document_id}",
        f"/memory delete {document_id} {exported['content_sha256']} --confirm",
        f"/memory expire {first['primary_grant_id']} --confirm",
        "/memory list",
        "/memory receipts",
    ))
    after_receipts = client.receipts()
    deletion = next(
        item for item in after_receipts
        if item["operation"] == "delete" and item["target_id"] == document_id
    )
    replay = client.delete(
        document_id, deletion["request_id"], exported["content_sha256"], True,
    )
    return {
        "document_count_before": len(documents),
        "exported_content": exported["content"],
        "receipts_before": before_receipts,
        "installed_shell": shell,
        "documents_after": client.documents(),
        "indexes_after": client.indexes(),
        "receipts_after": after_receipts,
        "delete_replay_same_receipt": replay["receipt_id"] == deletion["receipt_id"],
    }


def _client(service) -> MemoryConsoleClient:
    base = f"http://127.0.0.1:{service.port}"
    token = (service.runtime_root / "console.token").read_text().strip()
    return MemoryConsoleClient(base, token)


def _document(documents: list[dict], name: str) -> dict:
    return next(
        item for item in documents
        if item["approval"]["source_locator"].endswith(name)
    )


def _denied_delete(client: MemoryConsoleClient, document: dict) -> bool:
    try:
        client.delete(
            document["approval"]["document_id"], "denied-delete",
            document["content_sha256"], False,
        )
    except RuntimeError as error:
        return "403" in str(error) and "confirmation" in str(error)
    return False


def _console_assets(service) -> dict[str, bool]:
    base = f"http://127.0.0.1:{service.port}"
    page = urllib.request.urlopen(base, timeout=10).read()
    script = urllib.request.urlopen(base + "/memory.js", timeout=10).read()
    style = urllib.request.urlopen(base + "/memory.css", timeout=10).read()
    return {
        "ledger_visible": b"Memory ledger" in page,
        "correction_control": b"replacement_content_sha256" in script,
        "expiry_control": b"Expire grant" in script,
        "receipt_layout": b"memory-receipts" in style,
    }


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()
