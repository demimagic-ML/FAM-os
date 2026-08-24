"""Explicit terminal commands for owner-controlled persistent memory."""

import os
import stat
from pathlib import Path

from fam_os.memory import MAX_MANAGED_DOCUMENT_BYTES
from fam_os.shell.memory_render import render_memory_response


def execute_memory_command(controller, values: list[str]) -> str:
    if not values:
        raise ValueError("memory subcommand is required")
    command, arguments = values[0].casefold(), values[1:]
    if command == "list":
        offset, limit = _page(arguments)
        return render_memory_response(controller.memory_list(offset, limit))
    if command == "receipts":
        offset, limit = _page(arguments)
        return render_memory_response(controller.memory_receipts(offset, limit))
    if command == "inspect" and len(arguments) == 1:
        return render_memory_response(controller.memory_inspect(arguments[0]))
    if command == "export" and len(arguments) == 1:
        return render_memory_response(controller.memory_export(arguments[0]))
    if command == "correct" and len(arguments) == 4 and arguments[-1] == "--confirm":
        content = _read_replacement(Path(arguments[2]))
        return render_memory_response(controller.memory_correct(
            arguments[0], arguments[1], content, confirmed=True,
        ))
    if command == "delete" and len(arguments) == 3 and arguments[-1] == "--confirm":
        return render_memory_response(controller.memory_delete(
            arguments[0], arguments[1], confirmed=True,
        ))
    if command == "expire" and len(arguments) == 2 and arguments[-1] == "--confirm":
        return render_memory_response(controller.memory_expire(
            arguments[0], confirmed=True,
        ))
    raise ValueError("invalid memory command or missing --confirm")


def _page(arguments: list[str]) -> tuple[int, int]:
    if len(arguments) > 2:
        raise ValueError("memory page accepts OFFSET and LIMIT")
    try:
        offset = int(arguments[0]) if arguments else 0
        limit = int(arguments[1]) if len(arguments) == 2 else 100
    except ValueError as error:
        raise ValueError("memory page values must be integers") from error
    return offset, limit


def _read_replacement(path: Path) -> str:
    flags = os.O_RDONLY | os.O_CLOEXEC
    if hasattr(os, "O_NOFOLLOW"):
        flags |= os.O_NOFOLLOW
    descriptor = os.open(path, flags)
    try:
        details = os.fstat(descriptor)
        if not stat.S_ISREG(details.st_mode) or details.st_size > MAX_MANAGED_DOCUMENT_BYTES:
            raise ValueError("replacement must be one bounded regular file")
        content = _read_bounded(descriptor)
    finally:
        os.close(descriptor)
    try:
        return content.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise ValueError("replacement file must be strict UTF-8") from error


def _read_bounded(descriptor: int) -> bytes:
    chunks = []
    remaining = MAX_MANAGED_DOCUMENT_BYTES + 1
    while remaining:
        chunk = os.read(descriptor, min(65_536, remaining))
        if not chunk:
            break
        chunks.append(chunk)
        remaining -= len(chunk)
    content = b"".join(chunks)
    if len(content) > MAX_MANAGED_DOCUMENT_BYTES:
        raise ValueError("replacement file exceeds the memory document limit")
    return content
