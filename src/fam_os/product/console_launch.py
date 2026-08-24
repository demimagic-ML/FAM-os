"""Secure product service for opening the authenticated loopback Console."""

from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import re
import stat
from typing import Protocol
from urllib.parse import quote


_TOKEN = re.compile(r"[A-Za-z0-9_-]{32,256}")


class ConsoleAvailabilityProbe(Protocol):
    def ready(self, port: int) -> bool: ...


class ConsoleBrowser(Protocol):
    def open(self, uri: str) -> bool: ...


@dataclass(frozen=True, slots=True)
class ConsoleLaunchReceipt:
    opened: bool
    base_url: str
    authenticated_fragment_used: bool


class ConsoleLaunchService:
    def __init__(
        self,
        probe: ConsoleAvailabilityProbe,
        browser: ConsoleBrowser,
    ) -> None:
        self._probe = probe
        self._browser = browser

    def launch(self, runtime_root: Path, port: int) -> ConsoleLaunchReceipt:
        if not runtime_root.is_absolute():
            raise ValueError("console runtime root must be absolute")
        if not 1 <= port <= 65_535:
            raise ValueError("console port is invalid")
        if not self._probe.ready(port):
            raise ConnectionError("FAM Console is not ready on the loopback port")
        token = _private_token(runtime_root / "console.token")
        base_url = f"http://127.0.0.1:{port}"
        authenticated_url = f"{base_url}/#token={quote(token, safe='')}"
        if not self._browser.open(authenticated_url):
            raise RuntimeError("the desktop browser launcher failed")
        return ConsoleLaunchReceipt(True, base_url, True)


def _private_token(path: Path) -> str:
    flags = os.O_RDONLY | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags)
    try:
        details = os.fstat(descriptor)
        if (
            not stat.S_ISREG(details.st_mode)
            or details.st_uid != os.geteuid()
            or stat.S_IMODE(details.st_mode) != 0o600
            or details.st_nlink != 1
        ):
            raise PermissionError("console token must be a private owner file")
        if details.st_size > 512:
            raise ValueError("stored console token is invalid")
        with os.fdopen(os.dup(descriptor), encoding="utf-8") as stream:
            token = stream.read(513).strip()
    finally:
        os.close(descriptor)
    if _TOKEN.fullmatch(token) is None:
        raise ValueError("stored console token is invalid")
    return token
