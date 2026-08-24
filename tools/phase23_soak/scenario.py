"""Orchestrate the installed Phase 23 soak without acceptance composition."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tools.phase23_hardware_matrix.telemetry import managed_service_inactive

from .connector_churn import run_connector_churn
from .contracts import SoakSettings
from .evidence import EvidenceLedger
from .faults import run_daemon_restart, run_ollama_crash, run_verifier_crash
from .low_disk import run_low_disk_pressure
from .pressure import run_model_pressure
from .release_pair import SignedReleasePair, build_release_pair
from .service_session import InstalledSoakSession, InstalledSoakSessionFactory


def run_installed_soak(settings: SoakSettings) -> dict[str, Any]:
    settings.output_root.mkdir(parents=True, mode=0o700)
    work = Path(tempfile.mkdtemp(prefix="f23s-", dir="/tmp"))
    work.chmod(0o700)
    ledger = EvidenceLedger(settings.output_root, settings)
    owner_before = _owner_service()
    started_at = datetime.now(UTC).isoformat()
    started = time.monotonic()
    pair: SignedReleasePair | None = None
    installation: Any = None
    session: InstalledSoakSession | None = None
    candidate: dict[str, Any] = {}
    failure_type: str | None = None
    stage = "candidate-build"
    try:
        pair = build_release_pair(settings.repository, work / "candidate", settings.run_id)
        candidate = pair.identity()
        stage = "base-install"
        installation = pair.installation(work / "installation")
        receipt = installation.install(pair.base_bundle)
        if not receipt.healthy or receipt.release_id != pair.base_manifest.release_id:
            raise RuntimeError("signed soak base release did not install healthily")
        candidate["installed_module"] = _candidate_module(installation, work)
        factory = InstalledSoakSessionFactory(
            installation, work, settings.ollama_url, settings.source_model_root,
        )
        stage = "base-service"
        session = factory.new("base").start()
        stage = "base-inference"
        _record(ledger, "verified_inference", session.verified_ready(
            "phase23-soak-base-ready",
        ))
        _record(ledger, "resource_sample", {
            **session.resource_sample(), "passed": True,
        })
        stage = "verifier-crash"
        _record(ledger, "verifier_crash", run_verifier_crash(
            session, installation, work / "verifier-fault",
        ))
        stage = "ollama-crash"
        _record(ledger, "ollama_crash", run_ollama_crash(
            session, settings.ollama_url,
        ))
        stage = "daemon-restart"
        session, daemon = run_daemon_restart(session, factory.new)
        _record(ledger, "daemon_restart", daemon)
        session.stop()
        session = None
        stage = "low-disk"
        _record(ledger, "low_disk_pressure", run_low_disk_pressure(
            installation=installation,
            root=work / "low-disk",
            owner_ollama_url=settings.owner_ollama_url,
            source_model_root=settings.source_model_root,
        ))
        stage = "connector-churn"
        _record(ledger, "connector_churn", run_connector_churn(
            installation=installation,
            repository=settings.repository,
            root=work / "connector-initial",
            ollama_url=settings.owner_ollama_url,
            source_model_root=settings.source_model_root,
        ))
        stage = "model-pressure"
        _record(ledger, "model_pressure", run_model_pressure(
            installation=installation,
            repository=settings.repository,
            root=work / "model-pressure",
            ollama_url=settings.ollama_url,
            source_model_root=settings.source_model_root,
            full=settings.full_model_pressure,
        ))
        stage = "signed-update"
        update = installation.update(pair.update_bundle)
        _record(ledger, "signed_update", {
            **_receipt(update),
            "expected_release_id": pair.update_manifest.release_id,
            "passed": bool(
                update.healthy
                and update.release_id == pair.update_manifest.release_id
            ),
        })
        stage = "updated-service"
        session = factory.new("updated").start()
        _record(ledger, "verified_inference", session.verified_ready(
            "phase23-soak-update-ready",
        ))
        _record(ledger, "resource_sample", {
            **session.resource_sample(), "passed": True,
        })
        stage = "steady-operation"
        session = _steady_operation(
            session=session, factory=factory, installation=installation,
            pair=pair, ledger=ledger, settings=settings, work=work,
            started=started,
        )
        session.stop()
        session = None
        stage = "signed-rollback"
        rollback = installation.rollback(pair.base_manifest.release_id)
        _record(ledger, "signed_rollback", {
            **_receipt(rollback),
            "expected_release_id": pair.base_manifest.release_id,
            "passed": bool(
                rollback.healthy
                and rollback.release_id == pair.base_manifest.release_id
            ),
        })
        stage = "final-recovery"
        session = factory.new("final-base").start()
        _record(ledger, "final_recovery", session.verified_ready(
            "phase23-soak-final-recovery",
        ))
        _record(ledger, "resource_sample", {
            **session.resource_sample(), "passed": True,
        })
    except Exception as error:
        failure_type = type(error).__name__
        ledger.append("harness_failure", False, {
            "error_type": failure_type,
            "stage": stage,
        })
    finally:
        if session is not None:
            try:
                session.stop()
            except Exception:
                try:
                    session.crash()
                except Exception:
                    pass
        _stop_managed_provider()
        if pair is not None:
            source_log = pair.root / "wheel-build.log"
            if source_log.is_file():
                shutil.copy2(source_log, settings.output_root / "wheel-build.log")
        removed = _remove(installation)
        shutil.rmtree(work, ignore_errors=True)
        owner_after = _owner_service()
        cleanup = {
            "complete_removal": bool(removed and not work.exists()),
            "managed_ollama_inactive": managed_service_inactive(),
            "owner_service_before": owner_before,
            "owner_service_after": owner_after,
            "owner_service_preserved": bool(
                owner_before.get("http_status") == 200
                and owner_after.get("http_status") == 200
            ),
            "failure_type": failure_type,
        }
    return ledger.finalize(
        started_at=started_at,
        duration_seconds=time.monotonic() - started,
        candidate=candidate,
        cleanup=cleanup,
    )


def _steady_operation(
    *, session: InstalledSoakSession, factory: InstalledSoakSessionFactory,
    installation: Any, pair: SignedReleasePair, ledger: EvidenceLedger,
    settings: SoakSettings, work: Path, started: float,
) -> InstalledSoakSession:
    request_number = 0
    next_connector = time.monotonic() + settings.connector_interval_seconds
    next_daemon = time.monotonic() + settings.daemon_restart_interval_seconds
    next_provider = time.monotonic() + settings.provider_crash_interval_seconds
    while time.monotonic() - started < settings.duration_seconds:
        now = time.monotonic()
        if now >= next_connector:
            session.stop()
            _record(ledger, "connector_churn", run_connector_churn(
                installation=installation,
                repository=settings.repository,
                root=work / f"connector-{request_number}",
                ollama_url=settings.owner_ollama_url,
                source_model_root=settings.source_model_root,
            ))
            session = factory.new(f"connector-recovery-{request_number}").start()
            next_connector = now + settings.connector_interval_seconds
        if now >= next_daemon:
            session, event = run_daemon_restart(
                session, factory.new, event_id=str(request_number),
            )
            _record(ledger, "daemon_restart", event)
            next_daemon = now + settings.daemon_restart_interval_seconds
        if now >= next_provider:
            _record(ledger, "ollama_crash", run_ollama_crash(
                session, settings.ollama_url, event_id=str(request_number),
            ))
            next_provider = now + settings.provider_crash_interval_seconds
        probe = session.verified_ready(f"phase23-soak-steady-{request_number}")
        _record(ledger, "verified_inference", probe)
        _record(ledger, "resource_sample", {
            **session.resource_sample(), "passed": True,
        })
        request_number += 1
        remaining = settings.duration_seconds - (time.monotonic() - started)
        if remaining > 0:
            time.sleep(min(settings.request_interval_seconds, remaining))
    if session.release_id() != pair.update_manifest.release_id:
        raise RuntimeError("soak active release changed before planned rollback")
    return session


def _record(
    ledger: EvidenceLedger, kind: str, facts: dict[str, Any],
) -> None:
    passed = facts.get("passed") is True
    ledger.append(kind, passed, {
        key: value for key, value in facts.items() if key != "passed"
    })
    if not passed:
        raise RuntimeError(f"required soak event failed: {kind}")


def _candidate_module(installation: Any, cwd: Path) -> str:
    environment = dict(os.environ)
    environment.pop("PYTHONHOME", None)
    environment["PYTHONPATH"] = str(installation.prefix / "active/python")
    completed = subprocess.run(
        (sys.executable, "-c", "import fam_os; print(fam_os.__file__)"),
        cwd=cwd, env=environment, check=True, capture_output=True,
        text=True, timeout=30,
    )
    path = Path(completed.stdout.strip()).resolve()
    candidate = (installation.prefix / "active/python").resolve()
    if not path.is_relative_to(candidate):
        raise RuntimeError("soak subprocess imported FAM_OS outside the candidate")
    return str(path)


def _receipt(receipt: Any) -> dict[str, object]:
    return {
        "release_id": receipt.release_id,
        "healthy": receipt.healthy,
        "issues": tuple(receipt.issues),
    }


def _remove(installation: Any) -> bool:
    if installation is None:
        return True
    try:
        if installation.prefix.exists():
            installation.remove()
    except Exception:
        return False
    return not installation.prefix.exists()


def _stop_managed_provider() -> None:
    subprocess.run(
        ("systemctl", "--user", "stop", "fam-ollama.service"),
        check=False, capture_output=True, text=True, timeout=30,
    )


def _owner_service() -> dict[str, object]:
    try:
        response = urllib.request.urlopen("http://127.0.0.1:8765/", timeout=5)
        return {"http_status": response.status}
    except Exception as error:
        return {"http_status": None, "error_type": type(error).__name__}
