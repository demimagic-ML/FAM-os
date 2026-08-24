#!/usr/bin/env python3
"""Run one candidate service in a private bounded tmpfs and inject ENOSPC."""

from __future__ import annotations

import argparse
import errno
import json
import os
import shutil
import signal
import subprocess
import time
from pathlib import Path


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--seed-root", type=Path, required=True)
    parser.add_argument("--export-root", type=Path, required=True)
    parser.add_argument("--control-root", type=Path, required=True)
    parser.add_argument("--size-bytes", type=int, required=True)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    arguments = parser.parse_args()
    command = tuple(arguments.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        raise ValueError("low-disk launcher requires a service command")
    return _run(arguments, command)


def _run(arguments: argparse.Namespace, command: tuple[str, ...]) -> int:
    state_root = arguments.state_root.absolute()
    state_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    arguments.control_root.mkdir(parents=True, exist_ok=True, mode=0o700)
    subprocess.run(
        (
            "mount", "-t", "tmpfs", "-o",
            f"size={arguments.size_bytes},mode=700", "tmpfs", str(state_root),
        ),
        check=True, timeout=15,
    )
    child: subprocess.Popen[bytes] | None = None
    pressure: dict[str, object] = {}
    try:
        _copy_tree(arguments.seed_root, state_root)
        child = subprocess.Popen(command)
        _forward_signals(child)
        request = arguments.control_root / "pressure.request"
        while child.poll() is None:
            if request.is_file() and not pressure:
                pressure = _fill(state_root)
                _write_json(arguments.control_root / "pressure.json", pressure)
            time.sleep(0.05)
        return_code = child.returncode
        if not pressure:
            pressure = {"injected": False, "enospc_observed": False}
            _write_json(arguments.control_root / "pressure.json", pressure)
        _copy_tree(state_root, arguments.export_root, exclude={"pressure.bin"})
        _write_json(arguments.control_root / "export.json", {
            "child_return_code": return_code,
            "exported": arguments.export_root.is_dir(),
            "pressure": pressure,
        })
        return int(return_code or 0)
    finally:
        if child is not None and child.poll() is None:
            child.kill()
            child.wait(timeout=5)
        subprocess.run(("umount", str(state_root)), check=False, timeout=15)


def _fill(root: Path) -> dict[str, object]:
    before = shutil.disk_usage(root)
    path = root / "pressure.bin"
    written = 0
    enospc = False
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        with os.fdopen(descriptor, "wb", buffering=0) as stream:
            chunk = b"\0" * (1024 * 1024)
            while True:
                try:
                    written += stream.write(chunk)
                except OSError as error:
                    if error.errno != errno.ENOSPC:
                        raise
                    enospc = True
                    break
            try:
                stream.flush()
                os.fsync(stream.fileno())
            except OSError as error:
                if error.errno != errno.ENOSPC:
                    raise
                enospc = True
    finally:
        after = shutil.disk_usage(root)
    return {
        "injected": True,
        "filesystem_total_bytes": before.total,
        "free_before_bytes": before.free,
        "free_after_bytes": after.free,
        "fill_bytes": written,
        "enospc_observed": enospc,
    }


def _forward_signals(child: subprocess.Popen[bytes]) -> None:
    def forward(number: int, _frame: object) -> None:
        if child.poll() is None:
            child.send_signal(number)

    signal.signal(signal.SIGTERM, forward)
    signal.signal(signal.SIGINT, forward)


def _copy_tree(source: Path, target: Path, *, exclude: set[str] | None = None) -> None:
    target.mkdir(parents=True, exist_ok=True, mode=0o700)
    ignored = exclude or set()
    for child in source.iterdir() if source.is_dir() else ():
        if child.name in ignored:
            continue
        destination = target / child.name
        if child.is_dir():
            shutil.copytree(child, destination, dirs_exist_ok=True)
        elif child.is_file():
            shutil.copy2(child, destination)


def _write_json(path: Path, document: dict[str, object]) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(document, sort_keys=True) + "\n")
    temporary.replace(path)


if __name__ == "__main__":
    raise SystemExit(main())
