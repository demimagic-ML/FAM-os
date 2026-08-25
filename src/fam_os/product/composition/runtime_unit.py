"""Managed Ollama and model-store production composition."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from fam_os.adapters.cgroup.observer import CgroupV2ResourceObserver
from fam_os.adapters.linux.command import SubprocessCommandRunner
from fam_os.adapters.ollama import OllamaRuntime, OllamaSettings
from fam_os.adapters.systemd.lifecycle import SystemdUserServiceLifecycle
from fam_os.product.composition.managed_ollama import (
    ManagedOllamaService,
    ManagedOllamaSettings,
)
from fam_os.product.composition.ollama_model_import import OllamaModelStoreImporter
from fam_os.supervisor import ResourceLimits
from fam_os.supervisor import ResourceSnapshot


@dataclass(frozen=True, slots=True)
class ProductRuntimeSettings:
    executable: Path
    model_root: Path
    source_model_root: Path | None
    model_ref: str
    base_url: str
    limits: ResourceLimits
    accelerator_environment: tuple[tuple[str, str], ...] = ()


class ProductRuntimeUnit:
    def __init__(self, settings: ProductRuntimeSettings) -> None:
        self.settings = settings
        lifecycle = SystemdUserServiceLifecycle(SubprocessCommandRunner())
        self._service = ManagedOllamaService(
            ManagedOllamaSettings(
                settings.executable,
                settings.model_root,
                settings.base_url,
                limits=settings.limits,
                accelerator_environment=settings.accelerator_environment,
            ),
            lifecycle,
        )
        self._resource_observer = CgroupV2ResourceObserver(lifecycle)
        self.runtime: OllamaRuntime | None = None
        self._ensured: set[str] = set()

    def start(self) -> OllamaRuntime:
        self.ensure_model(self.settings.model_ref)
        self._service.reconcile()
        self.runtime = OllamaRuntime(OllamaSettings(self.settings.base_url, 180))
        return self.runtime

    def ensure_model(self, model_ref: str) -> None:
        if model_ref in self._ensured:
            return
        source = self.settings.source_model_root
        if source is not None and source.is_dir():
            OllamaModelStoreImporter(source, self.settings.model_root).import_model(model_ref)
        elif not _managed_manifest(self.settings, model_ref).is_file():
            raise FileNotFoundError("selected model is absent from managed Ollama storage")
        self._ensured.add(model_ref)

    def stop(self) -> None:
        self._service.stop()

    def recover(self) -> OllamaRuntime:
        """Reconcile the managed daemon and return a healthy runtime handle."""
        self._service.reconcile()
        if self.runtime is None:
            self.runtime = OllamaRuntime(OllamaSettings(self.settings.base_url, 180))
        return self.runtime

    def resource_snapshot(self) -> ResourceSnapshot | None:
        return self._resource_observer.observe(self._service.settings.service_id)


def _managed_manifest(settings: ProductRuntimeSettings, model_ref: str) -> Path:
    name, separator, tag = model_ref.partition(":")
    return (
        settings.model_root / "manifests/registry.ollama.ai/library" / name
        / (tag if separator else "latest")
    )
