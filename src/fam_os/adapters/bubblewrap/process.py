"""Streaming bounded subprocess execution behind an injectable launcher."""

import os
import selectors
import signal
import subprocess
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Callable, Protocol

from fam_os.adapters.bubblewrap.rlimits import apply_resource_limits
from fam_os.verification.sandbox import (
    IsolationLevel,
    SandboxLimits,
    SandboxResult,
    SandboxStatus,
)


class ProcessLauncher(Protocol):
    def run(
        self,
        command: tuple[str, ...],
        limits: SandboxLimits,
        environment: tuple[tuple[str, str], ...],
        isolation: IsolationLevel,
    ) -> SandboxResult: ...


@dataclass(slots=True)
class SubprocessProcessLauncher:
    clock: Callable[[], float] = perf_counter

    def run(self, command, limits, environment, isolation) -> SandboxResult:
        started = self.clock()
        child_environment = dict(environment)
        if command and Path(command[0]).name == "systemd-run":
            for name in ("XDG_RUNTIME_DIR", "DBUS_SESSION_BUS_ADDRESS"):
                if name in os.environ:
                    child_environment[name] = os.environ[name]
        try:
            process = subprocess.Popen(
                command,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=child_environment,
                preexec_fn=lambda: apply_resource_limits(limits),
                start_new_session=True,
            )
        except (OSError, subprocess.SubprocessError) as error:
            return SandboxResult(
                SandboxStatus.UNAVAILABLE, IsolationLevel.NONE,
                self.clock() - started,
                reason=f"sandbox process could not start: {error}",
            )
        stdout, stderr, timed_out = _capture_bounded(
            process, limits.output_bytes, started, limits.wall_seconds, self.clock
        )
        elapsed = self.clock() - started
        if timed_out:
            return SandboxResult(
                SandboxStatus.TIMED_OUT, isolation, elapsed, stdout, stderr,
                reason=f"sandbox exceeded {limits.wall_seconds:.1f}s wall-time limit",
            )
        return SandboxResult(
            SandboxStatus.COMPLETED, isolation, elapsed, stdout, stderr,
            process.returncode,
        )


def _capture_bounded(process, limit, started, wall_seconds, clock):
    selector = selectors.DefaultSelector()
    streams = {process.stdout: bytearray(), process.stderr: bytearray()}
    for stream in streams:
        os.set_blocking(stream.fileno(), False)
        selector.register(stream, selectors.EVENT_READ)
    timed_out = False
    while selector.get_map():
        remaining = wall_seconds - (clock() - started)
        if remaining <= 0 and not timed_out:
            timed_out = True
            _terminate_group(process)
        for key, _ in selector.select(0.05):
            chunk = os.read(key.fileobj.fileno(), 65_536)
            if not chunk:
                selector.unregister(key.fileobj)
            elif len(streams[key.fileobj]) < limit:
                target = streams[key.fileobj]
                target.extend(chunk[: limit - len(target)])
    process.wait()
    captured = tuple(
        bytes(streams[stream]).decode("utf-8", "replace") for stream in streams
    )
    for stream in streams:
        stream.close()
    return (*captured, timed_out)


def _terminate_group(process) -> None:
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
