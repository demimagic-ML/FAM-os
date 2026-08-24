"""Provider-neutral routing across homogeneous integration backends."""

from fam_os.core.engineering import IntegrationServiceKind
from fam_os.adapters.integration.composite_environment import (
    MixedIntegrationEnvironmentAdapter,
)


class IntegrationEnvironmentExecutorRouter:
    def __init__(self, *, docker=None, process=None, network=None) -> None:
        if docker is None and process is None:
            raise ValueError("integration executor router requires a backend")
        self.docker = docker
        self.process = process
        self.mixed = (
            None if docker is None or process is None
            else MixedIntegrationEnvironmentAdapter(
                docker, process, network=network,
            )
        )

    def launch(self, plan, candidate_root, permit, control):
        return self._executor(plan).launch(plan, candidate_root, permit, control)

    def cleanup(self, plan, receipt, candidate_root, permit):
        return self._executor(plan).cleanup(plan, receipt, candidate_root, permit)

    def reconcile(self, plan, candidate_root, permit):
        return self._executor(plan).reconcile(plan, candidate_root, permit)

    def recover(self, plan, candidate_root, permit):
        executor = self._executor(plan)
        recover = getattr(executor, "recover", executor.reconcile)
        return recover(plan, candidate_root, permit)

    def _executor(self, plan):
        kinds = {item.kind for item in plan.services}
        container = {
            IntegrationServiceKind.CONTAINER,
            IntegrationServiceKind.CLUSTER_CONTROL_PLANE,
        }
        process = {
            IntegrationServiceKind.PROCESS, IntegrationServiceKind.API,
            IntegrationServiceKind.BROWSER,
        }
        if kinds <= container and self.docker is not None:
            return self.docker
        if kinds <= process and self.process is not None:
            return self.process
        if kinds & container and kinds & process:
            if self.mixed is not None:
                return self.mixed
            raise PermissionError("mixed integration backends require both executors")
        raise PermissionError("requested integration environment backend is unavailable")
