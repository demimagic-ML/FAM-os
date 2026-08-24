import base64
import hashlib
import os
import socket
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from fam_os.adapters.integration import (
    DockerCommandClient, DockerIntegrationEnvironmentAdapter,
    IntegrationEnvironmentExecutorRouter, ProcessIntegrationEnvironmentAdapter,
)
from fam_os.core.engineering import (
    CandidateWorkspace, EngineeringAuthority, EngineeringEcosystem, IntegrationHealthKind,
    IntegrationNetworkMode, IntegrationServiceKind, SignedToolRecipe,
    ToolRecipePurpose,
)
from fam_os.core.engineering.integration_environment_service import (
    IntegrationEnvironmentService,
)
from fam_os.product.composition.storage_unit import ProductStorageUnit
from fam_os.product.integration_environment_api import ProductIntegrationEnvironmentApi
from fam_os.product.owner_identity import local_owner_id
from fam_os.core.engineering.execution_policy import (
    SignedToolRecipeCatalog, signed_recipe_payload,
)
from tests.contract.schema_integration_environment_fixtures import (
    NOW, integration_environment_schema_values,
)
from tests.integration.installed_database_authority_support import (
    ConsoleAuthorityClient, authority_api,
)


PYTHON_IMAGE = "python:3.12-slim-bookworm"
PYTHON_SHA256 = "d50fb7611f86d04a3b0471b46d7557818d88983fc3136726336b2a4c657aa30b"


class TrustFixture:
    def verify(self, key_id, payload, signature): return key_id == "test-release"


class NoSecrets:
    def environment(self, secret_refs, consumer_id):
        if secret_refs: raise PermissionError("unexpected mixed test secret")
        return {}


class Control:
    def cancelled(self): return False
    def authorization_active(self): return True


class UnusedAuthorizer:
    def authorize(self, request): raise AssertionError("recovery does not authorize")


class PythonContainerHealth:
    def __init__(self, client): self.client = client
    def healthy(self, signed_recipe_id, runtime_id, timeout_seconds):
        if signed_recipe_id != "integration.python.running.v1":
            raise PermissionError("mixed container health recipe is untrusted")
        result = self.client.run((
            "exec", runtime_id, "python3", "-c", "print('ready')",
        ), timeout_seconds=timeout_seconds)
        return result.exit_code == 0 and result.output.strip() == b"ready"


class RealMixedIntegrationEnvironmentTests(unittest.TestCase):
    def test_container_dependency_and_process_api_launch_and_restart_cleanup(self):
        if not all(Path(item).exists() for item in (
            "/usr/bin/docker", "/usr/bin/systemd-run", "/usr/bin/bwrap",
        )):
            self.skipTest("mixed integration toolchains are unavailable")
        client = DockerCommandClient()
        image = client.run(("image", "inspect", "--format", "{{.Id}}", PYTHON_IMAGE))
        if image.exit_code:
            self.skipTest("cached Python container image is unavailable")
        self.assertEqual("sha256:" + PYTHON_SHA256, image.output.decode().strip())
        with tempfile.TemporaryDirectory() as temporary:
            product_root = Path(temporary).resolve()
            root = product_root / "candidate"; root.mkdir(mode=0o700)
            script = root / ".fam/services/mixed_api.py"
            script.parent.mkdir(parents=True, mode=0o700)
            script.write_text(_API, encoding="utf-8")
            api_port = _free_port()
            plan, permit = _plan(root, api_port)
            process = ProcessIntegrationEnvironmentAdapter(
                _catalog(), clock=lambda: NOW,
            )
            router = IntegrationEnvironmentExecutorRouter(
                docker=DockerIntegrationEnvironmentAdapter(
                    NoSecrets(), client, clock=lambda: NOW,
                    health_recipes=PythonContainerHealth(client),
                ),
                process=process,
            )
            owner_id = local_owner_id(os.geteuid())
            storage = ProductStorageUnit(product_root / "product", os.geteuid())
            storage.start()
            candidate = CandidateWorkspace(
                plan.candidate_id, plan.task_id, "baseline-mixed",
                str(product_root / "owner"), str(root), NOW, "copy", "a" * 64, (),
            )
            storage.integration_environments.begin_start(plan, candidate)
            storage.integration_environments.record_permit(permit)
            receipt = router.launch(plan, root, permit, Control())
            units = {
                item.service_id: item.runtime_id for item in receipt.services
            }
            self.assertEqual(("dependency", "api"), tuple(units))
            container_memory = client.run((
                "inspect", "--format", "{{.HostConfig.Memory}}",
                units["dependency"],
            ))
            self.assertEqual(
                plan.maximum_memory_bytes // 2,
                int(container_memory.output.decode().strip()),
            )
            storage.stop()
            restarted = IntegrationEnvironmentExecutorRouter(
                docker=DockerIntegrationEnvironmentAdapter(
                    NoSecrets(), client, clock=lambda: NOW,
                    health_recipes=PythonContainerHealth(client),
                ),
                process=ProcessIntegrationEnvironmentAdapter(
                    _catalog(), clock=lambda: NOW,
                ),
            )
            storage = ProductStorageUnit(product_root / "product", os.geteuid())
            storage.start()
            api = ProductIntegrationEnvironmentApi(
                owner_id, IntegrationEnvironmentService(UnusedAuthorizer(), restarted),
                restarted, storage.integration_environments,
            )
            outcomes = api.recover_incomplete()
            self.assertEqual((True,), tuple(item.cleaned for item in outcomes))
            intent = storage.integration_environments.intent(plan.environment_id)
            cleaned = intent.recovery_receipt
            self.assertEqual("cleaned", cleaned.status.value)
            with ConsoleAuthorityClient(
                product_root / "console", authority_api(storage, owner_id), api,
            ) as console:
                visible = console.get(
                    "/api/v1/engineering/environment-start-intents/"
                    + plan.environment_id,
                )
                self.assertEqual("recovered", visible["state"])
                self.assertEqual(
                    "cleaned",
                    visible["recovery_receipt"]["payload"]["status"],
                )
            self.assertTrue(any(
                item.startswith("recovery-probed-container:")
                for item in cleaned.cleanup_evidence_ids
            ))
            self.assertTrue(any(
                item.startswith("recovery-probed-unit:")
                for item in cleaned.cleanup_evidence_ids
            ))
            for wrapper in process._wrappers.values():
                wrapper.wait(timeout=5)
            containers = client.run((
                "ps", "--all", "--quiet", "--filter",
                f"label=fam.environment={plan.environment_id}",
            ))
            self.assertEqual(b"", containers.output.strip())
            active = process._client.run(
                process._client.systemctl,
                ("--user", "is-active", "--quiet", units["api"] + ".scope"),
            )
            self.assertNotEqual(0, active.exit_code)
            storage.stop()


