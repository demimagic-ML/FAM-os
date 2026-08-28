"""Durable graphical-session bridge for Omarchy and Hyprland."""

from __future__ import annotations

import json
import os
import signal
import time
from datetime import datetime, timezone
from fam_os.adapters.hyprland.events import HyprlandEventStream, event_socket_path
from fam_os.adapters.omarchy.environment import omarchy_paths
from fam_os.adapters.omarchy.session import detect_session


class OmarchySessionBridge:
    def __init__(self, *, poll_seconds: float = 2.0) -> None:
        self.paths = omarchy_paths()
        self.poll_seconds = poll_seconds
        self._stopped = False
        self.state_file = self.paths.fam_runtime_root / "omarchy-session.json"

    def run(self) -> int:
        self.paths.fam_runtime_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.paths.fam_runtime_root, 0o700)
        for event in (signal.SIGINT, signal.SIGTERM):
            signal.signal(event, self._stop)
        attempts = 0
        while not self._stopped:
            session = detect_session()
            if not session.is_hyprland:
                self._write("waiting", "desktop-not-hyprland", attempts)
                time.sleep(self.poll_seconds)
                continue
            try:
                stream = HyprlandEventStream(event_socket_path())
                self._write("connected", "hyprland", attempts)
                attempts = 0
                for event in stream.events():
                    if self._stopped:
                        break
                    if event.name in {
                        "openwindow", "closewindow", "activewindow", "activewindowv2",
                        "workspace", "focusedmon", "monitoradded", "monitorremoved",
                    }:
                        self._write("connected", event.name, attempts, event.payload)
            except (OSError, RuntimeError):
                attempts += 1
                self._write("recovering", "hyprland-disconnected", attempts)
                time.sleep(min(30.0, self.poll_seconds * (2 ** min(attempts, 4))))
        self._write("stopped", "session-ended", attempts)
        return 0

    def _stop(self, *_args) -> None:
        self._stopped = True

    def _write(self, status: str, event: str, attempts: int, payload: str = "") -> None:
        document = {
            "contractVersion": "fam.omarchy.session/v1",
            "status": status, "event": event, "payload": payload[:4096],
            "recoveryAttempts": attempts,
            "observedAt": datetime.now(timezone.utc).isoformat(),
        }
        temporary = self.state_file.with_suffix(".tmp")
        temporary.write_text(json.dumps(document, sort_keys=True) + "\n")
        os.chmod(temporary, 0o600)
        os.replace(temporary, self.state_file)


def run_omarchy_session_bridge() -> int:
    return OmarchySessionBridge().run()
