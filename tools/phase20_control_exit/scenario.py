"""Exercise installed Shell and Console adaptation control behavior."""

from __future__ import annotations

import json
import subprocess
import sys
import urllib.request

from tools.phase20_control_exit.console_client import AdaptationConsoleClient
from tools.phase20_management_exit.shell_client import run_installed_shell


WORKFLOW = "intent:code"


def first_process_scenario(installation, repository, service) -> dict:
    seed = run_client(installation, repository, service, "seed")
    service.wait_for_prewarm("gemma4:26b")
    adapted = run_client(installation, repository, service, "adapted")
    service.wait_for_prewarm("qwen2.5-coder:7b")
    drift_workload = run_client(installation, repository, service, "drift")
    service.wait_for_quiescence()
    client = _client(service)
    status_after_drift = client.status()
    snapshots = client.snapshots()
    prewarms = client.prewarms()
    health = client.health()
    drift = client.drift()
    receipts = client.receipts()
    shell = run_installed_shell(
        installation,
        service,
        (
            "/adaptation status",
            "/adaptation snapshots",
            "/adaptation prewarms",
            "/adaptation health",
            "/adaptation drift",
            "/adaptation receipts",
            f"/adaptation rollback {WORKFLOW}",
        ),
    )
    canary = run_client(installation, repository, service, "canary")
    service.wait_for_quiescence()
    events_before_disable = service.events()
    confirmation_denied = _denied_disable(client)
    disabled_receipt = client.control(
        "disable",
        "phase20-control-disable",
        True,
    )
    disabled_status = client.status()
    disabled = run_client(installation, repository, service, "disabled")
    service.wait_for_quiescence()
    events_after_disable = service.events()
    return {
        "training": {
            "results": [
                *seed["results"],
                *adapted["results"],
                *drift_workload["results"],
            ],
        },
        "status_after_automatic_drift": status_after_drift,
        "snapshots": snapshots,
        "prewarms": prewarms,
        "health": health,
        "drift_reports": drift,
        "control_receipts": receipts,
        "installed_shell_inspection": shell,
        "canary_result": canary,
        "events_before_disable": events_before_disable,
        "disable_confirmation_denied": confirmation_denied,
        "disable_receipt": disabled_receipt,
        "disabled_status": disabled_status,
        "disabled_result": disabled,
        "events_after_disable": events_after_disable,
        "console_assets": _console_assets(service),
    }


def restarted_process_scenario(installation, repository, service) -> dict:
    client = _client(service)
    before = {
        "status": client.status(),
        "snapshots": client.snapshots(),
        "prewarms": client.prewarms(),
        "health": client.health(),
        "drift_reports": client.drift(),
        "control_receipts": client.receipts(),
    }
    retained = run_client(installation, repository, service, "restart")
    shell = run_installed_shell(
        installation,
        service,
        (
            "/adaptation status",
            f"/adaptation rollback {WORKFLOW}",
            f"/adaptation rollback {WORKFLOW} --confirm",
            "/adaptation reset --confirm",
            "/adaptation status",
            "/adaptation snapshots",
            "/adaptation prewarms",
            "/adaptation health",
            "/adaptation drift",
            "/adaptation receipts",
        ),
    )
    after = {
        "status": client.status(),
        "snapshots": client.snapshots(),
        "prewarms": client.prewarms(),
        "health": client.health(),
        "drift_reports": client.drift(),
        "control_receipts": client.receipts(),
    }
    return {
        "before": before,
        "retained_results": retained,
        "installed_shell_controls": shell,
        "after_reset": after,
        "runtime_events": service.events(),
    }


def run_client(installation, repository, service, mode: str) -> dict:
    output = service.run_root / f"control-client-{mode}.json"
    subprocess.run(
        (
            sys.executable,
            str(repository / "tools/phase20_control_exit/client_process.py"),
            "--installed-python",
            str(installation.prefix / "active/python"),
            "--repository",
            str(repository),
            "--socket",
            str(service.runtime_root / "shell.sock"),
            "--mode",
            mode,
            "--output",
            str(output),
        ),
        check=True,
        capture_output=True,
        text=True,
        timeout=300,
    )
    return json.loads(output.read_text(encoding="utf-8"))


def _client(service) -> AdaptationConsoleClient:
    base = f"http://127.0.0.1:{service.port}"
    token = (service.runtime_root / "console.token").read_text().strip()
    return AdaptationConsoleClient(base, token)


def _denied_disable(client: AdaptationConsoleClient) -> bool:
    try:
        client.control("disable", "phase20-control-denied", False)
    except RuntimeError as error:
        return "403" in str(error) and "confirmation" in str(error)
    return False


def _console_assets(service) -> dict[str, bool]:
    base = f"http://127.0.0.1:{service.port}"
    page = urllib.request.urlopen(base, timeout=10).read()
    script = urllib.request.urlopen(base + "/adaptation.js", timeout=10).read()
    style = urllib.request.urlopen(base + "/adaptation.css", timeout=10).read()
    return {
        "panel_visible": b"Resident intelligence" in page,
        "disable_control": b"Disable adaptation" in script,
        "reset_control": b"Reset learned behavior" in page,
        "drift_ledger": b"adaptation-ledger" in style,
    }
