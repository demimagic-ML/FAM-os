"""Validated configuration for ChatGPT-authenticated Codex inference."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


_REASONING_EFFORTS = frozenset({
    "low", "medium", "high", "xhigh", "max", "ultra",
})


@dataclass(frozen=True, slots=True)
class CodexSubscriptionSettings:
    executable: Path
    work_root: Path
    home: Path
    model_ref: str = "gpt-5.6-sol"
    reasoning_effort: str = "medium"
    timeout_seconds: float = 600.0
    maximum_prompt_bytes: int = 131_072
    maximum_stdout_bytes: int = 2_097_152
    maximum_stderr_bytes: int = 65_536

    def __post_init__(self) -> None:
        if not self.executable.is_absolute():
            raise ValueError("Codex executable must be absolute")
        if not self.work_root.is_absolute() or not self.home.is_absolute():
            raise ValueError("Codex roots must be absolute")
        if not self.model_ref.strip():
            raise ValueError("Codex model reference must not be empty")
        if self.reasoning_effort not in _REASONING_EFFORTS:
            raise ValueError("Codex reasoning effort is unsupported")
        if min(
            self.timeout_seconds, self.maximum_prompt_bytes,
            self.maximum_stdout_bytes, self.maximum_stderr_bytes,
        ) <= 0:
            raise ValueError("Codex runtime bounds must be positive")
