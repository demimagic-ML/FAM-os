"""Crash an installed requester mid-peer-call and verify restart recovery."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from tools.phase21_peer_exit.installed_service import InstalledPeerService
from tools.phase21_remote_exit.database import database_observation, databases_contain
from tools.phase21_remote_exit.scenario import LOCAL_MODEL, PROMPT, REMOTE_MODEL
from tools.phase21_state_exit.console_client import PeerConsoleClient

REQUEST_ID = "phase21-remote-loss-restart"
TASK_ID = f"task-{REQUEST_ID}"


def run_recovery_scenario(pair, repository: Path, root: Path, paired: dict) -> dict:
    desktop_state = Path(paired["desktop_state"])
    server_state = Path(paired["server_state"])
    enrollment_id = paired["desktop_enrollment_id"]
    with (
        InstalledPeerService(
            pair.desktop, desktop_state, root / "recovery-setup-desktop",
            ollama_url="http://127.0.0.1:11434", model_ref=LOCAL_MODEL,
        ) as desktop,
        InstalledPeerService(
            pair.server, server_state, root / "recovery-setup-server",
            ollama_url="http://127.0.0.1:11434", model_ref=REMOTE_MODEL,
        ) as server,
    ):
        desktop_client = _console(desktop)
        server_client = _console(server)
        probed = desktop_client.probe(enrollment_id, "phase21-recovery-probe")
        declaration = _gemma_declaration(probed["capabilities"])
        privacy = desktop_client.privacy(
            enrollment_id, "phase21-recovery-privacy", 0, True,
            raw_content_allowed=True, maximum_context_bytes=32768,
        )
        desktop_context_before = len(desktop_client.context_evidence())
        server_context_before = len(server_client.context_evidence())

    loss = _start_loss_server(pair, repository, root, server_state, paired)
    desktop = InstalledPeerService(
        pair.desktop, desktop_state, root / "recovery-crashed-desktop",
        ollama_url="http://127.0.0.1:11434", model_ref=LOCAL_MODEL,
    )
    try:
        desktop.wait_ready()
        client = _console(desktop)
        accepted = client.create_remote(
            REQUEST_ID, PROMPT, _authority(enrollment_id),
        )
        client.task(accepted["session_id"])
        _wait_file(loss["process"], loss["received"], loss["stderr"])
        desktop.crash()
        loss["process"].wait(timeout=30)
        if loss["process"].returncode != 0:
            raise RuntimeError(_failure("loss server failed", loss["stderr"]))
    except Exception as error:
        desktop.crash()
        raise RuntimeError(
            _failure("installed requester crash scenario failed", loss["stderr"]),
        ) from error
    finally:
        if loss["process"].poll() is None:
            loss["process"].terminate()
            loss["process"].wait(timeout=5)
        loss["stdout_handle"].close()
        loss["stderr_handle"].close()

    interrupted = _inspect(pair, repository, root, desktop_state, "interrupted")
    with InstalledPeerService(
        pair.desktop, desktop_state, root / "recovery-restarted-desktop",
        ollama_url="http://127.0.0.1:11434", model_ref=LOCAL_MODEL,
    ) as restarted:
        client = _console(restarted)
        terminal = client.wait_for_terminal(accepted["session_id"], timeout=360)
        recovery = client.remote_recovery(accepted["session_id"])
        remote = client.remote_execution(accepted["session_id"])
        verifications = client.verifications(accepted["session_id"])
        desktop_context_after = len(client.context_evidence())
    final = _inspect(pair, repository, root, desktop_state, "final")
    database = database_observation(desktop_state, (TASK_ID,))
    return {
        "declared_remote_model": declaration["model_ref"],
        "privacy_revision": privacy["resulting_revision"],
        "accepted": accepted,
        "interrupted_state": interrupted,
        "terminal": terminal,
        "remote_execution": remote,
        "remote_recovery": recovery,
        "verifications": verifications,
        "loss_server": json.loads(loss["output"].read_text("utf-8")),
        "desktop_context_count_before": desktop_context_before,
        "desktop_context_count_after": desktop_context_after,
        "server_context_count_before": server_context_before,
        "installed_state": final,
        "database": database,
        "database_contains_prompt": databases_contain(
            (desktop_state, server_state), (PROMPT.encode("utf-8"),),
        ),
    }


def _start_loss_server(pair, repository, root, server_state, paired) -> dict:
    ready = root / "loss-server.ready"
    received = root / "loss-server.received"
    output = root / "loss-server.json"
    stdout_path = root / "loss-server.stdout"
    stderr_path = root / "loss-server.stderr"
    stdout = stdout_path.open("w", encoding="utf-8")
    stderr = stderr_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        (
            sys.executable,
            str(repository / "tools/phase21_recovery_exit/loss_server.py"),
            "--installed-python", str(pair.server.prefix / "active/python"),
            "--repository", str(repository),
            "--state-root", str(server_state),
            "--device-name", "Home server",
            "--listen-host", "127.0.0.1",
            "--listen-port", str(paired["server_port"]),
            "--ready-file", str(ready),
            "--received-file", str(received),
            "--output", str(output),
        ),
        stdout=stdout,
        stderr=stderr,
        text=True,
    )
    _wait_file(process, ready, stderr_path)
    return {
        "process": process,
        "received": received,
        "output": output,
        "stderr": stderr_path,
        "stdout_handle": stdout,
        "stderr_handle": stderr,
    }


def _inspect(pair, repository, root, state, suffix) -> dict:
    output = root / f"recovery-inspection-{suffix}.json"
    subprocess.run(
        (
            sys.executable,
            str(repository / "tools/phase21_recovery_exit/inspect_process.py"),
            "--installed-python", str(pair.desktop.prefix / "active/python"),
            "--repository", str(repository),
            "--state-root", str(state),
            "--task-id", TASK_ID,
            "--output", str(output),
        ),
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return json.loads(output.read_text("utf-8"))


def _console(service: InstalledPeerService) -> PeerConsoleClient:
    token = (service.runtime_root / "console.token").read_text().strip()
    return PeerConsoleClient(f"http://127.0.0.1:{service.port}", token)


def _authority(enrollment_id: str) -> dict:
    return {
        "enrollment_id": enrollment_id,
        "expected_privacy_revision": 1,
        "purpose_id": "assist",
        "workspace_id": "workspace:installed",
        "sensitivity": "private",
        "maximum_context_bytes": 8192,
        "maximum_output_bytes": 4096,
        "confirmed": True,
    }


def _gemma_declaration(capabilities: list[dict]) -> dict:
    matches = tuple(
        item for item in capabilities
        if item["model_ref"] == REMOTE_MODEL
        and "language.generate" in item["capability_ids"]
    )
    if len(matches) != 1:
        raise RuntimeError("installed peer did not declare exactly one Gemma expert")
    return matches[0]


def _wait_file(process, path: Path, stderr: Path) -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if path.is_file():
            return
        if process.poll() is not None:
            raise RuntimeError(_failure("loss server exited early", stderr))
        time.sleep(0.05)
    raise TimeoutError(_failure(f"timed out waiting for {path.name}", stderr))


def _failure(prefix: str, stderr: Path) -> str:
    detail = stderr.read_text(errors="replace")[-12000:] if stderr.is_file() else ""
    return f"{prefix}: {detail}"
