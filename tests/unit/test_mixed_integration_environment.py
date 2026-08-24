import base64
import tempfile
import unittest
import json
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path

from fam_os.adapters.integration import IntegrationEnvironmentExecutorRouter
from fam_os.adapters.integration.composite_state import CompositeEnvironmentState
from fam_os.core.engineering import (
    EngineeringAuthority, IntegrationEnvironmentReceipt,
    IntegrationEnvironmentStatus, IntegrationServiceKind,
    IntegrationServiceReceipt, IntegrationNetworkMode,
    IntegrationNetworkAttachment, IntegrationNetworkAttachmentKind,
    IntegrationNetworkEnforcementRequest, IntegrationNetworkLease,
    IntegrationNetworkUsage, integration_environment_plan_digest,
)
from tests.contract.schema_integration_environment_fixtures import (
    integration_environment_schema_values,
)


NOW = datetime(2026, 7, 19, tzinfo=timezone.utc)


class Backend:
    def __init__(self, name, calls, *, fail_launch=False, fail_cleanup=False):
        self.name = name
        self.calls = calls
        self.fail_launch = fail_launch
        self.fail_cleanup = fail_cleanup
        self.plans = []
        self.permits = []

    def launch(self, plan, root, permit, control):
        self.plans.append(plan)
        self.permits.append(permit)
        self.calls.append(("launch", self.name, tuple(
            item.service_id for item in plan.services
        )))
        if self.fail_launch:
            raise RuntimeError(self.name + " launch failed")
        services = tuple(
            IntegrationServiceReceipt(
                item.service_id, self.name + ":" + item.service_id,
                item.image_sha256, (), "health:" + item.service_id, None,
            )
            for item in plan.services
        )
        return IntegrationEnvironmentReceipt(
            self.name + "-started", plan.environment_id, permit.permit_id,
            IntegrationEnvironmentStatus.READY, NOW, NOW, services, (), (),
        )

    def cleanup(self, plan, receipt, root, permit):
        self.calls.append(("cleanup", self.name, tuple(
            item.service_id for item in plan.services
        )))
        if self.fail_cleanup:
            raise RuntimeError(self.name + " cleanup failed")
        return replace(
            receipt, receipt_id=self.name + "-cleaned",
            status=IntegrationEnvironmentStatus.CLEANED,
            cleanup_evidence_ids=("cleaned:" + self.name,),
        )

    def reconcile(self, plan, root, permit):
        self.calls.append(("reconcile", self.name, tuple(
            item.service_id for item in plan.services
        )))
        if self.fail_cleanup:
            raise RuntimeError(self.name + " reconcile failed")
        return IntegrationEnvironmentReceipt(
            self.name + "-reconciled", plan.environment_id, permit.permit_id,
            IntegrationEnvironmentStatus.CLEANED, NOW, NOW, (), (),
            ("reconciled:" + self.name,),
        )

    def recover(self, plan, root, permit):
        self.calls.append(("recover", self.name, tuple(
            item.service_id for item in plan.services
        )))
        return IntegrationEnvironmentReceipt(
            self.name + "-recovered", plan.environment_id, permit.permit_id,
            IntegrationEnvironmentStatus.CLEANED, NOW, NOW, (), (),
            ("recovered:" + self.name,),
        )


class Control:
    def cancelled(self): return False
    def authorization_active(self): return True


