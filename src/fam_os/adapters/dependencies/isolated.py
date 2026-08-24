"""Stage allowlisted artifacts and install them only inside a candidate."""

import hashlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Protocol
from uuid import uuid4

from fam_os.core.engineering.dependencies import (
    DependencyResolutionReceipt,
    DependencyResolutionRequest,
    DependencyResolutionStatus,
    DependencyVulnerabilityFinding,
    SbomComponent,
)
from fam_os.core.engineering.transactions import CandidateWorkspace


class AllowlistedArtifactFetcher(Protocol):
    def fetch(self, registry_url: str, hosts: tuple[str, ...], packages: tuple[str, ...], limit: int) -> tuple[tuple[str, bytes], ...]: ...


class CandidatePackageInstaller(Protocol):
    def install(self, root: Path, environment: Path, artifacts: Path, ecosystem: str, wall_seconds: int) -> None: ...


class DependencyMetadataInspector(Protocol):
    def inspect(self, root: Path, environment: Path, ecosystem: str) -> tuple[tuple[SbomComponent, ...], tuple[DependencyVulnerabilityFinding, ...], tuple[str, ...]]: ...


class IsolatedDependencyResolverAdapter:
    def __init__(self, fetcher, installer, inspector, clock=None) -> None:
        self._fetcher = fetcher
        self._installer = installer
        self._inspector = inspector
        self._clock = clock or (lambda: datetime.now(timezone.utc))

    def resolve(self, request: DependencyResolutionRequest, candidate: CandidateWorkspace) -> DependencyResolutionReceipt:
        started = self._clock()
        root = Path(candidate.candidate_workspace).resolve(strict=True)
        environment = _inside(root, request.environment_path)
        evidence = root / ".fam" / "dependencies" / request.request_id
        evidence.mkdir(parents=True, mode=0o700)
        before_manifest = _digests(root, request.manifest_paths)
        before_lock = _digests(root, request.lockfile_paths)
        artifact_digests = []
        downloaded = 0
        for registry in request.registry_urls:
            remaining = request.budget.maximum_download_bytes - downloaded
            for name, content in self._fetcher.fetch(
                registry, request.network_hosts, request.requested_packages, remaining,
            ):
                if Path(name).name != name or len(content) > remaining:
                    raise PermissionError("dependency artifact exceeds its approved envelope")
                target = evidence / name
                target.write_bytes(content)
                target.chmod(0o400)
                downloaded += len(content)
                remaining -= len(content)
                artifact_digests.append(hashlib.sha256(content).hexdigest())
        self._installer.install(root, environment, evidence, request.ecosystem, request.budget.maximum_wall_seconds)
        components, findings, license_ids = self._inspector.inspect(root, environment, request.ecosystem)
        installed = _tree_size(environment)
        if installed > request.budget.maximum_installed_bytes:
            raise PermissionError("dependency installation exceeded its size budget")
        return DependencyResolutionReceipt(
            f"dependency-receipt-{uuid4().hex}", request.request_id,
            request.task_id, request.candidate_id, started, self._clock(),
            DependencyResolutionStatus.ACCEPTED,
            before_manifest, _digests(root, request.manifest_paths),
            before_lock, _digests(root, request.lockfile_paths),
            components, findings, license_ids, request.network_hosts,
            downloaded, installed, request.environment_path,
            tuple(artifact_digests), (), True,
        )


def _inside(root: Path, relative: str) -> Path:
    value = root / relative
    if value.is_symlink() or root not in value.resolve(strict=False).parents:
        raise PermissionError("dependency path escapes candidate workspace")
    return value


def _digests(root: Path, paths: tuple[str, ...]) -> tuple[str, ...]:
    values = []
    for relative in paths:
        path = _inside(root, relative)
        values.append(hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else hashlib.sha256(b"").hexdigest())
    return tuple(values)


def _tree_size(root: Path) -> int:
    if not root.exists():
        return 0
    return sum(path.stat().st_size for path in root.rglob("*") if path.is_file() and not path.is_symlink())
