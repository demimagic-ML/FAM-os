"""Installed recovery-mode Console authority proof."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from tools.phase19_exit.console_client import ConsoleClient

from .service import CandidateService


def run_recovery_console_scenario(
    *, installation: Any, root: Path, ollama_url: str,
    source_model_root: Path,
) -> dict[str, object]:
    state = root / "state"
    database = state / "state/fam.sqlite3"
    database.parent.mkdir(parents=True)
    database.write_bytes(b"existing encrypted state without owner key")
    service = CandidateService(
        installation, state, root / "run",
        ollama_url=ollama_url,
        source_model_root=source_model_root,
    )
    try:
        service.start()
        client = ConsoleClient(
            f"http://127.0.0.1:{service.port}",
            (service.runtime_root / "console.token").read_text().strip(),
        )
        snapshot = client.snapshot()
    finally:
        service.stop()
    items = {
        (section["section_id"], item["item_id"]): item
        for section in snapshot.get("sections", ())
        for item in section.get("items", ())
    }
    unavailable_sections = {}
    for section_id in (
        "resources", "experts", "permissions", "memory", "audit",
    ):
        section_items = tuple(
            item for (candidate_section, _), item in items.items()
            if candidate_section == section_id
        )
        unavailable_sections[section_id] = bool(section_items) and all(
            item.get("status") == "unavailable" for item in section_items
        )
    recovery = items.get(("recovery", "mode"), {})
    passed = all((
        snapshot.get("recovery_mode") is True,
        recovery.get("value") == "Enabled",
        recovery.get("status") == "attention",
        all(unavailable_sections.values()),
        database.is_file(),
        not (state / "state/master.key").exists(),
    ))
    return {
        "recovery_mode": snapshot.get("recovery_mode"),
        "recovery_item": recovery,
        "unavailable_sections": unavailable_sections,
        "owner_key_absent": not (state / "state/master.key").exists(),
        "passed": passed,
    }
