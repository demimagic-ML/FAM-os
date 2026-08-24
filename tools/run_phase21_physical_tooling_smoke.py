#!/usr/bin/env python3
"""Prove Phase 21.7 collectors from signed installs without claiming two hosts."""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

from tools.phase21_peer_exit.installed_service import InstalledPeerService
from tools.phase21_peer_exit.release_environment import build_and_install_pair
from tools.phase21_peer_exit.scenario import run_installed_peer_scenario
from tools.phase21_physical_exit.validation import phase21_7_tooling_smoke_passed


def main() -> int:
    repository = Path(__file__).resolve().parents[1]
    output = repository / "artifacts/fabric/phase21.7-tooling-smoke.json"
    document: dict = {}
    with tempfile.TemporaryDirectory() as temporary:
        root = Path(temporary)
        pair = build_and_install_pair(repository, root)
        desktop = server = restarted = None
        desktop_state = server_state = None
        try:
            paired = run_installed_peer_scenario(pair, repository, root)
            desktop_state = Path(paired["desktop_state"])
            server_state = Path(paired["server_state"])
            qualification_id = "phase21.7-installed-tooling-smoke"
            requester_host = _host_probe(
                repository, pair.desktop, desktop_state, "Desktop", "requester",
                qualification_id, root / "requester-host.json",
            )
            peer_host = _host_probe(
                repository, pair.server, server_state, "Home server", "expert_peer",
                qualification_id, root / "peer-host.json",
            )
            desktop = InstalledPeerService(
                pair.desktop, desktop_state, root / "tooling-desktop",
                ollama_url="http://127.0.0.1:11434", model_ref="qwen3:1.7b",
            )
            desktop.wait_ready()
            server = InstalledPeerService(
                pair.server, server_state, root / "tooling-server",
                ollama_url="http://127.0.0.1:11434", model_ref="gemma4:26b",
            )
            server.wait_ready()
            desktop_token = desktop.runtime_root / "console.token"
            peer_base = _peer_observation_arguments(
                repository, pair.server, server_state, server, qualification_id,
            )
            before_success = root / "peer-before-success.json"
            after_success = root / "peer-after-success.json"
            before_loss = root / "peer-before-loss.json"
            after_restart = root / "peer-after-restart.json"
            _run(
                repository, "tools/phase21_physical_exit/capture_peer_observation.py",
                *peer_base, "--checkpoint", "before_remote_success",
                "--output", before_success,
            )
            success_capture = root / "requester-success.json"
            requester_base = (
                "--installed-python", pair.desktop.prefix / "active/python",
                "--repository", repository, "--state-root", desktop_state,
                "--device-name", "Desktop", "--qualification-id", qualification_id,
                "--console-url", f"http://127.0.0.1:{desktop.port}",
                "--console-token-file", desktop_token,
                "--enrollment-id", paired["desktop_enrollment_id"],
                "--peer-device-id", paired["server_device_id"],
            )
            _run(
                repository, "tools/phase21_physical_exit/capture_requester.py",
                "success", *requester_base,
                "--configure-privacy", "--confirm-privacy",
                "--request-id", "phase21-tooling-success",
                "--output", success_capture, timeout=1_000,
            )
            _run(
                repository, "tools/phase21_physical_exit/capture_peer_observation.py",
                *peer_base, "--checkpoint", "after_remote_success",
                "--output", after_success,
            )
            _run(
                repository, "tools/phase21_physical_exit/capture_peer_observation.py",
                *peer_base, "--checkpoint", "before_peer_loss",
                "--output", before_loss,
            )
            server.stop()
            server = None
            loss_pending = root / "requester-loss-pending.json"
            _run(
                repository, "tools/phase21_physical_exit/capture_requester.py",
                "loss", *requester_base, "--privacy-revision", "1",
                "--peer-host", "127.0.0.1", "--peer-port", paired["server_port"],
                "--request-id", "phase21-tooling-loss",
                "--output", loss_pending, timeout=1_000,
            )
            restarted = InstalledPeerService(
                pair.server, server_state, root / "tooling-server-restarted",
                ollama_url="http://127.0.0.1:11434", model_ref="gemma4:26b",
            )
            restarted.wait_ready()
            loss_capture = root / "requester-loss.json"
            _run(
                repository, "tools/phase21_physical_exit/verify_peer_restart.py",
                "--loss-capture", loss_pending,
                "--console-url", f"http://127.0.0.1:{desktop.port}",
                "--console-token-file", desktop_token,
                "--output", loss_capture,
            )
            restart_base = _peer_observation_arguments(
                repository, pair.server, server_state, restarted, qualification_id,
            )
            _run(
                repository, "tools/phase21_physical_exit/capture_peer_observation.py",
                *restart_base, "--checkpoint", "after_peer_restart",
                "--output", after_restart,
            )
            success = root / "remote-success.json"
            loss = root / "peer-loss.json"
            _run(
                repository, "tools/phase21_physical_exit/finalize_scenarios.py",
                "--success-capture", success_capture,
                "--loss-capture", loss_capture,
                "--peer-before-success", before_success,
                "--peer-after-success", after_success,
                "--peer-before-loss", before_loss,
                "--peer-after-restart", after_restart,
                "--success-output", success, "--loss-output", loss,
            )
            success_document = _object(success)
            loss_document = _object(loss)
            document = {
                "phase": "21.7-tooling-smoke",
                "same_physical_host": True,
                "physical_gate_satisfied": False,
                "same_host_limitation": (
                    "Signed installed collectors ran on one physical workstation; "
                    "this cannot satisfy Phase 21.7."
                ),
                "requester_host": requester_host,
                "peer_host": peer_host,
                "remote_success": success_document,
                "peer_loss_recovery": loss_document,
                "requester_diagnosis_healthy": pair.desktop.diagnose().healthy,
                "peer_diagnosis_healthy": pair.server.diagnose().healthy,
                "raw_prompt_retained": any((
                    success_document["requester_prompt_retained"],
                    success_document["peer_prompt_retained"],
                    loss_document["requester_prompt_retained"],
                    loss_document["peer_prompt_retained"],
                )),
            }
        finally:
            for service in (restarted, server, desktop):
                if service is not None:
                    service.stop()
            pair.desktop.remove()
            pair.server.remove()
            for state in (desktop_state, server_state):
                if state is not None and state.exists():
                    shutil.rmtree(state)
        document["complete_removal"] = all((
            not pair.desktop.prefix.exists(), not pair.server.prefix.exists(),
            desktop_state is not None and not desktop_state.exists(),
            server_state is not None and not server_state.exists(),
        ))
        document["passed"] = phase21_7_tooling_smoke_passed(document)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8",
    )
    print(json.dumps({
        "artifact": str(output), "passed": document["passed"],
        "physical_gate_satisfied": document["physical_gate_satisfied"],
    }, sort_keys=True))
    return 0 if document["passed"] else 1


