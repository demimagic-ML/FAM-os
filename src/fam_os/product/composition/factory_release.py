"""Composition of pinned conversion, signed packaging, canary, and activation."""

from __future__ import annotations

import base64
import os
from dataclasses import dataclass, fields
from pathlib import Path

from cryptography.hazmat.primitives import serialization

from fam_os.adapters.crypto import Ed25519PackageSignatureVerifier
from fam_os.adapters.filesystem import (
    ImmutablePackageArtifactStore,
    JsonPackageLifecycleStateStore,
)
from fam_os.adapters.linux import (
    LinuxHardwareDiscovery,
    PrivacyReviewedLinuxResourceDiscovery,
)
from fam_os.adapters.linux.command import SubprocessCommandRunner
from fam_os.adapters.ollama.canary_installer import OllamaCanaryModelInstaller
from fam_os.adapters.training import conversion_worker
from fam_os.adapters.training.conversion_environment import (
    LlamaCppConversionEnvironmentProbe,
)
from fam_os.adapters.training.llama_cpp_conversion_backend import (
    LlamaCppConversionBackend,
)
from fam_os.core.ports.inference import InferenceRuntime
from fam_os.core.production.model_catalog import RuntimeModelCatalog
from fam_os.experts import ExpertCompatibilityEvaluator
from fam_os.fabric import PersistentDeviceCredentials
from fam_os.product.canary_verifier import DeclaredCanaryVerifier
from fam_os.product.composition.core_storage import CoreRepositorySet
from fam_os.product.composition.verifier_unit import production_verifier_catalog
from fam_os.product.factory_activation import ProductFactoryActivation
from fam_os.product.factory_canary import (
    FactorySpecialistCanaryRunner,
    ProductFactoryCanaryApprovals,
)
from fam_os.product.factory_conversion import ProductFactoryConversions
from fam_os.product.factory_conversion_workspace import FactoryConversionWorkspace
from fam_os.product.factory_releases import ProductFactoryReleases
from fam_os.product.factory_lifecycle import ProductFactoryLifecycle
from fam_os.product.factory_specialist_packaging import FactorySpecialistPackager
from fam_os.registry import (
    PackageTrustPolicy,
    PublisherKeyStatus,
    SignatureAlgorithm,
    TrustedPublisherKey,
)
from fam_os.registry.lifecycle import ExpertPackageLifecycle
from fam_os.registry.validation import ExpertPackageValidator
from fam_os.scheduler.resources import (
    FULL_REFERENCE_WORKSTATION_PROFILE_ID,
    AcceleratorResourceBudget,
    CpuResourceBudget,
    EffectiveResourceBudget,
    MemoryResourceBudget,
    StorageResourceBudget,
    ValidationProfilePurpose,
    ValidationProfileRef,
)
from fam_os.verification.sandbox import SandboxRunner


GIB = 1024**3


@dataclass(frozen=True, slots=True)
class FactoryReleaseRuntimeSettings:
    conversion_environment: Path
    conversion_wheelhouse_manifest: Path
    llama_cpp_directory: Path
    llama_cpp_revision: str
    model_directory: Path
    training_workspace_root: Path
    conversion_workspace_root: Path
    package_output_root: Path
    package_artifact_root: Path
    package_lifecycle_state: Path
    canary_workspace_root: Path
    canary_suite: Path
    ollama_executable: Path
    ollama_url: str
    allowed_licenses: tuple[str, ...] = ("Apache-2.0",)

    def __post_init__(self) -> None:
        paths = tuple(
            value for field in fields(self)
            if isinstance((value := getattr(self, field.name)), Path)
        )
        if any(not path.is_absolute() for path in paths):
            raise ValueError("factory release paths must be absolute")
        if len(self.llama_cpp_revision) != 40:
            raise ValueError("factory release requires an immutable llama.cpp revision")


