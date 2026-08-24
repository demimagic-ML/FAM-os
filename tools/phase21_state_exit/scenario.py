"""Exercise installed peer state, owner surfaces, and immediate revocation."""

from __future__ import annotations

import socket
import sqlite3
import subprocess
import sys
import urllib.request
from pathlib import Path

from tools.phase20_management_exit.shell_client import run_installed_shell
from tools.phase21_peer_exit.installed_service import InstalledPeerService
from tools.phase21_state_exit.console_client import PeerConsoleClient


def run_peer_state_scenario(pair, repository: Path, root: Path, paired: dict) -> dict:
    desktop_state = Path(paired["desktop_state"])
    server_state = Path(paired["server_state"])
    desktop_enrollment = paired["desktop_enrollment_id"]
    server_enrollment = paired["server_enrollment_id"]
    with (
        InstalledPeerService(pair.desktop, desktop_state, root / "desktop-state-run") as desktop,
        InstalledPeerService(pair.server, server_state, root / "server-state-run") as server,
    ):
        desktop_shell = run_installed_shell(pair.desktop, desktop, (
            "/peer list",
            f"/peer probe {desktop_enrollment}",
            f"/peer privacy {desktop_enrollment} 0 4096 private assist "
            "workspace:installed false owner.configured --confirm",
            "/peer receipts",
        ))
        console = _console(server)
        initial = console.peers()
        probed = console.probe(server_enrollment, "console-probe")
        privacy = console.privacy(server_enrollment, "console-privacy", 0, True)
        denied = _denied_revoke(console, server_enrollment)
        before_revoke = _health(
            pair.desktop, repository, desktop_state, paired["server_device_id"],
            root / "before-revoke.json", check=True,
        )
        revoked = console.revoke(server_enrollment, "console-revoke", 1, True)
        after_revoke = _health(
            pair.desktop, repository, desktop_state, paired["server_device_id"],
            root / "after-revoke.json", check=False,
        )
        post_revoke = console.peers()
        receipts = console.receipts()
        server_shell = run_installed_shell(pair.server, server, (
            "/peer list", "/peer receipts",
        ))
        assets = _assets(server)
        live_port_closed = not _connects(paired["server_port"])
    counts = _database_counts(desktop_state, server_state)
    with InstalledPeerService(pair.server, server_state, root / "server-state-restart") as restarted:
        restart_peers = _console(restarted).peers()
        restart_port_closed = not _connects(paired["server_port"])
    return {
        "desktop_installed_shell": desktop_shell,
        "console_initial_peer_count": len(initial),
        "console_probed_models": [item["model_ref"] for item in probed["capabilities"]],
        "console_measured_latency_ms": probed["latest_performance"]["round_trip_milliseconds"],
        "privacy_receipt": privacy,
        "unconfirmed_revoke_denied": denied,
        "before_revoke_health": before_revoke,
        "after_revoke_connection_denied": after_revoke["returncode"] != 0,
        "revocation_receipt": revoked,
        "post_revoke_discovery_count": len(post_revoke),
        "control_receipt_count": len(receipts),
        "server_installed_shell": server_shell,
        "console_assets": assets,
        "live_listener_closed": live_port_closed,
        "restart_discovery_count": len(restart_peers),
        "restart_listener_closed": restart_port_closed,
        "database_counts": counts,
        "database_contains_sensitive_labels": _database_contains(
            (desktop_state, server_state),
            (b"workspace:installed", b"qwen3:1.7b", b"Desktop", b"Home server"),
        ),
    }


def _console(service) -> PeerConsoleClient:
    token = (service.runtime_root / "console.token").read_text().strip()
    return PeerConsoleClient(f"http://127.0.0.1:{service.port}", token)


def _denied_revoke(client, enrollment_id) -> bool:
    try:
        client.revoke(enrollment_id, "console-revoke-denied", 1, False)
    except RuntimeError as error:
        return "403" in str(error) and "confirmation" in str(error)
    return False


def _health(installation, repository, state, peer_id, output, *, check):
    result = subprocess.run((
        sys.executable, str(repository / "tools/phase21_peer_exit/client_process.py"),
        "--installed-python", str(installation.prefix / "active/python"),
        "--repository", str(repository), "--state-root", str(state),
        "--device-name", "Desktop", "--peer-device-id", peer_id,
        "--output", str(output),
    ), check=False, capture_output=True, text=True, timeout=30)
    if check and result.returncode != 0:
        raise RuntimeError(result.stderr)
    document = {"returncode": result.returncode, "stderr": result.stderr[-1000:]}
    if output.is_file():
        import json
        document["result"] = json.loads(output.read_text())
    return document


def _assets(service) -> dict[str, bool]:
    base = f"http://127.0.0.1:{service.port}"
    return {
        "device_workspace": b"Device fabric" in urllib.request.urlopen(base).read(),
        "peer_controls": b"Revoke trust" in urllib.request.urlopen(base + "/peers.js").read(),
        "peer_layout": b"peer-workspace" in urllib.request.urlopen(base + "/peers.css").read(),
    }


def _database_counts(desktop, server) -> dict[str, dict[str, int]]:
    tables = {
        "enrollments": "fabric_peer_enrollments",
        "capabilities": "fabric_peer_capabilities",
        "performance": "fabric_peer_performance",
        "privacy": "fabric_peer_privacy_policies",
        "receipts": "fabric_peer_management_receipts",
    }
    values = {}
    for name, state in (("desktop", desktop), ("server", server)):
        connection = sqlite3.connect(state / "state/fam.sqlite3")
        try:
            values[name] = {
                label: connection.execute(f"SELECT count(*) FROM {table}").fetchone()[0]
                for label, table in tables.items()
            }
            values[name]["active_enrollments"] = connection.execute(
                "SELECT count(*) FROM fabric_peer_enrollments WHERE state='active'",
            ).fetchone()[0]
        finally:
            connection.close()
    return values


def _connects(port: int) -> bool:
    try:
        with socket.create_connection(("127.0.0.1", port), timeout=.5):
            return True
    except OSError:
        return False


def _database_contains(states, labels) -> bool:
    return any(
        label in path.read_bytes()
        for state in states
        for path in (state / "state").glob("fam.sqlite3*")
        if path.is_file()
        for label in labels
    )
