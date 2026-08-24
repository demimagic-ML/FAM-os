import unittest
from dataclasses import replace

from fam_os.core.engineering import (
    EngineeringAuthority,
    IntegrationEnvironmentStatus,
    IntegrationHealthKind,
    IntegrationNetworkMode,
    IntegrationNetworkUsage,
    IntegrationPortBinding,
    IntegrationServiceReceipt,
)
from tests.contract.schema_integration_environment_fixtures import (
    integration_environment_schema_values,
)


class IntegrationEnvironmentContractTests(unittest.TestCase):
    def setUp(self):
        self.service, self.plan, self.permit, self.receipt, self.start_result = (
            integration_environment_schema_values()
        )

    def test_loopback_and_digest_bound_service_is_valid(self):
        self.assertEqual("127.0.0.1", self.service.ports[0].host_address)
        self.assertEqual((EngineeringAuthority.EXECUTE,), self.plan.required_authorities)
        self.assertEqual(self.plan.environment_id, self.start_result.environment_id)
        self.assertEqual(self.permit, self.start_result.permit)
        self.assertEqual(self.receipt, self.start_result.receipt)

    def test_non_loopback_port_and_unpinned_image_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "loopback"):
            replace(
                self.service.ports[0], host_address="0.0.0.0",
            )
        with self.assertRaises(ValueError):
            replace(self.service, image_sha256=None)

    def test_network_hosts_require_allowlist_and_exact_authority(self):
        with self.assertRaisesRegex(ValueError, "allowlist"):
            replace(self.plan, network_hosts=("example.invalid:443",))
        with self.assertRaisesRegex(ValueError, "authorities"):
            replace(
                self.plan, network_mode=IntegrationNetworkMode.ALLOWLIST,
                network_hosts=("example.invalid:443",),
            )
        with self.assertRaisesRegex(ValueError, "positive network byte budget"):
            replace(
                self.plan, network_mode=IntegrationNetworkMode.ALLOWLIST,
                network_hosts=("example.invalid:443",),
                required_authorities=(
                    EngineeringAuthority.EXECUTE, EngineeringAuthority.NETWORK,
                ),
                resource_impact=replace(
                    self.plan.resource_impact, max_network_bytes=0,
                ),
            )

    def test_network_usage_is_strict_and_bounded(self):
        usage = IntegrationNetworkUsage(
            "broker-1", self.plan.environment_id, ("registry.example:443",),
            100, 200, 1_000, False, False, self.receipt.completed_at,
            "c" * 64,
        )
        self.assertEqual(300, usage.transmitted_bytes + usage.received_bytes)
        with self.assertRaisesRegex(ValueError, "exceeds"):
            replace(usage, received_bytes=901)
        with self.assertRaisesRegex(ValueError, "must be finalized"):
            replace(usage, quota_exceeded=True)

    def test_allowlist_requires_canonical_host_and_explicit_port(self):
        base = dict(
            network_mode=IntegrationNetworkMode.ALLOWLIST,
            required_authorities=(
                EngineeringAuthority.EXECUTE, EngineeringAuthority.NETWORK,
            ),
        )
        for endpoint in (
            "registry.example", "Registry.example:443", "registry.example:0",
            "registry.example:65536", "user@registry.example:443",
        ):
            with self.subTest(endpoint=endpoint), self.assertRaises(ValueError):
                replace(self.plan, network_hosts=(endpoint,), **base)
        accepted = replace(
            self.plan, network_hosts=("registry.example:443",), **base,
        )
        self.assertEqual(("registry.example:443",), accepted.network_hosts)

    def test_dependency_cycle_and_bad_health_port_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "dependency"):
            replace(self.plan, services=(replace(
                self.service, dependency_ids=(self.service.service_id,),
            ),))
        with self.assertRaisesRegex(ValueError, "undeclared"):
            replace(
                self.service,
                health_check=replace(
                    self.service.health_check, port_name="missing",
                ),
            )

    def test_receipts_cannot_claim_ready_without_services_or_cleanup_without_evidence(self):
        with self.assertRaisesRegex(ValueError, "requires services"):
            replace(self.receipt, services=())
        with self.assertRaisesRegex(ValueError, "cleanup evidence"):
            replace(
                self.receipt, status=IntegrationEnvironmentStatus.CLEANED,
                services=(IntegrationServiceReceipt(
                    "postgres-1", "runtime-1", "a" * 64, (), "health-1", 0,
                ),),
            )


if __name__ == "__main__":
    unittest.main()
