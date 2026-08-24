"""Bounded launch and health logic for one Docker service."""

from collections.abc import Callable, Mapping
from pathlib import Path
import os
import re
import shutil
import socket
import tempfile
import time
from typing import Protocol

from fam_os.adapters.integration.docker_support import (
    confined_path, directory_size, required_output, runtime_name,
)
from fam_os.adapters.integration.secret_consumer import (
    integration_secret_consumer_id,
)
from fam_os.core.engineering.integration_environment import IntegrationHealthKind
from fam_os.core.engineering.integration_environment_receipts import (
    IntegrationAllocatedPort, IntegrationServiceReceipt,
)


_SAFE_SECRET_KEY = re.compile(r"[A-Z][A-Z0-9_]{0,63}\Z")
_DENIED_SECRET_KEYS = frozenset({
    "DOCKER_CONFIG", "DOCKER_CONTEXT", "DOCKER_HOST", "HOME", "PATH",
})


class DockerSecretInjector(Protocol):
    def environment(
        self, secret_refs: tuple[str, ...], consumer_id: str,
    ) -> Mapping[str, str]: ...


class DockerHealthRecipeRunner(Protocol):
    def healthy(
        self, signed_recipe_id: str, runtime_id: str, timeout_seconds: int,
    ) -> bool: ...


