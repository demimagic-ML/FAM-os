#!/usr/bin/env python3
"""Repeated real Shell inference and Console health against an installed service."""

import argparse
import json
import signal
import socket
import subprocess
import tempfile
import time
import urllib.request
from pathlib import Path

from fam_os.adapters.shell import UnixShellClientConfiguration, UnixShellCoreClient
from fam_os.product.linux_installation import LinuxInstallation
from fam_os.shell import ShellAskCommand


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--duration-seconds", type=float, default=3600)
    parser.add_argument("--interval-seconds", type=float, default=10)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = _run(args.duration_seconds, args.interval_seconds)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, sort_keys=True))
    raise SystemExit(not report["passed"])


def _run(duration: float, interval: float) -> dict[str, object]:
    if min(duration, interval) <= 0:
        raise ValueError("operational soak intervals must be positive")
    with tempfile.TemporaryDirectory(prefix="fam-service-soak-") as directory:
        root = Path(directory)
        installation = LinuxInstallation(root / "installation")
        installation.install(Path("src/fam_os"), "operational-soak")
        port = _free_port()
        process = subprocess.Popen(_command(installation, root, port))
        try:
            _wait(root / "ready", process)
            samples = _cycles(root, port, duration, interval, process.pid)
        finally:
            _stop(process)
        installation.remove()
    failures = tuple(item["failure"] for item in samples if item["failure"])
    return {
        "contract_version": "fam.product.operational-soak/v1alpha1",
        "duration_seconds": duration, "samples": len(samples),
        "successful_shell_requests": sum(item["shell_ok"] for item in samples),
        "successful_console_requests": sum(item["console_ok"] for item in samples),
        "rss_start_bytes": samples[0]["rss_bytes"],
        "rss_peak_bytes": max(item["rss_bytes"] for item in samples),
        "rss_end_bytes": samples[-1]["rss_bytes"],
        "clean_shutdown": process.returncode == 0,
        "complete_removal": not installation.prefix.exists(),
        "failures": failures, "passed": not failures and process.returncode == 0,
    }


def _cycles(root, port, duration, interval, pid):
    started = time.monotonic()
    samples = []
    client = UnixShellCoreClient(UnixShellClientConfiguration(
        root / "runtime" / "shell.sock", 120,
    ))
    while time.monotonic() - started < duration:
        failure = ""
        try:
            accepted = client.ask(ShellAskCommand(
                f"soak-{len(samples)}", "Reply with exactly: OK",
            ))
            result = client.snapshot(accepted.session_id)
            shell_ok = result.result is not None and bool(result.result.content)
            console_ok = _console(root, port)
        except Exception as error:
            shell_ok, console_ok, failure = False, False, type(error).__name__
        samples.append({"shell_ok": shell_ok, "console_ok": console_ok,
                        "rss_bytes": _rss(pid), "failure": failure})
        time.sleep(min(interval, max(0, duration - (time.monotonic() - started))))
    return samples


def _command(installation, root, port):
    return (str(installation.prefix / "bin" / "fam-service"),
            "--state-root", str(root / "state"), "--runtime-root", str(root / "runtime"),
            "--model", "qwen3:1.7b", "--console-port", str(port),
            "--ready-file", str(root / "ready"))


def _console(root, port):
    token = (root / "runtime" / "console.token").read_text().strip()
    request = urllib.request.Request(f"http://127.0.0.1:{port}/api/v1/snapshot")
    request.add_header("Authorization", f"Bearer {token}")
    return len(json.loads(urllib.request.urlopen(request, timeout=10).read())["sections"]) == 6


def _wait(path, process, timeout=15):
    deadline = time.monotonic() + timeout
    while not path.exists():
        if process.poll() is not None or time.monotonic() >= deadline:
            raise RuntimeError("operational soak service did not start")
        time.sleep(.05)


def _rss(pid):
    for line in Path(f"/proc/{pid}/status").read_text().splitlines():
        if line.startswith("VmRSS:"):
            return int(line.split()[1]) * 1024
    raise RuntimeError("service RSS is unavailable")


def _stop(process):
    if process.poll() is None:
        process.send_signal(signal.SIGTERM)
    try:
        process.wait(timeout=15)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait()


def _free_port():
    with socket.socket() as stream:
        stream.bind(("127.0.0.1", 0))
        return stream.getsockname()[1]


if __name__ == "__main__":
    main()
