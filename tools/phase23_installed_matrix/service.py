"""Restartable installed service isolated from the owner's live service."""

from __future__ import annotations

import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path
from types import TracebackType
from typing import TextIO

from fam_os.product.bundle_installation import SignedBundleInstallation


_STACK_DUMP_BOOTSTRAP = (
    "import faulthandler,runpy,signal;"
    "faulthandler.register(signal.SIGUSR1, all_threads=True);"
    "runpy.run_module('fam_os.product.service', run_name='__main__')"
)


class CandidateService:
    def __init__(
        self, installation: SignedBundleInstallation, state_root: Path,
        run_root: Path, *,
        ollama_url: str, source_model_root: Path, model_ref: str = "qwen3:1.7b",
        home: Path | None = None, extra_arguments: tuple[str, ...] = (),
        manage_ollama: bool = False, validation_profile: str | None = None,
        launch_prefix: tuple[str, ...] = (),
    ) -> None:
        self.installation = installation
        self.state_root = state_root
        self.run_root = run_root
        self.ollama_url = ollama_url
        self.source_model_root = source_model_root
        self.model_ref = model_ref
        self.home = home
        self.extra_arguments = extra_arguments
        self.manage_ollama = manage_ollama
        self.validation_profile = validation_profile
        self.launch_prefix = launch_prefix
        # Managed startup may perform a digest-verified offline import of a
        # multi-gigabyte model before the product can publish readiness.
        self.startup_timeout_seconds = 300 if manage_ollama else 60
        self.port = _free_port()
        self.runtime_root = run_root / "runtime"
        self.ready = run_root / "ready"
        self._process: subprocess.Popen[str] | None = None
        self._stdout: TextIO | None = None
        self._stderr: TextIO | None = None

    @property
    def pid(self) -> int | None:
        process = self._process
        if process is None or process.poll() is not None:
            return None
        return process.pid

    def start(self) -> "CandidateService":
        if self._process is not None:
            raise RuntimeError("candidate service instance cannot be started twice")
        self.run_root.mkdir(parents=True, mode=0o700)
        self._stdout = (self.run_root / "service.stdout").open("w", encoding="utf-8")
        self._stderr = (self.run_root / "service.stderr").open("w", encoding="utf-8")
        environment = dict(os.environ)
        environment.pop("PYTHONPATH", None)
        environment.pop("PYTHONHOME", None)
        environment["PYTHONPATH"] = str(
            self.installation.prefix / "active/python"
        )
        if self.home is not None:
            environment["HOME"] = str(self.home)
        runtime_arguments = (
            () if self.manage_ollama else ("--external-ollama",)
        )
        profile_arguments = (
            () if self.validation_profile is None
            else ("--validation-profile", self.validation_profile)
        )
        self._process = subprocess.Popen(
            (
                *self.launch_prefix,
                sys.executable, "-c", _STACK_DUMP_BOOTSTRAP,
                "--state-root", str(self.state_root),
                "--runtime-root", str(self.runtime_root),
                *runtime_arguments, *profile_arguments,
                "--ollama-url", self.ollama_url,
                "--source-model-root", str(self.source_model_root),
                "--model", self.model_ref, "--console-port", str(self.port),
                "--ready-file", str(self.ready), *self.extra_arguments,
            ),
            cwd=self.run_root, env=environment, stdout=self._stdout,
            stderr=self._stderr, text=True, start_new_session=True,
        )
        try:
            self.wait_ready(self.startup_timeout_seconds)
        except BaseException:
            # A service that fails or times out during __enter__ never reaches
            # __exit__. Kill the partially composed process group so it cannot
            # resume startup after the qualification workspace is removed.
            try:
                self.crash()
            except BaseException:
                pass
            if self.manage_ollama:
                self._stop_orphaned_managed_provider()
            raise
        return self

    def wait_ready(self, timeout: float = 60) -> None:
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if self.ready.is_file():
                return
            if self._process is not None and self._process.poll() is not None:
                raise RuntimeError(self.failure("installed candidate service exited"))
            time.sleep(0.05)
        self.dump_stacks()
        raise TimeoutError(self.failure("installed candidate service did not become ready"))

    def dump_stacks(self) -> None:
        process = self._process
        if process is None or process.poll() is not None:
            return
        try:
            os.kill(process.pid, signal.SIGUSR1)
            time.sleep(0.2)
        except ProcessLookupError:
            pass

    def stop(self) -> None:
        self._terminate(signal.SIGTERM, 20)

    def crash(self) -> None:
        self._terminate(signal.SIGKILL, 5)

    def failure(self, prefix: str) -> str:
        if self._stdout is not None:
            self._stdout.flush()
        if self._stderr is not None:
            self._stderr.flush()
        stderr_path = self.run_root / "service.stderr"
        stdout_path = self.run_root / "service.stdout"
        stderr = (
            stderr_path.read_text(errors="replace")[-12000:]
            if stderr_path.is_file() else ""
        )
        stdout = (
            stdout_path.read_text(errors="replace")[-4000:]
            if stdout_path.is_file() else ""
        )
        process_state = "not-started"
        if self._process is not None:
            return_code = self._process.poll()
            process_state = (
                "running" if return_code is None else f"exited({return_code})"
            )
        return (
            f"{prefix}; process={process_state}; "
            f"stderr={stderr or '<empty>'}; stdout={stdout or '<empty>'}"
        )

    def _terminate(self, signal_number: signal.Signals, timeout: float) -> None:
        process = self._process
        if process is None:
            return
        if process.poll() is None:
            try:
                os.killpg(process.pid, signal_number)
            except ProcessLookupError:
                pass
        try:
            process.wait(timeout=timeout)
        except subprocess.TimeoutExpired:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait(timeout=5)
        if self._stdout is not None:
            self._stdout.close()
        if self._stderr is not None:
            self._stderr.close()
        self._process = None

    @staticmethod
    def _stop_orphaned_managed_provider() -> None:
        try:
            subprocess.run(
                ("systemctl", "--user", "stop", "fam-ollama.service"),
                check=False, capture_output=True, text=True, timeout=20,
            )
        except (OSError, subprocess.SubprocessError):
            pass

    def __enter__(self) -> "CandidateService":
        return self.start()

    def __exit__(
        self, _exception_type: type[BaseException] | None,
        _exception: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        self.stop()


def _free_port() -> int:
    with socket.socket() as stream:
        stream.bind(("127.0.0.1", 0))
        return int(stream.getsockname()[1])
