"""Exercise the installed two-device pairing and mutual-TLS lifecycle."""

from __future__ import annotations

import json
import socket
import stat
import subprocess
import sys
from pathlib import Path

from tools.phase21_peer_exit.installed_service import InstalledPeerService


def run_installed_peer_scenario(
    pair, repository: Path, root: Path, *,
    ollama_url: str = "http://127.0.0.1:11434",
) -> dict:
    desktop_state = root / "desktop-state"
    server_state = root / "server-state"
    desktop_port, server_port = _free_port(), _free_port()
    _configure(pair, pair.desktop, desktop_state, "Desktop", desktop_port)
    _configure(pair, pair.server, server_state, "Home server", server_port)
    desktop_offer = root / "desktop-offer.json"
    server_offer = root / "server-offer.json"
    desktop_offer.write_text(_offer(pair, pair.desktop, desktop_state, "Desktop"))
    server_offer.write_text(_offer(pair, pair.server, server_state, "Home server"))
    desktop_code = _code(
        pair, pair.desktop, desktop_state, "Desktop", desktop_offer, server_offer,
    )
    server_code = _code(
        pair, pair.server, server_state, "Home server", server_offer, desktop_offer,
    )
    denied = _approval_denied(
        pair, pair.desktop, desktop_state, "Desktop", desktop_offer, server_offer,
        desktop_code,
    )
    desktop_enrollment = _approve(
        pair, pair.desktop, desktop_state, "Desktop", desktop_offer, server_offer,
        desktop_code,
    )
    server_enrollment = _approve(
        pair, pair.server, server_state, "Home server", server_offer, desktop_offer,
        server_code,
    )
    # The server enrollment points at the desktop; the desktop enrollment points at the server.
    server_device_id = desktop_enrollment["payload"]["approval"]["peer_identity"]["device_id"]
    with (
        InstalledPeerService(
            pair.desktop, desktop_state, root / "desktop-run-1",
            ollama_url=ollama_url,
        ),
        InstalledPeerService(
            pair.server, server_state, root / "server-run-1",
            ollama_url=ollama_url,
        ),
    ):
        first = _health(
            pair.desktop, repository, desktop_state, "Desktop", server_device_id,
            root / "health-1.json",
        )
    with InstalledPeerService(
        pair.server, server_state, root / "server-run-2",
        ollama_url=ollama_url,
    ):
        second = _health(
            pair.desktop, repository, desktop_state, "Desktop", server_device_id,
            root / "health-2.json",
        )
    return {
        "pairing_codes_match": desktop_code == server_code,
        "unconfirmed_approval_denied": denied,
        "desktop_enrollment_id": desktop_enrollment["payload"]["enrollment_id"],
        "server_enrollment_id": server_enrollment["payload"]["enrollment_id"],
        "desktop_device_id": server_enrollment["payload"]["approval"]["peer_identity"]["device_id"],
        "server_device_id": server_device_id,
        "desktop_port": desktop_port,
        "server_port": server_port,
        "first_authenticated_health": first,
        "restarted_authenticated_health": second,
        "server_identity_stable": (
            first["response"]["responder_device_id"]
            == second["response"]["responder_device_id"]
            == server_device_id
        ),
        "database_contains_peer_display_names": _database_contains(
            (desktop_state, server_state), (b"Desktop", b"Home server"),
        ),
        "credential_modes_private": _credential_modes_private((desktop_state, server_state)),
        "desktop_state": str(desktop_state),
        "server_state": str(server_state),
    }


def _configure(pair, installation, state, name, port) -> None:
    _cli(pair, installation, (
        "peer", "--state-root", str(state), "--device-name", name,
        "configure", "--listen-host", "127.0.0.1", "--listen-port", str(port),
        "--advertised-host", "127.0.0.1", "--advertised-port", str(port), "--confirm",
    ))


def _offer(pair, installation, state, name) -> str:
    return _cli(pair, installation, (
        "peer", "--state-root", str(state), "--device-name", name, "offer",
    )).stdout


def _code(pair, installation, state, name, local, peer) -> str:
    result = _cli(pair, installation, (
        "peer", "--state-root", str(state), "--device-name", name, "code",
        "--local-offer", str(local), "--peer-offer", str(peer),
    ))
    return json.loads(result.stdout)["pairing_code"]


def _approval_denied(pair, installation, state, name, local, peer, code) -> bool:
    result = _cli(pair, installation, (
        "peer", "--state-root", str(state), "--device-name", name, "approve",
        "--local-offer", str(local), "--peer-offer", str(peer), "--code", code,
    ), check=False)
    return result.returncode != 0 and "requires --confirm" in result.stderr


def _approve(pair, installation, state, name, local, peer, code) -> dict:
    result = _cli(pair, installation, (
        "peer", "--state-root", str(state), "--device-name", name, "approve",
        "--local-offer", str(local), "--peer-offer", str(peer), "--code", code,
        "--confirm",
    ))
    return json.loads(result.stdout)


def _health(installation, repository, state, name, peer_id, output) -> dict:
    subprocess.run((
        sys.executable, str(repository / "tools/phase21_peer_exit/client_process.py"),
        "--installed-python", str(installation.prefix / "active/python"),
        "--repository", str(repository), "--state-root", str(state),
        "--device-name", name, "--peer-device-id", peer_id,
        "--output", str(output),
    ), check=True, capture_output=True, text=True, timeout=30)
    return json.loads(output.read_text("utf-8"))


def _cli(pair, installation, arguments, *, check=True):
    return subprocess.run((
        str(installation.prefix / "bin/fam-os"),
        "--prefix", str(installation.prefix),
        "--trusted-key", f"{pair.key_id}={pair.trusted_key_path}",
        *arguments,
    ), check=check, capture_output=True, text=True, timeout=30)


def _database_contains(states, values) -> bool:
    return any(
        value in path.read_bytes()
        for state in states
        for path in (state / "state").glob("fam.sqlite3*")
        if path.is_file()
        for value in values
    )


def _credential_modes_private(states) -> bool:
    files = tuple(
        path for state in states for path in (state / "fabric/identity").iterdir()
        if path.is_file()
    )
    return bool(files) and all(stat.S_IMODE(path.stat().st_mode) == 0o600 for path in files)


def _free_port() -> int:
    with socket.socket() as stream:
        stream.bind(("127.0.0.1", 0))
        return stream.getsockname()[1]
