"""Execute product test suites with the clean profile interpreter."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

from .environment import clean_environment


def run_unittest_suite(
    *, python: Path, repository: Path, start_directory: str, pattern: str,
    output_root: Path, name: str,
) -> dict[str, object]:
    result_path = output_root / f"{name}.json"
    log_path = output_root / f"{name}.log"
    with (output_root / f"{name}-process.log").open("w", encoding="utf-8") as process_log:
        completed = subprocess.run(
            (
                str(python), "-m", "tools.phase23_release_matrix.test_program",
                "--start-directory", start_directory,
                "--pattern", pattern,
                "--top-level", str(repository),
                "--output", str(result_path),
                "--log", str(log_path),
            ),
            cwd=repository, env=clean_environment(), text=True, timeout=3_600,
            stdout=process_log, stderr=subprocess.STDOUT,
        )
    if not result_path.is_file():
        raise RuntimeError(
            f"{name} suite exited {completed.returncode} without durable results"
        )
    document = json.loads(result_path.read_text(encoding="utf-8"))
    if completed.returncode != 0 or not document.get("passed"):
        raise RuntimeError(f"{name} suite failed; see {log_path}")
    return document


def skips_are_declared(
    suites: tuple[dict[str, object], ...], *, media_installed: bool,
) -> bool:
    common = (
        "AT-SPI is unavailable",
        "no unambiguous accessible application process",
        "live isolated VS Code acceptance is opt-in",
        "X11 desktop is unavailable",
        "focused X11 process identity is unavailable",
        "Linux procfs is unavailable",
        "live sandbox smoke disabled",
        "live parity disabled",
        "live systemd smoke disabled",
        "set FAM_",
        "for the live",
        "a named AppArmor profile authorizing userns is required",
        "set FAM_OLLAMA_SMOKE_MODEL",
    )
    allowed = common + (() if media_installed else (
        "optional Pillow capture backend is unavailable",
    ))
    reasons = (
        str(item["reason"])
        for suite in suites
        for item in suite.get("skipped", ())
        if isinstance(item, dict) and "reason" in item
    )
    return all(any(fragment in reason for fragment in allowed) for reason in reasons)
