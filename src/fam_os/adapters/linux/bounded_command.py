"""Bounded shell-free process transport for deterministic Linux adapters."""

import os
import selectors
import signal
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class BoundedCommandPolicy:
    timeout_seconds: float = 10.0
    maximum_stdout_bytes: int = 1_048_576
    maximum_stderr_bytes: int = 65_536

    def __post_init__(self) -> None:
        if min(
            self.timeout_seconds, self.maximum_stdout_bytes,
            self.maximum_stderr_bytes,
        ) <= 0:
            raise ValueError("bounded command policy values must be positive")


@dataclass(frozen=True, slots=True)
class BoundedCommandResult:
    exit_code: int | None
    stdout: str
    stderr: str
    timed_out: bool = False
    output_limited: bool = False

    @property
    def succeeded(self) -> bool:
        return self.exit_code == 0 and not self.timed_out and not self.output_limited


class BoundedSubprocessRunner:
    def __init__(self, policy=BoundedCommandPolicy()):
        self._policy = policy

    def run(self, command: tuple[str, ...], cwd=None, environment=None):
        _validate_command(command, cwd, environment)
        process = subprocess.Popen(
            command, stdin=subprocess.DEVNULL, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, shell=False, cwd=cwd,
            env=dict(environment or {}), start_new_session=True, close_fds=True,
        )
        try:
            return self._communicate(process)
        except BaseException:
            _terminate(process)
            raise
        finally:
            process.stdout.close()
            process.stderr.close()

    def _communicate(self, process):
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ, "stdout")
        selector.register(process.stderr, selectors.EVENT_READ, "stderr")
        buffers = {"stdout": bytearray(), "stderr": bytearray()}
        limits = {
            "stdout": self._policy.maximum_stdout_bytes,
            "stderr": self._policy.maximum_stderr_bytes,
        }
        deadline = time.monotonic() + self._policy.timeout_seconds
        timed_out = output_limited = False
        while selector.get_map():
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                timed_out = True
                break
            if _read_ready(selector, buffers, limits, min(remaining, 0.1)):
                output_limited = True
                break
        if timed_out or output_limited:
            _terminate(process)
        else:
            process.wait()
        selector.close()
        return BoundedCommandResult(
            process.returncode, _decode(buffers["stdout"]),
            _decode(buffers["stderr"]), timed_out, output_limited,
        )


def _read_ready(selector, buffers, limits, timeout):
    for key, _mask in selector.select(timeout):
        name = key.data
        chunk = os.read(key.fileobj.fileno(), 65_536)
        if not chunk:
            selector.unregister(key.fileobj)
            continue
        buffers[name].extend(chunk)
        if len(buffers[name]) > limits[name]:
            del buffers[name][limits[name]:]
            return True
    return False


def _terminate(process):
    if process.poll() is None:
        try:
            os.killpg(process.pid, signal.SIGKILL)
        except ProcessLookupError:
            pass
    process.wait()


def _validate_command(command, cwd, environment):
    if not command or any(not isinstance(item, str) or "\0" in item for item in command):
        raise ValueError("bounded command arguments must be null-free strings")
    executable = Path(command[0])
    if not executable.is_absolute() or not executable.is_file():
        raise ValueError("bounded command executable must be an absolute file")
    if not os.access(executable, os.X_OK):
        raise ValueError("bounded command executable is not executable")
    if cwd is not None and (not Path(cwd).is_absolute() or not Path(cwd).is_dir()):
        raise ValueError("bounded command working directory is invalid")
    if environment is not None and any(
        not key or "=" in key or "\0" in key or "\0" in value
        for key, value in environment.items()
    ):
        raise ValueError("bounded command environment is invalid")


def _decode(value):
    return bytes(value).decode("utf-8", errors="replace")
