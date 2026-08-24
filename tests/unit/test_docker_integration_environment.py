import base64
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from fam_os.adapters.integration.docker_client import DockerCommandResult
from fam_os.adapters.integration.docker_environment import (
    DockerIntegrationEnvironmentAdapter,
)
from fam_os.core.engineering import (
    EngineeringAuthority,
    IntegrationEnvironmentStatus,
    IntegrationNetworkMode,
    IntegrationNetworkAttachment, IntegrationNetworkAttachmentKind,
    IntegrationNetworkEnforcementRequest, IntegrationNetworkLease,
    IntegrationNetworkUsage, integration_environment_plan_digest,
)
from tests.contract.schema_integration_environment_fixtures import (
    NOW,
    integration_environment_schema_values,
)


class FakeDockerClient:
    def __init__(self, image_digest="a" * 64):
        self.image_digest = image_digest
        self.calls = []

    def run(self, arguments, **kwargs):
        self.calls.append((arguments, kwargs.get("environment", {})))
        if arguments[:2] == ("network", "create"):
            return DockerCommandResult(0, b"network-runtime\n")
        if arguments[:2] == ("image", "inspect"):
            return DockerCommandResult(0, f"sha256:{self.image_digest}\n".encode())
        if arguments[0] == "run":
            return DockerCommandResult(0, b"container-runtime\n")
        if arguments[0] == "port":
            return DockerCommandResult(0, b"127.0.0.1:49152\n")
        if arguments[:2] in {("rm", "--force"), ("network", "rm")}:
            return DockerCommandResult(0, b"removed\n")
        raise AssertionError(arguments)


class SecretInjector:
    def __init__(self, values=None):
        self.values = values or {}

    def environment(self, secret_refs, consumer_id):
        return self.values


class LiveControl:
    def __init__(self, active=True, cancelled=False):
        self.active = active
        self.is_cancelled = cancelled

    def authorization_active(self):
        return self.active

    def cancelled(self):
        return self.is_cancelled


