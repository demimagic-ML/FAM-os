"""Validated expected-file ledger for one signed product installation."""

from __future__ import annotations

import hashlib
import json
import os
from dataclasses import dataclass
from pathlib import Path

from fam_os.product.linux_installation import INSTALL_CONTRACT_VERSION


MARKER_NAME = ".fam-os-signed-installation.json"
MARKER_CONTRACT_VERSION = "fam.product.signed-installation-marker/v1alpha2"


@dataclass(frozen=True, slots=True)
class ExpectedManagedFile:
    relative_path: str
    sha256: str | None

    def __post_init__(self) -> None:
        _validate_relative_path(self.relative_path)
        if self.sha256 is not None and (
            len(self.sha256) != 64
            or any(character not in "0123456789abcdef" for character in self.sha256)
        ):
            raise ValueError("managed-file digest is invalid")


@dataclass(frozen=True, slots=True)
class SignedInstallationMarker:
    release_id: str
    managed_files: tuple[ExpectedManagedFile, ...]
    legacy_unhashed: bool = False

    def __post_init__(self) -> None:
        if not self.release_id.strip():
            raise ValueError("installation marker release identity is missing")
        paths = tuple(item.relative_path for item in self.managed_files)
        if not paths or len(set(paths)) != len(paths):
            raise ValueError("installation marker managed files are invalid")


def load_installation_marker(prefix: Path) -> SignedInstallationMarker:
    path = prefix / MARKER_NAME
    details = path.stat(follow_symlinks=False)
    if path.is_symlink() or not path.is_file():
        raise ValueError("signed installation marker is unsafe")
    if details.st_uid != os.geteuid() or details.st_mode & 0o077:
        raise ValueError("signed installation marker owner or mode is unsafe")
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict) or set(value) != {
        "contract_version", "release_id", "managed_files",
    }:
        raise ValueError("signed installation marker shape is invalid")
    release_id = value["release_id"]
    managed = value["managed_files"]
    if not isinstance(release_id, str) or not isinstance(managed, list):
        raise ValueError("signed installation marker fields are invalid")
    version = value["contract_version"]
    if version == INSTALL_CONTRACT_VERSION:
        files = tuple(_legacy_file(item) for item in managed)
        return SignedInstallationMarker(release_id, files, legacy_unhashed=True)
    if version != MARKER_CONTRACT_VERSION:
        raise ValueError("signed installation marker version is unsupported")
    files = tuple(_current_file(item) for item in managed)
    return SignedInstallationMarker(release_id, files)


def write_installation_marker(
    prefix: Path, release_id: str, managed_files: tuple[Path, ...],
) -> SignedInstallationMarker:
    files = tuple(
        ExpectedManagedFile(str(path.relative_to(prefix)), _sha256(path))
        for path in sorted(managed_files)
    )
    marker = SignedInstallationMarker(release_id, files)
    value = {
        "contract_version": MARKER_CONTRACT_VERSION,
        "release_id": marker.release_id,
        "managed_files": [
            {"relative_path": item.relative_path, "sha256": item.sha256}
            for item in marker.managed_files
        ],
    }
    path = prefix / MARKER_NAME
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)
    return marker


def managed_file_issues(
    prefix: Path, marker: SignedInstallationMarker,
) -> tuple[str, ...]:
    issues: list[str] = []
    if marker.legacy_unhashed:
        issues.append("installation_marker_upgrade_required")
    for expected in marker.managed_files:
        path = prefix / expected.relative_path
        if path.is_symlink() or not path.is_file():
            issues.append(f"managed_file_missing:{expected.relative_path}")
        elif expected.sha256 is not None and _sha256(path) != expected.sha256:
            issues.append(f"managed_file_digest_mismatch:{expected.relative_path}")
    return tuple(issues)


def _legacy_file(value: object) -> ExpectedManagedFile:
    if not isinstance(value, str):
        raise ValueError("legacy installation marker file is invalid")
    return ExpectedManagedFile(value, None)


def _current_file(value: object) -> ExpectedManagedFile:
    if not isinstance(value, dict) or set(value) != {"relative_path", "sha256"}:
        raise ValueError("installation marker managed-file shape is invalid")
    relative_path, digest = value["relative_path"], value["sha256"]
    if not isinstance(relative_path, str) or not isinstance(digest, str):
        raise ValueError("installation marker managed-file fields are invalid")
    return ExpectedManagedFile(relative_path, digest)


def _validate_relative_path(value: str) -> None:
    path = Path(value)
    if path.is_absolute() or len(path.parts) != 2 or ".." in path.parts:
        raise ValueError("managed-file path is unsafe")
    root, name = path.parts
    valid = (
        (root == "bin" and name in {
            "fam-network-authority", "fam-network-broker", "fam-os",
            "fam-service", "fam-shell",
        })
        or (root == "systemd" and name == Path(name).name and name.endswith(".service"))
        or (
            root == "trust" and name == Path(name).name and name.endswith(".pem")
            and name[:-4].replace("-", "").replace("_", "").isalnum()
        )
    )
    if not valid:
        raise ValueError("managed-file path is outside the installation contract")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()
