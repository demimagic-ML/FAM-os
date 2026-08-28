"""Omarchy snapshot capability and explicit snapshot creation."""

from __future__ import annotations

import shutil
import csv
import io
from dataclasses import dataclass

from fam_os.adapters.omarchy.commands import OmarchyCommandRunner


@dataclass(frozen=True, slots=True)
class SnapshotReceipt:
    available: bool
    created: bool
    reference: str | None
    detail: str
    references: tuple[str, ...] = ()
    recovery_command: str | None = None


class OmarchySnapshots:
    def __init__(self, runner=None, which=shutil.which):
        self._runner = runner or OmarchyCommandRunner()
        self._which = which

    def available(self) -> bool:
        return (
            self._which("omarchy-snapshot") is not None
            and self._which("snapper") is not None
            and self._which("sudo") is not None
        )

    def create(self, description: str) -> SnapshotReceipt:
        if not description.strip():
            raise ValueError("snapshot description is required")
        executable = self._which("omarchy-snapshot")
        snapper = self._which("snapper")
        sudo = self._which("sudo")
        if executable is None or snapper is None or sudo is None:
            return SnapshotReceipt(False, False, None, "omarchy-snapshot is unavailable")
        configs, issue = self._configs(sudo, snapper)
        if not configs:
            return SnapshotReceipt(
                True, False, None,
                issue or "Snapper is installed but has no configured snapshot roots",
            )
        try:
            before = {
                config: self._numbers(sudo, snapper, config)
                for config in configs
            }
        except RuntimeError as error:
            return SnapshotReceipt(True, False, None, str(error))
        result = self._runner.run((executable, "create"), timeout=120)
        if not result.succeeded:
            return SnapshotReceipt(
                True, False, None, result.stderr or result.stdout,
            )
        try:
            after = {
                config: self._numbers(sudo, snapper, config)
                for config in configs
            }
        except RuntimeError as error:
            return SnapshotReceipt(True, False, None, str(error))
        references = tuple(
            f"{config}:{number}"
            for config in configs
            for number in sorted(after[config] - before[config])
        )
        if not references:
            return SnapshotReceipt(
                True, False, None,
                "omarchy-snapshot exited successfully but no new Snapper IDs were observed",
            )
        return SnapshotReceipt(
            True, True, ",".join(references),
            result.stderr or result.stdout or "System snapshots created",
            references, "omarchy snapshot restore",
        )

    def _configs(self, sudo: str, snapper: str) -> tuple[tuple[str, ...], str]:
        result = self._runner.run(
            (sudo, "-n", snapper, "--csvout", "list-configs"),
        )
        if not result.succeeded:
            return (), result.stderr or "Snapper configurations could not be inspected"
        rows = _csv_rows(result.stdout)
        if len(rows) < 2:
            return (), "Snapper is installed but has no configured snapshot roots"
        return tuple(row[0].strip() for row in rows[1:] if row and row[0].strip()), ""

    def _numbers(self, sudo: str, snapper: str, config: str) -> set[int]:
        result = self._runner.run((
            sudo, "-n", snapper, "-c", config, "--csvout", "list",
            "--columns", "number",
        ))
        if not result.succeeded:
            raise RuntimeError(
                f"could not inspect Snapper config {config}: {result.stderr}"
            )
        return {
            int(cell)
            for row in _csv_rows(result.stdout)
            for cell in row[:1]
            if cell.strip().isdigit()
        }


def _csv_rows(value: str) -> list[list[str]]:
    sample = value[:1024]
    delimiter = ";" if sample.count(";") > sample.count(",") else ","
    return list(csv.reader(io.StringIO(value), delimiter=delimiter))
