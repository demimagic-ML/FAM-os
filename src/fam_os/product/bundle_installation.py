"""Install, update, roll back, diagnose, and remove signed release bundles."""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import sys
import tarfile
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

from fam_os.product.atomic_update import AtomicReleaseManager
from fam_os.product.installation_marker import (
    MARKER_NAME,
    SignedInstallationMarker,
    load_installation_marker,
    managed_file_issues,
    write_installation_marker,
)
from fam_os.product.linux_installation import InstallationReceipt
from fam_os.product.installed_launcher import (
    installed_launcher, stable_runtime_python,
)
from fam_os.product.release_bundle import load_release_bundle
from fam_os.product.update_contracts import SignedReleaseManifest
from fam_os.product.update_signing import verify_manifest
from fam_os.schemas import loads_document


class SignedBundleInstallation:
    def __init__(self, prefix: Path, trusted_keys: dict[str, Ed25519PublicKey]) -> None:
        self.prefix = prefix
        self._trusted_keys = {**_persisted_keys(prefix), **trusted_keys}
        self._manager = AtomicReleaseManager(prefix, self._trusted_keys)

    def install(self, bundle: Path) -> InstallationReceipt:
        self._prepare_root(new=True)
        self._write_trusted_keys()
        manifest = load_release_bundle(bundle)
        receipt = self._manager.apply(
            manifest, self._prepare_release, source_root=bundle,
        )
        if not receipt.activated:
            return self._receipt((receipt.reason,))
        self._write_stable_files(manifest.release_id)
        return self.diagnose()

    def update(self, bundle: Path) -> InstallationReceipt:
        self._require_marker()
        return self.install(bundle)

    def rollback(self, release_id: str) -> InstallationReceipt:
        self._require_marker()
        self._manager.rollback(release_id, self._release_healthy)
        self._write_stable_files(release_id)
        return self.diagnose()

    def repair(self) -> InstallationReceipt:
        self._require_marker()
        active = self._manager.active_release_id()
        if active is None or not self._release_healthy(self.prefix / "releases" / active):
            return self._receipt(("active_release_requires_signed_update_or_rollback",))
        self._write_stable_files(active)
        return self.diagnose()

    def diagnose(self) -> InstallationReceipt:
        try:
            marker = load_installation_marker(self.prefix)
        except (OSError, ValueError, json.JSONDecodeError):
            return self._receipt(("installation_marker_invalid",), None)
        issues = list(managed_file_issues(self.prefix, marker))
        if self.prefix.stat().st_uid != os.geteuid() or self.prefix.stat().st_mode & 0o077:
            issues.append("installation_root_not_private")
        active = self.prefix / "active"
        if not active.is_symlink() or not self._release_healthy(active.resolve()):
            issues.append("active_release_unhealthy")
        if marker.release_id != self._manager.active_release_id():
            issues.append("installation_marker_release_mismatch")
        return self._receipt(tuple(issues), marker)

    def remove(self) -> None:
        self._require_marker()
        resolved = self.prefix.resolve()
        if resolved == Path("/") or len(resolved.parts) < 3:
            raise ValueError("refusing unsafe signed installation removal path")
        _make_writable(self.prefix)
        shutil.rmtree(self.prefix)

    def install_user_unit(self, user_unit_root: Path) -> Path:
        self._require_marker()
        user_unit_root.mkdir(parents=True, exist_ok=True, mode=0o700)
        target = user_unit_root / "fam-os.service"
        if target.exists() or target.is_symlink():
            if not target.is_symlink() or target.resolve() != (
                self.prefix / "systemd/fam-os.service"
            ).resolve():
                raise FileExistsError("refusing to replace an unmanaged user unit")
            return target
        target.symlink_to(self.prefix / "systemd/fam-os.service")
        return target

    def remove_user_unit(self, user_unit_root: Path) -> None:
        target = user_unit_root / "fam-os.service"
        if target.is_symlink() and target.resolve().is_relative_to(self.prefix.resolve()):
            target.unlink()

    def _prepare_root(self, *, new: bool) -> None:
        if new and self.prefix.exists() and any(self.prefix.iterdir()):
            if not (self.prefix / MARKER_NAME).is_file():
                raise FileExistsError("refusing to replace an unmarked installation")
        self.prefix.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.prefix, 0o700)

    def _prepare_release(self, staging: Path) -> bool:
        try:
            wheelhouse = staging / "wheelhouse"
            _extract(staging / "service/wheelhouse.tar", wheelhouse)
            python_root = staging / "python"
            subprocess.run(
                (
                    sys.executable, "-m", "pip", "install", "--no-index",
                    "--find-links", str(wheelhouse), "--target", str(python_root),
                    "fam-os",
                ),
                check=True,
                capture_output=True,
                text=True,
                timeout=180,
            )
            for kind in ("schema", "expert", "connector", "console", "service_unit", "migration"):
                archive = next((staging / kind).glob("*.tar"))
                _extract(archive, staging / "share" / kind)
            return self._release_healthy(staging)
        except (OSError, ValueError, subprocess.SubprocessError, StopIteration, tarfile.TarError):
            return False

    def _release_healthy(self, release: Path) -> bool:
        python_root = release / "python"
        environment = {**os.environ, "PYTHONPATH": str(python_root)}
        try:
            result = subprocess.run(
                (sys.executable, "-c", "import fam_os; import fam_os.product.service"),
                env=environment,
                check=False,
                capture_output=True,
                timeout=30,
            )
        except OSError:
            return False
        required = (
            release / "release-manifest.json",
            release / "share/schema",
            release / "share/console/index.html",
            release / "share/service_unit/fam-os.service",
            release / "share/service_unit/fam-os-userns",
            release / "share/migration/0001_initial.sql",
            release / "share/connector/fam-os-vscode-connector.vsix",
        )
        return (
            result.returncode == 0
            and all(path.exists() for path in required)
            and self._release_signature_healthy(release)
        )

    def _release_signature_healthy(self, release: Path) -> bool:
        try:
            value = loads_document(
                (release / "release-manifest.json").read_text(encoding="utf-8")
            )
            if not isinstance(value, SignedReleaseManifest):
                return False
            key = self._trusted_keys.get(value.signer_key_id)
            if key is None:
                return False
            verify_manifest(value, key)
            for component in value.components:
                if _sha256(release / component.kind.value / component.name) != component.sha256:
                    return False
            return True
        except (OSError, ValueError):
            return False

    def _write_trusted_keys(self) -> None:
        root = self.prefix / "trust"
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        for key_id, key in self._trusted_keys.items():
            if not key_id.replace("-", "").replace("_", "").isalnum():
                raise ValueError("release trust key ID is unsafe")
            path = root / f"{key_id}.pem"
            content = key.public_bytes(
                serialization.Encoding.PEM,
                serialization.PublicFormat.SubjectPublicKeyInfo,
            )
            if path.exists():
                if path.read_bytes() != content:
                    raise FileExistsError("persisted release trust key conflicts")
                continue
            path.write_bytes(content)
            os.chmod(path, 0o400)

    def _write_stable_files(self, release_id: str) -> None:
        bin_root, unit_root = self.prefix / "bin", self.prefix / "systemd"
        bin_root.mkdir(mode=0o700, exist_ok=True)
        unit_root.mkdir(mode=0o700, exist_ok=True)
        runtime_python = stable_runtime_python()
        managed_files: list[Path] = []
        for name, module in (
            ("fam-os", "fam_os.product.cli"),
            ("fam-shell", "fam_os.adapters.shell.cli"),
            ("fam-service", "fam_os.product.service"),
            ("fam-network-broker", "fam_os.product.network_broker_service_cli"),
            ("fam-network-authority", "fam_os.product.network_authority_cli"),
        ):
            path = bin_root / name
            path.write_text(
                installed_launcher(self.prefix, module, runtime_python),
                encoding="utf-8",
            )
            os.chmod(path, 0o700)
            managed_files.append(path)
        for source in (self.prefix / "active/share/service_unit").glob("*.service"):
            target = unit_root / source.name
            content = source.read_text(encoding="utf-8")
            content = content.replace("@FAM_PREFIX@", str(self.prefix))
            content = content.replace("@PYTHON@", runtime_python)
            target.write_text(content, encoding="utf-8")
            os.chmod(target, 0o600)
            managed_files.append(target)
        managed_files.extend(sorted((self.prefix / "trust").glob("*.pem")))
        write_installation_marker(self.prefix, release_id, tuple(managed_files))

    def _receipt(
        self, issues: tuple[str, ...], marker: SignedInstallationMarker | None = None,
    ) -> InstallationReceipt:
        release_id = self._manager.active_release_id() or "none"
        expected = () if marker is None else marker.managed_files
        files = tuple(
            (item.relative_path, _sha256(self.prefix / item.relative_path))
            for item in expected
            if (self.prefix / item.relative_path).is_file()
            and not (self.prefix / item.relative_path).is_symlink()
        )
        return InstallationReceipt(
            str(self.prefix), release_id, files, not issues, issues,
        )

    def _require_marker(self) -> None:
        try:
            load_installation_marker(self.prefix)
        except (OSError, ValueError, json.JSONDecodeError) as error:
            raise FileNotFoundError("signed installation marker is missing or invalid") from error


def _extract(archive: Path, target: Path) -> None:
    target.mkdir(parents=True, exist_ok=False, mode=0o700)
    with tarfile.open(archive, "r") as source:
        for member in source.getmembers():
            path = Path(member.name)
            if path.is_absolute() or ".." in path.parts or not member.isfile():
                raise ValueError("release archive contains an unsafe member")
        source.extractall(target, filter="data")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _make_writable(root: Path) -> None:
    for path in root.rglob("*"):
        if path.is_dir() and not path.is_symlink():
            os.chmod(path, 0o700)
        elif path.is_file() and not path.is_symlink():
            os.chmod(path, 0o600)


def _persisted_keys(prefix: Path) -> dict[str, Ed25519PublicKey]:
    values = {}
    for path in (prefix / "trust").glob("*.pem"):
        try:
            key = serialization.load_pem_public_key(path.read_bytes())
        except (OSError, ValueError):
            continue
        if isinstance(key, Ed25519PublicKey):
            values[path.stem] = key
    return values
