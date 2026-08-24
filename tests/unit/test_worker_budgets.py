import unittest

from fam_os.adapters.systemd.commands import build_start_command
from fam_os.adapters.systemd.settings import SystemdUserSettings
from fam_os.product.worker_budgets import (
    WorkerBudgetPolicy,
    WorkerBudgetShare,
    WorkerKind,
    derive_worker_limits,
)
from fam_os.supervisor import ServiceDefinition
from tests.contract.schema_manifest_fixtures import effective_budget


class WorkerBudgetTests(unittest.TestCase):
    def test_full_budget_derives_bounded_worker_cgroups_without_losing_host_headroom(self) -> None:
        budget = effective_budget()
        plans = derive_worker_limits(budget, _policy())
        by_kind = {item.worker_kind: item.limits for item in plans}
        model = by_kind[WorkerKind.MODEL]
        self.assertEqual(int(52 * 1024**3 * .85), model.memory_max_bytes)
        self.assertEqual(2_000, model.cpu_quota_percent)
        self.assertLess(model.memory_high_bytes, model.memory_max_bytes)
        self.assertEqual(budget.memory.swap_limit_bytes, model.swap_max_bytes)
        self.assertGreater(by_kind[WorkerKind.TRAINING].memory_max_bytes, 32 * 1024**3)

    def test_systemd_command_applies_memory_high_and_max(self) -> None:
        limits = derive_worker_limits(effective_budget(), _policy())[0].limits
        command = build_start_command(
            ServiceDefinition("fam-model", ("/bin/true",), limits=limits),
            SystemdUserSettings(),
        )
        self.assertIn(f"--property=MemoryHigh={limits.memory_high_bytes}", command)
        self.assertIn(f"--property=MemoryMax={limits.memory_max_bytes}", command)
        self.assertIn("--property=CPUQuota=2000%", command)
        self.assertIn("--property=TasksMax=512", command)


def _policy() -> WorkerBudgetPolicy:
    return WorkerBudgetPolicy("workers.full.v1", (
        WorkerBudgetShare(WorkerKind.MODEL, .85, .9, 1, 512),
        WorkerBudgetShare(WorkerKind.VERIFIER, .15, .8, .25, 128),
        WorkerBudgetShare(WorkerKind.CONNECTOR, .05, .8, .1, 64),
        WorkerBudgetShare(WorkerKind.TRAINING, .75, .9, .8, 512),
    ))


if __name__ == "__main__":
    unittest.main()
