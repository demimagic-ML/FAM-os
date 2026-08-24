"""Start and observe the installed lifecycle candidate service."""

from __future__ import annotations

import subprocess
import time
import urllib.request
from pathlib import Path


def start_candidate_service(
    *, prefix: Path, state_root: Path, runtime_root: Path,
    ollama_url: str, model_ref: str, console_port: int,
) -> dict[str, object]:
    subprocess.run(
        (
            "systemd-run", "--user", "--unit=fam-os.service",
            "--property=NoNewPrivileges=yes", "--property=PrivateTmp=yes",
            "--", str(prefix / "bin/fam-service"),
            "--state-root", str(state_root),
            "--runtime-root", str(runtime_root),
            "--external-ollama", "--ollama-url", ollama_url,
            "--model", model_ref, "--console-port", str(console_port),
            "--device-name", "Phase 23 lifecycle candidate",
        ),
        check=True, capture_output=True, text=True, timeout=30,
    )
    deadline = time.monotonic() + 90
    last_error = "not_ready"
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(
                f"http://127.0.0.1:{console_port}/", timeout=3,
            ) as response:
                if response.status == 200:
                    return {"http_status": 200, "unit": "fam-os.service"}
        except Exception as error:
            last_error = type(error).__name__
        time.sleep(.25)
    journal = subprocess.run(
        ("journalctl", "--user", "-u", "fam-os.service", "-n", "80", "--no-pager"),
        check=False, capture_output=True, text=True, timeout=30,
    )
    raise RuntimeError(
        f"installed lifecycle service did not become ready: {last_error}\n"
        + journal.stdout[-4000:]
    )


def unit_inactive() -> bool:
    status = subprocess.run(
        ("systemctl", "--user", "is-active", "fam-os.service"),
        check=False, capture_output=True, text=True, timeout=30,
    )
    return status.stdout.strip() != "active"
