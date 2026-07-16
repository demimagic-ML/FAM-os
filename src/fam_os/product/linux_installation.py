"""Owner-private, diagnosable, repairable Linux product installation."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from uuid import uuid4


INSTALL_CONTRACT_VERSION = "fam.product.installation/v1alpha1"
MARKER = ".fam-os-installation.json"


@dataclass(frozen=True, slots=True)
class InstallationReceipt:
    prefix: str
    release_id: str
    files: tuple[tuple[str, str], ...]
    healthy: bool
    issues: tuple[str, ...]
    contract_version: str = INSTALL_CONTRACT_VERSION


class LinuxInstallation:
    def __init__(self, prefix: Path) -> None:
        self.prefix = prefix

    def install(self, source_package: Path, release_id: str) -> InstallationReceipt:
        if self.prefix.exists() and not (self.prefix / MARKER).is_file():
            raise FileExistsError("refusing to replace an unmarked directory")
        self.prefix.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.prefix, 0o700)
        release = self._stage_release(source_package, release_id)
        self._switch_current(release)
        self._write_managed_files(release_id)
        return self.diagnose()

    def update(self, source_package: Path, release_id: str) -> InstallationReceipt:
        self._require_marker()
        return self.install(source_package, release_id)

    def diagnose(self) -> InstallationReceipt:
        release_id, files = self._read_marker()
        issues = []
        if self.prefix.stat().st_uid != os.geteuid() or self.prefix.stat().st_mode & 0o077:
            issues.append("installation_root_not_private")
        current = self.prefix / "current"
        if not current.is_symlink() or not current.resolve().is_relative_to(self.prefix.resolve()):
            issues.append("current_release_pointer_invalid")
        for relative, expected in files:
            path = self.prefix / relative
            if not path.is_file() or _digest(path) != expected:
                issues.append(f"file_mismatch:{relative}")
        return InstallationReceipt(
            str(self.prefix), release_id, files, not issues, tuple(issues),
        )

    def repair(self, source_package: Path) -> InstallationReceipt:
        release_id, _files = self._read_marker()
        return self.install(source_package, release_id + "-repair")

    def remove(self) -> None:
        self._require_marker()
        resolved = self.prefix.resolve()
        if resolved == Path("/") or len(resolved.parts) < 3:
            raise ValueError("refusing unsafe installation removal path")
        _make_writable(self.prefix)
        shutil.rmtree(self.prefix)

    def _stage_release(self, source: Path, release_id: str) -> Path:
        if not source.is_dir() or source.is_symlink() or not release_id:
            raise ValueError("package source and release ID are required")
        releases = self.prefix / "releases"
        releases.mkdir(mode=0o700, exist_ok=True)
        target = releases / release_id
        if target.exists():
            raise FileExistsError("release ID already exists")
        staging = releases / f".{release_id}-{uuid4().hex}"
        try:
            staging.mkdir(mode=0o700)
            shutil.copytree(source, staging / "fam_os", symlinks=False)
            _make_read_only(staging)
            os.replace(staging, target)
        finally:
            shutil.rmtree(staging, ignore_errors=True)
        return target

    def _switch_current(self, release: Path) -> None:
        temporary = self.prefix / f".current-{uuid4().hex}"
        temporary.symlink_to(release.relative_to(self.prefix))
        os.replace(temporary, self.prefix / "current")

    def _write_managed_files(self, release_id: str) -> None:
        bin_dir = self.prefix / "bin"
        unit_dir = self.prefix / "systemd"
        bin_dir.mkdir(mode=0o700, exist_ok=True)
        unit_dir.mkdir(mode=0o700, exist_ok=True)
        launcher = bin_dir / "fam-shell"
        launcher.write_text(_launcher(self.prefix, "fam_os.adapters.shell.cli"))
        os.chmod(launcher, 0o700)
        service_launcher = bin_dir / "fam-service"
        service_launcher.write_text(_launcher(self.prefix, "fam_os.product.service"))
        os.chmod(service_launcher, 0o700)
        service = unit_dir / "fam-os.service"
        service.write_text(_service(self.prefix))
        files = tuple((str(path.relative_to(self.prefix)), _digest(path))
                      for path in (launcher, service_launcher, service))
        marker = {"contract_version": INSTALL_CONTRACT_VERSION,
                  "release_id": release_id, "files": files}
        _atomic_json(self.prefix / MARKER, marker)

    def _read_marker(self) -> tuple[str, tuple[tuple[str, str], ...]]:
        self._require_marker()
        value = json.loads((self.prefix / MARKER).read_text())
        if value.get("contract_version") != INSTALL_CONTRACT_VERSION:
            raise ValueError("unsupported installation marker")
        release_id = value.get("release_id")
        files = value.get("files")
        if not isinstance(release_id, str) or not isinstance(files, list):
            raise ValueError("invalid installation marker content")
        parsed = tuple(_parse_file_entry(item) for item in files)
        return release_id, parsed

    def _require_marker(self) -> None:
        marker = self.prefix / MARKER
        if marker.is_symlink() or not marker.is_file():
            raise FileNotFoundError("FAM_OS installation marker is missing")


def _launcher(prefix: Path, module: str) -> str:
    return ("#!/bin/sh\nset -eu\n"
            f"PYTHONPATH='{prefix}/current' exec '{sys.executable}' -m {module} \"$@\"\n")


def _service(prefix: Path) -> str:
    return ("[Unit]\nDescription=FAM_OS local intelligence service\n"
            "[Service]\nType=simple\nNoNewPrivileges=true\nPrivateTmp=true\n"
            f"Environment=PYTHONPATH={prefix}/current\n"
            f"ExecStart={prefix}/bin/fam-service\nRestart=on-failure\n"
            "RestartSec=2\n[Install]\nWantedBy=default.target\n")


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _make_read_only(root: Path) -> None:
    for path in root.rglob("*"):
        os.chmod(path, 0o500 if path.is_dir() else 0o400)
    os.chmod(root, 0o500)


def _make_writable(root: Path) -> None:
    for path in root.rglob("*"):
        if path.is_dir() and not path.is_symlink():
            os.chmod(path, 0o700)
    os.chmod(root, 0o700)


def _parse_file_entry(value: object) -> tuple[str, str]:
    if (not isinstance(value, list) or len(value) != 2
            or not all(isinstance(item, str) for item in value)):
        raise ValueError("invalid managed file entry")
    return value[0], value[1]


def _atomic_json(path: Path, value: object) -> None:
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")
    os.chmod(temporary, 0o600)
    os.replace(temporary, path)
