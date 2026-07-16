import unittest

from fam_os.core.activation import ActivationProbeStatus, ExpertActivationProbe
from fam_os.core.contracts import TaskRequest
from fam_os.core.execution.placement import PlacementExecutor
from fam_os.core.execution.policy import GenerationSettings
from fam_os.experts import ExpertTier
from fam_os.routing import RouteName

from tests.unit.execution_fakes import (
    FakeCatalog,
    FakePlanner,
    FakeRouter,
    FakeRuntime,
    expert,
    plan,
)


class ExpertActivationProbeTests(unittest.TestCase):
    def test_records_unverified_activation_without_task_result(self) -> None:
        router_expert = expert("router", "router:model", ExpertTier.MICRO)
        code_expert = expert("code", "code:model", ExpertTier.ECONOMICAL)
        runtime = FakeRuntime(["unverified candidate"])
        catalog = FakeCatalog((router_expert, code_expert))
        planner = FakePlanner((plan("code", ("router",)),))
        placement = PlacementExecutor(runtime, catalog, planner)
        probe = ExpertActivationProbe(runtime, FakeRouter(), catalog, placement)

        outcome = probe.execute(
            TaskRequest("request-1", "build it"),
            "code",
            GenerationSettings(384),
        )

        self.assertEqual(outcome.status, ActivationProbeStatus.ACTIVATED)
        self.assertEqual(outcome.candidate, "unverified candidate")
        self.assertEqual(outcome.evicted_expert_ids, ("router",))
        self.assertEqual(runtime.unloaded, ["router:model"])
        self.assertEqual(runtime.requests[0].model_ref, "code:model")
        self.assertFalse(hasattr(outcome, "result"))

    def test_non_code_route_does_not_activate_or_plan(self) -> None:
        code_expert = expert("code", "code:model", ExpertTier.ECONOMICAL)
        runtime = FakeRuntime([])
        catalog = FakeCatalog((code_expert,))
        planner = FakePlanner((plan("code"),))
        placement = PlacementExecutor(runtime, catalog, planner)
        probe = ExpertActivationProbe(
            runtime,
            FakeRouter(RouteName.RETRIEVAL),
            catalog,
            placement,
        )

        outcome = probe.execute(
            TaskRequest("request-1", "inspect files"),
            "code",
            GenerationSettings(384),
        )

        self.assertEqual(outcome.status, ActivationProbeStatus.ROUTE_NOT_SUPPORTED)
        self.assertEqual(runtime.requests, [])
        self.assertEqual(planner.requested, [])


if __name__ == "__main__":
    unittest.main()
