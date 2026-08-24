"""Confirmed complete removal of one user-owned FAM_OS installation."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from fam_os.product.bundle_installation import SignedBundleInstallation
from fam_os.product.owned_root import OwnedProductRoot
from fam_os.product.vscode_installation import VsCodeConnectorInstallation


Systemctl = Callable[..., object]


@dataclass(frozen=True, slots=True)
class CompleteRemovalReceipt:
    prefix: str
    state_root: str
    runtime_root: str
    extension_root: str
    installation_removed: bool
    state_removed: bool
    runtime_removed: bool
    connector_removed: bool
    stopped_units: tuple[str, ...]


class CompleteProductRemoval:
    def __init__(
        self,
        installation: SignedBundleInstallation,
        connector: VsCodeConnectorInstallation,
        state_root: Path,
        runtime_root: Path,
        user_unit_root: Path,
        systemctl: Systemctl,
    ) -> None:
        self._installation = installation
        self._connector = connector
        self._state = OwnedProductRoot(state_root, "state", os.geteuid())
        self._runtime = OwnedProductRoot(runtime_root, "runtime", os.geteuid())
        self._units = user_unit_root
        self._systemctl = systemctl

    def remove(self, *, confirmed: bool) -> CompleteRemovalReceipt:
        if not confirmed:
            raise PermissionError("complete FAM_OS removal requires --confirm")
        self._validate_paths()
        # Validate all deletion authorities before stopping a service or
        # removing any bytes. An unhealthy release may still be removed, but
        # its signed-installation marker must be present and readable.
        self._installation.diagnose()
        state_exists = self._validate_if_present(self._state)
        runtime_exists = self._validate_if_present(self._runtime)
        self._connector.status()

        stopped = ("fam-os.service", "fam-ollama.service")
        for unit in stopped:
            self._systemctl("disable", "--now", unit, check=False)
        self._installation.remove_user_unit(self._units)
        self._systemctl("daemon-reload", check=False)
        for unit in stopped:
            self._systemctl("reset-failed", unit, check=False)

        connector_after = self._connector.remove()
        runtime_removed = self._runtime.remove() if runtime_exists else False
        state_removed = self._state.remove() if state_exists else False
        self._installation.remove()
        return CompleteRemovalReceipt(
            prefix=str(self._installation.prefix),
            state_root=str(self._state.path),
            runtime_root=str(self._runtime.path),
            extension_root=connector_after.path,
            installation_removed=True,
            state_removed=state_removed,
            runtime_removed=runtime_removed,
            connector_removed=not connector_after.installed,
            stopped_units=stopped,
        )

    def _validate_paths(self) -> None:
        roots = (
            self._installation.prefix.resolve(),
            self._state.path.resolve(),
            self._runtime.path.resolve(),
        )
        for index, left in enumerate(roots):
            for right in roots[index + 1:]:
                if left == right or left.is_relative_to(right) or right.is_relative_to(left):
                    raise ValueError("FAM_OS removal roots must not overlap")

    @staticmethod
    def _validate_if_present(root: OwnedProductRoot) -> bool:
        if not root.path.exists() and not root.path.is_symlink():
            return False
        root.verify()
        return True
