"""Bounded no-shell client for the local Docker daemon."""

from dataclasses import dataclass
import os
from pathlib import Path
import selectors
import signal
import stat
import subprocess
import time


@dataclass(frozen=True, slots=True)
class DockerCommandResult:
    exit_code: int
    output: bytes


class DockerCommandClient:
    def __init__(
        self,
        executable: Path = Path("/usr/bin/docker"),
        maximum_output_bytes: int = 1_048_576,
        maximum_input_bytes: int = 64 * 1024 * 1024,
    ) -> None:
        details = executable.stat(follow_symlinks=False)
        if (
            not executable.is_absolute() or executable.is_symlink()
            or not stat.S_ISREG(details.st_mode) or details.st_uid != 0
            or details.st_mode & 0o022
        ):
            raise PermissionError("Docker client must be an immutable root-owned file")
        if maximum_output_bytes <= 0 or maximum_input_bytes <= 0:
            raise ValueError("Docker input and output limits must be positive")
        self._executable = executable
        self._maximum_output_bytes = maximum_output_bytes
        self._maximum_input_bytes = maximum_input_bytes

    def run(
        self,
        arguments: tuple[str, ...],
        *,
        timeout_seconds: int = 30,
        environment: dict[str, str] | None = None,
    ) -> DockerCommandResult:
        return self._run(
            arguments,
            timeout_seconds=timeout_seconds,
            environment=environment,
            input_bytes=None,
        )

    def run_with_input(
        self,
        arguments: tuple[str, ...],
        input_bytes: bytes,
        *,
        timeout_seconds: int = 30,
        environment: dict[str, str] | None = None,
    ) -> DockerCommandResult:
        """Stream bounded bytes to one explicit command without a shell."""

        if not isinstance(input_bytes, bytes) or len(input_bytes) > self._maximum_input_bytes:
            raise ValueError("Docker command input exceeds its bound")
        return self._run(
            arguments,
            timeout_seconds=timeout_seconds,
            environment=environment,
            input_bytes=input_bytes,
        )

    def _run(
        self, arguments, *, timeout_seconds, environment, input_bytes,
    ) -> DockerCommandResult:
        if (
            not arguments or any(not isinstance(value, str) or "\0" in value for value in arguments)
            or not 1 <= timeout_seconds <= 600
        ):
            raise ValueError("Docker command request is invalid")
        process = subprocess.Popen(
            (str(self._executable), *arguments),
            stdin=(subprocess.DEVNULL if input_bytes is None else subprocess.PIPE),
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, close_fds=True, start_new_session=True,
            env=environment or {"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8"},
        )
        try:
            output = self._exchange(process, timeout_seconds, input_bytes)
        except BaseException:
            _terminate(process)
            raise
        finally:
            if process.stdout is not None:
                process.stdout.close()
            if process.stdin is not None:
                process.stdin.close()
        return DockerCommandResult(process.wait(), output)

    def _exchange(self, process, timeout_seconds: int, input_bytes) -> bytes:
        if process.stdout is None:
            raise RuntimeError("Docker output pipe is unavailable")
        deadline = time.monotonic() + timeout_seconds
        output = bytearray()
        selector = selectors.DefaultSelector()
        selector.register(process.stdout, selectors.EVENT_READ, "stdout")
        input_offset = 0
        if input_bytes is not None:
            if process.stdin is None:
                raise RuntimeError("Docker input pipe is unavailable")
            selector.register(process.stdin, selectors.EVENT_WRITE, "stdin")
        try:
            while True:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("Docker command exceeded its deadline")
                events = selector.select(min(remaining, 0.25))
                for key, _mask in events:
                    if key.data == "stdout":
                        chunk = os.read(key.fileobj.fileno(), 65_536)
                        if not chunk:
                            selector.unregister(key.fileobj)
                            continue
                        output.extend(chunk)
                        if len(output) > self._maximum_output_bytes:
                            raise RuntimeError("Docker command output exceeded its bound")
                        continue
                    try:
                        written = os.write(
                            key.fileobj.fileno(),
                            input_bytes[input_offset:input_offset + 65_536],
                        )
                    except BrokenPipeError:
                        written = 0
                        input_offset = len(input_bytes)
                    else:
                        input_offset += written
                    if input_offset >= len(input_bytes):
                        selector.unregister(key.fileobj)
                        key.fileobj.close()
                if process.poll() is not None and not any(
                    key.data == "stdout" for key in selector.get_map().values()
                ):
                    break
        finally:
            selector.close()
        return bytes(output)


def _terminate(process) -> None:
    if process.poll() is not None:
        return
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait(timeout=5)