@dataclass(frozen=True, slots=True)
class FactoryReleaseServices:
    conversions: ProductFactoryConversions
    releases: ProductFactoryReleases
    canary_approvals: ProductFactoryCanaryApprovals
    canary_runner: FactorySpecialistCanaryRunner
    activation: ProductFactoryActivation
    lifecycle: ProductFactoryLifecycle


def compose_factory_release(
    *, settings: FactoryReleaseRuntimeSettings,
    repositories: CoreRepositorySet, credentials: PersistentDeviceCredentials,
    runtime: InferenceRuntime, catalog: RuntimeModelCatalog, owner_uid: int,
    sandbox: SandboxRunner,
) -> FactoryReleaseServices:
    _directory(settings.conversion_environment, "conversion environment")
    _file(settings.conversion_wheelhouse_manifest, "conversion wheelhouse manifest")
    _directory(settings.llama_cpp_directory, "llama.cpp source")
    _directory(settings.model_directory, "conversion base model")
    _directory(settings.training_workspace_root, "training workspace")
    _file(settings.canary_suite, "canary suite")
    _file(settings.ollama_executable, "Ollama executable")
    for root in (
        settings.conversion_workspace_root, settings.package_output_root,
        settings.package_artifact_root, settings.canary_workspace_root,
    ):
        _private_root(root, owner_uid)
    probe = LlamaCppConversionEnvironmentProbe(
        environment_directory=settings.conversion_environment,
        wheelhouse_manifest=settings.conversion_wheelhouse_manifest,
        llama_cpp_directory=settings.llama_cpp_directory,
        expected_revision=settings.llama_cpp_revision,
        ollama=settings.ollama_executable,
    )
    backend = LlamaCppConversionBackend(
        repositories=repositories, environment_probe=probe,
        environment_directory=settings.conversion_environment,
        worker_script=Path(conversion_worker.__file__).absolute(),
        llama_cpp_directory=settings.llama_cpp_directory,
        model_directory=settings.model_directory,
        training_workspace_root=settings.training_workspace_root,
        workspace=FactoryConversionWorkspace(
            settings.conversion_workspace_root, owner_uid,
        ),
    )
    conversions = ProductFactoryConversions(repositories, probe, backend=backend)
    lifecycle = ExpertPackageLifecycle(
        JsonPackageLifecycleStateStore(settings.package_lifecycle_state),
        ImmutablePackageArtifactStore(settings.package_artifact_root),
    )
    lifecycle.recover()
    public_key = credentials.identity_key.public_key().public_bytes(
        serialization.Encoding.Raw, serialization.PublicFormat.Raw,
    )
    publisher_id = f"fam-device:{credentials.identity.device_id}"
    policy = PackageTrustPolicy(
        f"factory-policy:{credentials.identity.device_id}",
        settings.allowed_licenses,
        publisher_keys=(TrustedPublisherKey(
            credentials.identity.device_id, publisher_id,
            SignatureAlgorithm.ED25519,
            base64.b64encode(public_key).decode("ascii"),
            PublisherKeyStatus.ACTIVE,
        ),),
    )
    discovery = PrivacyReviewedLinuxResourceDiscovery(
        LinuxHardwareDiscovery(), SubprocessCommandRunner(),
        "factory-host-current", "factory-state-current",
    ).collect()
    budget = _full_host_budget(discovery)
    packager = FactorySpecialistPackager(
        output_directory=settings.package_output_root, lifecycle=lifecycle,
        validator=ExpertPackageValidator(
            policy, Ed25519PackageSignatureVerifier(),
        ),
        compatibility_evaluator=ExpertCompatibilityEvaluator(),
        inventory=discovery.inventory, budget=budget,
        publisher_id=publisher_id,
        signer_key_id=credentials.identity.device_id,
        signing_key=credentials.identity_key,
    )
    releases = ProductFactoryReleases(
        repositories=repositories, packager=packager,
        model_directory=settings.model_directory,
        conversion_workspace_root=settings.conversion_workspace_root,
    )
    canary_approvals = ProductFactoryCanaryApprovals(
        repositories, suite_path=settings.canary_suite,
    )
    installer = OllamaCanaryModelInstaller(
        settings.ollama_executable, settings.ollama_url,
    )
    canary_runner = FactorySpecialistCanaryRunner(
        repositories=repositories, artifact_root=settings.package_artifact_root,
        suite_path=settings.canary_suite,
        workspace_root=settings.canary_workspace_root,
        installer=installer,
        runtime=runtime,
        verifier=DeclaredCanaryVerifier(
            production_verifier_catalog(), sandbox,
        ),
        signer_key_id=credentials.identity.device_id,
        signing_key=credentials.identity_key,
    )
    activation = ProductFactoryActivation(repositories, lifecycle, catalog)
    factory_lifecycle = ProductFactoryLifecycle(
        repositories=repositories, lifecycle=lifecycle, catalog=catalog,
        installer=installer, artifact_root=settings.package_artifact_root,
        workspace_root=settings.canary_workspace_root / "lifecycle",
    )
    factory_lifecycle.reconcile()
    return FactoryReleaseServices(
        conversions, releases, canary_approvals, canary_runner, activation,
        factory_lifecycle,
    )


