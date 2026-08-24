"""Installed verifier, provider, and product-daemon fault injections."""

from __future__ import annotations

import os
import signal
import subprocess
import sys
import time
import urllib.request
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .service_session import InstalledSoakSession


SessionFactory = Callable[[str], InstalledSoakSession]


def run_verifier_crash(
    session: InstalledSoakSession, installation: Any, root: Path,
) -> dict[str, object]:
    root.mkdir(parents=True, mode=0o700)
    crash_output = root / "crash.json"
    process = _verifier_process(installation, "crash", crash_output)
    victim = _wait_verifier_descendant(process.pid, set(), timeout=60)
    process_group = os.getpgid(victim)
    if process_group == os.getpgid(process.pid):
        raise RuntimeError("verifier sandbox shares the driver process group")
    os.killpg(process_group, signal.SIGKILL)
    stdout, stderr = process.communicate(timeout=60)
    if process.returncode != 0 or not crash_output.is_file():
        raise RuntimeError(
            "installed verifier crash driver failed: "
            + (stderr or stdout)[-1000:]
        )
    crash = _json(crash_output)
    healthy_output = root / "healthy.json"
    healthy_process = _verifier_process(installation, "healthy", healthy_output)
    healthy_stdout, healthy_stderr = healthy_process.communicate(timeout=60)
    if healthy_process.returncode != 0 or not healthy_output.is_file():
        raise RuntimeError(
            "installed verifier recovery driver failed: "
            + (healthy_stderr or healthy_stdout)[-1000:]
        )
    healthy = _json(healthy_output)
    candidate_root = (installation.prefix / "active/python").resolve()
    candidate_only = all(
        Path(str(item["candidate_module"])).resolve().is_relative_to(candidate_root)
        for item in (crash, healthy)
    )
    recovery = session.verified_ready("phase23-soak-after-verifier-crash")
    return {
        "killed_pid": victim,
        "killed_process_group": process_group,
        "crash_status": crash.get("status"),
        "crash_activation_trust": crash.get("activation_trust"),
        "healthy_status": healthy.get("status"),
        "healthy_activation_trust": healthy.get("activation_trust"),
        "release_id": healthy.get("release_id"),
        "candidate_only": candidate_only,
        "recovery": recovery,
        "passed": bool(
            crash.get("passed") is False
            and crash.get("activation_trust") == "signed"
            and healthy.get("passed") is True
            and healthy.get("activation_trust") == "signed"
            and candidate_only
            and recovery.get("passed") is True
        ),
    }


def run_ollama_crash(
    session: InstalledSoakSession, ollama_url: str, event_id: str = "initial",
) -> dict[str, object]:
    before = _unit_properties()
    accepted = session.submit_ready(f"phase23-soak-ollama-crash-{event_id}")
    killed = subprocess.run(
        (
            "systemctl", "--user", "kill", "--kill-whom=main",
            "--signal=SIGKILL", "fam-ollama.service",
        ),
        capture_output=True, text=True, timeout=15,
    )
    recovered = _wait_provider_recovery(
        ollama_url, previous_pid=before.get("MainPID", ""), timeout=120,
    )
    try:
        terminal = session.console.wait_for_terminal(
            accepted["session_id"], timeout=420,
        )
        initial = _terminal_facts(terminal)
    except Exception as error:
        initial = {
            "terminal": False,
            "error_type": type(error).__name__,
        }
    follow_up = session.verified_ready(
        f"phase23-soak-after-ollama-crash-{event_id}",
    )
    after = _unit_properties()
    return {
        "session_id": accepted["session_id"],
        "kill_return_code": killed.returncode,
        "main_pid_before": before.get("MainPID"),
        "main_pid_after": after.get("MainPID"),
        "restart_count_before": before.get("NRestarts"),
        "restart_count_after": after.get("NRestarts"),
        "provider_recovered": recovered,
        "initial_task": initial,
        "follow_up": follow_up,
        "passed": bool(
            killed.returncode == 0
            and recovered
            and before.get("MainPID") != after.get("MainPID")
            and follow_up.get("passed") is True
        ),
    }


