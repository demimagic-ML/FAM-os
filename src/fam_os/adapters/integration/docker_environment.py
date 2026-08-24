"""Digest-pinned, loopback-only Docker integration environments."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from fam_os.adapters.integration.docker_client import DockerCommandClient
from fam_os.adapters.integration.docker_state import DockerEnvironmentState
from fam_os.adapters.integration.docker_service import (
    DockerHealthRecipeRunner,
    DockerSecretInjector,
    DockerServiceLauncher,
)
from fam_os.adapters.integration.docker_support import (
    ordered_services,
    required_output,
    runtime_name,
)
from fam_os.adapters.integration.docker_network import (
    DockerNetworkAttachment, docker_network_evidence,
)
from fam_os.adapters.integration.retained_artifacts import capture_retained_artifacts
from fam_os.core.engineering.integration_environment import (
    IntegrationEnvironmentStatus,
    IntegrationNetworkMode,
    IntegrationServiceKind,
)
from fam_os.core.engineering.integration_environment_receipts import (
    IntegrationEnvironmentReceipt,
)


class DockerIntegrationEnvironmentAdapter:
    def __init__(
        self,
        secrets: DockerSecretInjector,
        client: DockerCommandClient | None = None,
        clock: Callable[[], datetime] | None = None,
        identifier: Callable[[], str] | None = None,
        sleeper: Callable[[float], None] | None = None,
        tcp_probe: Callable[[str, int, int], bool] | None = None,
        health_recipes: DockerHealthRecipeRunner | None = None,
        network=None,
    ) -> None:
        self._client = client or DockerCommandClient()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._identifier = identifier or (lambda: str(uuid4()))
        self._services = DockerServiceLauncher(
            self._client, secrets, sleeper, tcp_probe, health_recipes,
        )
        self._network = DockerNetworkAttachment(network)

    def launch(
        self, plan, candidate_root, permit, control,
    ) -> IntegrationEnvironmentReceipt:
        self._validate_launch(plan, candidate_root, permit)
        state = DockerEnvironmentState(candidate_root, plan.environment_id)
        state.claim()
        started = self._clock()
        network_id = None
        lease = None
        receipts = []
        try:
            if plan.network_mode is IntegrationNetworkMode.ALLOWLIST:
                lease, network_id, proxy_environment = self._network.open(
                    plan, permit, state,
                )
            else:
                network_id = self._create_network(plan)
                state.record_network(network_id)
                proxy_environment = ()
            for service in ordered_services(plan):
                self._require_live(control)
                receipt = self._services.launch(
                    plan, service, candidate_root, network_id, state, self._remove,
                    proxy_environment,
                )
                receipts.append(receipt)
                self._services.wait_healthy(
                    service, receipt, control, self._require_live,
                )
            state.finish("ready")
            usage = self._network.observe(lease)
            return IntegrationEnvironmentReceipt(
                self._identifier(), plan.environment_id, permit.permit_id,
                IntegrationEnvironmentStatus.READY, started, self._clock(),
                tuple(receipts), (), (), network_usage=usage,
            )
        except BaseException as launch_error:
            try:
                self._retire_runtime(
                    tuple(item.runtime_id for item in receipts), network_id,
                    state.load(), permit,
                )
            except BaseException as cleanup_error:
                raise RuntimeError("Docker launch cleanup is incomplete") from cleanup_error
            state.finish("failed_cleaned")
            raise launch_error

    def cleanup(
        self, plan, receipt, candidate_root, permit,
    ) -> IntegrationEnvironmentReceipt:
        self._validate_cleanup(plan, receipt, candidate_root, permit)
        state = DockerEnvironmentState(candidate_root, plan.environment_id)
        document = state.load()
        container_ids = tuple(document["container_ids"])
        network_id = document["network_id"]
        usage = self._retire_runtime(container_ids, network_id, document, permit)
        artifacts = capture_retained_artifacts(
            candidate_root, plan.retained_artifact_paths,
            plan.resource_impact.max_changed_bytes,
        )
        cleanup_ids = tuple(
            f"removed-container:{value}" for value in container_ids
        ) + docker_network_evidence(document, network_id, usage, "removed")
        state.finish("cleaned")
        return replace(
            receipt, receipt_id=self._identifier(),
            status=IntegrationEnvironmentStatus.CLEANED,
            completed_at=self._clock(), retained_artifacts=artifacts,
            cleanup_evidence_ids=cleanup_ids,
            network_usage=usage,
        )

    def reconcile(
        self, plan, candidate_root, permit,
    ) -> IntegrationEnvironmentReceipt:
        self._validate_reconcile(plan, candidate_root, permit)
        state = DockerEnvironmentState(candidate_root, plan.environment_id)
        document = state.load()
        if document["stage"] in {"cleaned", "reconciled_cleaned"}:
            raise PermissionError("Docker environment is already cleaned")
        container_ids = tuple(document["container_ids"])
        network_id = document["network_id"]
        usage = self._retire_runtime(container_ids, network_id, document, permit)
        artifacts = capture_retained_artifacts(
            candidate_root, plan.retained_artifact_paths,
            plan.resource_impact.max_changed_bytes,
        )
        cleanup_ids = tuple(
            f"reconciled-container:{value}" for value in container_ids
        ) + docker_network_evidence(document, network_id, usage, "reconciled")
        state.finish("reconciled_cleaned")
        instant = self._clock()
        return IntegrationEnvironmentReceipt(
            self._identifier(), plan.environment_id, permit.permit_id,
            IntegrationEnvironmentStatus.CLEANED, instant, instant, (), artifacts,
            cleanup_ids,
            network_usage=usage,
        )

    def recover(self, plan, candidate_root, permit):
        """Remove deterministic runtime identities after an interrupted launch."""
        self._validate_reconcile(plan, candidate_root, permit)
        state = DockerEnvironmentState(candidate_root, plan.environment_id)
        try:
            document = state.load()
        except FileNotFoundError:
            document = {
                "container_ids": [], "network_id": None,
                "network_opening": False, "network_lease": None,
            }
            has_state = False
        else:
            has_state = True
        expected = tuple(
            runtime_name("service", f"{plan.environment_id}:{item.service_id}")
            for item in plan.services
        )
        containers = tuple(dict.fromkeys(
            tuple(document["container_ids"]) + expected
        ))
        network = document["network_id"] or runtime_name(
            "network", plan.environment_id,
        )
        errors = []
        try:
            self._remove(
                containers,
                None if document["network_lease"] is not None else network,
            )
        except BaseException as error:
            errors.append(error)
        try: usage = self._network.recover(document, permit)
        except BaseException as error:
            errors.append(error); usage = None
        if errors:
            raise RuntimeError("Docker interrupted recovery is incomplete") from errors[-1]
        artifacts = capture_retained_artifacts(
            candidate_root, plan.retained_artifact_paths,
            plan.resource_impact.max_changed_bytes,
        )
        if has_state:
            state.finish("interrupted_recovered")
        instant = self._clock()
        evidence = tuple(
            f"recovery-probed-container:{item}" for item in containers
        ) + (f"recovery-probed-network:{network}",)
        return IntegrationEnvironmentReceipt(
            self._identifier(), plan.environment_id, permit.permit_id,
            IntegrationEnvironmentStatus.CLEANED, instant, instant, (),
            artifacts, evidence,
            network_usage=usage,
        )

    def _validate_launch(self, plan, root: Path, permit) -> None:
        now = self._clock()
        if (
            root != Path(plan.candidate_root)
            or root.is_symlink() or not root.is_dir()
            or permit.environment_id != plan.environment_id
            or permit.approved_changeset_id != plan.approved_changeset_id
            or permit.exact_host_id != plan.exact_host_id
            or not permit.issued_at <= now < permit.expires_at
        ):
            raise PermissionError("Docker integration launch identity is invalid")
        if (
            plan.network_mode is IntegrationNetworkMode.ALLOWLIST
            and not self._network.available
        ):
            raise PermissionError("Docker allowlisted egress broker is unavailable")
        for service in plan.services:
            if service.kind not in {
                IntegrationServiceKind.CONTAINER,
                IntegrationServiceKind.CLUSTER_CONTROL_PLANE,
            }:
                raise PermissionError("Docker adapter accepts container services only")
            retained = set(plan.retained_artifact_paths)
            if any(
                volume.retain_artifacts
                and volume.candidate_relative_path not in retained
                for volume in service.volumes
            ):
                raise PermissionError("retained Docker volume is not declared as an artifact")

    def _validate_cleanup(self, plan, receipt, root, permit) -> None:
        if (
            root != Path(plan.candidate_root)
            or root.is_symlink() or not root.is_dir()
            or receipt.environment_id != plan.environment_id
            or receipt.permit_id != permit.permit_id
            or permit.environment_id != plan.environment_id
        ):
            raise PermissionError("Docker integration cleanup identity is invalid")

    def _validate_reconcile(self, plan, root, permit) -> None:
        if (
            root != Path(plan.candidate_root)
            or root.is_symlink() or not root.is_dir()
            or permit.environment_id != plan.environment_id
            or permit.approved_changeset_id != plan.approved_changeset_id
            or permit.exact_host_id != plan.exact_host_id
        ):
            raise PermissionError("Docker reconciliation identity is invalid")

    def _create_network(self, plan) -> str:
        name = runtime_name("network", plan.environment_id)
        result = self._client.run((
            "network", "create", "--internal",
            "--label", f"fam.environment={plan.environment_id}", name,
        ))
        return required_output(result, "Docker network creation")

    def _remove(self, container_ids: tuple[str, ...], network_id: str | None) -> None:
        for runtime_id in reversed(container_ids):
            result = self._client.run(("rm", "--force", runtime_id))
            if result.exit_code != 0 and b"No such container" not in result.output:
                raise RuntimeError("Docker container cleanup failed")
        if network_id:
            result = self._client.run(("network", "rm", network_id))
            if result.exit_code != 0 and b"not found" not in result.output:
                raise RuntimeError("Docker network cleanup failed")

    def _retire_runtime(self, container_ids, network_id, document, permit):
        errors, usage = [], None
        try:
            self._remove(
                container_ids,
                None if document["network_lease"] is not None else network_id,
            )
        except BaseException as error:
            errors.append(error)
        try: usage = self._network.close(document, permit)
        except BaseException as error:
            errors.append(error)
        if errors:
            raise RuntimeError("Docker environment cleanup is incomplete") from errors[-1]
        return usage

    @staticmethod
    def _require_live(control) -> None:
        if control.cancelled() or not control.authorization_active():
            raise PermissionError("Docker integration was cancelled or revoked")
