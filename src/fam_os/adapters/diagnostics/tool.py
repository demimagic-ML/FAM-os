"""No-shell helper for ephemeral core analysis and compiler sanitizers."""

from __future__ import annotations

import os
from pathlib import Path
import selectors
import signal
import subprocess
import sys
from time import monotonic


MAXIMUM_OUTPUT_BYTES = 2_000_000
WALL_SECONDS = 30


def main(argv: tuple[str, ...] | None = None) -> int:
    arguments = tuple(sys.argv[1:] if argv is None else argv)
    if len(arguments) != 2 or arguments[0] not in {
        "core", "race", "leak", "run", "stack",
    }:
        print(
            "usage: diagnostic-tool {core|race|leak|run|stack} /workspace/target",
            file=sys.stderr,
        )
        return 64
    try:
        target = _target(arguments[1])
        if arguments[0] == "core":
            return _core(target)
        if arguments[0] == "run":
            return _run_target(target)
        if arguments[0] == "stack":
            return _stack(target)
        return _sanitizer(arguments[0], target)
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        print(f"diagnostic tool unavailable: {error}", file=sys.stderr)
        return 69


def _target(value: str) -> Path:
    lexical = Path(value)
    if not lexical.is_absolute() or lexical.is_symlink():
        raise ValueError("diagnostic target must be an absolute regular candidate path")
    target = lexical.resolve(strict=True)
    workspace = Path("/workspace").resolve(strict=True)
    if workspace not in target.parents or not target.is_file():
        raise ValueError("diagnostic target escapes /workspace")
    return target


def _core(target: Path) -> int:
    core = Path("/tmp/fam-diagnostic.core")
    target_command = (
        ("/usr/bin/python3", str(target))
        if target.suffix == ".py" else (str(target),)
    )
    command = (
        "/usr/bin/gdb", "--batch", "-ex", "run", "-ex",
        f"generate-core-file {core}", "-ex", "bt", "--args", *target_command,
    )
    result, output = _run(command)
    generated = core.is_file() and core.stat().st_size > 0
    core.unlink(missing_ok=True)
    _emit(output)
    if not generated:
        print("ephemeral core dump was not generated", file=sys.stderr)
        return 65
    return result


def _sanitizer(mode: str, target: Path) -> int:
    output = Path("/tmp/fam-sanitized-target")
    flags = {
        "race": ("-fsanitize=thread", "-pthread", "-fno-pie", "-no-pie"),
        "leak": ("-fsanitize=leak",),
    }[mode]
    compile_command = (
        "/usr/bin/gcc", *flags, "-fno-omit-frame-pointer", "-g",
        "-o", str(output), str(target),
    )
    compiled, compile_output = _run(compile_command)
    _emit(compile_output)
    if compiled != 0:
        return compiled
    try:
        run_command = (str(output),)
        if mode == "race":
            run_command = ("/usr/bin/setarch", "x86_64", "-R", str(output))
        executed, run_output = _run(run_command)
        _emit(run_output)
        if mode == "race" and (
            b"ThreadSanitizer: unexpected memory mapping" in run_output
            or (executed != 0 and not run_output)
        ):
            if not run_output:
                print("ThreadSanitizer runtime unavailable: terminated without report", file=sys.stderr)
            return 69
        return executed
    finally:
        output.unlink(missing_ok=True)


def _run_target(target: Path) -> int:
    command = (
        ("/usr/bin/python3", str(target))
        if target.suffix == ".py" else (str(target),)
    )
    executed, output = _run(command)
    _emit(output)
    return executed


def _stack(target: Path) -> int:
    command = (
        ("/usr/bin/python3", "-X", "faulthandler", str(target))
        if target.suffix == ".py"
        else (
            "/usr/bin/gdb", "--batch", "-ex", "run", "-ex", "bt",
            "--args", str(target),
        )
    )
    executed, output = _run(command)
    _emit(output)
    return executed


def _run(command: tuple[str, ...]) -> tuple[int, bytes]:
    process = subprocess.Popen(
        command, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        env={"PATH": "/usr/bin:/bin", "LANG": "C.UTF-8"},
        start_new_session=True,
    )
    output = _capture(process)
    return process.returncode, output


def _capture(process: subprocess.Popen) -> bytes:
    selector = selectors.DefaultSelector()
    chunks = bytearray()
    started = monotonic()
    for stream in (process.stdout, process.stderr):
        os.set_blocking(stream.fileno(), False)
        selector.register(stream, selectors.EVENT_READ)
    while selector.get_map():
        if monotonic() - started > WALL_SECONDS:
            os.killpg(process.pid, signal.SIGKILL)
            process.wait()
            raise ValueError("diagnostic subprocess exceeded wall limit")
        for key, _events in selector.select(0.1):
            chunk = os.read(key.fileobj.fileno(), 65_536)
            if not chunk:
                selector.unregister(key.fileobj)
            elif len(chunks) + len(chunk) > MAXIMUM_OUTPUT_BYTES:
                os.killpg(process.pid, signal.SIGKILL)
                process.wait()
                raise ValueError("diagnostic subprocess exceeded output limit")
            else:
                chunks.extend(chunk)
    process.wait()
    return bytes(chunks)


def _emit(content: bytes) -> None:
    sys.stdout.buffer.write(content)
    sys.stdout.buffer.flush()


if __name__ == "__main__":
    raise SystemExit(main())
