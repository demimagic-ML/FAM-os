"""Run the signed fresh-profile Phase 23.8 lifecycle."""

from __future__ import annotations

import json
import shutil
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from tools.phase23_soak.release_pair import build_release_pair

from .commands import clean_environment, installed_cli, source_install
from .contracts import CONTRACT_VERSION, LifecycleSettings
from .service import start_candidate_service, unit_inactive


def run_lifecycle(settings: LifecycleSettings) -> dict[str, Any]:
    settings.output_root.mkdir(parents=True, mode=0o700)
    work = Path(tempfile.mkdtemp(prefix="f23l-", dir="/tmp"))
    work.chmod(0o700)
    home = work / "home"
    home.mkdir(mode=0o700)
    environment = clean_environment(home)
    prefix = home / ".local/share/fam-os-installation"
    state = home / ".local/share/fam-os"
    runtime = work / "runtime/fam-os"
    runtime.parent.mkdir(mode=0o700)
    extensions = home / ".vscode/extensions"
    pair = None
    events: list[dict[str, object]] = []
    failure: dict[str, str] | None = None
    stage = "build"
    started_at = datetime.now(UTC).isoformat()
    try:
        pair = build_release_pair(settings.repository, work / "candidate", settings.run_id)
        stage = "fresh-install"
        _event(events, stage, source_install(
            repository=settings.repository, prefix=prefix,
            bundle=pair.base_bundle, key_id=pair.key_id,
            key_path=pair.public_key_path, environment=environment,
        ), expected_release=pair.base_manifest.release_id)
        stage = "signed-update"
        _event(events, stage, installed_cli(
            prefix, ("update", "--bundle", str(pair.update_bundle)), environment,
        ), expected_release=pair.update_manifest.release_id)
        stage = "signed-rollback"
        _event(events, stage, installed_cli(
            prefix, ("rollback", "--release-id", pair.base_manifest.release_id),
            environment,
        ), expected_release=pair.base_manifest.release_id)
        stage = "damaged-launcher-diagnosis"
        (prefix / "bin/fam-shell").unlink()
        diagnosis = installed_cli(
            prefix, ("diagnose",), environment, accepted_codes=(1,),
        )
        passed = (
            diagnosis.get("healthy") is False
            and "managed_file_missing:bin/fam-shell" in diagnosis["issues"]
        )
        _event(events, stage, diagnosis, passed=passed)
        stage = "signed-repair"
        _event(events, stage, installed_cli(prefix, ("repair",), environment))
        stage = "connector-install"
        connector = installed_cli(prefix, (
            "connector", "install", "vscode",
            "--extension-root", str(extensions),
        ), environment)
        _event(events, stage, connector, passed=connector.get("installed") is True)
        stage = "candidate-sandbox"
        sandbox = installed_cli(
            prefix, ("host-security", "diagnose"), environment,
            accepted_codes=(0, 1),
        )
        implementation = Path(str(sandbox["implementation_path"])).resolve()
        _event(events, stage, sandbox, passed=bool(
            sandbox.get("healthy") is True
            and implementation.is_relative_to((prefix / "active/python").resolve())
        ), fatal=False)
        stage = "installed-service"
        service = start_candidate_service(
            prefix=prefix, state_root=state, runtime_root=runtime,
            ollama_url=settings.owner_ollama_url, model_ref=settings.model_ref,
            console_port=settings.console_port,
        )
        _event(events, stage, service)
        stage = "total-removal"
        removal = installed_cli(prefix, (
            "remove", "--state-root", str(state),
            "--runtime-root", str(runtime),
            "--extension-root", str(extensions), "--confirm",
        ), environment)
        removal_passed = all((
            removal.get("installation_removed") is True,
            removal.get("state_removed") is True,
            removal.get("runtime_removed") is True,
            removal.get("connector_removed") is True,
            not prefix.exists(), not state.exists(), not runtime.exists(),
            unit_inactive(),
            not tuple(extensions.glob("fam-os.fam-os-vscode-connector-*")),
        ))
        _event(events, stage, removal, passed=removal_passed)
    except Exception as error:
        failure = {"stage": stage, "error_type": type(error).__name__}
    finally:
        subprocess_cleanup()
        if pair is not None and (pair.root / "wheel-build.log").is_file():
            shutil.copy2(pair.root / "wheel-build.log", settings.output_root / "wheel-build.log")
    document = {
        "contract_version": CONTRACT_VERSION,
        "run_id": settings.run_id,
        "started_at": started_at,
        "candidate": None if pair is None else pair.identity(),
        "events": events,
        "failure": failure,
        "passed": bool(failure is None and events and all(event["passed"] for event in events)),
    }
    (settings.output_root / "installed-lifecycle.json").write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    shutil.rmtree(work, ignore_errors=True)
    return document


def _event(
    events: list[dict[str, object]], kind: str, facts: dict[str, Any],
    *, passed: bool | None = None, expected_release: str | None = None,
    fatal: bool = True,
) -> None:
    if passed is None:
        passed = facts.get("healthy", True) is True
    if expected_release is not None:
        passed = passed and facts.get("release_id") == expected_release
    events.append({"kind": kind, "passed": passed, "facts": facts})
    if not passed and fatal:
        raise RuntimeError(f"Phase 23.8 event failed: {kind}")


def subprocess_cleanup() -> None:
    import subprocess

    for action in (("stop", "fam-os.service"), ("stop", "fam-ollama.service")):
        subprocess.run(
            ("systemctl", "--user", *action), check=False,
            capture_output=True, text=True, timeout=30,
        )
