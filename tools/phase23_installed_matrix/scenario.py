"""Orchestrate all real scenarios around one signed installed candidate."""

from __future__ import annotations

import shutil
import tempfile
import urllib.request
from pathlib import Path

from .application_scenario import run_application_scenario
from .candidate import build_candidate
from .console_authority_scenario import run_recovery_console_scenario
from .contracts import InstalledMatrixSettings, InstalledScenario
from .escalation_scenario import run_escalation_scenario
from .evidence import finalize, initial_document, write
from .factory_scenario import run_factory_scenario
from .local_scenario import run_local_scenario
from .media_scenario import run_media_scenario
from .memory_scenario import run_memory_scenario
from .remote_scenario import run_candidate_remote_scenario
from .service import CandidateService


MANAGED_OLLAMA_URL = "http://127.0.0.1:11435"


def run_installed_matrix(settings: InstalledMatrixSettings) -> dict[str, object]:
    settings.output_root.mkdir(parents=True, mode=0o700)
    output = settings.output_root / "installed-scenario-matrix.json"
    # Preserve the run identity in signed evidence, not in AF_UNIX socket paths.
    with tempfile.TemporaryDirectory(prefix="f23i-") as raw:
        work = Path(raw)
        candidate = build_candidate(
            settings.repository, work / "candidate", settings.run_id,
        )
        document = initial_document(settings.run_id, candidate)
        document["live_owner_service_before"] = _live_owner_service()
        write(output, document)
        workstation = candidate.install("workstation")
        peer = candidate.install("remote-peer")
        try:
            _record(document, output, InstalledScenario.LOCAL, lambda: _local(
                workstation, work / "local", settings,
            ))
            _record(document, output, InstalledScenario.APPLICATION, lambda: (
                run_application_scenario(
                    installation=workstation, repository=settings.repository,
                    root=work / "application", ollama_url=settings.ollama_url,
                    source_model_root=settings.source_model_root,
                )
            ))
            _record(document, output, InstalledScenario.MEMORY, lambda: (
                run_memory_scenario(
                    installation=workstation, root=work / "memory",
                    ollama_url=MANAGED_OLLAMA_URL,
                    source_model_root=settings.source_model_root,
                    manage_ollama=True,
                )
            ))
            _record(document, output, InstalledScenario.ESCALATION, lambda: (
                run_escalation_scenario(
                    installation=workstation, repository=settings.repository,
                    root=work / "escalation", ollama_url=MANAGED_OLLAMA_URL,
                    source_model_root=settings.source_model_root,
                    manage_ollama=True,
                )
            ))
            _record(document, output, InstalledScenario.MEDIA, lambda: _media(
                workstation, work / "media", settings,
            ))
            _record(document, output, InstalledScenario.REMOTE, lambda: (
                run_candidate_remote_scenario(
                    candidate=candidate, desktop=workstation, server=peer,
                    repository=settings.repository, root=work / "remote",
                    ollama_url=settings.ollama_url,
                )
            ))
            _record(document, output, InstalledScenario.FACTORY, lambda: (
                run_factory_scenario(
                    installation=workstation, repository=settings.repository,
                    root=work / "factory", run_id=settings.run_id,
                    ollama_url=settings.ollama_url,
                )
            ))
        finally:
            document["complete_removal"] = candidate.remove_all()
            source_log = candidate.root / "wheel-build.log"
            if source_log.is_file():
                shutil.copy2(source_log, settings.output_root / "wheel-build.log")
            document["live_owner_service_after"] = _live_owner_service()
            document["live_owner_service_preserved"] = bool(
                document["live_owner_service_before"].get("http_status") == 200
                and document["live_owner_service_after"].get("http_status") == 200
            )
            finalize(document)
            write(output, document)
    return document


def _local(installation, root: Path, settings):
    service = CandidateService(
        installation, root / "state", root / "run",
        ollama_url=settings.ollama_url,
        source_model_root=settings.source_model_root,
    )
    with service:
        local = run_local_scenario(service)
    recovery = run_recovery_console_scenario(
        installation=installation,
        root=root / "recovery-console",
        ollama_url=settings.ollama_url,
        source_model_root=settings.source_model_root,
    )
    local["recovery_console"] = recovery
    local["passed"] = bool(local["passed"] and recovery["passed"])
    return local


def _media(installation, root: Path, settings):
    service = CandidateService(
        installation, root / "state", root / "run",
        ollama_url=settings.ollama_url,
        source_model_root=settings.source_model_root,
    )
    image = settings.repository / "artifacts/expert_fabric/phase9.6/work/ocr.png"
    with service:
        return run_media_scenario(service, image)


def _record(document, output, scenario, operation) -> None:
    try:
        value = operation()
    except Exception as error:
        value = {
            "passed": False,
            "error": {"type": type(error).__name__, "message": str(error)},
        }
    document["scenarios"][scenario.value] = value
    write(output, document)


def _live_owner_service() -> dict[str, object]:
    try:
        response = urllib.request.urlopen("http://127.0.0.1:8765/", timeout=5)
        return {"http_status": response.status}
    except Exception as error:
        return {"http_status": None, "error": type(error).__name__}