def _full_host_budget(discovery) -> EffectiveResourceBudget:
    inventory = discovery.inventory
    cpu_ids = inventory.cpu.logical_cpu_ids
    reserved = cpu_ids[-2:] if len(cpu_ids) > 4 else cpu_ids[-1:]
    schedulable = tuple(item for item in cpu_ids if item not in reserved)
    total = inventory.memory.total_bytes
    current = max(0, total - inventory.memory.available_bytes)
    memory_reserve = min(8 * GIB, max(GIB, total // 8))
    accelerators = []
    runtime_by_id = {item.device_id: item for item in discovery.accelerators}
    for item in inventory.accelerators:
        limit = item.memory_total_bytes or 0
        reserve = min(GIB, limit // 8)
        runtime_state = runtime_by_id.get(item.device_id)
        accelerators.append(AcceleratorResourceBudget(
            item.device_id, limit > reserve,
            limit, max(0, limit - reserve), reserve,
            0 if runtime_state is None else runtime_state.current_memory_bytes,
        ))
    storage = tuple(StorageResourceBudget(
        item.storage_id, item.capacity_bytes,
        max(1, item.capacity_bytes - min(100 * GIB, item.capacity_bytes // 10)),
        min(100 * GIB, item.capacity_bytes // 10),
        max(0, item.capacity_bytes - item.available_bytes),
    ) for item in inventory.storage)
    return EffectiveResourceBudget(
        "factory-full-host-current", inventory.inventory_id,
        discovery.captured_at,
        ValidationProfileRef(
            FULL_REFERENCE_WORKSTATION_PROFILE_ID,
            ValidationProfilePurpose.FULL_HOST_CAPABILITY,
        ),
        CpuResourceBudget(
            cpu_ids, schedulable, reserved, float(len(schedulable)), 0,
        ),
        MemoryResourceBudget(
            total, total - memory_reserve, memory_reserve, current,
            inventory.memory.swap_total_bytes,
            inventory.memory.swap_total_bytes - inventory.memory.swap_free_bytes,
        ),
        tuple(accelerators), storage,
    )


def _directory(path: Path, label: str) -> None:
    if not path.is_dir() or path.is_symlink():
        raise ValueError(f"{label} is unavailable or unsafe")


def _file(path: Path, label: str) -> None:
    if not path.is_file() or path.is_symlink():
        raise ValueError(f"{label} is unavailable or unsafe")


def _private_root(path: Path, owner_uid: int) -> None:
    path.mkdir(parents=True, mode=0o700, exist_ok=True)
    os.chmod(path, 0o700)
    if path.is_symlink() or path.stat().st_uid != owner_uid:
        raise PermissionError("factory release root ownership is unsafe")
