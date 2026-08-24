"""Installed approval-restart and uncertain-action recovery scenarios."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from tools.phase19_exit.console_client import ConsoleClient

from .mcp_scenario import run_installed_mcp_scenario
from .service import CandidateService


def run_application_scenario(
    *, installation, repository: Path, root: Path, ollama_url: str,
    source_model_root: Path,
) -> dict[str, object]:
    home = root / "home"
    home.mkdir(parents=True)
    pending = _pending_restart(
        installation, root / "pending", home, ollama_url, source_model_root,
    )
    uncertain = _uncertain_recovery(
        installation, repository, root / "uncertain", home,
        ollama_url, source_model_root,
    )
    mcp = run_installed_mcp_scenario(
        installation=installation, repository=repository, root=root / "mcp",
        home=home, ollama_url=ollama_url,
        source_model_root=source_model_root,
    )
    return {
        "awaiting_approval_restart": pending,
        "uncertain_action_recovery": uncertain,
        "mcp_application_weaving": mcp,
        "passed": bool(pending["passed"] and uncertain["passed"] and mcp["passed"]),
    }


def _pending_restart(installation, root, home, ollama_url, model_root):
    state = root / "state"
    target = home / "Phase23PendingRestart"
    first = _service(installation, state, root / "run-1", home, ollama_url, model_root)
    first.start()
    client = _client(first)
    accepted = client.create(
        "phase23-action-pending", f"Create directory {target}", [], [], False,
    )
    before = client.wait_for_approval(accepted["session_id"])
    console_before = client.snapshot()
    first.crash()
    second = _service(installation, state, root / "run-2", home, ollama_url, model_root)
    try:
        second.start()
        client = _client(second)
        after = client.wait_for_approval(accepted["session_id"])
        console_after_restart = client.snapshot()
        client.approve(after)
        terminal = client.wait_for_terminal(accepted["session_id"], timeout=30)
        console_after_action = client.snapshot()
    finally:
        second.stop()
    result = terminal.get("result") or {}
    grants_before = _item_value(console_before, "permissions", "application-grants")
    grants_after = _item_value(
        console_after_restart, "permissions", "application-grants",
    )
    audit_after = _item_value(
        console_after_action, "audit", "application-actions",
    )
    return {
        "session_id": accepted["session_id"],
        "proposal_stable": (
            before["approval"]["proposal_id"] == after["approval"]["proposal_id"]
        ),
        "target_created": target.is_dir(),
        "terminal": terminal,
        "console_authority": {
            "active_grants_before_restart": grants_before,
            "active_grants_after_restart": grants_after,
            "verified_action_records_after": audit_after,
            "passed": grants_before >= 1 and grants_after >= 1 and audit_after >= 1,
        },
        "passed": all((
            result.get("status") == "verified", target.is_dir(),
            before["approval"]["proposal_id"] == after["approval"]["proposal_id"],
            grants_before >= 1, grants_after >= 1, audit_after >= 1,
        )),
    }


def _uncertain_recovery(
    installation, repository, root, home, ollama_url, model_root,
):
    state = root / "state"
    target = home / "Phase23UncertainRecovery"
    first = _service(installation, state, root / "run-1", home, ollama_url, model_root)
    first.start()
    client = _client(first)
    accepted = client.create(
        "phase23-action-uncertain", f"Create directory {target}", [], [], False,
    )
    client.wait_for_approval(accepted["session_id"])
    first.crash()
    injection = root / "fault-window.json"
    _inject_fault_window(
        installation, repository, state, root / "inject-runtime", home,
        accepted["session_id"], target, ollama_url, model_root, injection,
    )
    second = _service(installation, state, root / "run-2", home, ollama_url, model_root)
    try:
        second.start()
        client = _client(second)
        terminal = client.wait_for_terminal(accepted["session_id"], timeout=30)
    finally:
        second.stop()
    result = terminal.get("result") or {}
    injected = json.loads(injection.read_text("utf-8"))
    audit = state / "audit/application-actions.jsonl"
    return {
        "session_id": accepted["session_id"],
        "fault_window": injected,
        "target_created": target.is_dir(),
        "terminal": terminal,
        "audit_present": audit.is_file() and bool(audit.read_text().strip()),
        "passed": all((
            injected.get("state") == "invoking",
            injected.get("candidate_module_from_install") is True,
            result.get("status") == "verified", target.is_dir(), audit.is_file(),
        )),
    }


def _inject_fault_window(
    installation, repository, state, runtime, home, session_id, target,
    ollama_url, model_root, output,
):
    environment = dict(os.environ)
    environment["HOME"] = str(home)
    environment["PYTHONPATH"] = str(installation.prefix / "active/python")
    subprocess.run((
        sys.executable,
        str(repository / "tools/phase23_installed_matrix/fault_window.py"),
        "--state-root", str(state), "--runtime-root", str(runtime),
        "--session-id", session_id, "--target", str(target),
        "--ollama-url", ollama_url, "--source-model-root", str(model_root),
        "--installation-prefix", str(installation.prefix),
        "--output", str(output),
    ), check=True, capture_output=True, text=True, env=environment, timeout=60)


def _service(installation, state, run, home, ollama_url, model_root):
    return CandidateService(
        installation, state, run, ollama_url=ollama_url,
        source_model_root=model_root, home=home,
    )


def _client(service) -> ConsoleClient:
    token = (service.runtime_root / "console.token").read_text().strip()
    return ConsoleClient(f"http://127.0.0.1:{service.port}", token)


def _item_value(snapshot: dict, section_id: str, item_id: str) -> int:
    value = next(
        item["value"]
        for section in snapshot.get("sections", ())
        if section.get("section_id") == section_id
        for item in section.get("items", ())
        if item.get("item_id") == item_id
    )
    return int(value)
