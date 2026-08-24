"""Managed user-scoped installation of the signed VS Code connector."""

import hashlib
import json
import os
import shutil
import zipfile
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4

from fam_os.product.vscode_package import VSIX_NAME, extract_vscode_vsix


MARKER = ".fam-os-connector.json"


@dataclass(frozen=True, slots=True)
class VsCodeConnectorReceipt:
    installed: bool
    extension_id: str
    version: str | None
    path: str
    source_digest: str | None


class VsCodeConnectorInstallation:
    def __init__(self, release_root: Path, extension_root: Path) -> None:
        self._release = release_root
        self._root = extension_root

    def install(self) -> VsCodeConnectorReceipt:
        source, extension_id, version = self._source()
        self._prepare_root()
        target = self._root / f"{extension_id}-{version}"
        if target.exists():
            receipt = self.status()
            if receipt.installed and receipt.version == version:
                return receipt
            raise FileExistsError("VS Code connector target is unmanaged")
        if self._managed_targets():
            raise FileExistsError("VS Code connector is installed; use update")
        self._stage_install(source, target, extension_id, version)
        return self.status()

    def update(self) -> VsCodeConnectorReceipt:
        source, extension_id, version = self._source()
        self._prepare_root()
        target = self._root / f"{extension_id}-{version}"
        previous = self._managed_targets()
        if target.exists() and target not in previous:
            raise FileExistsError("VS Code connector target is unmanaged")
        self._stage_install(source, target, extension_id, version)
        receipt = self._status_target(target)
        if not receipt.installed:
            raise RuntimeError("staged VS Code connector failed validation")
        for old_target in previous:
            if old_target != target:
                shutil.rmtree(old_target)
        return self.status()

    def remove(self) -> VsCodeConnectorReceipt:
        for target in self._managed_targets():
            shutil.rmtree(target)
        return self.status()

    def status(self) -> VsCodeConnectorReceipt:
        targets = self._managed_targets()
        if len(targets) != 1:
            return VsCodeConnectorReceipt(
                False, "fam-os.fam-os-vscode-connector", None,
                str(self._root), None,
            )
        return self._status_target(targets[0])

    def _status_target(self, target: Path) -> VsCodeConnectorReceipt:
        marker = json.loads((target / MARKER).read_text(encoding="utf-8"))
        digest = _tree_digest(target, exclude_marker=True)
        installed = marker.get("source_digest") == digest and _healthy(target)
        return VsCodeConnectorReceipt(
            installed, marker["extension_id"], marker["version"],
            str(target), digest,
        )

    def _stage_install(
        self, source: Path, target: Path, extension_id: str, version: str,
    ) -> None:
        staging = self._root / f".fam-os-{uuid4().hex}"
        backup = self._root / f".fam-os-backup-{uuid4().hex}"
        try:
            staging.mkdir()
            extract_vscode_vsix(source, staging)
            digest = _tree_digest(staging)
            (staging / MARKER).write_text(json.dumps({
                "extension_id": extension_id,
                "version": version,
                "source_digest": digest,
            }, sort_keys=True) + "\n", encoding="utf-8")
            if not self._status_target(staging).installed:
                raise RuntimeError("staged VS Code connector failed validation")
            if target.exists():
                os.replace(target, backup)
            try:
                os.replace(staging, target)
            except BaseException:
                if backup.exists() and not target.exists():
                    os.replace(backup, target)
                raise
            shutil.rmtree(backup, ignore_errors=True)
        finally:
            shutil.rmtree(staging, ignore_errors=True)
            if backup.exists() and not target.exists():
                os.replace(backup, target)

    def _source(self):
        source = self._release / "share/connector" / VSIX_NAME
        if source.is_symlink() or not source.is_file():
            raise ValueError("signed VSIX is missing")
        with zipfile.ZipFile(source) as archive:
            package = json.loads(archive.read("extension/package.json"))
        extension_id = f"{package.get('publisher')}.{package.get('name')}"
        version = package.get("version")
        if extension_id != "fam-os.fam-os-vscode-connector" or not isinstance(version, str):
            raise ValueError("signed VS Code connector identity is invalid")
        return source, extension_id, version

    def _prepare_root(self) -> None:
        self._root.mkdir(parents=True, exist_ok=True, mode=0o700)
        if self._root.is_symlink() or self._root.stat().st_uid != os.geteuid():
            raise PermissionError("VS Code extension root is not owner controlled")

    def _managed_targets(self) -> tuple[Path, ...]:
        if not self._root.is_dir() or self._root.is_symlink():
            return ()
        return tuple(sorted(
            path for path in self._root.glob("fam-os.fam-os-vscode-connector-*")
            if _managed_target(path)
        ))


def _healthy(path: Path) -> bool:
    return all((path / item).is_file() for item in (
        "package.json", "out/extension.js", "schemas/vscode.workspace_edit.input.v1.schema.json",
    ))


def _managed_target(path: Path) -> bool:
    marker_path = path / MARKER
    if path.is_symlink() or not path.is_dir() or marker_path.is_symlink():
        return False
    try:
        marker = json.loads(marker_path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return False
    extension_id = marker.get("extension_id") if isinstance(marker, dict) else None
    version = marker.get("version") if isinstance(marker, dict) else None
    return (
        extension_id == "fam-os.fam-os-vscode-connector"
        and isinstance(version, str)
        and path.name == f"{extension_id}-{version}"
    )


def _tree_digest(root: Path, *, exclude_marker: bool = False) -> str:
    digest = hashlib.sha256()
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.is_symlink():
            continue
        relative = path.relative_to(root)
        if exclude_marker and relative == Path(MARKER):
            continue
        digest.update(str(relative).encode("utf-8") + b"\0")
        digest.update(path.read_bytes())
    return digest.hexdigest()
