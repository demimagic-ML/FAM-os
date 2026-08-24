import socket
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fam_os.adapters.crypto.engineering_recipes import Ed25519RecipeSignatureVerifier, sign_recipe_specification
from fam_os.adapters.bubblewrap.engineering import toolchain_tree_sha256
from fam_os.adapters.integration import BoundedDevToolsClient, ProcessIntegrationEnvironmentAdapter
from fam_os.core.engineering import (
    EngineeringEcosystem, IntegrationHealthKind, IntegrationNetworkMode,
    IntegrationServiceKind, ToolRecipePurpose, ToolchainMount,
)
from fam_os.core.engineering.execution_policy import SignedToolRecipeCatalog
from fam_os.core.engineering.production_recipes import ToolRecipeSpecification
from tests.contract.schema_integration_environment_fixtures import NOW, integration_environment_schema_values


class Control:
    def cancelled(self): return False
    def authorization_active(self): return True


class RealBrowserIntegrationEnvironmentTests(unittest.TestCase):
    def test_chrome_headless_devtools_is_loopback_bounded_and_cleaned(self):
        source = Path("/opt/google/chrome")
        executable = source / "google-chrome"
        if not executable.exists(): self.skipTest("Google Chrome is unavailable")
        port = _free_port()
        template = (
            "--headless=new", "--no-sandbox", "--disable-gpu",
            "--disable-dev-shm-usage", "--no-first-run",
            "--no-default-browser-check", "--disable-background-networking",
            "--disable-component-update", "--disable-sync",
            "--metrics-recording-only", "--user-data-dir=/tmp/chrome-profile",
            "--remote-debugging-address=127.0.0.1",
            "--remote-debugging-port={port:devtools}", "about:blank",
        )
        arguments = (*template[:-2], f"--remote-debugging-port={port}", template[-1])
        key = Ed25519PrivateKey.generate()
        recipe = sign_recipe_specification(ToolRecipeSpecification(
            EngineeringEcosystem.HTML, ToolRecipePurpose.ACCEPTANCE,
            "/opt/fam/toolchains/chrome/google-chrome", template,
            "integration.browser.devtools.v1",
        ), "release", key, toolchain_mounts=(ToolchainMount(
            str(source), "/opt/fam/toolchains/chrome", toolchain_tree_sha256(source),
        ),))
        catalog = SignedToolRecipeCatalog(Ed25519RecipeSignatureVerifier({"release": key.public_key()}))
        catalog.admit(recipe)
        service, plan, permit, _receipt, _result = integration_environment_schema_values()
        service = replace(
            service, service_id="browser", kind=IntegrationServiceKind.BROWSER,
            signed_launch_recipe_id=f"{recipe.recipe_id}@{recipe.recipe_version}",
            launch_arguments=arguments, image_ref=None, image_sha256=None,
            ports=(replace(
                service.ports[0], name="devtools", container_port=port,
                requested_host_port=port,
            ),), volumes=(), health_check=replace(
                service.health_check, kind=IntegrationHealthKind.HTTP,
                port_name="devtools", path="/json/version", signed_recipe_id=None,
                interval_seconds=1, timeout_seconds=1, maximum_attempts=20,
            ),
        )
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary).resolve(); identity = "browser-" + uuid4().hex
            plan = replace(
                plan, environment_id=identity, candidate_root=str(root),
                services=(service,), retained_artifact_paths=(),
                network_mode=IntegrationNetworkMode.ISOLATED,
                maximum_memory_bytes=536_870_912,
                resource_impact=replace(plan.resource_impact, max_processes=128),
            )
            permit = replace(permit, environment_id=identity)
            adapter = ProcessIntegrationEnvironmentAdapter(catalog, clock=lambda: NOW)
            receipt = adapter.launch(plan, root, permit, Control())
            try:
                self.assertTrue(receipt.services[0].health_evidence_id.startswith("health:"))
                unit = receipt.services[0].runtime_id
                devtools = BoundedDevToolsClient(port)
                self.assertEqual("", devtools.evaluate("document.title"))
                screenshot = devtools.screenshot_png()
                self.assertGreater(len(screenshot), 100)
            finally:
                cleaned = adapter.cleanup(plan, receipt, root, permit)
            self.assertTrue(cleaned.cleanup_evidence_ids)
            result = adapter._client.run(
                adapter._client.systemctl,
                ("--user", "is-active", "--quiet", unit + ".scope"),
            )
            self.assertNotEqual(0, result.exit_code)


def _free_port():
    with socket.socket() as stream:
        stream.bind(("127.0.0.1", 0)); return stream.getsockname()[1]


if __name__ == "__main__": unittest.main()
