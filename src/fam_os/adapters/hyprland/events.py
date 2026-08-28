"""Reconnectable Hyprland event stream for session-lifecycle observation."""

from __future__ import annotations

import os
import socket
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Mapping


@dataclass(frozen=True, slots=True)
class HyprlandEvent:
    name: str
    payload: str


def event_socket_path(
    environment: Mapping[str, str] | None = None,
) -> Path:
    values = os.environ if environment is None else environment
    signature = values.get("HYPRLAND_INSTANCE_SIGNATURE")
    if not signature or "/" in signature or signature in {".", ".."}:
        raise RuntimeError("Hyprland instance signature is unavailable")
    runtime = Path(values.get("XDG_RUNTIME_DIR", f"/run/user/{os.geteuid()}"))
    preferred = runtime / "hypr" / signature / ".socket2.sock"
    legacy = Path("/tmp/hypr") / signature / ".socket2.sock"
    return preferred if preferred.exists() or not legacy.exists() else legacy


def parse_event(line: str) -> HyprlandEvent | None:
    name, separator, payload = line.partition(">>")
    if not separator or not name:
        return None
    return HyprlandEvent(name, payload)


class HyprlandEventStream:
    def __init__(self, path: Path | None = None, socket_factory=socket.socket):
        self.path = path or event_socket_path()
        self._socket_factory = socket_factory

    def events(self) -> Iterator[HyprlandEvent]:
        connection = self._socket_factory(socket.AF_UNIX, socket.SOCK_STREAM)
        try:
            connection.connect(str(self.path))
            buffer = b""
            while True:
                chunk = connection.recv(16 * 1024)
                if not chunk:
                    return
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    event = parse_event(line.decode("utf-8", errors="replace"))
                    if event is not None:
                        yield event
        finally:
            connection.close()
