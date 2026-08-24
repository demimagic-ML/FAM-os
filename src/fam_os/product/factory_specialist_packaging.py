"""Deterministic signed packaging and disabled Expert Fabric installation."""

from __future__ import annotations

import base64
import hashlib
import io
import os
import re
import tarfile
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Callable

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fam_os.expert_factory import (
    FactorySpecialistPackageReceipt,
    FactorySpecialistReleaseLineage,
    build_specialist_package_receipt,
)
from fam_os.experts import (
    ExpertCompatibilityEvaluator,
    ExpertManifest,
    ExpertResourceRequirements,
    ExpertRuntimeBinding,
    ExpertTier,
)
from fam_os.experts.registry_contracts import ExpertPackageCoordinate
from fam_os.registry import (
    ArtifactDigest,
    PackageMetadata,
    PackageSignature,
    PackageTrustLevel,
    SignatureAlgorithm,
)
from fam_os.registry.lifecycle import ExpertPackageLifecycle
from fam_os.registry.signing_payload import expert_package_signing_payload
from fam_os.registry.validation import ExpertPackageValidator, PackageValidationRequest
from fam_os.scheduler.resources import EffectiveResourceBudget, HostInventory
from fam_os.schemas import dumps_document


_SAFE_NAME = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{0,127}$")


@dataclass(frozen=True, slots=True)
class PackagedSpecialist:
    lineage: FactorySpecialistReleaseLineage
    manifest: ExpertManifest
    runtime_binding: ExpertRuntimeBinding
    signature: PackageSignature
    receipt: FactorySpecialistPackageReceipt
    bundle_path: Path


