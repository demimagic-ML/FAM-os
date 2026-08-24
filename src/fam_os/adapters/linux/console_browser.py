"""Linux adapters used by the authenticated Console launcher."""

from __future__ import annotations

import http.client
import subprocess


class LoopbackConsoleProbe:
    def ready(self, port: int) -> bool:
        connection = http.client.HTTPConnection("127.0.0.1", port, timeout=2)
        try:
            connection.request("GET", "/")
            response = connection.getresponse()
            response.read()
            return response.status == 200
        except (OSError, http.client.HTTPException):
            return False
        finally:
            connection.close()


class XdgConsoleBrowser:
    def open(self, uri: str) -> bool:
        try:
            process = subprocess.Popen(
                ("xdg-open", uri),
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                close_fds=True,
                start_new_session=True,
            )
        except OSError:
            return False
        try:
            return process.wait(timeout=0.25) == 0
        except subprocess.TimeoutExpired:
            # Desktop launchers may remain attached to an existing browser. The
            # successful spawn is sufficient; the CLI must not kill that handoff.
            return True
