"""Build once, then qualify both installed hardware profiles independently."""

from __future__ import annotations

import shutil
import tempfile
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from tools.phase23_installed_matrix.candidate import build_candidate
from tools.phase23_installed_matrix.escalation_scenario import run_escalation_scenario
from tools.phase23_installed_matrix.memory_scenario import run_memory_scenario

from .contracts import HardwareMatrixSettings
from .evidence import finalize, initial_document, write
from .owner_workload import OwnerModelQuiescence
from .profile_scenario import MANAGED_OLLAMA_URL, run_profile_scenario
from .telemetry import managed_service_inactive


def run_hardware_matrix(settings: HardwareMatrixSettings) -> dict[str, Any]:
    settings.output_root.mkdir(parents=True, mode=0o700)
    output = settings.output_root / "installed-hardware-matrix.json"
    # AF_UNIX paths are limited to 107 encoded bytes on Linux. Evidence keeps
    # the full run identity; the private execution root stays deliberately short.
    with tempfile.TemporaryDirectory(prefix="f23h-") as raw:
        work = Path(raw)
        candidate = build_candidate(
            settings.repository, work / "candidate", settings.run_id,
        )
        document: dict[str, Any] = initial_document(settings.run_id, candidate)
        owner_before = _owner_status()
        document["live_owner_service_before"] = owner_before
        quiescence = OwnerModelQuiescence(
            settings.owner_ollama_url,
            enabled=settings.quiesce_owner_models,
        )
        document["owner_model_quiescence"] = quiescence.prepare()
        write(output, document)
        installation = candidate.install("hardware-matrix")
        try:
            for profile_id in (
                "compat-cpu-16gb", "full-reference-workstation",
            ):
                if profile_id == "full-reference-workstation":
                    document["owner_model_quiescence"] = quiescence.start_monitor()
                profile_task = _record(lambda: (
                    run_profile_scenario(
                        installation=installation,
                        root=work / profile_id / "verified-local",
                        source_model_root=settings.source_model_root,
                        profile_id=profile_id,
                    )
                ))
                memory = _record(lambda: run_memory_scenario(
                    installation=installation,
                    root=work / profile_id / "memory",
                    ollama_url=MANAGED_OLLAMA_URL,
                    source_model_root=settings.source_model_root,
                    manage_ollama=True,
                    validation_profile=profile_id,
                ))
                document["profiles"][profile_id] = {
                    "verified_local": profile_task,
                    "grounded_memory_restart": memory,
                    "passed": bool(
                        profile_task.get("passed") is True
                        and memory.get("passed") is True
                    ),
                }
                if profile_id == "full-reference-workstation":
                    document["owner_model_quiescence"] = quiescence.assert_idle()
                write(output, document)
            document["owner_model_quiescence"] = quiescence.assert_idle()
            document["full_strong_escalation"] = _record(lambda: (
                run_escalation_scenario(
                    installation=installation, repository=settings.repository,
                    root=work / "full-strong-escalation",
                    ollama_url=MANAGED_OLLAMA_URL,
                    source_model_root=settings.source_model_root,
                    manage_ollama=True,
                    validation_profile="full-reference-workstation",
                )
            ))
            document["owner_model_quiescence"] = quiescence.assert_idle()
        finally:
            document["complete_removal"] = candidate.remove_all()
            source_log = candidate.root / "wheel-build.log"
            if source_log.is_file():
                shutil.copy2(source_log, settings.output_root / "wheel-build.log")
            document["managed_service_inactive"] = managed_service_inactive()
            document["owner_model_quiescence"] = quiescence.final()
            owner_after = _owner_status()
            document["live_owner_service_after"] = owner_after
            document["live_owner_service_preserved"] = bool(
                owner_before.get("http_status") == 200
                and owner_after.get("http_status") == 200
            )
            finalize(document)
            write(output, document)
    return document


def _record(operation: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    try:
        return dict(operation())
    except Exception as error:
        return {
            "passed": False,
            "error": {"type": type(error).__name__, "message": str(error)},
        }


def _owner_status() -> dict[str, object]:
    try:
        response = urllib.request.urlopen("http://127.0.0.1:8765/", timeout=5)
        return {"http_status": response.status}
    except Exception as error:
        return {"http_status": None, "error": type(error).__name__}
