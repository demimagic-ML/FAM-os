"""Private loopback client used by Omarchy's FAM agent launcher."""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import time
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from uuid import uuid4

from fam_os.adapters.omarchy.context import collect_omarchy_context


def submit_from_omarchy(
    prompt: str, workspace: Path, *, goal_mode: bool,
    authority_profile: str, runtime_root: Path,
    source: str = "omarchy-agent",
) -> dict[str, object]:
    descriptor = _descriptor(runtime_root, start=True)
    endpoint = str(descriptor["endpoint"]).rstrip("/")
    token_path = Path(str(descriptor["tokenPath"]))
    token = token_path.read_text(encoding="ascii").strip()
    body = json.dumps({
        "commandId": f"launcher-{uuid4().hex}",
        "prompt": prompt,
        "workspace_root": str(workspace.resolve(strict=True)),
        "authority_profile": authority_profile,
        "goal_mode": goal_mode,
        "source": source,
        "context": collect_omarchy_context(workspace, prompt, source),
    }).encode()
    request = Request(
        endpoint + "/api/v1/agent/submit", data=body, method="POST",
        headers={
            "Content-Type": "application/json",
            "X-FAM-Widget-Token": token,
        },
    )
    try:
        with urlopen(request, timeout=7200) as response:
            result = json.load(response)
    except HTTPError as error:
        detail = error.read().decode("utf-8", "replace")
        raise RuntimeError(f"FAM_OS rejected the task: {detail}") from error
    except URLError as error:
        raise RuntimeError(f"FAM_OS is unavailable: {error.reason}") from error
    if not isinstance(result, dict):
        raise RuntimeError("FAM_OS returned an invalid agent result")
    return result


def widget_request(
    runtime_root: Path, path: str, *, document: dict[str, object] | None = None,
) -> dict[str, object]:
    """Perform one authenticated request against the local desktop API."""
    descriptor = _descriptor(runtime_root, start=True)
    endpoint = str(descriptor["endpoint"]).rstrip("/")
    token = Path(str(descriptor["tokenPath"])).read_text(encoding="ascii").strip()
    data = None if document is None else json.dumps(document).encode()
    request = Request(
        endpoint + path, data=data,
        method="GET" if document is None else "POST",
        headers={
            "Content-Type": "application/json",
            "X-FAM-Widget-Token": token,
        },
    )
    try:
        with urlopen(request, timeout=30) as response:
            result = json.load(response)
    except HTTPError as error:
        detail = error.read().decode("utf-8", "replace")
        raise RuntimeError(f"FAM_OS rejected the request: {detail}") from error
    except URLError as error:
        raise RuntimeError(f"FAM_OS is unavailable: {error.reason}") from error
    if not isinstance(result, dict):
        raise RuntimeError("FAM_OS returned an invalid response")
    return result


def _descriptor(runtime_root: Path, *, start: bool) -> dict[str, object]:
    path = runtime_root / "widget.json"
    if start and not path.is_file():
        subprocess.run(
            ("systemctl", "--user", "start", "fam-os.service"),
            check=False, capture_output=True, timeout=30,
        )
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline and not path.is_file():
            time.sleep(0.2)
    try:
        descriptor = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as error:
        raise RuntimeError(
            "FAM_OS runtime descriptor is unavailable; run `fam-os setup omarchy`"
        ) from error
    if (
        not isinstance(descriptor, dict)
        or descriptor.get("contractVersion") != "fam.widget-runtime/v1"
    ):
        raise RuntimeError("FAM_OS runtime descriptor is incompatible")
    return descriptor


def default_runtime_root() -> Path:
    return Path(
        os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.geteuid()}")
    ) / "fam-os"
