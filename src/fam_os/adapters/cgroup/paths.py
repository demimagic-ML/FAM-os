"""Replaceable cgroup-v2 filesystem location."""

from dataclasses import dataclass
from pathlib import Path, PurePosixPath


@dataclass(frozen=True, slots=True)
class CgroupV2Paths:
    root: Path = Path("/sys/fs/cgroup")

    def group(self, resource_group: str) -> Path:
        relative = PurePosixPath(resource_group.lstrip("/"))
        if not relative.parts or ".." in relative.parts:
            raise ValueError("resource group path is invalid")
        return self.root.joinpath(*relative.parts)
