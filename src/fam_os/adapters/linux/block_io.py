"""Read-only Linux root-storage I/O counters with privacy-safe identity."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from fam_os.adapters.linux.command import CommandRunner


ROOT_SOURCE_QUERY = (
    "findmnt",
    "--noheadings",
    "--output",
    "SOURCE",
    "--target",
    "/",
)
_DEVICE_NAME = re.compile(r"^[A-Za-z0-9._-]+$")


@dataclass(frozen=True, slots=True)
class BlockIoReading:
    storage_id: str
    read_bytes: int
    write_bytes: int
    read_operations: int
    write_operations: int
    scope: str = "host_root_partition"

    def __post_init__(self) -> None:
        values = (
            self.read_bytes,
            self.write_bytes,
            self.read_operations,
            self.write_operations,
        )
        if not self.storage_id.strip() or any(value < 0 for value in values):
            raise ValueError("block I/O reading is invalid")


def query_root_block_io(
    runner: CommandRunner, sys_class_block: Path = Path("/sys/class/block")
) -> BlockIoReading | None:
    source = runner.run(ROOT_SOURCE_QUERY)
    if not source:
        return None
    name = Path(source.strip()).name
    if not _DEVICE_NAME.fullmatch(name):
        return None
    try:
        device = sys_class_block / name
        fields = (device / "stat").read_text().split()
        block_size = _logical_block_size(device)
        return parse_block_io(fields, block_size)
    except (OSError, ValueError):
        return None


def _logical_block_size(device: Path) -> int:
    direct = device / "queue" / "logical_block_size"
    if direct.is_file():
        return int(direct.read_text())
    parent = device.resolve().parent / "queue" / "logical_block_size"
    return int(parent.read_text())


def parse_block_io(fields: list[str], block_size: int) -> BlockIoReading:
    if len(fields) < 7 or block_size <= 0:
        raise ValueError("Linux block stat is incomplete")
    reads, sectors_read = int(fields[0]), int(fields[2])
    writes, sectors_written = int(fields[4]), int(fields[6])
    return BlockIoReading(
        "storage-root",
        sectors_read * block_size,
        sectors_written * block_size,
        reads,
        writes,
    )