def run_daemon_restart(
    session: InstalledSoakSession, factory: SessionFactory,
    event_id: str = "initial",
) -> tuple[InstalledSoakSession, dict[str, object]]:
    accepted = session.submit_ready(f"phase23-soak-daemon-restart-{event_id}")
    accepted_state = accepted.get("state")
    old_pid = session.pid
    session.crash()
    replacement = factory(f"daemon-recovery-{event_id}").start()
    terminal = replacement.console.wait_for_terminal(
        accepted["session_id"], timeout=420,
    )
    terminal_facts = _terminal_facts(terminal)
    follow_up = replacement.verified_ready(
        f"phase23-soak-after-daemon-restart-{event_id}",
    )
    return replacement, {
        "session_id": accepted["session_id"],
        "accepted_state": accepted_state,
        "old_pid": old_pid,
        "new_pid": replacement.pid,
        "reconciled_task": terminal_facts,
        "follow_up": follow_up,
        "passed": bool(
            old_pid != replacement.pid
            and terminal.get("state") == "terminal"
            and follow_up.get("passed") is True
        ),
    }


def _wait_verifier_descendant(
    root_pid: int, before: set[int], timeout: float,
) -> int:
    deadline = time.monotonic() + timeout
    latest: dict[int, str] = {}
    while time.monotonic() < deadline:
        latest = {
            pid: _cmdline(pid)
            for pid in _descendants(root_pid)
            if pid not in before
        }
        for pid, command in latest.items():
            if "systemd-run" in command or "bwrap" in command:
                return pid
        time.sleep(0.05)
    raise TimeoutError(f"verifier process did not appear: {latest}")


def _verifier_process(
    installation: Any, mode: str, output: Path,
) -> subprocess.Popen[str]:
    environment = dict(os.environ)
    environment.pop("PYTHONHOME", None)
    environment["PYTHONPATH"] = str(installation.prefix / "active/python")
    driver = Path(__file__).with_name("verifier_fault_process.py").absolute()
    return subprocess.Popen(
        (
            sys.executable, str(driver), "--mode", mode,
            "--output", str(output),
        ),
        cwd=output.parent, env=environment,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        text=True, start_new_session=True,
    )


def _json(path: Path) -> dict[str, Any]:
    import json

    document = json.loads(path.read_text("utf-8"))
    if not isinstance(document, dict):
        raise ValueError("verifier fault evidence must be an object")
    return document


def _descendants(root_pid: int) -> tuple[int, ...]:
    discovered: list[int] = []
    pending = [root_pid]
    while pending:
        parent = pending.pop()
        path = Path(f"/proc/{parent}/task/{parent}/children")
        try:
            children = [int(value) for value in path.read_text().split()]
        except (FileNotFoundError, ProcessLookupError, ValueError):
            children = []
        for child in children:
            if child not in discovered:
                discovered.append(child)
                pending.append(child)
    return tuple(discovered)


def _cmdline(pid: int) -> str:
    try:
        return Path(f"/proc/{pid}/cmdline").read_bytes().replace(b"\0", b" ").decode(
            "utf-8", errors="replace",
        )
    except (FileNotFoundError, ProcessLookupError):
        return ""


def _unit_properties() -> dict[str, str]:
    completed = subprocess.run(
        (
            "systemctl", "--user", "show", "fam-ollama.service",
            "--property", "MainPID", "--property", "NRestarts",
            "--property", "ActiveState",
        ),
        check=True, capture_output=True, text=True, timeout=15,
    )
    return dict(
        line.split("=", 1) for line in completed.stdout.splitlines() if "=" in line
    )


def _wait_provider_recovery(
    url: str, *, previous_pid: str, timeout: float,
) -> bool:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        properties = _unit_properties()
        try:
            response = urllib.request.urlopen(f"{url}/api/tags", timeout=2)
            healthy = response.status == 200
        except Exception:
            healthy = False
        if (
            healthy
            and properties.get("ActiveState") == "active"
            and properties.get("MainPID") not in {"", "0", previous_pid}
        ):
            return True
        time.sleep(0.2)
    return False


def _terminal_facts(terminal: dict[str, Any]) -> dict[str, object]:
    result = terminal.get("result") or {}
    return {
        "terminal": terminal.get("state") == "terminal",
        "status": result.get("status"),
        "assurance": result.get("assurance"),
        "revision": terminal.get("revision"),
    }
