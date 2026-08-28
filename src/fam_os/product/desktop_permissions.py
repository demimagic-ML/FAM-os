"""Owner-managed global switches for privacy-sensitive desktop capabilities."""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from fam_os.product.composition.fallback_policy import parse_fallback_policy


_EMPTY_POLICY = {
    "contract_version": "fam.product.fallbacks/v1alpha1",
    "accessibility": {
        "enabled": False,
        "privacy_acknowledged": False,
        "include_text": False,
        "actions_enabled": False,
        "allowed_actions": ["click", "press", "activate"],
        "targets": [],
    },
    "screen_input": {
        "enabled": False,
        "privacy_acknowledged": False,
        "actions_enabled": False,
        "allowed_kinds": ["pointer_click", "key_chord"],
        "allowed_keys": ["Control_L", "Shift_L", "Alt_L", "Escape", "Return"],
        "targets": [],
    },
}


class DesktopPermissionStore:
    """Read and atomically change capture/input switches without widening targets."""

    def __init__(self, path: Path, owner_uid: int | None = None) -> None:
        self._path = path.absolute()
        self._owner_uid = os.geteuid() if owner_uid is None else owner_uid

    def status(self) -> dict[str, object]:
        document = self._read()
        screen = document["screen_input"]
        return {
            "configuration": str(self._path),
            "screen_capture": bool(screen["enabled"]),
            "input_control": bool(screen["actions_enabled"]),
            "target_count": len(screen["targets"]),
            "target_scoped": True,
        }

    def update(
        self, *, screen_capture: bool | None = None,
        input_control: bool | None = None,
    ) -> dict[str, object]:
        document = self._read()
        screen = document["screen_input"]
        capture = bool(screen["enabled"]) if screen_capture is None else screen_capture
        control = (
            bool(screen["actions_enabled"])
            if input_control is None else input_control
        )
        if screen_capture is False and input_control is None:
            control = False
        if control and not capture:
            raise ValueError("input control requires screen capture to be enabled")
        if capture and not screen["targets"]:
            raise ValueError(
                "screen capture requires at least one owner-approved exact target in "
                + str(self._path)
            )
        screen["enabled"] = capture
        screen["actions_enabled"] = control if capture else False
        screen["privacy_acknowledged"] = capture
        parse_fallback_policy(document)
        self._write(document)
        return self.status()

    def _read(self) -> dict:
        if not self._path.exists():
            return json.loads(json.dumps(_EMPTY_POLICY))
        details = self._path.lstat()
        if self._path.is_symlink() or not self._path.is_file():
            raise PermissionError("desktop permission configuration must be a regular file")
        if details.st_uid != self._owner_uid or details.st_mode & 0o077:
            raise PermissionError(
                "desktop permission configuration must be owner-controlled mode 0600"
            )
        document = json.loads(self._path.read_text(encoding="utf-8"))
        parse_fallback_policy(document)
        return document

    def _write(self, document: dict) -> None:
        parent = self._path.parent
        parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        if parent.is_symlink() or parent.stat().st_uid != self._owner_uid:
            raise PermissionError("desktop permission directory must be owner-controlled")
        os.chmod(parent, 0o700)
        descriptor, temporary = tempfile.mkstemp(prefix=".fallbacks-", dir=parent)
        temporary_path = Path(temporary)
        try:
            os.fchmod(descriptor, 0o600)
            with os.fdopen(descriptor, "w", encoding="utf-8") as handle:
                json.dump(document, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_path, self._path)
            os.chmod(self._path, 0o600)
        finally:
            if temporary_path.exists():
                temporary_path.unlink()
