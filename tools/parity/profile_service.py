"""One profile-driven Ollama service composition for every parity workload."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from urllib.parse import urlparse

from fam_os.adapters.cgroup.observer import CgroupV2ResourceObserver
from fam_os.adapters.linux.command import SubprocessCommandRunner
from fam_os.adapters.ollama.errors import OllamaTransportError
from fam_os.adapters.ollama.runtime import OllamaRuntime
from fam_os.adapters.ollama.settings import OllamaSettings
from fam_os.adapters.systemd.lifecycle import SystemdUserServiceLifecycle
from fam_os.scheduler import AcceleratorVisibility
from fam_os.supervisor.contracts import ResourceLimits, ResourceSnapshot, ServiceDefinition
from fam_os.supervisor.errors import ServiceLifecycleError
from tools.parity.composition import BenchmarkComposition


@dataclass(frozen=True, slots=True)
class ProfiledServiceSettings:
    base_url: str
    timeout_seconds: float
    composition: BenchmarkComposition
    service_id: str = "fam-parity-ollama"
    models_path: str = "/usr/share/ollama/.ollama/models"
    ollama_executable: str = "/usr/local/bin/ollama"
    readiness_seconds: float = 15.0

    def __post_init__(self) -> None:
        parsed = urlparse(self.base_url)
        if parsed.scheme != "http" or not parsed.netloc or parsed.path not in {"", "/"}:
            raise ValueError("parity service requires a plain HTTP base URL")
        if self.timeout_seconds <= 0 or self.readiness_seconds <= 0:
            raise ValueError("service timeouts must be positive")

    @property
    def host(self) -> str:
        return urlparse(self.base_url).netloc


@dataclass(slots=True)
class ProfiledOllamaService:
    settings: ProfiledServiceSettings
    lifecycle: SystemdUserServiceLifecycle = field(
        default_factory=lambda: SystemdUserServiceLifecycle(SubprocessCommandRunner())
    )
    runtime: OllamaRuntime = field(init=False)
    resources: CgroupV2ResourceObserver = field(init=False)

    def __post_init__(self) -> None:
        self.runtime = OllamaRuntime(
            OllamaSettings(self.settings.base_url, self.settings.timeout_seconds)
        )
        self.resources = CgroupV2ResourceObserver(self.lifecycle)

    def __enter__(self) -> "ProfiledOllamaService":
        self.start()
        return self

    def __exit__(self, *_: object) -> None:
        self.stop()

    def start(self) -> None:
        self.stop()
        self.lifecycle.start(self.definition())
        deadline = time.monotonic() + self.settings.readiness_seconds
        while time.monotonic() < deadline:
            try:
                self.runtime.loaded_models()
                return
            except OllamaTransportError:
                time.sleep(0.25)
        self.stop()
        raise TimeoutError("profiled Ollama parity service did not become ready")

    def stop(self) -> None:
        try:
            self.lifecycle.stop(self.settings.service_id)
        except ServiceLifecycleError:
            pass

    def snapshot(self) -> ResourceSnapshot | None:
        return self.resources.observe(self.settings.service_id)

    def definition(self) -> ServiceDefinition:
        settings = self.settings
        profile = settings.composition.profile
        environment = [
            ("OLLAMA_HOST", settings.host),
            ("OLLAMA_MODELS", settings.models_path),
        ]
        if profile.service.accelerator_visibility is AcceleratorVisibility.DENY_ALL:
            environment.extend(_cpu_only_environment())
        cpu_cores = (
            profile.service.cpu_quota_cores
            if profile.service.cpu_quota_cores is not None
            else settings.composition.budget.cpu.scheduler_quota_cores
        )
        return ServiceDefinition(
            service_id=settings.service_id,
            command=(settings.ollama_executable, "serve"),
            environment=tuple(environment),
            limits=ResourceLimits(
                memory_max_bytes=profile.service.memory_max_bytes,
                swap_max_bytes=profile.service.swap_max_bytes,
                cpu_quota_percent=cpu_cores * 100 if cpu_cores is not None else None,
            ),
        )


def _cpu_only_environment() -> tuple[tuple[str, str], ...]:
    return (
        ("CUDA_VISIBLE_DEVICES", "-1"),
        ("GGML_VK_VISIBLE_DEVICES", "-1"),
        ("OLLAMA_VULKAN", "0"),
        ("OLLAMA_LLM_LIBRARY", "cpu_avx2"),
    )
