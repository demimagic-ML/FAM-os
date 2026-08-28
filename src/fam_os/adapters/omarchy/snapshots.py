"""Omarchy snapshot capability and explicit snapshot creation."""

from __future__ import annotations

import shutil
from dataclasses import dataclass

from fam_os.adapters.omarchy.commands import OmarchyCommandRunner


@dataclass(frozen=True, slots=True)
class SnapshotReceipt:
    available: bool
    created: bool
    reference: str | None
    detail: str


class OmarchySnapshots:
    def __init__(self, runner=None, which=shutil.which):
        self._runner = runner or OmarchyCommandRunner()
        self._which = which

    def available(self) -> bool:
        return self._which("omarchy-snapshot") is not None

    def create(self, description: str) -> SnapshotReceipt:
        if not description.strip():
            raise ValueError("snapshot description is required")
        executable = self._which("omarchy-snapshot")
        if executable is None:
            return SnapshotReceipt(False, False, None, "omarchy-snapshot is unavailable")
        result = self._runner.run((executable, "create", description.strip()), timeout=120)
        reference = result.stdout.splitlines()[-1] if result.succeeded and result.stdout else None
        return SnapshotReceipt(True, result.succeeded, reference, result.stderr or result.stdout)
