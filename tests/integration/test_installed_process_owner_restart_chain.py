import base64
import hashlib
import os
import socket
import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fam_os.adapters.crypto.engineering_recipes import Ed25519RecipeSignatureVerifier, sign_recipe_specification
from fam_os.adapters.integration import ProcessIntegrationEnvironmentAdapter
from fam_os.adapters.shell import (
    ShellRequestDispatcher, UnixShellClientConfiguration, UnixShellCoreClient,
    UnixShellServer, UnixShellServerConfiguration,
)
from fam_os.applications.transport.auth import PeerAuthorizationPolicy
from fam_os.core.engineering import (
    CandidateWorkspace, EngineeringAuthority, EngineeringAuthorityGrant,
    EngineeringDelegationMode, EngineeringEcosystem, EngineeringGrantScope,
    EngineeringGrantScopeKind, EngineeringResourceImpact, GrantLifecycleState,
    IntegrationEnvironmentPlan, IntegrationHealthCheck, IntegrationHealthKind,
    IntegrationNetworkMode, IntegrationPortBinding, IntegrationServiceKind,
    IntegrationServiceSpec, ReversibilityPolicy, SecretExposurePolicy,
    ToolRecipePurpose, VerificationRequirement,
)
from fam_os.core.engineering.execution_policy import SignedToolRecipeCatalog
from fam_os.core.engineering.integration_environment_service import IntegrationEnvironmentService
from fam_os.core.engineering.production_recipes import ToolRecipeSpecification
from fam_os.product.composition.storage_unit import ProductStorageUnit
from fam_os.product.integration_environment_api import ProductIntegrationEnvironmentApi
from fam_os.product.engineering_secret_api import (
    ProductEngineeringSecretApi, engineering_secret_operation_digest,
)
from fam_os.product.engineering_secret_lifecycle import (
    EngineeringSecretLifecycleCoordinator,
)
from fam_os.product.owner_identity import local_owner_id
from fam_os.schemas import encode_document
from fam_os.shell import ShellIntegrationEnvironmentOperation, ShellIntegrationEnvironmentQuery
from tests.integration.installed_database_authority_support import (
    ConsoleAuthorityClient, UnusedCore, authority_api, console_activate, serve,
)


