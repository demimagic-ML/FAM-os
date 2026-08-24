import json
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from fam_os.applications import (
    ActionConfirmation, ActionPreparationRequest, ApplicationCapabilityRegistry,
    ConfirmationDecision, ObservationRequest,
)
from fam_os.product.composition.application_conditions import (
    LiveApplicationConditionVerifier,
)
from fam_os.product.composition.os_tools import ProductOsTools


class ProductOsToolsTests(unittest.TestCase):
    def test_scoped_file_and_fixed_command_are_live_capabilities(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            project.mkdir()
            readme = project / "README.md"
            readme.write_text("# Local project\n")
            config = root / "os-tools.json"
            config.write_text(json.dumps(_configuration(project)))
            os.chmod(config, 0o600)
            registry = ApplicationCapabilityRegistry()
            tools = ProductOsTools.from_file(registry, config)
            tools.start()
            try:
                entries = registry.entries("project-demo")
                transport = tools.transport("os-tools-demo")
                read = next(
                    item for item in entries
                    if item.capability_id == "os.file.read"
                )
                self.assertEqual((project.as_uri() + "/",), read.resource_scopes)
                observed = transport.observe(ObservationRequest(
                    "observe-file", "project-demo", "os.file.read", "grant-file",
                    {}, readme.as_uri(),
                ))
                self.assertEqual("# Local project\n", observed.payload["content"])
                action = next(item for item in entries if item.capability.kind.value == "action")
                self.assertEqual((), action.resource_scopes)
                proposal = transport.prepare_action(ActionPreparationRequest(
                    "run-test", "project-demo", action.capability_id, "grant-test",
                    "Run tests", {},
                ))
                result = transport.execute_action(proposal, ActionConfirmation(
                    "confirm-test", proposal.proposal_id, "grant-test",
                    ConfirmationDecision.APPROVED, "local-owner",
                    datetime.now(timezone.utc),
                ))
                verified = LiveApplicationConditionVerifier(None).verify(
                    proposal.postconditions[0], proposal, result,
                )
                self.assertTrue(result.verified)
                self.assertTrue(verified.passed)
            finally:
                tools.close()
            self.assertEqual((), registry.entries())

    def test_configuration_must_be_owner_private(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            project.mkdir()
            config = root / "os-tools.json"
            config.write_text(json.dumps(_configuration(project)))
            os.chmod(config, 0o644)
            with self.assertRaises(PermissionError):
                ProductOsTools.from_file(ApplicationCapabilityRegistry(), config)


def _configuration(project):
    return {
        "contract_version": "fam.product.os-tools/v1alpha1",
        "projects": [{
            "project_id": "demo", "display_name": "Demo project",
            "root": str(project),
            "commands": [{
                "capability_id": "project.test", "display_name": "Run project tests",
                "executable": "/bin/true", "arguments": [],
            }],
        }],
    }


if __name__ == "__main__":
    unittest.main()
