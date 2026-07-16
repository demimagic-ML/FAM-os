#!/usr/bin/env python3
"""Execute product lifecycle probes and bind all Phase 14 exit evidence."""

from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fam_os.console.contracts import REQUIRED_SECTIONS
from fam_os.console.provider import LocalConsoleProvider
from fam_os.product.atomic_update import AtomicReleaseManager
from fam_os.product.linux_installation import LinuxInstallation
from fam_os.product.phase14_exit import phase14_exit
from fam_os.product.recovery_mode import RecoveryModePolicy, RecoveryOperation
from fam_os.product.update_contracts import ComponentKind, ReleaseComponent
from fam_os.product.update_signing import sign_manifest
from fam_os.product.user_isolation import PrivateUserRuntime, UserRuntimeIdentity


SOAK = Path("artifacts/product/phase14.4/five-minute-soak.json")
BENCHMARK = Path("artifacts/product/phase14.7/reference-benchmarks.json")
SECURITY = Path("artifacts/security/phase14.1/security-review.json")


def main() -> None:
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        update_ok = _update_probe(root)
        lifecycle_ok = _installation_probe(root)
        isolation_ok = _isolation_probe(root)
        console_ok = _console_probe(root)
    soak = json.loads(SOAK.read_text())
    benchmark = json.loads(BENCHMARK.read_text())
    security = json.loads(SECURITY.read_text())
    report = phase14_exit(
        security_review_passed=security["passed"],
        atomic_update_and_rollback_passed=update_ok,
        user_isolation_and_recovery_passed=isolation_ok,
        extended_soak_passed=soak["passed"],
        install_diagnose_repair_remove_passed=lifecycle_ok,
        shell_console_visibility_passed=console_ok,
        reference_benchmarks_passed=benchmark["passed"],
        soak_sha256=_digest(SOAK), benchmark_sha256=_digest(BENCHMARK),
    )
    output = Path("artifacts/product/phase14-exit.json")
    output.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n")
    print(json.dumps(report.to_dict(), sort_keys=True))
    raise SystemExit(not report.passed)


def _update_probe(root: Path) -> bool:
    key = Ed25519PrivateKey.generate()
    manager = AtomicReleaseManager(root / "updates", {"key": key.public_key()})
    first = manager.apply(_manifest(root, "v1", key), lambda path: True)
    failed = manager.apply(_manifest(root, "bad", key), lambda path: False)
    second = manager.apply(_manifest(root, "v2", key), lambda path: True)
    rollback = manager.rollback("v1", lambda path: True)
    return (first.activated and not failed.activated and failed.active_release_id == "v1"
            and second.activated and rollback.rolled_back
            and manager.active_release_id() == "v1")


def _manifest(root: Path, release_id: str, key):
    values = []
    for kind in ComponentKind:
        path = root / f"{release_id}-{kind.value}"
        path.write_text(f"{release_id}:{kind.value}")
        values.append(ReleaseComponent(kind, "payload", str(path), _digest(path)))
    return sign_manifest(release_id, tuple(values), "key", key)


def _installation_probe(root: Path) -> bool:
    installation = LinuxInstallation(root / "installed" / "fam-os")
    installed = installation.install(Path("src/fam_os"), "phase14")
    launcher = installation.prefix / "bin" / "fam-shell"
    launcher.write_text("damaged")
    damage_seen = not installation.diagnose().healthy
    repaired = installation.repair(Path("src/fam_os"))
    installation.remove()
    return installed.healthy and damage_seen and repaired.healthy and not installation.prefix.exists()


def _isolation_probe(root: Path) -> bool:
    runtime = PrivateUserRuntime(root / "user", UserRuntimeIdentity("owner", os.geteuid()))
    runtime.initialize()
    policy = RecoveryModePolicy()
    denied = all(not policy.decide(item).allowed for item in (
        RecoveryOperation.RUN_INFERENCE, RecoveryOperation.APPLICATION_ACTION,
        RecoveryOperation.MUTATE_MEMORY, RecoveryOperation.TRAIN_EXPERT,
        RecoveryOperation.NETWORK_ACCESS,
    ))
    return denied and runtime.private_path("memory", "state").parent.name == "memory"


def _console_probe(root: Path) -> bool:
    snapshot = LocalConsoleProvider(root / "user", "phase14").snapshot()
    return tuple(item.section_id for item in snapshot.sections) == REQUIRED_SECTIONS


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    main()
