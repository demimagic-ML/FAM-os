import unittest

from fam_os.supervisor import (
    ConstrainedServiceLifecycle,
    CountCeiling,
    CpuQuotaCeiling,
    InMemoryServiceOwnershipRegistry,
    OwnedServiceLifecycle,
    ResourceCeiling,
    ResourceLimits,
    ResourceSnapshot,
    ServiceDefinition,
    ServiceState,
    ServiceStatus,
    SupervisorAuthorizationError,
    SupervisorCallContext,
    SupervisorCapability,
)


class FakeLifecycle:
    def __init__(self) -> None:
        self.state = ServiceState.UNKNOWN
        self.starts = 0
        self.stops = 0

    def start(self, definition) -> ServiceStatus:
        self.starts += 1
        self.state = ServiceState.ACTIVE
        return self.status(definition.service_id)

    def stop(self, service_id) -> ServiceStatus:
        self.stops += 1
        self.state = ServiceState.INACTIVE
        return self.status(service_id)

    def status(self, service_id) -> ServiceStatus:
        return ServiceStatus(service_id, self.state)


class FakeAuthorizer:
    def __init__(self) -> None:
        self.denied: set[SupervisorCapability] = set()

    def require(self, context, capability, service_id) -> None:
        if capability in self.denied:
            raise SupervisorAuthorizationError("denied")


class FakeObserver:
    def __init__(self, value: ResourceSnapshot | None) -> None:
        self.value = value

    def observe(self, service_id: str) -> ResourceSnapshot | None:
        return self.value


def context() -> SupervisorCallContext:
    return SupervisorCallContext("request", "principal", "session", "authority")


def definition() -> ServiceDefinition:
    return ServiceDefinition(
        "fam-constrained",
        ("/usr/bin/sleep", "10"),
        limits=ResourceLimits(64, 0, 25.0, 8),
    )


def observed(memory: int = 64) -> ResourceSnapshot:
    return ResourceSnapshot(
        "fam-constrained",
        memory_limit=ResourceCeiling(memory),
        swap_limit=ResourceCeiling(0),
        cpu_quota=CpuQuotaCeiling(25.0),
        tasks_limit=CountCeiling(8),
    )


class ConstrainedServiceLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = FakeLifecycle()
        self.authorizer = FakeAuthorizer()
        owned = OwnedServiceLifecycle(
            self.adapter, self.authorizer, InMemoryServiceOwnershipRegistry()
        )
        self.owned = owned

    def test_reports_constrained_only_after_exact_observation(self) -> None:
        use_case = ConstrainedServiceLifecycle(self.owned, FakeObserver(observed()))
        outcome = use_case.start(context(), definition())
        self.assertTrue(outcome.constrained)
        self.assertIsNone(outcome.cleanup_status)
        self.assertEqual(0, self.adapter.stops)

    def test_mismatch_rolls_back_started_service(self) -> None:
        use_case = ConstrainedServiceLifecycle(
            self.owned, FakeObserver(observed(memory=128))
        )
        outcome = use_case.start(context(), definition())
        self.assertFalse(outcome.constrained)
        self.assertEqual(ServiceState.INACTIVE, outcome.cleanup_status.state)
        self.assertEqual(1, self.adapter.stops)

    def test_limit_authority_is_required_before_start(self) -> None:
        self.authorizer.denied.add(
            SupervisorCapability.APPLY_SERVICE_RESOURCE_LIMITS
        )
        use_case = ConstrainedServiceLifecycle(self.owned, FakeObserver(observed()))
        with self.assertRaises(SupervisorAuthorizationError):
            use_case.start(context(), definition())
        self.assertEqual(0, self.adapter.starts)


if __name__ == "__main__":
    unittest.main()
