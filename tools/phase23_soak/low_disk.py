"""Real low-disk product fault in a private mount namespace."""

from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

from fam_os.product.bundle_installation import SignedBundleInstallation

from .service_session import InstalledSoakSession


TMPFS_BYTES = 256 * 1024 * 1024


def run_low_disk_pressure(
    *, installation: SignedBundleInstallation, root: Path,
    owner_ollama_url: str, source_model_root: Path,
) -> dict[str, object]:
    seed = root / "seed"
    export = root / "export"
    target = root / "mounted-state"
    control = root / "control"
    run_root = root / "run"
    root.mkdir(parents=True, mode=0o700)
    seed.mkdir(mode=0o700)
    pressured = InstalledSoakSession(
        installation=installation, state_root=target, run_root=run_root,
        ollama_url=owner_ollama_url, source_model_root=source_model_root,
        manage_ollama=False,
        launch_prefix=_namespace_prefix(target, seed, export, control),
    ).start()
    request_outcome: dict[str, object]
    try:
        (control / "pressure.request").write_text("inject\n")
        pressure = _wait_json(control / "pressure.json", timeout=30)
        try:
            request_outcome = pressured.verified_ready("phase23-soak-low-disk")
        except Exception as error:
            request_outcome = {
                "passed": False,
                "safe_failure": True,
                "error_type": type(error).__name__,
            }
    finally:
        pressured.stop()
    exported = _wait_json(control / "export.json", timeout=30)
    recovery_target = root / "recovery-mounted-state"
    recovery_export = root / "recovery-export"
    recovery_control = root / "recovery-control"
    recovery = InstalledSoakSession(
        installation=installation, state_root=recovery_target,
        run_root=root / "recovery-run", ollama_url=owner_ollama_url,
        source_model_root=source_model_root, manage_ollama=False,
        launch_prefix=_namespace_prefix(
            recovery_target, export, recovery_export, recovery_control,
        ),
    ).start()
    try:
        recovered = recovery.verified_ready("phase23-soak-low-disk-recovery")
    finally:
        recovery.stop()
    return {
        "tmpfs_bytes": TMPFS_BYTES,
        "host_owner_uid": os.geteuid(),
        "namespace_owner_uid": 0,
        "isolated_state_continuity": True,
        "pressure": pressure,
        "pressured_request": request_outcome,
        "export": exported,
        "recovery": recovered,
        "passed": bool(
            pressure.get("injected") is True
            and pressure.get("enospc_observed") is True
            and _integer_fact(pressure, "free_after_bytes") < 2 * 1024 * 1024
            and exported.get("exported") is True
            and recovered.get("passed") is True
        ),
    }


def _namespace_prefix(
    target: Path, seed: Path, export: Path, control: Path,
) -> tuple[str, ...]:
    launcher = Path(__file__).with_name("low_disk_launcher.py").absolute()
    return (
        "unshare", "--user", "--map-root-user", "--mount",
        sys.executable, str(launcher),
        "--state-root", str(target),
        "--seed-root", str(seed),
        "--export-root", str(export),
        "--control-root", str(control),
        "--size-bytes", str(TMPFS_BYTES), "--",
    )


def _wait_json(path: Path, timeout: float) -> dict[str, object]:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.is_file():
            document = json.loads(path.read_text("utf-8"))
            if not isinstance(document, dict) or any(
                not isinstance(key, str) for key in document
            ):
                raise ValueError(f"low-disk helper published invalid {path.name}")
            return document
        time.sleep(0.05)
    raise TimeoutError(f"low-disk helper did not publish {path.name}")


def _integer_fact(document: dict[str, object], key: str) -> int:
    value = document.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"low-disk helper omitted integer {key}")
    return value