def _plan(root, api_port):
    service, plan, permit, _receipt, _result = integration_environment_schema_values()
    dependency_health = replace(
        service.health_check, kind=IntegrationHealthKind.SIGNED_RECIPE,
        port_name=None, path=None,
        signed_recipe_id="integration.python.running.v1",
        interval_seconds=1, timeout_seconds=1, maximum_attempts=20,
    )
    dependency = replace(
        service, service_id="dependency", image_ref=PYTHON_IMAGE,
        image_sha256=PYTHON_SHA256,
        launch_arguments=("python3", "-c", "import time; time.sleep(600)"),
        ports=(), volumes=(), health_check=dependency_health, secret_refs=(),
    )
    api_health = replace(
        service.health_check, kind=IntegrationHealthKind.HTTP,
        port_name="api", path="/health", signed_recipe_id=None,
        interval_seconds=1, timeout_seconds=1, maximum_attempts=20,
    )
    api = replace(
        service, service_id="api", kind=IntegrationServiceKind.API,
        signed_launch_recipe_id="integration.mixed-api@1.0.0",
        launch_arguments=(
            "/workspace/.fam/services/mixed_api.py", str(api_port),
        ), image_ref=None, image_sha256=None,
        ports=(replace(
            service.ports[0], name="api", container_port=api_port,
            requested_host_port=api_port,
        ),), volumes=(), health_check=api_health,
        dependency_ids=("dependency",), secret_refs=(),
    )
    identity = "mixed-" + uuid4().hex
    plan = replace(
        plan, environment_id=identity, candidate_root=str(root),
        services=(dependency, api), retained_artifact_paths=(),
        network_mode=IntegrationNetworkMode.ISOLATED,
        resource_impact=replace(plan.resource_impact, max_processes=64),
        maximum_memory_bytes=536_870_912,
        maximum_cpu_millis_per_second=1000,
        required_authorities=(EngineeringAuthority.EXECUTE,),
    )
    return plan, replace(permit, environment_id=identity)


def _catalog():
    arguments = (
        "/workspace/.fam/services/mixed_api.py", "{port:api}",
    )
    placeholder = SignedToolRecipe(
        "integration.mixed-api", "1.0.0", EngineeringEcosystem.PYTHON,
        ToolRecipePurpose.ACCEPTANCE, "/usr/bin/python3", arguments, (), (0,),
        ("integration.http.health",), "test-release", "0" * 64,
        base64.b64encode(b"0" * 64).decode(),
    )
    recipe = replace(
        placeholder,
        payload_sha256=hashlib.sha256(signed_recipe_payload(placeholder)).hexdigest(),
    )
    catalog = SignedToolRecipeCatalog(TrustFixture()); catalog.admit(recipe)
    return catalog


def _free_port():
    with socket.socket() as stream:
        stream.bind(("127.0.0.1", 0)); return stream.getsockname()[1]


_API = """from http.server import HTTPServer,BaseHTTPRequestHandler
import sys
class H(BaseHTTPRequestHandler):
 def do_GET(self): self.send_response(204); self.end_headers()
 def log_message(self,*a): pass
HTTPServer(('127.0.0.1',int(sys.argv[1])),H).serve_forever()
"""


if __name__ == "__main__":
    unittest.main()