class DockerServiceLauncher:
    def __init__(
        self, client, secrets, sleeper=None, tcp_probe=None, health_recipes=None,
    ) -> None:
        self._client = client
        self._secrets = secrets
        self._sleep = sleeper or time.sleep
        self._tcp_probe = tcp_probe or _tcp_probe
        self._health_recipes = health_recipes

    def launch(
        self, plan, service, root, network_id, state, remover,
        proxy_environment=(),
    ):
        self._verify_image(service.image_ref, service.image_sha256)
        arguments = self._arguments(plan, service, root, network_id)
        secret_arguments, secret_root = self._secret_arguments(root, service)
        arguments.extend(secret_arguments)
        for value in proxy_environment:
            arguments.extend(("--env", value))
        arguments.append(service.image_ref)
        arguments.extend(service.launch_arguments)
        try:
            result = self._client.run(
                tuple(arguments), environment=self._docker_environment(root),
            )
        finally:
            if secret_root is not None:
                shutil.rmtree(secret_root)
        runtime_id = required_output(result, "Docker container launch")
        try:
            state.record_container(runtime_id)
            allocated = tuple(
                IntegrationAllocatedPort(
                    port.name, self._allocated_port(runtime_id, port.container_port),
                )
                for port in service.ports
            )
        except BaseException:
            remover((runtime_id,), None)
            raise
        return IntegrationServiceReceipt(
            service.service_id, runtime_id, service.image_sha256,
            allocated, f"health:{service.service_id}", None,
        )

    def wait_healthy(self, service, receipt, control, require_live) -> None:
        check = service.health_check
        for _attempt in range(check.maximum_attempts):
            require_live(control)
            if self._health_passed(check, receipt):
                return
            self._sleep(check.interval_seconds)
        raise RuntimeError("Docker service failed its bounded health check")

    def _arguments(self, plan, service, root, network_id):
        arguments = [
            "run", "--detach", "--pull", "never", "--init", "--read-only",
            "--security-opt", "no-new-privileges", "--cap-drop", "ALL",
            "--cap-add", "CHOWN", "--cap-add", "DAC_OVERRIDE",
            "--cap-add", "FOWNER", "--cap-add", "SETGID", "--cap-add", "SETUID",
            "--pids-limit", str(plan.resource_impact.max_processes),
            "--memory", str(plan.maximum_memory_bytes),
            "--cpu-period", "100000", "--cpu-quota",
            str(plan.maximum_cpu_millis_per_second * 100),
            "--network", network_id,
            "--name", runtime_name(
                "service", f"{plan.environment_id}:{service.service_id}",
            ),
            "--label", f"fam.environment={plan.environment_id}",
            "--label", f"fam.service={service.service_id}",
            "--tmpfs", "/tmp:rw,nosuid,nodev,noexec,size=67108864",
            "--tmpfs", "/run:rw,nosuid,nodev,noexec,size=16777216",
            "--tmpfs", "/var/run/postgresql:rw,nosuid,nodev,noexec,size=16777216",
        ]
        for port in service.ports:
            host = "" if port.requested_host_port == 0 else str(port.requested_host_port)
            arguments.extend((
                "--publish",
                f"{port.host_address}:{host}:{port.container_port}/{port.protocol}",
            ))
        arguments.extend(self._volume_arguments(root, service))
        return arguments

    def _volume_arguments(self, root, service) -> tuple[str, ...]:
        values = []
        for volume in service.volumes:
            path = confined_path(root, volume.candidate_relative_path)
            if volume.read_only:
                if not path.is_dir() or directory_size(path) > volume.maximum_bytes:
                    raise PermissionError("Docker read-only volume exceeds its bound")
                specification = f"type=bind,src={path},dst={volume.mount_path},readonly"
            else:
                specification = (
                    f"type=tmpfs,dst={volume.mount_path},"
                    f"tmpfs-size={volume.maximum_bytes},tmpfs-mode=0700"
                )
            values.extend(("--mount", specification))
        return tuple(values)

    def _secret_arguments(self, root, service):
        values = dict(self._secrets.environment(
            service.secret_refs,
            integration_secret_consumer_id(service),
        ))
        if not values:
            return (), None
        if set(values) & _DENIED_SECRET_KEYS or any(
            not _SAFE_SECRET_KEY.fullmatch(key) or key.endswith("_FILE")
            or not isinstance(value, str) or "\0" in value or len(value) > 65_536
            for key, value in values.items()
        ):
            raise PermissionError("Docker secret injection is invalid")
        parent = root / ".fam" / "secret-injection"
        parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        secret_root = Path(tempfile.mkdtemp(prefix="service-", dir=parent))
        arguments = []
        try:
            for key in sorted(values):
                path = secret_root / key
                descriptor = os.open(
                    path, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                    0o600,
                )
                with os.fdopen(descriptor, "w", encoding="utf-8") as stream:
                    stream.write(values[key])
                    stream.flush()
                    os.fsync(stream.fileno())
                target = f"/run/fam-secrets/{key}"
                arguments.extend((
                    "--mount", f"type=bind,src={path},dst={target},readonly",
                    "--env", f"{key}_FILE={target}",
                ))
        except BaseException:
            shutil.rmtree(secret_root)
            raise
        return tuple(arguments), secret_root

    @staticmethod
    def _docker_environment(root):
        docker_config = root / ".fam" / "docker-empty"
        docker_config.mkdir(parents=True, exist_ok=True, mode=0o700)
        return {
            "LANG": "C.UTF-8", "LC_ALL": "C.UTF-8",
            "HOME": str(root), "DOCKER_CONFIG": str(docker_config),
        }

    def _verify_image(self, image_ref, expected_sha256) -> None:
        result = self._client.run(("image", "inspect", "--format", "{{.Id}}", image_ref))
        observed = required_output(result, "Docker image inspection")
        if observed != f"sha256:{expected_sha256}":
            raise PermissionError("Docker image content digest does not match")

    def _allocated_port(self, runtime_id: str, container_port: int) -> int:
        result = self._client.run(("port", runtime_id, f"{container_port}/tcp"))
        value = required_output(result, "Docker port inspection")
        try:
            host, port = value.rsplit(":", 1)
            if host not in {"127.0.0.1", "0.0.0.0"}:
                raise ValueError
            return int(port)
        except ValueError as error:
            raise RuntimeError("Docker returned an invalid port binding") from error

    def _health_passed(self, check, receipt) -> bool:
        if check.kind is IntegrationHealthKind.TCP:
            port = next(
                item.host_port for item in receipt.allocated_ports
                if item.name == check.port_name
            )
            return self._tcp_probe("127.0.0.1", port, check.timeout_seconds)
        if check.kind is IntegrationHealthKind.SIGNED_RECIPE:
            if self._health_recipes is None:
                raise PermissionError("Docker signed health recipes are unavailable")
            return self._health_recipes.healthy(
                check.signed_recipe_id, receipt.runtime_id, check.timeout_seconds,
            )
        raise PermissionError("Docker HTTP health checks are not yet supported")


def _tcp_probe(host: str, port: int, timeout: int) -> bool:
    try:
        with socket.create_connection((host, port), timeout):
            return True
    except OSError:
        return False
