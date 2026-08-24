"""Append-only content-free evidence and strict final qualification policy."""

from __future__ import annotations

import hashlib
import json
import os
import platform
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .contracts import CONTRACT_VERSION, REQUIRED_EVENT_MINIMUMS, SoakSettings


class EvidenceLedger:
    def __init__(self, root: Path, settings: SoakSettings) -> None:
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        self.root = root
        self.events_path = root / "events.jsonl"
        self.report_path = root / "installed-soak.json"
        self.settings = settings
        self._sequence = 0
        self._head = "0" * 64

    def append(self, kind: str, passed: bool, facts: dict[str, Any]) -> dict[str, Any]:
        self._sequence += 1
        event = {
            "contract_version": CONTRACT_VERSION,
            "sequence": self._sequence,
            "captured_at": datetime.now(UTC).isoformat(),
            "kind": kind,
            "passed": passed,
            "facts": facts,
            "previous_sha256": self._head,
        }
        encoded = json.dumps(event, sort_keys=True, separators=(",", ":")).encode()
        self._head = hashlib.sha256(encoded).hexdigest()
        event["event_sha256"] = self._head
        descriptor = os.open(
            self.events_path, os.O_WRONLY | os.O_CREAT | os.O_APPEND, 0o600,
        )
        with os.fdopen(descriptor, "a", encoding="utf-8") as stream:
            stream.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
            stream.flush()
            os.fsync(stream.fileno())
        return event

    def finalize(
        self, *, started_at: str, duration_seconds: float,
        candidate: dict[str, Any], cleanup: dict[str, Any],
    ) -> dict[str, Any]:
        events = self.read_events()
        event_chain_valid = _chain_valid(events)
        counts = {
            kind: sum(event["kind"] == kind and event["passed"] for event in events)
            for kind in REQUIRED_EVENT_MINIMUMS
        }
        required = {
            kind: {
                "observed": counts[kind],
                "minimum": minimum,
                "passed": counts[kind] >= minimum,
            }
            for kind, minimum in REQUIRED_EVENT_MINIMUMS.items()
        }
        all_events_passed = bool(events) and event_chain_valid and all(
            event["passed"] for event in events
        )
        preflight_passed = bool(
            all_events_passed
            and all(item["passed"] for item in required.values())
            and cleanup.get("complete_removal") is True
            and cleanup.get("owner_service_preserved") is True
            and cleanup.get("managed_ollama_inactive") is True
        )
        qualification_passed = bool(
            preflight_passed
            and self.settings.qualification_eligible
            and duration_seconds >= self.settings.duration_seconds
        )
        document = {
            "contract_version": CONTRACT_VERSION,
            "run_id": self.settings.run_id,
            "started_at": started_at,
            "completed_at": datetime.now(UTC).isoformat(),
            "host": {
                "hostname": platform.node(),
                "machine": platform.machine(),
                "kernel": platform.release(),
                "uid": os.geteuid(),
            },
            "requested_duration_seconds": self.settings.duration_seconds,
            "observed_duration_seconds": duration_seconds,
            "minimum_qualification_seconds": 86_400,
            "qualification_eligible": self.settings.qualification_eligible,
            "candidate": candidate,
            "event_count": len(events),
            "event_chain_head_sha256": self._head,
            "event_chain_valid": event_chain_valid,
            "required_events": required,
            "cleanup": cleanup,
            "preflight_passed": preflight_passed,
            "qualification_passed": qualification_passed,
            "passed": qualification_passed,
        }
        _atomic_json(self.report_path, document)
        return document

    def read_events(self) -> list[dict[str, Any]]:
        if not self.events_path.is_file():
            return []
        return [
            json.loads(line) for line in self.events_path.read_text("utf-8").splitlines()
            if line.strip()
        ]


def _atomic_json(path: Path, document: dict[str, Any]) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    temporary.replace(path)


def _chain_valid(events: list[dict[str, Any]]) -> bool:
    previous = "0" * 64
    for sequence, event in enumerate(events, start=1):
        claimed = event.get("event_sha256")
        unsigned = {key: value for key, value in event.items() if key != "event_sha256"}
        encoded = json.dumps(unsigned, sort_keys=True, separators=(",", ":")).encode()
        calculated = hashlib.sha256(encoded).hexdigest()
        if (
            event.get("sequence") != sequence
            or event.get("previous_sha256") != previous
            or claimed != calculated
        ):
            return False
        previous = calculated
    return True
