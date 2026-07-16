"""Pure parsers and read-only readers for Linux procfs facts."""

from __future__ import annotations

from pathlib import Path


_UNIT_MULTIPLIERS = {"b": 1, "kb": 1024, "mb": 1024**2, "gb": 1024**3}


def parse_meminfo(content: str) -> dict[str, int]:
    values: dict[str, int] = {}
    for line in content.splitlines():
        if ":" not in line:
            continue
        key, raw = line.split(":", 1)
        parts = raw.strip().split()
        if not parts:
            continue
        unit = parts[1].lower() if len(parts) > 1 else "b"
        multiplier = _UNIT_MULTIPLIERS.get(unit)
        try:
            if multiplier is not None:
                values[key] = int(parts[0]) * multiplier
        except ValueError:
            continue
    return values


def read_meminfo(path: Path) -> dict[str, int]:
    try:
        return parse_meminfo(path.read_text())
    except OSError:
        return {}


def parse_cpu_model(content: str) -> str | None:
    candidates: dict[str, str] = {}
    for line in content.splitlines():
        if ":" not in line:
            continue
        key, value = (part.strip() for part in line.split(":", 1))
        candidates.setdefault(key.lower(), value)
    for key in ("model name", "hardware", "model"):
        if candidates.get(key):
            return candidates[key]
    processor = candidates.get("processor")
    return processor if processor and not processor.isdigit() else None


def read_cpu_model(path: Path) -> str | None:
    try:
        return parse_cpu_model(path.read_text())
    except OSError:
        return None

