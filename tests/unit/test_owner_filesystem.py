import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from fam_os.applications import (
    ActionConfirmation, ActionPreparationRequest, ActionStatus,
    ApplicationCapabilityRegistry, ConfirmationDecision, ObservationRequest,
    WORKSPACE_MAP_CAPABILITY,
    WORKSPACE_PATCH_CAPABILITY, WORKSPACE_RESTORE_CAPABILITY,
    WORKSPACE_RETRIEVE_CAPABILITY,
)
from fam_os.product.composition.owner_filesystem import OwnerFilesystem


class OwnerFilesystemTests(unittest.TestCase):
    def test_lists_directory_and_reads_explicit_file_with_bounded_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            project.mkdir()
            readme = project / "README.md"
            readme.write_text("# Local project\n")
            registry = ApplicationCapabilityRegistry()
            provider = OwnerFilesystem(registry, root)
            provider.start()
            try:
                capabilities = {
                    entry.capability_id
                    for entry in registry.entries("owner-filesystem")
                }
                self.assertTrue({
                    "os.directory.inspect", "os.directory.list", "os.file.read",
                    "os.directory.create", "os.directory.remove-empty",
                    WORKSPACE_MAP_CAPABILITY, WORKSPACE_RETRIEVE_CAPABILITY,
                    WORKSPACE_PATCH_CAPABILITY, WORKSPACE_RESTORE_CAPABILITY,
                }.issubset(capabilities))

                listing = provider.observe(ObservationRequest(
                    "list-1", "owner-filesystem", "os.directory.list", "grant-1",
                    {}, project.as_uri() + "/",
                ))
                read = provider.observe(ObservationRequest(
                    "read-1", "owner-filesystem", "os.file.read", "grant-1",
                    {}, readme.as_uri(),
                ))

                self.assertEqual("README.md", listing.payload["entries"][0]["name"])
                self.assertEqual("# Local project\n", read.payload["content"])
                self.assertEqual(readme.stat().st_size, read.payload["size_bytes"])
            finally:
                provider.close()

    def test_maps_retrieves_applies_and_restores_hash_bound_workspace_patch(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            source = project / "src/app.py"
            source.parent.mkdir(parents=True)
            source.write_text('GREETING = "old"\n')
            (project / "AGENTS.md").write_text("Keep changes bounded.\n")
            ignored = project / "node_modules/package/index.js"
            ignored.parent.mkdir(parents=True)
            ignored.write_text("generated\n")
            outside = root / "outside.txt"
            outside.write_text("must remain outside the workspace\n")
            (project / "outside-link.txt").symlink_to(outside)
            registry = ApplicationCapabilityRegistry()
            provider = OwnerFilesystem(registry, root)
            provider.start()
            try:
                workspace_uri = project.as_uri() + "/"
                mapped = provider.observe(ObservationRequest(
                    "map-1", "owner-filesystem", WORKSPACE_MAP_CAPABILITY,
                    "grant-1", {}, workspace_uri,
                ))
                retrieved = provider.observe(ObservationRequest(
                    "retrieve-1", "owner-filesystem", WORKSPACE_RETRIEVE_CAPABILITY,
                    "grant-1", {"query": "update app greeting"}, workspace_uri,
                ))
                paths = [item["path"] for item in mapped.payload["files"]]
                documents = {
                    item["path"]: item for item in retrieved.payload["documents"]
                }
                self.assertNotIn("node_modules/package/index.js", paths)
                self.assertNotIn("outside-link.txt", paths)
                self.assertIn("src/app.py", documents)
                request = ActionPreparationRequest(
                    "patch-1", "owner-filesystem", WORKSPACE_PATCH_CAPABILITY,
                    "grant-1", "Update greeting", {
                        "plan": ["Update the observed greeting constant."],
                        "changes": [{
                            "path": "src/app.py", "content": 'GREETING = "new"\n',
                            "expected_sha256": documents["src/app.py"]["sha256"],
                        }],
                    }, workspace_uri, retrieved.revision,
                )
                proposal = provider.prepare_action(request)
                result = provider.execute_action(
                    proposal, _confirmation(proposal.proposal_id),
                )

                self.assertTrue(result.verified)
                self.assertEqual('GREETING = "new"\n', source.read_text())
                self.assertIn("-GREETING = \"old\"", proposal.preview["files"][0]["diff"])

                restore_request = ActionPreparationRequest(
                    "restore-1", "owner-filesystem", WORKSPACE_RESTORE_CAPABILITY,
                    "grant-1", "Restore patch",
                    {"reversal_token": result.reversal_token}, workspace_uri,
                )
                restore = provider.prepare_action(restore_request)
                restored = provider.execute_action(
                    restore, _confirmation(restore.proposal_id),
                )
                self.assertTrue(restored.verified)
                self.assertEqual('GREETING = "old"\n', source.read_text())
            finally:
                provider.close()

    def test_patch_and_restore_fail_closed_when_approved_bytes_change(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            project = root / "project"
            project.mkdir()
            source = project / "app.py"
            source.write_text('VALUE = "old"\n')
            provider = OwnerFilesystem(ApplicationCapabilityRegistry(), root)
            provider.start()
            try:
                uri = project.as_uri() + "/"
                observed = provider.observe(ObservationRequest(
                    "retrieve-stale", "owner-filesystem",
                    WORKSPACE_RETRIEVE_CAPABILITY, "grant-1",
                    {"query": "app value"}, uri,
                ))
                digest = observed.payload["documents"][0]["sha256"]
                request = ActionPreparationRequest(
                    "patch-stale", "owner-filesystem", WORKSPACE_PATCH_CAPABILITY,
                    "grant-1", "Update value", {
                        "plan": ["Update the observed value."],
                        "changes": [{
                            "path": "app.py", "content": 'VALUE = "new"\n',
                            "expected_sha256": digest,
                        }],
                    }, uri, observed.revision,
                )
                proposal = provider.prepare_action(request)
                source.write_text('VALUE = "external"\n')

                stale = provider.execute_action(
                    proposal, _confirmation(proposal.proposal_id),
                )

                self.assertEqual(ActionStatus.PRECONDITION_FAILED, stale.status)
                self.assertEqual('VALUE = "external"\n', source.read_text())
            finally:
                provider.close()


def _confirmation(proposal_id):
    return ActionConfirmation(
        f"confirmation-{proposal_id}", proposal_id, "grant-1",
        ConfirmationDecision.APPROVED, "local-owner", datetime.now(timezone.utc),
    )


if __name__ == "__main__":
    unittest.main()