class NetworkBroker:
    def __init__(self, request):
        self.calls = []
        self.lease = IntegrationNetworkLease(
            "fam-network-docker", request.request_id, request.environment_id,
            request.principal_id, request.session_id, request.authority_ref,
            (IntegrationNetworkAttachment(
                IntegrationNetworkAttachmentKind.DOCKER_INTERNAL_NETWORK,
                "broker-network-1", "http://[fd43::1]:8080",
            ),), request.destinations, request.maximum_network_bytes,
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


class DockerIntegrationEnvironmentTests(unittest.TestCase):
    def setUp(self):
        service, plan, permit, _receipt, _result = integration_environment_schema_values()
        self.service = service
        self.plan = replace(plan, retained_artifact_paths=())
        self.permit = permit
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.plan = replace(self.plan, candidate_root=str(self.root))

    def tearDown(self):
        self.temporary.cleanup()

    def test_digest_pinned_launch_uses_bounded_flags_and_exact_cleanup(self):
        client = FakeDockerClient()
        identifiers = iter(("receipt-1", "cleanup-receipt-1"))
        adapter = DockerIntegrationEnvironmentAdapter(
            SecretInjector(), client, lambda: NOW, lambda: next(identifiers),
            lambda _seconds: None, lambda _host, _port, _timeout: True,
        )
        receipt = adapter.launch(self.plan, self.root, self.permit, LiveControl())
        self.assertEqual(IntegrationEnvironmentStatus.READY, receipt.status)
        run = next(arguments for arguments, _env in client.calls if arguments[0] == "run")
        self.assertIn("--read-only", run)
        self.assertIn("no-new-privileges", run)
        self.assertIn("--pids-limit", run)
        self.assertNotIn("a" * 64, run)
        cleaned = adapter.cleanup(self.plan, receipt, self.root, self.permit)
        self.assertEqual(IntegrationEnvironmentStatus.CLEANED, cleaned.status)
        self.assertEqual("cleanup-receipt-1", cleaned.receipt_id)
        self.assertTrue(cleaned.cleanup_evidence_ids)

    def test_secret_is_environment_only_and_never_an_argument(self):
        service = replace(self.service, secret_refs=("secret.postgres",))
        plan = replace(
            self.plan, services=(service,),
            required_authorities=(
                EngineeringAuthority.EXECUTE, EngineeringAuthority.SECRET_USE,
            ),
        )
        client = FakeDockerClient()
        adapter = DockerIntegrationEnvironmentAdapter(
            SecretInjector({"POSTGRES_PASSWORD": "never-in-command"}),
            client, lambda: NOW, lambda: "receipt-1", lambda _seconds: None,
            lambda _host, _port, _timeout: True,
        )
        adapter.launch(plan, self.root, self.permit, LiveControl())
        arguments, environment = next(
            item for item in client.calls if item[0][0] == "run"
        )
        self.assertIn(
            "POSTGRES_PASSWORD_FILE=/run/fam-secrets/POSTGRES_PASSWORD",
            arguments,
        )
        self.assertNotIn("never-in-command", arguments)
        self.assertNotIn("POSTGRES_PASSWORD", environment)
        self.assertEqual(
            [], list((self.root / ".fam" / "secret-injection").glob("service-*")),
        )

    def test_image_mismatch_cancellation_allowlist_and_replay_fail_closed(self):
        client = FakeDockerClient("b" * 64)
        adapter = DockerIntegrationEnvironmentAdapter(
            SecretInjector(), client, lambda: NOW, lambda: "receipt-1",
            lambda _seconds: None, lambda _host, _port, _timeout: True,
        )
        with self.assertRaisesRegex(PermissionError, "digest"):
            adapter.launch(self.plan, self.root, self.permit, LiveControl())
        self.assertTrue(any(call[0][:2] == ("network", "rm") for call in client.calls))
        with self.assertRaises(FileExistsError):
            adapter.launch(self.plan, self.root, self.permit, LiveControl())
        other_root = self.root / "other"
        other_root.mkdir()
        other_plan = replace(
            self.plan, candidate_root=str(other_root),
            network_mode=IntegrationNetworkMode.ALLOWLIST,
            network_hosts=("example.invalid:443",),
            required_authorities=(
                EngineeringAuthority.EXECUTE, EngineeringAuthority.NETWORK,
            ),
        )
        with self.assertRaisesRegex(PermissionError, "broker is unavailable"):
            adapter.launch(other_plan, other_root, self.permit, LiveControl())

    def test_allowlisted_docker_uses_broker_network_and_final_accounting(self):
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
            (IntegrationNetworkAttachmentKind.DOCKER_INTERNAL_NETWORK,),
            plan.network_hosts, plan.resource_impact.max_network_bytes,
            self.permit.expires_at,
        )
        permit = replace(self.permit, network_request=request)
        broker, client = NetworkBroker(request), FakeDockerClient()
        identifiers = iter(("network-start", "network-cleanup"))
        adapter = DockerIntegrationEnvironmentAdapter(
            SecretInjector(), client, lambda: NOW, lambda: next(identifiers),
            lambda _seconds: None, lambda *_args: True, network=broker,
        )
        receipt = adapter.launch(plan, self.root, permit, LiveControl())
        run = next(arguments for arguments, _env in client.calls if arguments[0] == "run")
        self.assertEqual("broker-network-1", run[run.index("--network") + 1])
        self.assertIn("HTTPS_PROXY=http://[fd43::1]:8080", run)
        self.assertEqual(broker.live, receipt.network_usage)
        cleaned = adapter.cleanup(plan, receipt, self.root, permit)
        self.assertEqual(broker.final, cleaned.network_usage)
        self.assertEqual(["open", "observe", "close"], broker.calls)
        self.assertFalse(any(call[0][:2] == ("network", "rm") for call in client.calls))

    def test_revocation_after_network_creation_cleans_partial_resources(self):
        client = FakeDockerClient()
        adapter = DockerIntegrationEnvironmentAdapter(
            SecretInjector(), client, lambda: NOW, lambda: "receipt-1",
            lambda _seconds: None, lambda _host, _port, _timeout: True,
        )
        with self.assertRaisesRegex(PermissionError, "cancelled or revoked"):
            adapter.launch(self.plan, self.root, self.permit, LiveControl(active=False))
        self.assertTrue(any(call[0][:2] == ("network", "rm") for call in client.calls))

    def test_restart_reconciliation_removes_only_recorded_resources(self):
        client = FakeDockerClient()
        adapter = DockerIntegrationEnvironmentAdapter(
            SecretInjector(), client, lambda: NOW, lambda: "receipt-1",
            lambda _seconds: None, lambda _host, _port, _timeout: True,
        )
        adapter.launch(self.plan, self.root, self.permit, LiveControl())
        restarted = DockerIntegrationEnvironmentAdapter(
            SecretInjector(), client, lambda: NOW, lambda: "reconcile-1",
        )
        receipt = restarted.reconcile(self.plan, self.root, self.permit)
        self.assertEqual(IntegrationEnvironmentStatus.CLEANED, receipt.status)
        self.assertTrue(receipt.cleanup_evidence_ids)
        with self.assertRaisesRegex(PermissionError, "already cleaned"):
            restarted.reconcile(self.plan, self.root, self.permit)


if __name__ == "__main__":
    unittest.main()