class Broker:
    def __init__(self, request):
        self.calls = []
        self.lease = IntegrationNetworkLease(
            "fam-network-mixed", request.request_id, request.environment_id,
            request.principal_id, request.session_id, request.authority_ref,
            (
                IntegrationNetworkAttachment(
                    IntegrationNetworkAttachmentKind.DOCKER_INTERNAL_NETWORK,
                    "docker-network", "http://[fd43::1]:8000",
                ),
                IntegrationNetworkAttachment(
                    IntegrationNetworkAttachmentKind.LINUX_NAMESPACE,
                    "/run/netns/fam-mixed", "http://[fd42::1]:8001",
                ),
            ), request.destinations, request.maximum_network_bytes,
            NOW, request.expires_at, "b" * 64,
        )
        self.live = IntegrationNetworkUsage(
            self.lease.enforcement_id, request.environment_id, (), 0, 0,
            request.maximum_network_bytes, False, False, NOW, "c" * 64,
        )
        self.final = replace(self.live, finalized=True, evidence_sha256="d" * 64)

    def open(self, request): self.calls.append("open"); return self.lease
    def observe(self, lease): self.calls.append("observe"); return self.live
    def close(self, lease): self.calls.append("close"); return self.final
    def recover(self, request): self.calls.append("recover"); return self.final


