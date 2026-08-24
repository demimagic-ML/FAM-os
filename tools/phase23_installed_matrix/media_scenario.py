"""Real multimodal inference and signed media verification."""

from __future__ import annotations

import hashlib
from pathlib import Path

from tools.phase19_exit.console_client import ConsoleClient


def run_media_scenario(service, image: Path) -> dict[str, object]:
    digest = hashlib.sha256(image.read_bytes()).hexdigest()
    client = _client(service)
    accepted = client.create_verified(
        "phase23-media-ocr",
        "Read the image and report the exact visible text as the required JSON.",
        {
            "kind": "media_artifact_text", "artifact_path": str(image),
            "artifact_sha256": digest, "expected_text": "FAM LOCAL 5080",
            "maximum_artifact_bytes": image.stat().st_size,
        },
    )
    terminal = client.wait_for_terminal(accepted["session_id"], timeout=600)
    runs = client.verifications(accepted["session_id"])
    result = terminal.get("result") or {}
    return {
        "image_sha256": digest, "accepted": accepted, "terminal": terminal,
        "verification_runs": runs,
        "passed": all((
            result.get("status") == "verified", bool(runs),
            any(item.get("status") == "passed" for item in runs),
            "qwen3-vl:8b" in str(accepted) + str(terminal),
        )),
    }


def _client(service) -> ConsoleClient:
    token = (service.runtime_root / "console.token").read_text().strip()
    return ConsoleClient(f"http://127.0.0.1:{service.port}", token)
