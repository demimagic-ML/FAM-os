"""Versioned JSON artifact writing for migration benchmarks."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def captured_at() -> str:
    return datetime.now(timezone.utc).isoformat()


def write_report(output_dir: Path, prefix: str, payload: dict[str, Any]) -> Path:
    if not prefix.strip() or "/" in prefix:
        raise ValueError("report prefix must be a simple non-empty name")
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S-%f")
    output = output_dir / f"{prefix}-{timestamp}.json"
    output.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    return output
