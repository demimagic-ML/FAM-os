#!/usr/bin/env python3
"""Prove a fresh installed service through real Ollama, Shell, and Console."""

from __future__ import annotations

import hashlib
import json
import signal
import socket
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

from fam_os.adapters.ollama import OllamaRuntime, OllamaSettings
from fam_os.product.linux_installation import LinuxInstallation


MODEL = "qwen3:1.7b"
OUTPUT = Path("artifacts/product/phase15/installed-operational-acceptance.json")


def main() -> None:
    with tempfile.TemporaryDirectory(prefix="fam-operational-") as directory:
        root = Path(directory)
        installation = LinuxInstallation(root / "installation")
        installed = installation.install(Path("src/fam_os"), "phase15-live")
        unit_verified = _verify_unit(installation)
        port = _free_port()
        process = _start_service(installation, root, port)
        try:
            _wait_ready(root / "ready", process)
            transcript = _shell_request(installation, root)
            console, console_ui_loaded = _console_snapshot(root, port)
            loaded = _loaded_model()
        finally:
            _stop(process)
        healthy_before_damage = installation.diagnose().healthy
        (installation.prefix / "bin" / "fam-shell").write_text("damaged")
        damage_detected = not installation.diagnose().healthy
        repaired = installation.repair(Path("src/fam_os")).healthy
        installation.remove()
        removed = not installation.prefix.exists()
    report = {
        "contract_version": "fam.product.operational-acceptance/v1alpha1",
        "model_ref": MODEL,
        "installed_healthy": installed.healthy,
        "systemd_unit_verified": unit_verified,
        "shell_status": "completed",
        "shell_transcript_sha256": hashlib.sha256(transcript.encode()).hexdigest(),
        "shell_output_nonempty": "FAM operational" in transcript,
        "console_sections": [item["section_id"] for item in console["sections"]],
        "console_owner_uid": console["owner_uid"],
        "console_ui_loaded": console_ui_loaded,
        "model_resident_bytes": loaded.resident_bytes,
        "model_accelerator_bytes": loaded.accelerator_bytes,
        "clean_shutdown": process.returncode == 0,
        "healthy_before_damage": healthy_before_damage,
        "damage_detected": damage_detected,
        "repair_passed": repaired,
        "complete_removal": removed,
    }
    report["passed"] = all((
        report["installed_healthy"], unit_verified, report["shell_output_nonempty"],
        len(report["console_sections"]) == 6, console_ui_loaded, report["clean_shutdown"],
        healthy_before_damage, damage_detected, repaired, removed,
    ))
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))
    raise SystemExit(not report["passed"])


def _start_service(installation, root, port):
    command = (
        str(installation.prefix / "bin" / "fam-service"),
        "--state-root", str(root / "state"),
        "--runtime-root", str(root / "runtime"),
        "--model", MODEL, "--console-port", str(port),
        "--ready-file", str(root / "ready"),
    )
    return subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)


def _wait_ready(path: Path, process: subprocess.Popen, timeout=15) -> None:
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if path.is_file():
            return
        if process.poll() is not None:
            output, error = process.communicate()
            raise RuntimeError(f"installed service exited: {output} {error}")
        time.sleep(.05)
    raise TimeoutError("installed service did not become ready")


def _shell_request(installation: LinuxInstallation, root: Path) -> str:
    command = (
        str(installation.prefix / "bin" / "fam-shell"),
        "--socket", str(root / "runtime" / "shell.sock"), "--timeout", "120",
    )
    result = subprocess.run(
        command, input="ask Reply with exactly: FAM operational\nrefresh\nquit\n",
        capture_output=True, text=True, timeout=130, check=True,
    )
    if "Result: completed" not in result.stdout or "FAM operational" not in result.stdout:
        raise RuntimeError("installed FAM Shell did not complete the local request")
    return result.stdout


def _console_snapshot(root: Path, port: int):
    token = (root / "runtime" / "console.token").read_text().strip()
    request = urllib.request.Request(f"http://127.0.0.1:{port}/api/v1/snapshot")
    request.add_header("Authorization", f"Bearer {token}")
    snapshot = json.loads(urllib.request.urlopen(request, timeout=10).read())
    ui = urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=10).read()
    return snapshot, b"Your machine, thinking in public" in ui


def _loaded_model():
    runtime = OllamaRuntime(OllamaSettings("http://127.0.0.1:11434", 30))
    return next(item for item in runtime.loaded_models() if item.model_ref == MODEL)


def _stop(process: subprocess.Popen) -> None:
    if process.poll() is None:
        process.send_signal(signal.SIGTERM)
    try:
        process.communicate(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()
        process.communicate()


def _free_port() -> int:
    with socket.socket() as stream:
        stream.bind(("127.0.0.1", 0))
        return stream.getsockname()[1]


def _verify_unit(installation: LinuxInstallation) -> bool:
    unit = installation.prefix / "systemd" / "fam-os.service"
    result = subprocess.run(
        ("systemd-analyze", "--user", "verify", str(unit)),
        capture_output=True, text=True, check=False,
    )
    return result.returncode == 0


if __name__ == "__main__":
    main()
