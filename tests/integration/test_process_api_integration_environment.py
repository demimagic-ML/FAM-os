import base64
import hashlib
import socket
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from fam_os.adapters.integration.process_environment import ProcessIntegrationEnvironmentAdapter
from fam_os.core.engineering import (
    EngineeringAuthority, EngineeringEcosystem, IntegrationHealthKind, IntegrationNetworkMode,
    IntegrationServiceKind, SignedToolRecipe, ToolRecipePurpose,
)
from fam_os.core.engineering.execution_policy import SignedToolRecipeCatalog, signed_recipe_payload
from tests.contract.schema_integration_environment_fixtures import (
    NOW, integration_environment_schema_values,
)


class TrustFixture:
    def verify(self, key_id, payload, signature): return key_id == "test-release"


class Control:
    def cancelled(self): return False
    def authorization_active(self): return True


class ApiSecrets:
    def environment(self, secret_refs, consumer_id):
        if secret_refs != ("secret.api-test",):
            raise PermissionError("unexpected secret reference")
        return {"API_TOKEN": "opaque-api-token"}


class ProcessApiIntegrationEnvironmentTests(unittest.TestCase):
    def test_real_loopback_http_api_is_isolated_bounded_healthy_and_cleaned(self):
        if not all(Path(item).exists() for item in (
            "/usr/bin/systemd-run", "/usr/bin/systemctl", "/usr/bin/bwrap",
        )):
            self.skipTest("systemd or Bubblewrap is unavailable")
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve()
            (root / "server.py").write_text(
                "from http.server import HTTPServer,BaseHTTPRequestHandler\n"
                "from pathlib import Path\n"
                "import os,sys\n"
                "assert Path(os.environ['API_TOKEN_FILE']).read_text() == 'opaque-api-token'\n"
                "assert not tuple(Path('/workspace/.fam/secret-injection').glob('process-*'))\n"
                "Path('artifacts').mkdir(); Path('artifacts/api.txt').write_text('ready\\n')\n"
                "class H(BaseHTTPRequestHandler):\n"
                " def do_GET(self): self.send_response(204); self.end_headers()\n"
                " def log_message(self,*a): pass\n"
                "HTTPServer(('127.0.0.1',int(sys.argv[1])),H).serve_forever()\n",
                encoding="utf-8",
            )
            port = _free_port()
            arguments = ("/workspace/server.py", str(port))
            catalog = SignedToolRecipeCatalog(TrustFixture())
            catalog.admit(_recipe(("/workspace/server.py", "{port:api}")))
            service, plan, permit, _receipt, _result = integration_environment_schema_values()
            health = replace(
                service.health_check, kind=IntegrationHealthKind.HTTP,
                port_name="api", path="/health", signed_recipe_id=None,
                interval_seconds=1, timeout_seconds=1, maximum_attempts=15,
            )
            service = replace(
                service, service_id="api", kind=IntegrationServiceKind.API,
                signed_launch_recipe_id="integration.api@1.0.0",
                launch_arguments=arguments, image_ref=None, image_sha256=None,
                ports=(replace(
                    service.ports[0], name="api", container_port=port,
                    requested_host_port=port,
                ),), volumes=(), health_check=health,
                secret_refs=("secret.api-test",),
            )
            identity = "process-" + uuid4().hex
            plan = replace(
                plan, environment_id=identity, candidate_root=str(root),
                services=(service,), retained_artifact_paths=("artifacts/api.txt",),
                network_mode=IntegrationNetworkMode.ISOLATED,
                resource_impact=replace(plan.resource_impact, max_processes=16),
                required_authorities=(
                    EngineeringAuthority.EXECUTE,
                    EngineeringAuthority.SECRET_USE,
                ),
            )
            permit = replace(permit, environment_id=identity)
            adapter = ProcessIntegrationEnvironmentAdapter(
                catalog, clock=lambda: NOW, secrets=ApiSecrets(),
            )
            receipt = adapter.launch(plan, root, permit, Control())
            try:
                self.assertTrue(receipt.services[0].health_evidence_id.startswith("health:"))
                unit = receipt.services[0].runtime_id
                limits = adapter._client.run(
                    adapter._client.systemctl,
                    (
                        "--user", "show", unit + ".scope", "--no-pager",
                        "--property=MemoryMax", "--property=TasksMax",
                        "--property=CPUQuotaPerSecUSec",
                        "--property=IPAddressDeny", "--property=IPAddressAllow",
                    ),
                )
                self.assertEqual(0, limits.exit_code)
                self.assertIn(f"MemoryMax={plan.maximum_memory_bytes}", limits.output)
                self.assertIn("TasksMax=16", limits.output)
                self.assertNotIn("CPUQuotaPerSecUSec=infinity", limits.output)
                self.assertEqual(1, len(tuple(
                    (root / ".fam/secret-injection").glob("process-*")
                )))
            finally:
                cleaned = adapter.cleanup(plan, receipt, root, permit)
            self.assertTrue(cleaned.cleanup_evidence_ids)
            self.assertEqual("artifacts/api.txt", cleaned.retained_artifacts[0].relative_path)
            self.assertEqual(
                hashlib.sha256(b"ready\n").hexdigest(),
                cleaned.retained_artifacts[0].sha256,
            )
            observed = adapter._client.run(
                adapter._client.systemctl,
                ("--user", "is-active", "--quiet", unit + ".scope"),
            )
            self.assertNotEqual(0, observed.exit_code)
            self.assertEqual([], list(
                (root / ".fam/secret-injection").glob("process-*")
            ))


def _recipe(arguments):
    placeholder = SignedToolRecipe(
        "integration.api", "1.0.0", EngineeringEcosystem.PYTHON,
        ToolRecipePurpose.ACCEPTANCE, "/usr/bin/python3", arguments, (), (0,),
        ("integration.http.health",), "test-release", "0" * 64,
        base64.b64encode(b"0" * 64).decode(),
    )
    return replace(
        placeholder,
        payload_sha256=hashlib.sha256(signed_recipe_payload(placeholder)).hexdigest(),
    )


def _free_port():
    with socket.socket() as stream:
        stream.bind(("127.0.0.1", 0)); return stream.getsockname()[1]


if __name__ == "__main__": unittest.main()
