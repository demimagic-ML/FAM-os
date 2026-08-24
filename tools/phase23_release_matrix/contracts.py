"""Immutable Phase 23 release-profile definitions."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class ProfileKind(str, Enum):
    PYTHON = "python"
    VSCODE = "vscode"


@dataclass(frozen=True, slots=True)
class ReleaseProfile:
    name: str
    extra: str | None
    kind: ProfileKind
    distributions: tuple[str, ...]
    phase23_required: bool = True
    run_hardware_suite: bool = False

    @property
    def install_suffix(self) -> str:
        return f"[{self.extra}]" if self.extra else ""


PROFILES = (
    ReleaseProfile("base", None, ProfileKind.PYTHON, ()),
    ReleaseProfile(
        "verification", "verification", ProfileKind.PYTHON, ("mypy", "ruff"),
    ),
    ReleaseProfile(
        "mathematics", "mathematics", ProfileKind.PYTHON, ("sympy",),
    ),
    ReleaseProfile(
        "media", "media", ProfileKind.PYTHON,
        ("faster-whisper", "pillow", "piper-tts"),
    ),
    ReleaseProfile(
        "development", "development", ProfileKind.PYTHON,
        ("build", "coverage", "mypy", "ruff", "wheel"),
        phase23_required=False,
    ),
    ReleaseProfile(
        "hardware", "hardware", ProfileKind.PYTHON,
        ("nvidia-ml-py", "psutil"), run_hardware_suite=True,
    ),
    ReleaseProfile(
        "training", "training", ProfileKind.PYTHON,
        (
            "accelerate", "bitsandbytes", "datasets", "peft", "torch",
            "transformers", "trl",
        ),
    ),
    ReleaseProfile("vscode", None, ProfileKind.VSCODE, ()),
)

HARDWARE_SUITE_PATTERN = "*_smoke.py"


def select_profiles(names: tuple[str, ...]) -> tuple[ReleaseProfile, ...]:
    available = {profile.name: profile for profile in PROFILES}
    selected_names = names or tuple(
        profile.name for profile in PROFILES if profile.phase23_required
    )
    unknown = tuple(name for name in selected_names if name not in available)
    if unknown:
        raise ValueError(f"unknown release profiles: {', '.join(unknown)}")
    if len(set(selected_names)) != len(selected_names):
        raise ValueError("release profiles must be unique")
    return tuple(available[name] for name in selected_names)
