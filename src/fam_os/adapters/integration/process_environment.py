"""Signed-recipe systemd/Bubblewrap process and loopback API environments."""

from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import time
from uuid import uuid4

from fam_os.adapters.integration.process_client import ProcessCommandClient
from fam_os.adapters.integration.process_state import ProcessEnvironmentState
from fam_os.adapters.integration.process_secrets import ProcessSecretFiles
from fam_os.adapters.integration.process_recipes import (
    expanded_arguments, recipe_coordinate,
)
from fam_os.adapters.integration.process_recovery import recover_process_environment
from fam_os.adapters.integration.process_network import ProcessNetworkAttachment
from fam_os.adapters.integration.process_health import ProcessHealthMonitor
from fam_os.adapters.integration.process_retirement import retire_process_resources
from fam_os.adapters.integration.docker_support import ordered_services, runtime_name
from fam_os.adapters.integration.process_toolchains import recipe_mount_arguments
from fam_os.adapters.integration.retained_artifacts import capture_retained_artifacts
from fam_os.core.engineering import (
    IntegrationAllocatedPort, IntegrationEnvironmentReceipt,
    IntegrationEnvironmentStatus, IntegrationNetworkMode,
    IntegrationServiceKind, IntegrationServiceReceipt,
)


class ProcessIntegrationEnvironmentAdapter:
    def __init__(self, recipes, client=None, clock=None, identifier=None, sleeper=None, secrets=None, network=None):
        self._recipes = recipes
        self._client = client or ProcessCommandClient()
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._identifier = identifier or (lambda: str(uuid4()))
        self._sleep = sleeper or time.sleep
        self._wrappers = {}
        self._secrets = ProcessSecretFiles(secrets)
        self._network = ProcessNetworkAttachment(network)
        self._health = ProcessHealthMonitor(self._client, self._sleep)

    def launch(self, plan, candidate_root, permit, control):
        self._validate(plan, candidate_root, permit, launching=True)
        state = ProcessEnvironmentState(candidate_root, plan.environment_id)
        state.claim()
        lease = None
        started, receipts = self._clock(), []
        try:
            lease = self._network.open(plan, permit, state)
            for service in ordered_services(plan):
                self._require_live(control)
                receipt = self._start_service(
                    plan, service, candidate_root, state, lease,
                )
                receipts.append(receipt)
                state.record_unit(receipt.runtime_id)
                receipts[-1] = replace(
                    receipt,
                    health_evidence_id=self._health.wait(
                        service, receipt, control, self._require_live,
                    ),
                )
            state.finish("ready")
            usage = self._network.observe(lease)
            return IntegrationEnvironmentReceipt(
                self._identifier(), plan.environment_id, permit.permit_id,
                IntegrationEnvironmentStatus.READY, started, self._clock(),
                tuple(receipts), (), (), network_usage=usage,
            )
        except BaseException:
            document = state.load()
            retire_process_resources(
                stop=self._stop,
                units=tuple(item.runtime_id for item in receipts),
                secrets=self._secrets, root=candidate_root,
                secret_roots=document["secret_roots"], network=self._network,
                document=document, permit=permit,
            )
            state.finish("failed_cleaned")
            raise

    def cleanup(self, plan, receipt, candidate_root, permit):
        self._validate(plan, candidate_root, permit, launching=False)
        if receipt.environment_id != plan.environment_id or receipt.permit_id != permit.permit_id:
            raise PermissionError("process cleanup receipt identity is invalid")
        state = ProcessEnvironmentState(candidate_root, plan.environment_id)
        document = state.load()
        units = tuple(document["units"])
        secret_evidence, usage = retire_process_resources(
            stop=self._stop, units=units, secrets=self._secrets,
            root=candidate_root, secret_roots=document["secret_roots"],
            network=self._network, document=document, permit=permit,
        )
        artifacts = capture_retained_artifacts(
            candidate_root, plan.retained_artifact_paths,
            plan.resource_impact.max_changed_bytes,
        )
        state.finish("cleaned")
        return replace(
            receipt, receipt_id=self._identifier(),
            status=IntegrationEnvironmentStatus.CLEANED,
            completed_at=self._clock(),
            retained_artifacts=artifacts,
            cleanup_evidence_ids=(
                tuple(f"stopped-unit:{item}" for item in units) + secret_evidence
                + _network_evidence(usage)
            ),
            network_usage=usage,
        )

    def reconcile(self, plan, candidate_root, permit):
        self._validate(plan, candidate_root, permit, launching=False)
        state = ProcessEnvironmentState(candidate_root, plan.environment_id)
        document = state.load()
        if document["stage"] in {"cleaned", "reconciled_cleaned"}:
            raise PermissionError("process environment is already cleaned")
        units = tuple(document["units"])
        secret_evidence, usage = retire_process_resources(
            stop=self._stop, units=units, secrets=self._secrets,
            root=candidate_root, secret_roots=document["secret_roots"],
            network=self._network, document=document, permit=permit,
        )
        artifacts = capture_retained_artifacts(
            candidate_root, plan.retained_artifact_paths,
            plan.resource_impact.max_changed_bytes,
        )
        state.finish("reconciled_cleaned")
        instant = self._clock()
        return IntegrationEnvironmentReceipt(
            self._identifier(), plan.environment_id, permit.permit_id,
            IntegrationEnvironmentStatus.CLEANED, instant, instant, (), artifacts,
            tuple(f"reconciled-unit:{item}" for item in units) + secret_evidence,
            network_usage=usage,
        )

    def recover(self, plan, candidate_root, permit):
        """Probe deterministic scope and secret identities after launch interruption."""
        self._validate(plan, candidate_root, permit, launching=False)
        receipt = recover_process_environment(
            plan, candidate_root, permit, stop=self._stop,
            secrets=self._secrets, clock=self._clock,
            identifier=self._identifier,
        )
        try:
            document = ProcessEnvironmentState(candidate_root, plan.environment_id).load()
        except FileNotFoundError:
            document = {"network_opening": False}
        usage = self._network.recover(document, permit)
        return replace(
            receipt, network_usage=usage,
            cleanup_evidence_ids=receipt.cleanup_evidence_ids + _network_evidence(usage),
        )

    def _start_service(self, plan, service, root, state, lease):
        recipe_id, version = recipe_coordinate(service.signed_launch_recipe_id)
        recipe = self._recipes.get(recipe_id, version)
        if service.launch_arguments != expanded_arguments(recipe.argv_template, service):
            raise PermissionError("process launch arguments differ from signed recipe")
        mounts = recipe_mount_arguments(recipe)
        secret_mounts, secret_root = self._secrets.materialize(
            root, plan.environment_id, service,
        )
        if secret_root is not None:
            try:
                state.record_secret_root(secret_root)
            except BaseException:
                self._secrets.cleanup(root, (secret_root,))
                raise
        unit = runtime_name("process", plan.environment_id + ":" + service.service_id)
        wrapper = self._client.start_scope(
            self._start_command(
                plan, root, unit, recipe, service.launch_arguments,
                mounts + secret_mounts, lease,
            ),
        )
        self._wrappers[unit] = wrapper
        ports = tuple(
            IntegrationAllocatedPort(item.name, item.requested_host_port)
            for item in service.ports
        )
        return IntegrationServiceReceipt(
            service.service_id, unit, None, ports, "health-pending", None,
        )

    def _start_command(self, plan, root, unit, recipe, arguments, mounts, lease):
        quota = max(1, plan.maximum_cpu_millis_per_second // 10)
        network, proxy_environment = self._network.scope_arguments(plan, lease)
        inner = (
            str(self._client.bubblewrap), "--unshare-user", "--unshare-pid",
            "--unshare-ipc", "--unshare-uts", "--unshare-cgroup", "--new-session",
            "--clearenv", "--cap-drop", "ALL", "--ro-bind", "/usr", "/usr",
            "--ro-bind", "/bin", "/bin", "--ro-bind", "/lib", "/lib",
            "--ro-bind-try", "/lib64", "/lib64", "--proc", "/proc",
            "--dev", "/dev", "--bind", str(root), "/workspace",
            "--tmpfs", "/tmp", "--chdir", "/workspace",
            "--tmpfs", "/workspace/.fam/secret-injection",
            "--ro-bind-try", "/etc/fonts", "/etc/fonts",
            "--ro-bind-try", "/etc/ssl/certs", "/etc/ssl/certs",
            "--ro-bind-try", "/etc/machine-id", "/etc/machine-id",
            *mounts, "--setenv", "HOME", "/tmp", *proxy_environment,
            "--", recipe.executable_path,
            *arguments,
        )
        return (
            "--user", "--scope", "--quiet", f"--unit={unit}",
            "--property=KillMode=control-group", "--property=SendSIGKILL=yes",
            "--property=TimeoutStopSec=3s",
            "--property=MemorySwapMax=0", f"--property=MemoryMax={plan.maximum_memory_bytes}",
            f"--property=TasksMax={plan.resource_impact.max_processes}",
            f"--property=CPUQuota={quota}%", *network, "--", *inner,
        )

    def _stop(self, units):
        for unit in reversed(units):
            name = unit + ".scope"
            self._client.run(
                self._client.systemctl,
                ("--user", "kill", "--kill-whom=all", "--signal=TERM", name),
            )
            for _attempt in range(30):
                if not self._scope_active(name):
                    break
                self._sleep(0.1)
            if self._scope_active(name):
                self._client.run(
                    self._client.systemctl,
                    ("--user", "kill", "--kill-whom=all", "--signal=KILL", name),
                )
            self._client.run(
                self._client.systemctl, ("--user", "stop", "--no-block", name),
            )
            for _attempt in range(50):
                if not self._scope_active(name):
                    break
                self._sleep(0.1)
            if self._scope_active(name):
                raise RuntimeError("process scope remained active after bounded kill")
            self._client.run(
                self._client.systemctl,
                ("--user", "reset-failed", name),
            )
            wrapper = self._wrappers.pop(unit, None)
            if wrapper is not None:
                try:
                    wrapper.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    wrapper.kill(); wrapper.wait(timeout=5)

    def _scope_active(self, name):
        result = self._client.run(
            self._client.systemctl, ("--user", "is-active", "--quiet", name),
        )
        return result.exit_code == 0

    def _validate(self, plan, root, permit, *, launching):
        if root != Path(plan.candidate_root) or root.is_symlink() or not root.is_dir():
            raise PermissionError("process candidate root is invalid")
        if permit.environment_id != plan.environment_id or permit.exact_host_id != plan.exact_host_id:
            raise PermissionError("process permit identity is invalid")
        if launching and not permit.issued_at <= self._clock() < permit.expires_at:
            raise PermissionError("process permit is expired")
        if (
            plan.network_mode is IntegrationNetworkMode.ALLOWLIST
            and not self._network.available
        ):
            raise PermissionError("process allowlisted egress broker is unavailable")
        if any(item.volumes for item in plan.services):
            raise PermissionError("process volumes are unsupported")
        kinds = {
            IntegrationServiceKind.PROCESS, IntegrationServiceKind.API,
            IntegrationServiceKind.BROWSER,
        }
        if any(item.kind not in kinds for item in plan.services):
            raise PermissionError("process adapter accepts process API and browser services only")
        if any(any(port.requested_host_port == 0 for port in item.ports) for item in plan.services):
            raise PermissionError("process ports must be allocated before admission")
        ports = [port.requested_host_port for item in plan.services for port in item.ports]
        if len(ports) != len(set(ports)):
            raise PermissionError("process host ports must be unique")

    @staticmethod
    def _require_live(control):
        if control.cancelled() or not control.authorization_active():
            raise PermissionError("process environment was cancelled or revoked")


def _network_evidence(usage):
    if usage is None: return ()
    state = "network-finalized:" if usage.finalized else "network-observed:"
    return (state + usage.enforcement_id,)
