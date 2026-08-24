"""Lifecycle wrapper for an installed peer-enabled FAM_OS service."""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import time
from pathlib import Path


class InstalledPeerService:
    def __init__(
        self,
        installation,
        state_root: Path,
        run_root: Path,
        *,
        ollama_url: str = "http://127.0.0.1:1",
        model_ref: str = "qwen3:1.7b",
    ) -> None:
        self.state_root = state_root
        self.run_root = run_root
        self.runtime_root = run_root / "runtime"
        self.ready = run_root / "ready"
        self.port = _free_port()
        run_root.mkdir()
        self._stdout = (run_root / "service.stdout").open("w", encoding="utf-8")
        self._stderr = (run_root / "service.stderr").open("w", encoding="utf-8")
        self._process = subprocess.Popen(
            (
                str(installation.prefix / "bin/fam-service"),
                "--state-root", str(state_root),
                "--runtime-root", str(self.runtime_root),
                "--external-ollama",
                "--ollama-url", ollama_url,
                "--model", model_ref,
                "--console-port", str(self.port),
                "--ready-file", str(self.ready),
            ),
            stdout=self._stdout, stderr=self._stderr, text=True,
            start_new_session=True,
        )

    def wait_ready(self, timeout: float = 30) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.ready.is_file():
                return
            if self._process.poll() is not None:
                raise RuntimeError(self._failure("installed peer service exited"))
            time.sleep(0.05)
        raise TimeoutError(self._failure("installed peer service did not become ready"))

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

    def crash(self) -> None:
        """Simulate abrupt process loss without a graceful service shutdown."""
        if self._process.poll() is None:
            try:
                os.killpg(self._process.pid, signal.SIGKILL)
            except ProcessLookupError:
                pass
        self._process.wait(timeout=5)
        self._stdout.close()
        self._stderr.close()

    def _failure(self, prefix: str) -> str:
        self._stdout.flush()
        self._stderr.flush()
        detail = (self.run_root / "service.stderr").read_text(errors="replace")[-6000:]
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
