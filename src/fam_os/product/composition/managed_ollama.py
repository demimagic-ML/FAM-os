"""Dedicated owner-scoped Ollama service composition."""

from __future__ import annotations

import os
import stat
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from fam_os.adapters.linux.process_identity import LinuxProcessIdentity
from fam_os.supervisor import (
    ResourceLimits,
    ServiceDefinition,
    ServiceRestartMode,
    ServiceRestartPolicy,
    ServiceState,
    ServiceStatus,
)


class OllamaServiceLifecycle(Protocol):
    def start(self, definition: ServiceDefinition) -> ServiceStatus: ...
    def stop(self, service_id: str) -> ServiceStatus: ...
    def status(self, service_id: str) -> ServiceStatus: ...


class OllamaHealth(Protocol):
    def ready(self, base_url: str) -> bool: ...


class OllamaProcessIdentity(Protocol):
    def matches(
        self, status: ServiceStatus, definition: ServiceDefinition,
    ) -> bool: ...


@dataclass(frozen=True, slots=True)
class ManagedOllamaSettings:
    executable: Path
    model_root: Path
    base_url: str = "http://127.0.0.1:11435"
    service_id: str = "fam-ollama"
    startup_timeout_seconds: float = 30.0
    poll_interval_seconds: float = 0.1
    limits: ResourceLimits = ResourceLimits()
    accelerator_environment: tuple[tuple[str, str], ...] = ()
    restart_policy: ServiceRestartPolicy = ServiceRestartPolicy(
        ServiceRestartMode.ON_FAILURE,
    )

    def __post_init__(self) -> None:
        if not self.executable.is_absolute() or self.executable.is_symlink():
            raise ValueError("managed Ollama executable must be an absolute non-symlink path")
        if not self.base_url.startswith("http://127.0.0.1:"):
            raise ValueError("managed Ollama must bind an explicit loopback port")
        if self.startup_timeout_seconds <= 0 or self.poll_interval_seconds <= 0:
            raise ValueError("managed Ollama health timing must be positive")

    def definition(self) -> ServiceDefinition:
        host = self.base_url.removeprefix("http://")
        return ServiceDefinition(
            self.service_id,
            (str(self.executable), "serve"),
            (
                ("OLLAMA_HOST", host),
                ("OLLAMA_MODELS", str(self.model_root)),
                ("OLLAMA_KEEP_ALIVE", "5m"),
            ) + self.accelerator_environment,
            limits=self.limits,
            restart_policy=self.restart_policy,
        )


class OllamaHttpHealth:
    def __init__(self, timeout_seconds: float = 1.0) -> None:
        self._timeout = timeout_seconds

    def ready(self, base_url: str) -> bool:
        try:
            with urllib.request.urlopen(
                f"{base_url}/api/tags", timeout=self._timeout,
            ) as response:
                status = response.status
                return isinstance(status, int) and status == 200
        except (OSError, urllib.error.URLError):
            return False


class ManagedOllamaService:
    def __init__(
        self, settings: ManagedOllamaSettings,
        lifecycle: OllamaServiceLifecycle, health: OllamaHealth | None = None,
        identity: OllamaProcessIdentity | None = None,
    ) -> None:
        self.settings: ManagedOllamaSettings = settings
        self._lifecycle: OllamaServiceLifecycle = lifecycle
        self._health = health or OllamaHttpHealth()
        self._identity = identity or LinuxProcessIdentity()

    def start(self) -> ServiceStatus:
        self._prepare_model_root()
        definition = self.settings.definition()
        status = self._lifecycle.status(self.settings.service_id)
        if (
            status.state is ServiceState.ACTIVE
            and not self._identity.matches(status, definition)
        ):
            status = self._lifecycle.stop(self.settings.service_id)
        if status.state is not ServiceState.ACTIVE:
            status = self._lifecycle.start(definition)
        if status.state is not ServiceState.ACTIVE or not self._wait_ready():
            self._lifecycle.stop(self.settings.service_id)
            raise RuntimeError("managed Ollama did not become healthy")
        return status

    def stop(self) -> ServiceStatus:
        return self._lifecycle.stop(self.settings.service_id)

    def reconcile(self) -> ServiceStatus:
        status = self._lifecycle.status(self.settings.service_id)
        if (
            status.state is ServiceState.ACTIVE
            and self._identity.matches(status, self.settings.definition())
            and self._health.ready(self.settings.base_url)
        ):
            self._prepare_model_root()
            return status
        if status.state not in {ServiceState.INACTIVE, ServiceState.UNKNOWN}:
            self._lifecycle.stop(self.settings.service_id)
        return self.start()

    def _wait_ready(self) -> bool:
        deadline = time.monotonic() + self.settings.startup_timeout_seconds
        while time.monotonic() < deadline:
            if self._health.ready(self.settings.base_url):
                return True
            time.sleep(self.settings.poll_interval_seconds)
        return False

    def _prepare_model_root(self) -> None:
        root = self.settings.model_root
        if root.is_symlink():
            raise OSError("managed model root cannot be a symlink")
        root.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(root, 0o700)
        metadata = root.stat(follow_symlinks=False)
        if metadata.st_uid != os.geteuid() or stat.S_IMODE(metadata.st_mode) != 0o700:
            raise PermissionError("managed model root has unsafe owner or mode")