class FactorySpecialistPackager:
    def __init__(
        self, *, output_directory: Path, lifecycle: ExpertPackageLifecycle,
        validator: ExpertPackageValidator,
        compatibility_evaluator: ExpertCompatibilityEvaluator,
        inventory: HostInventory, budget: EffectiveResourceBudget,
        publisher_id: str, signer_key_id: str,
        signing_key: Ed25519PrivateKey,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self._output = output_directory
        self._lifecycle = lifecycle
        self._validator = validator
        self._compatibility = compatibility_evaluator
        self._inventory = inventory
        self._budget = budget
        self._publisher_id = publisher_id
        self._signer_key_id = signer_key_id
        self._signing_key = signing_key
        self._now = now or (lambda: datetime.now(UTC))

    def package(
        self, lineage: FactorySpecialistReleaseLineage,
        conversion_output: Path,
    ) -> PackagedSpecialist:
        _validate_conversion_output(lineage, conversion_output)
        name = _package_name(lineage.package_id, lineage.package_version)
        self._output.mkdir(parents=True, mode=0o700, exist_ok=True)
        os.chmod(self._output, 0o700)
        bundle = self._output / f"{name}.tar"
        _build_bundle(bundle, lineage, conversion_output)
        if bundle.stat().st_size > lineage.storage_bytes:
            bundle.unlink(missing_ok=True)
            raise RuntimeError("specialist bundle exceeds declared storage")
        artifact_digest = ArtifactDigest("sha256", _file_sha256(bundle))
        manifest = ExpertManifest(
            package=PackageMetadata(
                package_id=lineage.package_id,
                package_version=lineage.package_version,
                publisher_id=self._publisher_id,
                license_id=lineage.license_id,
                trust_level=PackageTrustLevel.SIGNED,
                artifact_digest=artifact_digest,
                signature_key_id=self._signer_key_id,
            ),
            expert_id=lineage.expert_id,
            display_name=f"FAM specialist {lineage.training_capability_id}",
            tier=ExpertTier.SPECIALIST,
            capabilities=lineage.declared_capabilities,
            runtime_contract_id="fam.inference.chat/v1",
            artifact_ids=("ollama.bundle",),
            resources=ExpertResourceRequirements(
                estimated_resident_bytes=lineage.estimated_resident_bytes,
                storage_bytes=lineage.storage_bytes,
                max_context_tokens=lineage.max_context_tokens,
                minimum_system_memory_bytes=(
                    lineage.minimum_system_memory_bytes
                ),
                minimum_accelerator_memory_bytes=(
                    lineage.minimum_accelerator_memory_bytes
                ),
                accelerator_optional=lineage.accelerator_optional,
                supported_architectures=lineage.supported_architectures,
            ),
            required_verifier_ids=lineage.required_verifier_ids,
        )
        signature_bytes = self._signing_key.sign(
            expert_package_signing_payload(manifest),
        )
        signature = PackageSignature(
            self._signer_key_id, SignatureAlgorithm.ED25519,
            base64.b64encode(signature_bytes).decode("ascii"),
        )
        validation = self._validator.validate(PackageValidationRequest(
            manifest, artifact_digest, signature,
        ))
        if not validation.accepted:
            bundle.unlink(missing_ok=True)
            raise PermissionError(
                f"specialist package validation failed: {validation.reason_code}",
            )
        compatibility = self._compatibility.evaluate(
            manifest, self._inventory, self._budget,
        )
        current = self._lifecycle.state_store.load()
        operation = (
            self._lifecycle.update_disabled
            if any(item.expert_id == manifest.expert_id for item in current.packages)
            else self._lifecycle.install_disabled
        )
        state = operation(manifest, str(bundle), validation, compatibility)
        coordinate = ExpertPackageCoordinate(
            lineage.package_id, lineage.package_version,
        )
        installed = next(
            item for item in state.packages if item.coordinate == coordinate
        )
        runtime_binding = ExpertRuntimeBinding(
            coordinate=coordinate, expert_id=lineage.expert_id,
            runtime_contract_id=manifest.runtime_contract_id,
            runtime_adapter_id="ollama.local/v1",
            artifact_id="ollama.bundle",
            artifact_ref=lineage.runtime_model_ref,
            expected_artifact_digest=artifact_digest,
        )
        manifest_bytes = dumps_document(manifest).encode()
        binding_bytes = dumps_document(runtime_binding).encode()
        compatibility_bytes = dumps_document(compatibility).encode()
        receipt = build_specialist_package_receipt(
            receipt_id=f"specialist-package-{lineage.release_id}",
            release_id=lineage.release_id,
            package_id=lineage.package_id,
            package_version=lineage.package_version,
            lineage_sha256=lineage.lineage_sha256,
            artifact_sha256=artifact_digest.value,
            expert_manifest_sha256=hashlib.sha256(manifest_bytes).hexdigest(),
            runtime_binding_sha256=hashlib.sha256(binding_bytes).hexdigest(),
            signature_sha256=hashlib.sha256(signature_bytes).hexdigest(),
            signature_key_id=signature.key_id,
            validation_policy_id=validation.policy_id,
            compatibility_sha256=hashlib.sha256(
                compatibility_bytes,
            ).hexdigest(),
            artifact_locator=installed.artifact_locator,
            lifecycle_revision=state.revision,
            installed_disabled=not installed.enabled,
            installed_at=self._now(),
        )
        sidecars = {
            "expert-manifest.json": manifest_bytes,
            "runtime-binding.json": binding_bytes,
            "signature.json": dumps_document(signature).encode(),
            "package-receipt.json": dumps_document(receipt).encode(),
        }
        for suffix, payload in sidecars.items():
            _write_private_new(self._output / f"{name}.{suffix}", payload + b"\n")
        return PackagedSpecialist(
            lineage, manifest, runtime_binding, signature, receipt, bundle,
        )


def _build_bundle(
    target: Path, lineage: FactorySpecialistReleaseLineage, output: Path,
) -> None:
    if target.exists() or target.is_symlink():
        raise FileExistsError("specialist bundle already exists")
    temporary = target.with_suffix(".tmp")
    lineage_bytes = dumps_document(lineage).encode()
    with tarfile.open(temporary, "w", format=tarfile.GNU_FORMAT) as archive:
        _add_bytes(archive, "factory-lineage.json", lineage_bytes)
        for source_name, archive_name in (
            ("base.gguf", "runtime/base.gguf"),
            ("adapter.gguf", "runtime/adapter.gguf"),
            ("Modelfile", "runtime/Modelfile"),
        ):
            source = output / source_name
            metadata = tarfile.TarInfo(archive_name)
            metadata.size = source.stat().st_size
            _normalize_tar_metadata(metadata)
            with source.open("rb") as stream:
                archive.addfile(metadata, stream)
    os.chmod(temporary, 0o600)
    os.replace(temporary, target)


def _add_bytes(archive: tarfile.TarFile, name: str, payload: bytes) -> None:
    metadata = tarfile.TarInfo(name)
    metadata.size = len(payload)
    _normalize_tar_metadata(metadata)
    archive.addfile(metadata, io.BytesIO(payload))


def _normalize_tar_metadata(metadata: tarfile.TarInfo) -> None:
    metadata.mtime = 0
    metadata.uid = metadata.gid = 0
    metadata.uname = metadata.gname = ""
    metadata.mode = 0o600


def _validate_conversion_output(
    lineage: FactorySpecialistReleaseLineage, output: Path,
) -> None:
    expected = {
        "base.gguf": lineage.base_gguf_sha256,
        "adapter.gguf": lineage.adapter_gguf_sha256,
        "Modelfile": lineage.modelfile_sha256,
    }
    if not output.is_dir() or output.is_symlink():
        raise ValueError("specialist conversion output is invalid")
    for name, digest in expected.items():
        path = output / name
        if not path.is_file() or path.is_symlink() or _file_sha256(path) != digest:
            raise PermissionError(f"specialist conversion output changed: {name}")


def _package_name(package_id: str, version: str) -> str:
    name = f"{package_id}-{version}"
    if _SAFE_NAME.fullmatch(name) is None:
        raise ValueError("specialist package filename is unsafe")
    return name


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _write_private_new(path: Path, payload: bytes) -> None:
    descriptor = os.open(
        path, os.O_CREAT | os.O_EXCL | os.O_WRONLY | os.O_NOFOLLOW, 0o600,
    )
    with os.fdopen(descriptor, "wb") as stream:
        stream.write(payload)
        stream.flush()
        os.fsync(stream.fileno())