def _host_probe(
    repository, installation, state, name, role, qualification_id, output,
) -> dict:
    _run(
        repository, "tools/phase21_physical_exit/host_probe.py",
        "--installed-python", installation.prefix / "active/python",
        "--repository", repository, "--prefix", installation.prefix,
        "--state-root", state, "--device-name", name,
        "--qualification-id", qualification_id, "--role", role,
        "--output", output,
    )
    return _object(output)


def _peer_observation_arguments(
    repository, installation, state, service, qualification_id,
) -> tuple:
    return (
        "--installed-python", installation.prefix / "active/python",
        "--repository", repository, "--state-root", state,
        "--device-name", "Home server", "--qualification-id", qualification_id,
        "--console-url", f"http://127.0.0.1:{service.port}",
        "--console-token-file", service.runtime_root / "console.token",
    )


def _run(repository: Path, script: str, *arguments, timeout: int = 120) -> None:
    result = subprocess.run(
        (sys.executable, str(repository / script), *map(str, arguments)),
        capture_output=True, text=True, timeout=timeout,
    )
    if result.returncode != 0:
        raise RuntimeError(
            f"{script} failed\nstdout={result.stdout}\nstderr={result.stderr}",
        )


def _object(path: Path) -> dict:
    value = json.loads(path.read_text("utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"{path} does not contain an object")
    return value


if __name__ == "__main__":
    raise SystemExit(main())
