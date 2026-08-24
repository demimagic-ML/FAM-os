"""Deterministic redaction for untrusted engineering diagnostic text."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import re


_ANSI = re.compile(r"\x1b(?:\[[0-?]*[ -/]*[@-~]|\][^\x07]*(?:\x07|\x1b\\))")
_CONTROL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]")
_PRIVATE_KEY = re.compile(
    r"-----BEGIN [A-Z0-9 ]*PRIVATE KEY-----.*?"
    r"-----END [A-Z0-9 ]*PRIVATE KEY-----",
    re.DOTALL,
)
_SECRET = re.compile(
    r"(?i)("
    r"authorization\s*:\s*(?:bearer|basic)\s+\S+|"
    r"(?:password|passwd|secret|api[_ -]?key|access[_ -]?token|"
    r"refresh[_ -]?token|client[_ -]?secret|auth[_ -]?token|token)"
    r"\s*[:=]\s*[^\s,;]+|"
    r"gh[pousr]_[A-Za-z0-9_]{20,}|"
    r"xox[baprs]-[A-Za-z0-9-]{10,}|"
    r"AKIA[A-Z0-9]{16}|"
    r"AIza[0-9A-Za-z_-]{30,}|"
    r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"
    r")"
)
_HOST_PATH = re.compile(
    r"(?<![A-Za-z0-9_.-])(?:/home/[^/\s:'\"<>]+|/root|"
    r"/tmp/tmp[A-Za-z0-9._-]+)(?:/[^\s:'\"<>]*)?"
)


@dataclass(frozen=True, slots=True)
class SanitizedDiagnosticText:
    content: bytes
    sanitizer_evidence_id: str


class DeterministicDiagnosticTextSanitizer:
    """Remove credentials, private host paths, ANSI, and control bytes."""

    def sanitize(self, value: str, maximum_bytes: int) -> SanitizedDiagnosticText:
        if not isinstance(value, str) or maximum_bytes <= 0:
            raise ValueError("diagnostic sanitization input is invalid")
        cleaned = _clean(value)
        content = cleaned.encode("utf-8")
        if len(content) > maximum_bytes:
            raise ValueError("sanitized diagnostic output exceeds its artifact limit")
        if _has_secret(cleaned):
            raise ValueError("diagnostic output remains secret-bearing after sanitization")
        return SanitizedDiagnosticText(
            content,
            "diagnostic-text-sanitizer-v2:" + hashlib.sha256(content).hexdigest(),
        )


def sanitize_diagnostic_feedback(
    values,
    *,
    maximum_items: int = 16,
    maximum_item_bytes: int = 2_048,
    maximum_total_bytes: int = 16_384,
) -> tuple[str, ...]:
    """Return model-safe, bounded diagnostic excerpts with source digests."""
    if min(maximum_items, maximum_item_bytes, maximum_total_bytes) <= 0:
        raise ValueError("diagnostic feedback bounds must be positive")
    raw_values = tuple(values)
    if any(not isinstance(value, str) or not value.strip() for value in raw_values):
        raise ValueError("diagnostic feedback values must be non-empty text")
    selected = raw_values[:maximum_items]
    if len(raw_values) > maximum_items:
        selected = raw_values[: max(0, maximum_items - 1)] + (
            _omission_marker(raw_values[maximum_items - 1:]),
        )
    result: list[str] = []
    used = 0
    for value in selected:
        source_digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
        if _has_secret(value):
            safe = f"[REDACTED_DIAGNOSTIC sha256={source_digest}]"
        else:
            cleaned = _clean(value)
            safe = f"diagnostic_sha256={source_digest};{cleaned}"
        safe = _bounded(safe, maximum_item_bytes, source_digest)
        size = len(safe.encode("utf-8"))
        if used + size > maximum_total_bytes:
            marker = f"[TRUNCATED_DIAGNOSTICS sha256={source_digest}]"
            if used + len(marker.encode("utf-8")) <= maximum_total_bytes:
                result.append(marker)
            break
        result.append(safe)
        used += size
    return tuple(result)


def sanitize_diagnostic_evidence(
    value: str, *, maximum_bytes: int = 4_096,
) -> str:
    """Return bounded persisted evidence, replacing secret-bearing text wholly."""
    if not isinstance(value, str) or maximum_bytes <= 0:
        raise ValueError("diagnostic evidence input is invalid")
    source_digest = hashlib.sha256(value.encode("utf-8")).hexdigest()
    safe = (
        f"[REDACTED_DIAGNOSTIC sha256={source_digest}]"
        if _has_secret(value) else _clean(value)
    )
    safe = _bounded(safe, maximum_bytes, source_digest)
    if _has_secret(safe):
        raise ValueError("diagnostic evidence remains secret-bearing after redaction")
    return safe


def _clean(value: str) -> str:
    cleaned = _ANSI.sub("", value)
    cleaned = _CONTROL.sub("�", cleaned)
    cleaned = _PRIVATE_KEY.sub("[REDACTED]", cleaned)
    cleaned = _SECRET.sub("[REDACTED]", cleaned)
    return _HOST_PATH.sub("[REDACTED_PATH]", cleaned)


def _has_secret(value: str) -> bool:
    return _PRIVATE_KEY.search(value) is not None or _SECRET.search(value) is not None


def _bounded(value: str, maximum_bytes: int, source_digest: str) -> str:
    encoded = value.encode("utf-8")
    if len(encoded) <= maximum_bytes:
        return value
    marker = f"...[TRUNCATED sha256={source_digest}]"
    available = maximum_bytes - len(marker.encode("utf-8"))
    if available <= 0:
        return marker.encode("utf-8")[:maximum_bytes].decode("utf-8", "ignore")
    prefix = encoded[:available].decode("utf-8", "ignore")
    return prefix + marker


def _omission_marker(values: tuple[str, ...]) -> str:
    digest = hashlib.sha256("\0".join(values).encode("utf-8")).hexdigest()
    return f"omitted_diagnostic_count={len(values)};sha256={digest}"
