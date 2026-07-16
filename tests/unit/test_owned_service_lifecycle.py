import unittest

from fam_os.supervisor import (
    InMemoryServiceOwnershipRegistry,
    OwnedServiceLifecycle,
    ServiceDefinition,
    ServiceDefinitionConflictError,
    ServiceOwnershipError,
    ServiceState,
    ServiceStatus,
    SupervisorAuthorizationError,
    SupervisorCallContext,
    SupervisorCapability,
)


class FakeLifecycle:
    def __init__(self) -> None:
        self.states: dict[str, ServiceStatus] = {}
        self.starts = 0
        self.stops = 0

    def start(self, definition: ServiceDefinition) -> ServiceStatus:
        self.starts += 1
        status = ServiceStatus(definition.service_id, ServiceState.ACTIVE)
        self.states[definition.service_id] = status
        return status

    def stop(self, service_id: str) -> ServiceStatus:
        self.stops += 1
        status = ServiceStatus(service_id, ServiceState.INACTIVE)
        self.states[service_id] = status
        return status

    def status(self, service_id: str) -> ServiceStatus:
        return self.states.get(service_id, ServiceStatus(service_id, ServiceState.UNKNOWN))


class FakeAuthorizer:
    def __init__(self) -> None:
        self.denied: set[SupervisorCapability] = set()
        self.calls: list[tuple[SupervisorCapability, str]] = []

    def require(self, context, capability, service_id) -> None:
        self.calls.append((capability, service_id))
        if capability in self.denied:
            raise SupervisorAuthorizationError("capability denied")


def context(principal: str = "principal-1", session: str = "session-1"):
    return SupervisorCallContext("request-1", principal, session, "authority-1")


def definition(command: str = "/usr/bin/sleep") -> ServiceDefinition:
    return ServiceDefinition("fam-owned-service", (command, "10"))


class OwnedServiceLifecycleTests(unittest.TestCase):
    def setUp(self) -> None:
        self.adapter = FakeLifecycle()
        self.authorizer = FakeAuthorizer()
        self.registry = InMemoryServiceOwnershipRegistry()
        self.lifecycle = OwnedServiceLifecycle(
            self.adapter, self.authorizer, self.registry
        )

    def test_start_claims_service_and_is_idempotent_when_active(self) -> None:
        first = self.lifecycle.start(context(), definition())
        second = self.lifecycle.start(context(), definition())
        self.assertEqual(ServiceState.ACTIVE, first.state)
        self.assertEqual(first, second)
        self.assertEqual(1, self.adapter.starts)

    def test_rejects_definition_change_and_cross_owner_access(self) -> None:
        self.lifecycle.start(context(), definition())
        with self.assertRaises(ServiceDefinitionConflictError):
            self.lifecycle.start(context(), definition("/usr/bin/false"))
        with self.assertRaises(ServiceOwnershipError):
            self.lifecycle.status(context("principal-2"), definition().service_id)

    def test_authorization_precedes_claim_and_adapter_access(self) -> None:
        self.authorizer.denied.add(SupervisorCapability.START_UNPRIVILEGED_SERVICE)
        with self.assertRaises(SupervisorAuthorizationError):
            self.lifecycle.start(context(), definition())
        self.assertIsNone(self.registry.get(definition().service_id))
        self.assertEqual(0, self.adapter.starts)

    def test_stop_and_status_require_owner_and_are_idempotent(self) -> None:
        self.lifecycle.start(context(), definition())
        self.assertEqual(
            ServiceState.ACTIVE,
            self.lifecycle.status(context(), definition().service_id).state,
        )
        first = self.lifecycle.stop(context(), definition().service_id)
        second = self.lifecycle.stop(context(), definition().service_id)
        self.assertEqual(ServiceState.INACTIVE, first.state)
        self.assertEqual(first, second)
        self.assertEqual(1, self.adapter.stops)

    def test_unclaimed_arbitrary_service_id_is_never_forwarded(self) -> None:
        with self.assertRaises(ServiceOwnershipError):
            self.lifecycle.stop(context(), "ssh.service")
        self.assertEqual(0, self.adapter.stops)

    def test_cannot_claim_arbitrary_unit_even_when_authorizer_allows_it(self) -> None:
        arbitrary = ServiceDefinition("ssh.service", ("/usr/bin/sleep", "10"))
        with self.assertRaisesRegex(ServiceOwnershipError, "FAM-owned"):
            self.lifecycle.start(context(), arbitrary)
        self.assertEqual(0, self.adapter.starts)


if __name__ == "__main__":
    unittest.main()