class InstalledProcessOwnerRestartChainTests(unittest.TestCase):
    def test_console_start_restart_cleanup_and_shell_terminal_inspection(self):
        profile = os.environ.get("FAM_ENGINEERING_HARDWARE_PROFILE")
        if profile is not None:
            self.assertIn(profile, {"compat-cpu-16gb", "full-reference-workstation"})
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            state_root = root / "product"; state_root.mkdir(mode=0o700)
            candidate_root = root / "candidate"; candidate_root.mkdir(mode=0o700)
            entry = candidate_root / ".fam/services/api.py"
            entry.parent.mkdir(parents=True, mode=0o700)
            entry.write_text(_SERVER, encoding="utf-8")
            owner_id = local_owner_id(os.geteuid())
            plan, candidate = _environment(candidate_root, _free_port())
            grant = _grant(owner_id, plan, candidate)
            first_adapter, unit = self._start_through_console(
                root, state_root, owner_id, plan, candidate, grant,
            )
            self._restart_reconcile_and_shell_inspect(
                root, state_root, owner_id, plan, first_adapter, unit,
            )

    def test_rotation_stops_exact_active_process_before_secret_commit(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            state_root = root / "product"; state_root.mkdir(mode=0o700)
            candidate_root = root / "candidate"; candidate_root.mkdir(mode=0o700)
            entry = candidate_root / ".fam/services/api.py"
            entry.parent.mkdir(parents=True, mode=0o700)
            entry.write_text(_SERVER, encoding="utf-8")
            owner_id = local_owner_id(os.geteuid())
            plan, candidate = _environment(candidate_root, _free_port())
            grant = _grant(owner_id, plan, candidate)
            storage = ProductStorageUnit(state_root, os.geteuid()); storage.start()
            lifecycle = EngineeringSecretLifecycleCoordinator()
            adapter = ProcessIntegrationEnvironmentAdapter(
                _catalog(), secrets=storage.engineering_secrets,
            )
            api = ProductIntegrationEnvironmentApi(
                owner_id,
                IntegrationEnvironmentService(storage.engineering_authorizer, adapter),
                adapter, storage.integration_environments, lifecycle,
            )
            secret_api = ProductEngineeringSecretApi(
                owner_id, storage.engineering_secrets,
                storage.engineering_authentication, lifecycle=lifecycle,
                environments=api,
            )
            with ConsoleAuthorityClient(
                root / "console-rotate", authority_api(storage, owner_id), api,
                secret_api,
            ) as console:
                _provision_secret(console, owner_id)
                console_activate(console, grant)
                result = console.post("/api/v1/engineering/environments/start", {
                    "owner_id": owner_id, "plan": encode_document(plan),
                    "candidate": encode_document(candidate),
                    "grant_id": grant.grant_id,
                    "principal_id": grant.principal_id, "confirmed": True,
                })
                unit = result["payload"]["receipt"]["services"][0]["runtime_id"]
                rotated = _rotate_secret(console, owner_id)
                self.assertEqual(2, rotated["generation"])
                stored = storage.integration_environments.get(plan.environment_id)
                self.assertEqual("cleaned", stored.state)
                self.assertTrue(stored.latest_receipt.cleanup_evidence_ids)
            for wrapper in adapter._wrappers.values():
                wrapper.wait(timeout=5)
            observed = adapter._client.run(
                adapter._client.systemctl,
                ("--user", "is-active", "--quiet", unit + ".scope"),
            )
            self.assertNotEqual(0, observed.exit_code)
            self.assertFalse(tuple(
                (candidate_root / ".fam/secret-injection").glob("process-*")
            ))
            storage.stop()

    def _start_through_console(self, root, state_root, owner_id, plan, candidate, grant):
        storage = ProductStorageUnit(state_root, os.geteuid()); storage.start()
        lifecycle = EngineeringSecretLifecycleCoordinator()
        adapter = ProcessIntegrationEnvironmentAdapter(
            _catalog(), secrets=storage.engineering_secrets,
        )
        api = ProductIntegrationEnvironmentApi(
            owner_id, IntegrationEnvironmentService(storage.engineering_authorizer, adapter),
            adapter, storage.integration_environments, lifecycle,
        )
        secret_api = ProductEngineeringSecretApi(
            owner_id, storage.engineering_secrets, storage.engineering_authentication,
            lifecycle=lifecycle, environments=api,
        )
        with ConsoleAuthorityClient(
            root / "console-start", authority_api(storage, owner_id), api,
            secret_api,
        ) as console:
            _provision_secret(console, owner_id)
            console_activate(console, grant)
            result = console.post("/api/v1/engineering/environments/start", {
                "owner_id": owner_id, "plan": encode_document(plan),
                "candidate": encode_document(candidate), "grant_id": grant.grant_id,
                "principal_id": grant.principal_id, "confirmed": True,
            })
            self.assertEqual("ready", result["payload"]["receipt"]["status"])
            active = storage.integration_environments.active()
            self.assertEqual(1, len(active))
            unit = active[0].start_result.receipt.services[0].runtime_id
            intents = console.get(
                "/api/v1/engineering/environment-start-intents",
            )
            self.assertEqual("committed", intents["start_intents"][0]["state"])
            self.assertNotIn("installed-owner-secret", str(intents))
        storage.stop()
        return adapter, unit

    def _restart_reconcile_and_shell_inspect(self, root, state_root, owner_id, plan, first, unit):
        storage = ProductStorageUnit(state_root, os.geteuid()); storage.start()
        adapter = ProcessIntegrationEnvironmentAdapter(
            _catalog(), secrets=storage.engineering_secrets,
        )
        api = ProductIntegrationEnvironmentApi(
            owner_id, IntegrationEnvironmentService(storage.engineering_authorizer, adapter),
            adapter, storage.integration_environments,
        )
        outcomes = api.reconcile_active()
        self.assertEqual((True,), tuple(item.cleaned for item in outcomes))
        socket_path = root / "runtime/shell.sock"; socket_path.parent.mkdir(mode=0o700)
        server = UnixShellServer(
            UnixShellServerConfiguration(socket_path), PeerAuthorizationPolicy(os.geteuid()),
            ShellRequestDispatcher(UnusedCore(), integration_environment=api),
        )
        server.open()
        try:
            client = UnixShellCoreClient(UnixShellClientConfiguration(socket_path))
            response = serve(server, lambda: client.integration_environment_query(
                ShellIntegrationEnvironmentQuery(
                    "inspect-environment", ShellIntegrationEnvironmentOperation.INSPECT,
                    owner_id, plan.environment_id,
                ),
            ))
            self.assertEqual("cleaned", response.record.state)
            self.assertTrue(response.record.latest_receipt.cleanup_evidence_ids)
            intent = serve(server, lambda: client.integration_environment_query(
                ShellIntegrationEnvironmentQuery(
                    "inspect-intent", ShellIntegrationEnvironmentOperation.INTENT_INSPECT,
                    owner_id, plan.environment_id,
                ),
            ))
            self.assertEqual("committed", intent.intent_record.state)
            self.assertTrue(
                intent.intent_record.permit.authorization_decision_ids,
            )
        finally:
            server.close(); storage.stop()
            for wrapper in first._wrappers.values():
                wrapper.wait(timeout=5)
        observed = adapter._client.run(
            adapter._client.systemctl,
            ("--user", "is-active", "--quiet", unit + ".scope"),
        )
        self.assertNotEqual(0, observed.exit_code)


def _environment(root, port):
    instant = datetime.now(timezone.utc)
    impact = EngineeringResourceImpact(300, 2, 16, 4, 1_048_576, 1_048_576)
    service = IntegrationServiceSpec(
        "api", IntegrationServiceKind.API, "engineering.python.acceptance@1.0.0",
        ("/workspace/.fam/services/api.py", str(port)), None, None,
        (IntegrationPortBinding("api", port, port),), (),
        IntegrationHealthCheck(IntegrationHealthKind.HTTP, "api", "/health", None, 1, 1, 15),
        (), ("secret.api",),
    )
    plan = IntegrationEnvironmentPlan(
        "owner-process-environment", "task-process", "candidate-process", "changeset-process",
        "host-process", str(root), (service,), IntegrationNetworkMode.ISOLATED, (), (),
        impact, 134_217_728, 50,
        (EngineeringAuthority.EXECUTE, EngineeringAuthority.SECRET_USE), True,
        instant, instant + timedelta(minutes=20),
    )
    candidate = CandidateWorkspace(
        plan.candidate_id, plan.task_id, "baseline", str(root.parent / "owner"),
        str(root), instant, "copy", "a" * 64, (),
    )
    return plan, candidate


def _grant(owner_id, plan, candidate):
    instant = datetime.now(timezone.utc)
    return EngineeringAuthorityGrant(
        "grant-process", owner_id, "fam-core", EngineeringDelegationMode.CUSTOM,
        (EngineeringAuthority.EXECUTE, EngineeringAuthority.SECRET_USE), EngineeringGrantScope(
            EngineeringGrantScopeKind.TASK, plan.task_id, (candidate.owner_workspace,),
            (), (), ("integration-environment",), (), (), (), (), ("secret.api",),
        ), "Run the exact bounded candidate API", instant - timedelta(seconds=1),
        instant + timedelta(minutes=20), GrantLifecycleState.ACTIVE,
        ReversibilityPolicy.REQUIRED, SecretExposurePolicy.OPAQUE_CREDENTIAL_INJECTION,
        VerificationRequirement.REQUIRED, plan.resource_impact,
    )


def _catalog():
    key = Ed25519PrivateKey.generate()
    recipe = sign_recipe_specification(ToolRecipeSpecification(
        EngineeringEcosystem.PYTHON, ToolRecipePurpose.ACCEPTANCE, "/usr/bin/python3",
        ("/workspace/.fam/services/api.py", "{port:api}"), "integration.http.health.v1",
    ), "release", key)
    catalog = SignedToolRecipeCatalog(Ed25519RecipeSignatureVerifier({"release": key.public_key()}))
    catalog.admit(recipe); return catalog


def _free_port():
    with socket.socket() as stream:
        stream.bind(("127.0.0.1", 0)); return stream.getsockname()[1]


def _provision_secret(console, owner_id):
    digest = engineering_secret_operation_digest(
        "provision", "secret.api", "API_TOKEN", "integration:api",
        "installed-owner-secret",
    )
    context = console.post("/api/v1/engineering/authentication-contexts", {
        "owner_id": owner_id, "purpose": "engineering-secret-provision",
        "payload_sha256": digest, "confirmed": True,
    })
    result = console.post("/api/v1/engineering/secrets/provision", {
        "owner_id": owner_id, "secret_ref": "secret.api", "tool_key": "API_TOKEN",
        "consumer_id": "integration:api", "value": "installed-owner-secret",
        "authentication_context_id": context["context_id"], "confirmed": True,
    })
    if "value" in result or result["state"] != "active":
        raise AssertionError("secret provisioning response is not metadata-only")


def _rotate_secret(console, owner_id):
    digest = engineering_secret_operation_digest(
        "rotate", "secret.api", "", "", "installed-owner-secret-rotated",
    )
    context = console.post("/api/v1/engineering/authentication-contexts", {
        "owner_id": owner_id, "purpose": "engineering-secret-rotate",
        "payload_sha256": digest, "confirmed": True,
    })
    return console.post("/api/v1/engineering/secrets/secret.api/rotate", {
        "owner_id": owner_id, "secret_ref": "secret.api",
        "value": "installed-owner-secret-rotated",
        "authentication_context_id": context["context_id"], "confirmed": True,
    })


_SERVER = """from http.server import HTTPServer,BaseHTTPRequestHandler
from pathlib import Path
import os,sys
assert Path(os.environ['API_TOKEN_FILE']).read_text() == 'installed-owner-secret'
assert not tuple(Path('/workspace/.fam/secret-injection').glob('process-*'))
class H(BaseHTTPRequestHandler):
 def do_GET(self): self.send_response(204); self.end_headers()
 def log_message(self,*args): pass
HTTPServer(('127.0.0.1',int(sys.argv[1])),H).serve_forever()
"""


if __name__ == "__main__": unittest.main()
