"""Lifecycle wrapper for the installed live-adaptation service."""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path


class InstalledLiveAdaptationService:
    def __init__(
        self,
        installation,
        repository: Path,
        product_root: Path,
        run_root: Path,
        model_root: Path,
        responses: tuple[dict, ...],
        health_samples: tuple[dict, ...] = (),
    ) -> None:
        self.product_root = product_root
        self.run_root = run_root
        self.port = _free_port()
        run_root.mkdir()
        response_file = run_root / "responses.json"
        response_file.write_text(json.dumps(responses), encoding="utf-8")
        health_file = run_root / "health.json"
        health_file.write_text(json.dumps(health_samples), encoding="utf-8")
        self.telemetry = run_root / "telemetry.jsonl"
        self.ready = run_root / "ready"
        self.runtime_root = product_root / "runtime"
        self._stdout = (run_root / "service.stdout").open("w", encoding="utf-8")
        self._stderr = (run_root / "service.stderr").open("w", encoding="utf-8")
        command = [
            sys.executable,
            str(repository / "tools/phase20_live_exit/service_process.py"),
            "--installed-python",
            str(installation.prefix / "active/python"),
            "--repository",
            str(repository),
            "--state-root",
            str(product_root / "state"),
            "--runtime-root",
            str(self.runtime_root),
            "--ready-file",
            str(self.ready),
            "--responses",
            str(response_file),
            "--telemetry",
            str(self.telemetry),
            "--source-model-root",
            str(model_root),
            "--port",
            str(self.port),
        ]
        if health_samples:
            command.extend(("--health", str(health_file)))
        self._process = subprocess.Popen(
            tuple(command),
            cwd=run_root,
            stdout=self._stdout,
            stderr=self._stderr,
            text=True,
            start_new_session=True,
        )

    def wait_ready(self, timeout: float = 30) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.ready.is_file():
                return
            if self._process.poll() is not None:
                raise RuntimeError(self._failure("installed live service exited"))
            time.sleep(0.05)
        raise TimeoutError(self._failure("installed live service was not ready"))

    def events(self) -> tuple[dict, ...]:
        if not self.telemetry.is_file():
            return ()
        return tuple(
            json.loads(line)
            for line in self.telemetry.read_text().splitlines()
            if line.strip()
        )

    def wait_for_prewarm(self, model_ref: str, timeout: float = 30) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if any(
                item["kind"] == "prewarm" and item["model_ref"] == model_ref
                for item in self.events()
            ):
                return
            if self._process.poll() is not None:
                raise RuntimeError(self._failure("service exited before prewarm"))
            time.sleep(0.02)
        raise TimeoutError(self._failure(f"model was not prewarmed: {model_ref}"))

    def wait_for_quiescence(
        self,
        timeout: float = 30,
        stable_seconds: float = 0.2,
    ) -> None:
        deadline = time.monotonic() + timeout
        previous = self.events()
        stable_since = time.monotonic()
        while time.monotonic() < deadline:
            time.sleep(min(0.05, stable_seconds))
            current = self.events()
            if current != previous:
                previous = current
                stable_since = time.monotonic()
            elif time.monotonic() - stable_since >= stable_seconds:
                return
            if self._process.poll() is not None:
                raise RuntimeError(self._failure("service exited before becoming idle"))
        raise TimeoutError(self._failure("installed live service did not become idle"))

    def stop(self) -> None:
        if self._process.poll() is None:
            try:
                os.killpg(self._process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
        try:
            self._process.wait(timeout=30)
        except subprocess.TimeoutExpired:
            os.killpg(self._process.pid, signal.SIGKILL)
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
