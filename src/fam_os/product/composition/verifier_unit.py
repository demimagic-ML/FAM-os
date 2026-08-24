"""Source and signed-release composition of production verifier runtimes."""

from __future__ import annotations

import tarfile
from importlib import resources
from pathlib import Path

from fam_os.adapters.bubblewrap import BubblewrapSandboxRunner, BubblewrapSettings
from fam_os.core.production.declared_verifiers import ProductionDeclaredVerifier
from fam_os.product.release_trust import verify_installed_release
from fam_os.product.update_contracts import ComponentKind
from fam_os.registry import ArtifactDigest, PackageTrustLevel
from fam_os.registry.trust_contracts import PackageValidationReport
from fam_os.schemas import loads_document
from fam_os.verification.activation import (
    DeclaredVerifierCatalog,
    VerifierRuntimePackage,
)
from fam_os.verification.artifact import verifier_tree_digest
from fam_os.verification.manifest import VerifierManifest
from fam_os.verification.runtime_binding import VerifierRuntimeBinding
from fam_os.verification.sandbox import SandboxRunner


_ISOLATION = (
    "isolation.process",
    "isolation.network-denied",
    "isolation.temporary-directory",
    "runtime.explicit-entrypoint",
)


def production_sandbox(apparmor_profile: str | None = None) -> SandboxRunner:
    return BubblewrapSandboxRunner(BubblewrapSettings(
        apparmor_profile=apparmor_profile,
    ))


def production_verifier(
    repositories, sandbox: SandboxRunner | None = None,
    catalog: DeclaredVerifierCatalog | None = None,
) -> ProductionDeclaredVerifier:
    return ProductionDeclaredVerifier(
        repositories, catalog or production_verifier_catalog(),
        sandbox or production_sandbox(),
    )


def production_verifier_catalog() -> DeclaredVerifierCatalog:
    installation_root = Path(__file__).resolve().parents[4]
    verifier_root = Path(__file__).resolve().parents[2] / "verification"
    digest = ArtifactDigest("sha256", verifier_tree_digest(verifier_root))
    manifest_path = installation_root / "release-manifest.json"
    if manifest_path.is_file():
        packages, trust = _signed_packages(installation_root, digest)
    else:
        packages, trust = _source_packages(installation_root, digest)
    return DeclaredVerifierCatalog(packages, trust, _ISOLATION)


def _source_packages(root: Path, digest: ArtifactDigest):
    config = root / "configs/packages"
    manifests = _path_documents(config / "verifiers", VerifierManifest)
    bindings = _path_documents(config / "verifier-bindings", VerifierRuntimeBinding)
    if bool(manifests) != bool(bindings):
        raise RuntimeError("production verifier source configuration is incomplete")
    if not manifests:
        manifests = _resource_documents("verifiers", VerifierManifest)
        bindings = _resource_documents("verifier-bindings", VerifierRuntimeBinding)
    return (
        _packages(
            manifests, bindings, digest, PackageTrustLevel.LOCAL_UNVERIFIED,
            "source-development", None, None,
        ),
        PackageTrustLevel.LOCAL_UNVERIFIED,
    )


def _signed_packages(root: Path, digest: ArtifactDigest):
    release = verify_installed_release(root, root.parents[1] / "trust")
    component = next(item for item in release.components if item.kind is ComponentKind.EXPERT)
    archive = root / component.kind.value / component.name
    with tarfile.open(archive, "r") as source:
        manifests = _archive_documents(source, "verifiers/", VerifierManifest)
        bindings = _archive_documents(
            source, "verifier-bindings/", VerifierRuntimeBinding,
        )
    return (
        _packages(
            manifests, bindings, digest, PackageTrustLevel.SIGNED,
            f"signed-release-{release.release_id}",
            release.release_id, release.signer_key_id,
        ),
        PackageTrustLevel.SIGNED,
    )


def _packages(
    manifests, bindings, digest, effective_trust, policy_id, release_id, signer_key_id,
):
    if len({item.verifier_id for item in bindings}) != len(bindings):
        raise RuntimeError("production verifier bindings contain duplicate verifier IDs")
    binding_map = {item.verifier_id: item for item in bindings}
    manifest_ids = {item.verifier_id for item in manifests}
    orphan_bindings = sorted(set(binding_map) - manifest_ids)
    if orphan_bindings:
        raise RuntimeError(
            "production verifier bindings lack matching manifests: "
            + ", ".join(orphan_bindings)
        )
    values = []
    for manifest in manifests:
        binding = binding_map.get(manifest.verifier_id)
        if binding is None:
            continue
        accepted = manifest.package.artifact_digest == digest
        report = PackageValidationReport(
            manifest.package.package_id, manifest.package.package_version,
            accepted, "accepted" if accepted else "artifact.digest_mismatch",
            effective_trust if accepted else None, digest, policy_id,
            signer_key_id if accepted and effective_trust is PackageTrustLevel.SIGNED else None,
        )
        values.append(VerifierRuntimePackage(
            manifest, binding, report, release_id, signer_key_id,
        ))
    if not values:
        raise RuntimeError("no declared production verifier bindings were found")
    return tuple(values)


def _path_documents(root: Path, expected_type):
    if root.is_symlink() or not root.is_dir():
        return ()
    values = []
    for path in sorted(root.glob("*.json")):
        if path.is_symlink() or not path.is_file():
            raise ValueError("verifier configuration path is unsafe")
        value = loads_document(path.read_text(encoding="utf-8"))
        if isinstance(value, expected_type):
            values.append(value)
    return tuple(values)


def _resource_documents(directory: str, expected_type):
    root = resources.files("fam_os.product.resources").joinpath(directory)
    values = []
    for item in sorted(root.iterdir(), key=lambda candidate: candidate.name):
        if not item.name.endswith(".json") or not item.is_file():
            continue
        value = loads_document(item.read_text(encoding="utf-8"))
        if isinstance(value, expected_type):
            values.append(value)
    return tuple(values)


def _archive_documents(source: tarfile.TarFile, prefix: str, expected_type):
    values = []
    for member in source.getmembers():
        if not member.name.startswith(prefix) or not member.name.endswith(".json"):
            continue
        if not member.isfile() or member.issym() or member.islnk():
            raise ValueError("signed verifier configuration member is unsafe")
        stream = source.extractfile(member)
        if stream is None:
            raise ValueError("signed verifier configuration member is unreadable")
        value = loads_document(stream.read().decode("utf-8"))
        if isinstance(value, expected_type):
            values.append(value)
    return tuple(values)
