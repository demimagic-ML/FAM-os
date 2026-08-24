"""Exercise installed truncated-frame handling after a complete remote release."""

from __future__ import annotations

import json
import subprocess
import sys
import time
from pathlib import Path

from tools.phase21_peer_exit.installed_service import InstalledPeerService
from tools.phase21_remote_exit.database import database_observation, databases_contain
from tools.phase21_remote_exit.scenario import LOCAL_MODEL, PROMPT
from tools.phase21_state_exit.console_client import PeerConsoleClient

PARTIAL_REQUEST_ID = "phase21-partial-remote-frame"
PARTIAL_TASK_ID = f"task-{PARTIAL_REQUEST_ID}"
PARTIAL_SENTINEL = "PARTIAL_REMOTE_OUTPUT_MUST_NEVER_PERSIST"


def run_partial_frame_scenario(
    pair,
    repository: Path,
    root: Path,
    paired: dict,
) -> dict:
    desktop_state = Path(paired["desktop_state"])
    server_state = Path(paired["server_state"])
    before = database_observation(desktop_state, ())
    ready = root / "partial-server.ready"
    output = root / "partial-server.json"
    stdout_path = root / "partial-server.stdout"
    stderr_path = root / "partial-server.stderr"
    stdout = stdout_path.open("w", encoding="utf-8")
    stderr = stderr_path.open("w", encoding="utf-8")
    process = subprocess.Popen(
        (
            sys.executable,
            str(repository / "tools/phase21_evidence_exit/partial_server.py"),
            "--installed-python", str(pair.server.prefix / "active/python"),
            "--repository", str(repository),
            "--state-root", str(server_state),
            "--device-name", "Home server",
            "--listen-host", "127.0.0.1",
            "--listen-port", str(paired["server_port"]),
            "--ready-file", str(ready),
            "--output", str(output),
        ),
        stdout=stdout,
        stderr=stderr,
        text=True,
    )
    desktop = InstalledPeerService(
        pair.desktop, desktop_state, root / "desktop-partial-run",
        ollama_url="http://127.0.0.1:11434", model_ref=LOCAL_MODEL,
    )
    try:
        _wait_ready(process, ready, stderr_path)
        with desktop:
            client = _console(desktop)
            context_before = len(client.context_evidence())
            accepted = client.create_remote(
                PARTIAL_REQUEST_ID,
                PROMPT,
                _authority(paired["desktop_enrollment_id"]),
            )
            terminal = client.wait_for_terminal(accepted["session_id"], timeout=60)
            remote_evidence = client.remote_execution(accepted["session_id"])
            context_after = len(client.context_evidence())
        process.wait(timeout=30)
        if process.returncode != 0:
            raise RuntimeError(_failure("partial server failed", stderr_path))
    except Exception as error:
        raise RuntimeError(
            _failure("installed partial-frame scenario failed", stderr_path)
            + "\n"
            + _service_stderr(desktop)
        ) from error
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        stdout.close()
        stderr.close()

    after = database_observation(desktop_state, (PARTIAL_TASK_ID,))
    routes = _inspect_routes(pair, repository, root, desktop_state)
    return {
        "accepted": accepted,
        "terminal": terminal,
        "remote_execution": remote_evidence,
        "authenticated_partial_server": json.loads(output.read_text("utf-8")),
        "context_disclosure_count_before": context_before,
        "context_disclosure_count_after": context_after,
        "request_count_delta": after["request_count"] - before["request_count"],
        "attempt_budget_count_delta": (
            after["attempt_budget_count"] - before["attempt_budget_count"]
        ),
        "database": after,
        "installed_core_routes": routes,
        "database_contains_partial_sentinel": databases_contain(
            (desktop_state, server_state), (PARTIAL_SENTINEL.encode("ascii"),),
        ),
    }


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


def _console(service: InstalledPeerService) -> PeerConsoleClient:
    token = (service.runtime_root / "console.token").read_text().strip()
    return PeerConsoleClient(f"http://127.0.0.1:{service.port}", token)


def _wait_ready(process, ready: Path, stderr: Path) -> None:
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        if ready.is_file():
            return
        if process.poll() is not None:
            raise RuntimeError(_failure("partial server exited before ready", stderr))
        time.sleep(0.05)
    raise TimeoutError(_failure("partial server did not become ready", stderr))


def _inspect_routes(pair, repository: Path, root: Path, state: Path) -> dict:
    output = root / "phase21.5-installed-core-routes.json"
    subprocess.run(
        (
            sys.executable,
            str(repository / "tools/phase21_remote_exit/inspect_process.py"),
            "--installed-python", str(pair.desktop.prefix / "active/python"),
            "--repository", str(repository),
            "--state-root", str(state),
            "--remote-task-id", "task-phase21-remote-gemma",
            "--local-task-id", "task-phase21-local-baseline",
            "--partial-task-id", PARTIAL_TASK_ID,
            "--output", str(output),
        ),
        check=True,
        capture_output=True,
        text=True,
        timeout=30,
    )
    return json.loads(output.read_text("utf-8"))


def _failure(prefix: str, stderr: Path) -> str:
    detail = stderr.read_text(errors="replace")[-12000:] if stderr.is_file() else ""
    return f"{prefix}: {detail}"


def _service_stderr(service: InstalledPeerService) -> str:
    path = service.run_root / "service.stderr"
    return path.read_text(errors="replace")[-12000:] if path.is_file() else ""
