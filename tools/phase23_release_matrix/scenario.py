"""Orchestrate independent clean profiles around one built wheel."""

from __future__ import annotations

import tempfile
from pathlib import Path

from .artifacts import build_wheel, file_sha256
from .contracts import HARDWARE_SUITE_PATTERN, ProfileKind, ReleaseProfile
from .environment import create_profile_environment
from .evidence import (
    matrix_document,
    source_identity,
    write_evidence,
)
from .settings import MatrixSettings
from .suites import run_unittest_suite, skips_are_declared
from .vscode import run_vscode_profile


def run_matrix(settings: MatrixSettings) -> dict[str, object]:
    settings.output_root.mkdir(parents=True, exist_ok=False)
    wheel = build_wheel(
        settings.repository, settings.python, settings.output_root / "wheel",
        settings.output_root / "wheel-build.log",
    )
    profiles: list[dict[str, object]] = []
    with tempfile.TemporaryDirectory(prefix=f"fam-{settings.run_id}-") as raw:
        work_root = Path(raw)
        for profile in settings.profiles:
            profiles.append(_run_profile(settings, profile, wheel, work_root))
    document = matrix_document(
        run_id=settings.run_id,
        wheel=wheel,
        wheel_sha256=file_sha256(wheel),
        source=source_identity(settings.repository),
        profiles=tuple(profiles),
    )
    write_evidence(settings.output_root / "profile-matrix.json", document)
    return document


def _run_profile(
    settings: MatrixSettings, profile: ReleaseProfile, wheel: Path, work_root: Path,
) -> dict[str, object]:
    output = settings.output_root / "profiles" / profile.name
    output.mkdir(parents=True)
    record: dict[str, object] = {
        "extra": profile.extra,
        "kind": profile.kind.value,
        "name": profile.name,
        "phase23_required": profile.phase23_required,
    }
    try:
        python, installation = create_profile_environment(
            profile=profile, wheel=wheel,
            root=work_root / profile.name,
            log_path=output / "install.log",
            dependency_wheelhouse=settings.dependency_wheelhouse,
        )
        record["installation"] = installation
        suites: list[dict[str, object]] = []
        record["suites"] = suites
        suites.append(run_unittest_suite(
            python=python, repository=settings.repository,
            start_directory="tests", pattern="test*.py",
            output_root=output, name="standard-suite",
        ))
        if profile.run_hardware_suite:
            suites.append(run_unittest_suite(
                python=python, repository=settings.repository,
                start_directory="tests/hardware", pattern=HARDWARE_SUITE_PATTERN,
                output_root=output, name="hardware-suite",
            ))
        connector = None
        if profile.kind is ProfileKind.VSCODE:
            connector = run_vscode_profile(
                python=python, repository=settings.repository,
                root=work_root / f"{profile.name}-connector",
                output_root=output, code=settings.code,
            )
        declared = skips_are_declared(
            tuple(suites), media_installed=profile.name == "media",
        )
        record.update({
            "connector": connector,
            "installation": installation,
            "passed": declared and all(bool(suite["passed"]) for suite in suites),
            "skips_declared": declared,
            "suites": suites,
        })
    except Exception as error:  # preserve the complete matrix instead of hiding later profiles
        record.update({
            "error": {"message": str(error), "type": type(error).__name__},
            "passed": False,
        })
    return record
