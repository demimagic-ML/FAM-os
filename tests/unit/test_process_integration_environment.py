import tempfile
import base64
import unittest
from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace

from fam_os.adapters.integration.process_client import ProcessCommandResult
from fam_os.adapters.integration.process_environment import ProcessIntegrationEnvironmentAdapter
from fam_os.core.engineering import (
    EngineeringAuthority, IntegrationEnvironmentStatus, IntegrationHealthKind, IntegrationNetworkMode,
    IntegrationServiceKind, IntegrationNetworkAttachment,
    IntegrationNetworkAttachmentKind, IntegrationNetworkEnforcementRequest,
    IntegrationNetworkLease, IntegrationNetworkUsage,
    integration_environment_plan_digest,
)
from tests.contract.schema_integration_environment_fixtures import (
    NOW, integration_environment_schema_values,
)


class Recipes:
    def __init__(self, arguments):
        self.recipe = SimpleNamespace(
            executable_path="/usr/bin/python3", argv_template=arguments,
            toolchain_mounts=(),
        )

    def get(self, recipe_id, version):
        if (recipe_id, version) != ("integration.api", "1.0.0"):
            raise LookupError
        return self.recipe


class Client:
    systemd_run = Path("/usr/bin/systemd-run")
    systemctl = Path("/usr/bin/systemctl")
    bubblewrap = Path("/usr/bin/bwrap")

    def __init__(self): self.calls = []; self.scope_active = True

    def run(self, executable, arguments):
        self.calls.append((executable, arguments))
        if "kill" in arguments:
            self.scope_active = False
        if "is-active" in arguments:
            return ProcessCommandResult(0 if self.scope_active else 3, "")
        return ProcessCommandResult(0, "active")

    def start_scope(self, arguments):
        self.calls.append((self.systemd_run, arguments))
        return Wrapper()


class Wrapper:
    def wait(self, timeout=None): return 0
    def kill(self): pass


class Control:
    def __init__(self, active=True): self.active = active
    def cancelled(self): return False
    def authorization_active(self): return self.active


class RevokingControl:
    def __init__(self): self.calls = 0
    def cancelled(self): return False
    def authorization_active(self):
        self.calls += 1
        return self.calls == 1


class Secrets:
    def __init__(self, values): self.values = values
    def environment(self, secret_refs, consumer_id): return self.values


