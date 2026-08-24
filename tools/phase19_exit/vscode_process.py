"""Launch the connector from the signed install in an isolated VS Code profile."""

from __future__ import annotations

import json
import os
import signal
import subprocess
import time
from pathlib import Path


class InstalledVsCodeProcess:
    def __init__(
        self, code_path: Path, profile_root: Path, extension_root: Path,
        socket_path: Path,
    ) -> None:
        self._code = code_path
        self._profile = profile_root
        self._extensions = extension_root
        self._socket = socket_path
        self._process: subprocess.Popen | None = None

    def start(self, workspace: Path, active_file: Path) -> None:
        user_data = self._profile / "user-data"
        settings = user_data / "User/settings.json"
        settings.parent.mkdir(parents=True, mode=0o700)
        settings.write_text(json.dumps({
            "famOS.connector.autoConnect": True,
            "famOS.connector.socketPath": str(self._socket),
            "security.workspace.trust.enabled": False,
            "files.autoSave": "off",
        }), encoding="utf-8")
        self._process = subprocess.Popen(
            (
                str(self._code), "--new-window", "--wait",
                f"--user-data-dir={user_data}",
                f"--extensions-dir={self._extensions}",
                str(workspace), "--goto", f"{active_file}:1:1",
            ),
            stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL, start_new_session=True,
        )

    def stop(self) -> None:
        process, self._process = self._process, None
        if process is None:
            return
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            try:
                process.wait(timeout=8)
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass
                process.wait(timeout=5)
        self._terminate_profile_processes()

    def _terminate_profile_processes(self) -> None:
        marker = str(self._profile).encode()
        process_ids = []
        for path in Path("/proc").glob("[0-9]*"):
            try:
                if path.stat().st_uid != os.geteuid():
                    continue
                arguments = (path / "cmdline").read_bytes().split(b"\0")
            except (FileNotFoundError, PermissionError, ProcessLookupError):
                continue
            if any(marker in item for item in arguments):
                process_ids.append(int(path.name))
        for process_id in process_ids:
            try:
                os.kill(process_id, signal.SIGTERM)
            except ProcessLookupError:
                pass
        time.sleep(0.2)
        for process_id in process_ids:
            if Path(f"/proc/{process_id}").exists():
                try:
                    os.kill(process_id, signal.SIGKILL)
                except ProcessLookupError:
                    pass

    def __enter__(self):
        return self

    def __exit__(self, *_error):
        self.stop()
