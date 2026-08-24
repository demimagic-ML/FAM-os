"""Lifecycle wrapper for the installed verifier qualification service."""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path


class InstalledVerifierService:
    def __init__(self, installation, repository: Path, root: Path, responses) -> None:
        self.root = root
        self.port = _free_port()
        self._responses = root / "responses.json"
        self._responses.write_text(json.dumps(tuple(responses)), encoding="utf-8")
        self.observations = root / "runtime-observations.json"
        self.ready = root / "ready"
        self.runtime_root = root / "runtime"
        self._stdout = (root / "service.stdout").open("w", encoding="utf-8")
        self._stderr = (root / "service.stderr").open("w", encoding="utf-8")
        self._process = subprocess.Popen(
            (
                sys.executable,
                str(repository / "tools/phase18_verifier_exit/service_process.py"),
                "--installed-python", str(installation.prefix / "active/python"),
                "--repository", str(repository),
                "--state-root", str(root / "state"),
                "--runtime-root", str(self.runtime_root),
                "--ready-file", str(self.ready),
                "--responses", str(self._responses),
                "--observations", str(self.observations),
                "--port", str(self.port),
            ),
            cwd=root, stdout=self._stdout, stderr=self._stderr,
            text=True, start_new_session=True,
        )

    def wait_ready(self, timeout: float = 30) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.ready.is_file():
                return
            if self._process.poll() is not None:
                raise RuntimeError(self._failure("installed verifier service exited"))
            time.sleep(0.05)
        raise TimeoutError(self._failure("installed verifier service did not become ready"))

    def stop(self) -> None:
        if self._process.poll() is None:
            try:
                os.killpg(self._process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        try:
            self._process.wait(timeout=20)
        except subprocess.TimeoutExpired:
            os.killpg(self._process.pid, signal.SIGKILL)
            self._process.wait(timeout=5)
        self._stdout.close()
        self._stderr.close()

    def _failure(self, prefix: str) -> str:
        self._stdout.flush()
        self._stderr.flush()
        detail = (self.root / "service.stderr").read_text(errors="replace")[-4000:]
        return f"{prefix}: {detail}"

    def __enter__(self):
        self.wait_ready()
        return self

    def __exit__(self, *_error):
        self.stop()


def _free_port() -> int:
    with socket.socket() as stream:
        stream.bind(("127.0.0.1", 0))
        return stream.getsockname()[1]