class MixedIntegrationEnvironmentTests(unittest.TestCase):
    def setUp(self):
        service, plan, self.permit, _receipt, _result = (
            integration_environment_schema_values()
        )
        self.container_id = service.service_id
        process = replace(
            service, service_id="api", kind=IntegrationServiceKind.API,
            signed_launch_recipe_id="api@1", launch_arguments=("--serve",),
            image_ref=None, image_sha256=None, volumes=(),
            dependency_ids=(service.service_id,),
        )
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.plan = replace(
            plan, candidate_root=str(self.root), services=(service, process),
            resource_impact=replace(plan.resource_impact, max_processes=2),
            retained_artifact_paths=(),
        )
        self.calls = []

    def tearDown(self):
        self.temporary.cleanup()

    def router(self, *, process_launch=False, process_cleanup=False):
        return IntegrationEnvironmentExecutorRouter(
            docker=Backend("docker", self.calls),
            process=Backend(
                "process", self.calls, fail_launch=process_launch,
                fail_cleanup=process_cleanup,
            ),
        )

    def test_dependency_order_launches_and_reverse_cleans_both_backends(self):
        router = self.router()
        receipt = router.launch(self.plan, self.root, self.permit, Control())
        self.assertEqual((self.container_id, "api"), tuple(
            item.service_id for item in receipt.services
        ))
        cleaned = router.cleanup(self.plan, receipt, self.root, self.permit)
        self.assertEqual("cleaned", cleaned.status.value)
        self.assertEqual(
            ["launch", "launch", "cleanup", "cleanup"],
            [item[0] for item in self.calls],
        )
        self.assertEqual(
            ["docker", "process", "process", "docker"],
            [item[1] for item in self.calls],
        )
        self.assertEqual(
            ("cleaned:process", "cleaned:docker"),
            cleaned.cleanup_evidence_ids,
        )
        plans = (router.docker.plans[0], router.process.plans[0])
        self.assertEqual(
            self.plan.maximum_memory_bytes,
            sum(item.maximum_memory_bytes for item in plans),
        )
        self.assertEqual(
            self.plan.maximum_cpu_millis_per_second,
            sum(item.maximum_cpu_millis_per_second for item in plans),
        )
        self.assertEqual(
            self.plan.resource_impact.max_processes,
            sum(item.resource_impact.max_processes for item in plans),
        )

    def test_second_backend_launch_failure_compensates_first(self):
        router = self.router(process_launch=True)
        with self.assertRaisesRegex(RuntimeError, "process launch failed"):
            router.launch(self.plan, self.root, self.permit, Control())
        self.assertEqual(
            [("launch", "docker"), ("launch", "process"), ("cleanup", "docker")],
            [(item[0], item[1]) for item in self.calls],
        )

    def test_allowlisted_mixed_environment_uses_one_shared_broker_lease(self):
        plan = replace(
            self.plan, network_mode=IntegrationNetworkMode.ALLOWLIST,
            network_hosts=("registry.example:443",),
            required_authorities=(
                EngineeringAuthority.EXECUTE, EngineeringAuthority.NETWORK,
            ),
        )
        request = IntegrationNetworkEnforcementRequest(
            "network-request-1", plan.environment_id, self.permit.permit_id,
            plan.exact_host_id, "fam-core", "session-1", "authority-1",
            "device-key-1", base64.b64encode(b"\0" * 64).decode(),
            integration_environment_plan_digest(plan),
            (
                IntegrationNetworkAttachmentKind.DOCKER_INTERNAL_NETWORK,
                IntegrationNetworkAttachmentKind.LINUX_NAMESPACE,
            ), plan.network_hosts, plan.resource_impact.max_network_bytes,
            self.permit.expires_at,
        )
        permit = replace(self.permit, network_request=request)
        broker = Broker(request)
        router = IntegrationEnvironmentExecutorRouter(
            docker=Backend("docker", self.calls),
            process=Backend("process", self.calls), network=broker,
        )
        receipt = router.launch(plan, self.root, permit, Control())
        self.assertEqual(broker.live, receipt.network_usage)
        self.assertIs(broker.lease, router.docker.permits[0].network_lease)
        self.assertIs(broker.lease, router.process.permits[0].network_lease)
        cleaned = router.cleanup(plan, receipt, self.root, permit)
        self.assertEqual(broker.final, cleaned.network_usage)
        self.assertEqual(["open", "observe", "close"], broker.calls)
        self.assertIn(
            "network-finalized:fam-network-mixed",
            cleaned.cleanup_evidence_ids,
        )

    def test_partial_cleanup_is_journaled_and_reconcile_resumes_only_remaining(self):
        router = self.router(process_cleanup=True)
        receipt = router.launch(self.plan, self.root, self.permit, Control())
        with self.assertRaisesRegex(RuntimeError, "cleanup is incomplete"):
            router.cleanup(self.plan, receipt, self.root, self.permit)
        router.process.fail_cleanup = False
        recovered = router.reconcile(self.plan, self.root, self.permit)
        self.assertEqual(
            ("cleaned:docker", "reconciled:process"),
            recovered.cleanup_evidence_ids,
        )
        self.assertEqual(1, sum(
            item[:2] == ("cleanup", "docker") for item in self.calls
        ))

    def test_cross_backend_group_cycle_and_journal_tamper_fail_closed(self):
        container, process = self.plan.services
        second_container = replace(
            container, service_id="second-container",
            dependency_ids=(process.service_id,), volumes=(),
        )
        interleaved = replace(
            self.plan, services=(container, process, second_container),
            resource_impact=replace(
                self.plan.resource_impact, max_processes=3,
            ),
        )
        with self.assertRaisesRegex(PermissionError, "cross-backend"):
            self.router().launch(interleaved, self.root, self.permit, Control())

        router = self.router()
        receipt = router.launch(self.plan, self.root, self.permit, Control())
        state = self.root / ".fam/integration" / (
            "composite-" + self.plan.environment_id + ".json"
        )
        document = json.loads(state.read_text(encoding="utf-8"))
        document["backend_order"].reverse()
        state.write_text(json.dumps(document), encoding="utf-8")
        with self.assertRaisesRegex(PermissionError, "order does not match"):
            router.cleanup(self.plan, receipt, self.root, self.permit)
        document["backend_order"].reverse()
        document["launched_backends"].pop()
        state.write_text(json.dumps(document), encoding="utf-8")
        with self.assertRaisesRegex(PermissionError, "launch evidence is incomplete"):
            router.cleanup(self.plan, receipt, self.root, self.permit)
        self.assertFalse(any(item[0] == "cleanup" for item in self.calls))

    def test_claimed_pre_result_journal_recovers_every_deterministic_backend(self):
        state = CompositeEnvironmentState(self.root, self.plan.environment_id)
        state.claim(("docker", "process"))
        recovered = self.router().recover(
            self.plan, self.root, self.permit,
        )
        self.assertEqual(
            ("recovered:process", "recovered:docker"),
            recovered.cleanup_evidence_ids,
        )
        self.assertEqual(
            [("recover", "process"), ("recover", "docker")],
            [(item[0], item[1]) for item in self.calls],
        )
        self.assertTrue(state.load()["terminal"])


if __name__ == "__main__":
    unittest.main()