class NetworkBroker:
    def __init__(self, request):
        self.calls = []
        self.lease = IntegrationNetworkLease(
            "fam-network-process", request.request_id, request.environment_id,
            request.principal_id, request.session_id, request.authority_ref,
            (IntegrationNetworkAttachment(
                IntegrationNetworkAttachmentKind.LINUX_NAMESPACE,
                "/run/netns/fam-process", "http://[fd42::1]:8080",
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


class OpenResponseLossBroker(NetworkBroker):
    def open(self, request):
        self.calls.append("open")
        raise TimeoutError("deliberate response loss after broker effect")


class ProcessIntegrationEnvironmentTests(unittest.TestCase):
    def setUp(self):
        service, plan, permit, _receipt, _result = integration_environment_schema_values()
        health = replace(
            service.health_check, kind=IntegrationHealthKind.SIGNED_RECIPE,
            port_name=None, path=None, signed_recipe_id="integration.health.v1",
        )
        arguments = ("-c", "import time; time.sleep(60)")
        service = replace(
            service, kind=IntegrationServiceKind.API,
            signed_launch_recipe_id="integration.api@1.0.0",
            launch_arguments=arguments, image_ref=None, image_sha256=None,
            ports=(), volumes=(), health_check=health,
        )
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name).resolve()
        self.plan = replace(
            plan, candidate_root=str(self.root), services=(service,),
            retained_artifact_paths=(), network_mode=IntegrationNetworkMode.ISOLATED,
        )
        self.permit = permit
        self.client = Client()
        self.adapter = ProcessIntegrationEnvironmentAdapter(
            Recipes(arguments), self.client, lambda: NOW,
            iter(("start-1", "cleanup-1")).__next__, lambda _seconds: None,
        )

    def tearDown(self): self.temporary.cleanup()

    def test_signed_exact_recipe_is_systemd_bounded_and_cleanup_is_exact(self):
        (self.root / "result.txt").write_text("verified\n")
        self.plan = replace(self.plan, retained_artifact_paths=("result.txt",))
        receipt = self.adapter.launch(self.plan, self.root, self.permit, Control())
        command = self.client.calls[0][1]
        self.assertIn("--property=IPAddressDeny=any", command)
        self.assertIn("--property=IPAddressAllow=localhost", command)
        self.assertIn(f"--property=MemoryMax={self.plan.maximum_memory_bytes}", command)
        self.assertIn("--property=TimeoutStopSec=3s", command)
        self.assertIn("--unshare-user", command)
        self.assertIn("--clearenv", command)
        cleaned = self.adapter.cleanup(self.plan, receipt, self.root, self.permit)
        self.assertEqual(IntegrationEnvironmentStatus.CLEANED, cleaned.status)
        self.assertEqual("cleanup-1", cleaned.receipt_id)
        self.assertEqual("result.txt", cleaned.retained_artifacts[0].relative_path)
        self.assertTrue(cleaned.cleanup_evidence_ids[0].startswith("stopped-unit:"))

    def test_recipe_substitution_revocation_and_allowlist_fail_before_effect(self):
        bad_service = replace(self.plan.services[0], launch_arguments=("--version",))
        with self.assertRaisesRegex(PermissionError, "signed recipe"):
            self.adapter.launch(
                replace(self.plan, services=(bad_service,)), self.root,
                self.permit, Control(),
            )
        self.assertEqual([], self.client.calls)
        other = tempfile.TemporaryDirectory(); self.addCleanup(other.cleanup)
        other_root = Path(other.name).resolve()
        with self.assertRaisesRegex(PermissionError, "cancelled or revoked"):
            self.adapter.launch(
                replace(self.plan, environment_id="other", candidate_root=str(other_root)),
                other_root, replace(self.permit, environment_id="other"), Control(False),
            )
        with self.assertRaisesRegex(PermissionError, "allowlisted"):
            self.adapter.launch(
                replace(
                    self.plan, network_mode=IntegrationNetworkMode.ALLOWLIST,
                    network_hosts=("example.invalid:443",),
                    required_authorities=(
                        EngineeringAuthority.EXECUTE, EngineeringAuthority.NETWORK,
                    ),
                ), self.root, self.permit, Control(),
            )

    def test_allowlisted_process_uses_broker_namespace_and_final_accounting(self):
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
            (IntegrationNetworkAttachmentKind.LINUX_NAMESPACE,),
            plan.network_hosts, plan.resource_impact.max_network_bytes,
            self.permit.expires_at,
        )
        permit = replace(self.permit, network_request=request)
        broker = NetworkBroker(request)
        adapter = ProcessIntegrationEnvironmentAdapter(
            Recipes(plan.services[0].launch_arguments), self.client, lambda: NOW,
            iter(("start-network", "cleanup-network")).__next__,
            lambda _seconds: None, network=broker,
        )
        receipt = adapter.launch(plan, self.root, permit, Control())
        command = self.client.calls[0][1]
        self.assertIn(
            "--property=NetworkNamespacePath=/run/netns/fam-process", command,
        )
        self.assertIn("HTTPS_PROXY", command)
        self.assertNotIn("--property=IPAddressDeny=any", command)
        self.assertEqual(broker.live, receipt.network_usage)
        cleaned = adapter.cleanup(plan, receipt, self.root, permit)
        self.assertEqual(broker.final, cleaned.network_usage)
        self.assertEqual(["open", "observe", "close"], broker.calls)
        self.assertIn(
            "network-finalized:fam-network-process",
            cleaned.cleanup_evidence_ids,
        )

    def test_network_open_response_loss_recovers_from_durable_opening_intent(self):
        plan = replace(
            self.plan, network_mode=IntegrationNetworkMode.ALLOWLIST,
            network_hosts=("registry.example:443",),
            required_authorities=(
                EngineeringAuthority.EXECUTE, EngineeringAuthority.NETWORK,
            ),
        )
        request = IntegrationNetworkEnforcementRequest(
            "network-request-loss", plan.environment_id, self.permit.permit_id,
            plan.exact_host_id, "fam-core", "session-1", "authority-1",
            "device-key-1", base64.b64encode(b"\0" * 64).decode(),
            integration_environment_plan_digest(plan),
            (IntegrationNetworkAttachmentKind.LINUX_NAMESPACE,),
            plan.network_hosts, plan.resource_impact.max_network_bytes,
            self.permit.expires_at,
        )
        broker = OpenResponseLossBroker(request)
        adapter = ProcessIntegrationEnvironmentAdapter(
            Recipes(plan.services[0].launch_arguments), self.client,
            lambda: NOW, lambda: "unused", lambda _seconds: None,
            network=broker,
        )
        with self.assertRaisesRegex(TimeoutError, "response loss"):
            adapter.launch(
                plan, self.root, replace(self.permit, network_request=request),
                Control(),
            )
        self.assertEqual(["open", "recover"], broker.calls)
        self.assertEqual([], self.client.calls)

    def test_substituted_plan_digest_is_denied_before_broker_intent(self):
        plan = replace(
            self.plan, network_mode=IntegrationNetworkMode.ALLOWLIST,
            network_hosts=("registry.example:443",),
            required_authorities=(
                EngineeringAuthority.EXECUTE, EngineeringAuthority.NETWORK,
            ),
        )
        request = IntegrationNetworkEnforcementRequest(
            "network-request-substituted", plan.environment_id,
            self.permit.permit_id, plan.exact_host_id, "fam-core", "session-1",
            "authority-1", "device-key-1",
            base64.b64encode(b"\0" * 64).decode(), "f" * 64,
            (IntegrationNetworkAttachmentKind.LINUX_NAMESPACE,),
            plan.network_hosts, plan.resource_impact.max_network_bytes,
            self.permit.expires_at,
        )
        broker = NetworkBroker(request)
        adapter = ProcessIntegrationEnvironmentAdapter(
            Recipes(plan.services[0].launch_arguments), self.client,
            lambda: NOW, lambda: "unused", lambda _seconds: None,
            network=broker,
        )
        with self.assertRaisesRegex(PermissionError, "differs from plan"):
            adapter.launch(
                plan, self.root, replace(self.permit, network_request=request),
                Control(),
            )
        self.assertEqual([], broker.calls)

    def test_secret_is_file_only_restart_cleanable_and_never_in_command(self):
        service = replace(self.plan.services[0], secret_refs=("secret.api",))
        plan = replace(
            self.plan, services=(service,), required_authorities=(
                EngineeringAuthority.EXECUTE, EngineeringAuthority.SECRET_USE,
            ),
        )
        adapter = ProcessIntegrationEnvironmentAdapter(
            Recipes(service.launch_arguments), self.client, lambda: NOW,
            lambda: "start-secret", lambda _seconds: None,
            secrets=Secrets({"API_TOKEN": "protected-value"}),
        )
        adapter.launch(plan, self.root, self.permit, Control())
        command = self.client.calls[0][1]
        rendered = " ".join(str(item) for item in command)
        self.assertNotIn("protected-value", rendered)
        self.assertIn("API_TOKEN_FILE", command)
        self.assertIn("/workspace/.fam/secret-injection", command)
        roots = tuple((self.root / ".fam/secret-injection").glob("process-*"))
        self.assertEqual(1, len(roots))
        self.assertEqual("protected-value", (roots[0] / "API_TOKEN").read_text())

        restarted = ProcessIntegrationEnvironmentAdapter(
            Recipes(service.launch_arguments), self.client, lambda: NOW,
            lambda: "reconciled-secret", lambda _seconds: None,
            secrets=Secrets({}),
        )
        cleaned = restarted.reconcile(plan, self.root, self.permit)
        self.assertFalse(roots[0].exists())
        self.assertTrue(any(
            item.startswith("removed-secret-root:")
            for item in cleaned.cleanup_evidence_ids
        ))

    def test_invalid_secret_and_post_launch_revocation_leave_no_secret_root(self):
        service = replace(self.plan.services[0], secret_refs=("secret.api",))
        plan = replace(
            self.plan, services=(service,), required_authorities=(
                EngineeringAuthority.EXECUTE, EngineeringAuthority.SECRET_USE,
            ),
        )
        adapter = ProcessIntegrationEnvironmentAdapter(
            Recipes(service.launch_arguments), self.client, lambda: NOW,
            lambda: "unused", lambda _seconds: None,
            secrets=Secrets({"LD_PRELOAD": "hostile"}),
        )
        with self.assertRaisesRegex(PermissionError, "secret injection"):
            adapter.launch(plan, self.root, self.permit, Control())
        self.assertEqual([], self.client.calls)
        self.assertEqual([], list((self.root / ".fam/secret-injection").glob("process-*")))

    def test_post_launch_revocation_stops_scope_and_erases_secret_root(self):
        service = replace(self.plan.services[0], secret_refs=("secret.api",))
        plan = replace(
            self.plan, services=(service,), required_authorities=(
                EngineeringAuthority.EXECUTE, EngineeringAuthority.SECRET_USE,
            ),
        )
        adapter = ProcessIntegrationEnvironmentAdapter(
            Recipes(service.launch_arguments), self.client, lambda: NOW,
            lambda: "unused", lambda _seconds: None,
            secrets=Secrets({"API_TOKEN": "protected-value"}),
        )

        with self.assertRaisesRegex(PermissionError, "cancelled or revoked"):
            adapter.launch(plan, self.root, self.permit, RevokingControl())

        self.assertTrue(any("kill" in call[1] for call in self.client.calls))
        self.assertEqual([], list((self.root / ".fam/secret-injection").glob("process-*")))


if __name__ == "__main__": unittest.main()
