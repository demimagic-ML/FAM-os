"""Real granted workspace indexing, grounding, isolation, and restart proof."""

from __future__ import annotations

import time
from pathlib import Path

from tools.phase20_management_exit.console_client import MemoryConsoleClient

from .service import CandidateService


def run_memory_scenario(
    *, installation, root: Path, ollama_url: str, source_model_root: Path,
    manage_ollama: bool = False, validation_profile: str | None = None,
) -> dict[str, object]:
    workspace = root / "workspace"
    workspace.mkdir(parents=True)
    phrase = "PHASE23_WORKSPACE_FACT: the resident fabric uses verified local evidence."
    (workspace / "README.md").write_text(
        "# Installed matrix workspace\n" + phrase + "\n", encoding="utf-8",
    )
    (workspace / "notes.txt").write_text(
        "A second file proves recursive whole-workspace indexing.\n", encoding="utf-8",
    )
    state = root / "state"
    first = _service(
        installation, state, root / "run-1", ollama_url, source_model_root,
        manage_ollama, validation_profile,
    )
    first.start()
    try:
        first_client = _client(first)
        console_before = first_client.snapshot()
        receipt = first_client.create_index({
            "path": str(workspace), "kind": "folder", "recursive": True,
            "allowed_extensions": [".md", ".txt"],
            "application_ids": ["fam.shell"],
            "expires_in_hours": 24, "confirmed": True,
        })
        documents = _wait_documents(first_client, 2)
        console_after_index = first_client.snapshot()
        first_answer = _grounded(first_client, "phase23-memory-first")
        isolated = _client(first)
        cross_session_indexes = isolated.indexes()
    finally:
        first.stop()
    second = _service(
        installation, state, root / "run-2", ollama_url, source_model_root,
        manage_ollama, validation_profile,
    )
    try:
        second.start()
        restarted = _client(second)
        indexes_after_restart = restarted.indexes()
        console_after_restart = restarted.snapshot()
        documents_after_restart = _wait_documents(restarted, 2)
        second_answer = _grounded(restarted, "phase23-memory-restart")
    finally:
        second.stop()
    expected_paths = {
        (workspace / name).resolve().as_uri() for name in ("README.md", "notes.txt")
    }
    observed_paths = {
        item.get("approval", {}).get("source_locator")
        for item in documents_after_restart
    }
    console_indexes = (
        _index_count(console_before), _index_count(console_after_index),
        _index_count(console_after_restart),
    )
    passed = all((
        len(receipt.get("indexed_document_ids", ())) >= 2,
        len(documents) >= 2,
        bool(cross_session_indexes), bool(indexes_after_restart),
        expected_paths <= observed_paths,
        _answer_passed(first_answer, phrase),
        _answer_passed(second_answer, phrase),
        console_indexes[0] == 0,
        console_indexes[1] >= 1,
        console_indexes[2] >= 1,
    ))
    return {
        "grant_receipt": receipt,
        "document_count": len(documents),
        "cross_session_index_count": len(cross_session_indexes),
        "restart_index_count": len(indexes_after_restart),
        "restart_document_count": len(documents_after_restart),
        "console_authority": {
            "active_indexes_before": console_indexes[0],
            "active_indexes_after": console_indexes[1],
            "active_indexes_after_restart": console_indexes[2],
            "passed": (
                console_indexes[0] == 0
                and console_indexes[1] >= 1
                and console_indexes[2] >= 1
            ),
        },
        "first_answer": first_answer, "restart_answer": second_answer,
        "passed": passed,
    }


def _grounded(client, request_id: str) -> dict:
    accepted = client.create(
        request_id,
        "What exact PHASE23_WORKSPACE_FACT statement is in this workspace?",
        [], [], False,
    )
    terminal = client.wait_for_terminal(accepted["session_id"], timeout=360)
    return terminal


def _answer_passed(terminal: dict, phrase: str) -> bool:
    result = terminal.get("result") or {}
    citations = result.get("citations") or []
    return all((
        result.get("status") == "verified",
        phrase in (result.get("content") or ""), bool(citations),
        all(item.get("source_locator", "").startswith("file:") for item in citations),
    ))


def _wait_documents(client, minimum: int, timeout: float = 120) -> list[dict]:
    deadline = time.monotonic() + timeout
    latest = []
    while time.monotonic() < deadline:
        latest = client.documents()
        if len(latest) >= minimum:
            return latest
        time.sleep(0.2)
    raise TimeoutError(f"installed document indexing did not finish: {latest}")


def _service(
    installation, state, run, ollama_url, model_root, manage_ollama,
    validation_profile,
):
    return CandidateService(
        installation, state, run, ollama_url=ollama_url,
        source_model_root=model_root, manage_ollama=manage_ollama,
        validation_profile=validation_profile,
    )


def _client(service) -> MemoryConsoleClient:
    token = (service.runtime_root / "console.token").read_text().strip()
    return MemoryConsoleClient(f"http://127.0.0.1:{service.port}", token)


def _index_count(snapshot: dict) -> int:
    value = next(
        item["value"]
        for section in snapshot.get("sections", ())
        if section.get("section_id") == "memory"
        for item in section.get("items", ())
        if item.get("item_id") == "indexes"
    )
    return int(value)
