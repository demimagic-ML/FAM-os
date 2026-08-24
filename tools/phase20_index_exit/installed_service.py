"""Lifecycle wrapper for the installed document-index service."""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path


class InstalledIndexService:
    def __init__(
        self, installation, repository: Path, product_root: Path,
        model_root: Path, run_root: Path,
    ) -> None:
        self.product_root = product_root
        self.run_root = run_root
        self.port = _free_port()
        run_root.mkdir()
        self.ready = run_root / "ready"
        self.runtime_root = product_root / "runtime"
        self._stdout = (run_root / "service.stdout").open("w", encoding="utf-8")
        self._stderr = (run_root / "service.stderr").open("w", encoding="utf-8")
        self._process = subprocess.Popen(
            (
                sys.executable,
                str(repository / "tools/phase20_index_exit/service_process.py"),
                "--installed-python", str(installation.prefix / "active/python"),
                "--repository", str(repository),
                "--state-root", str(product_root / "state"),
                "--runtime-root", str(self.runtime_root),
                "--model-root", str(model_root),
                "--ready-file", str(self.ready),
                "--port", str(self.port),
            ),
            cwd=run_root, stdout=self._stdout, stderr=self._stderr,
            text=True, start_new_session=True,
        )

    def wait_ready(self, timeout: float = 30) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.ready.is_file():
                return
            if self._process.poll() is not None:
                raise RuntimeError(self._failure("installed index service exited"))
            time.sleep(0.05)
        raise TimeoutError(self._failure("installed index service did not become ready"))

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
        detail = (self.run_root / "service.stderr").read_text(errors="replace")[-4000:]
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
