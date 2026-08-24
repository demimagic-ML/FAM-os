import hashlib
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from fam_os.applications import (
    ActionPreparationRequest, ActionProposal, ActionResult, ActionStatus,
    ConditionEvidence, ConditionRequirement, ConfirmationPolicy, Reversibility,
)
from fam_os.product.composition.application_conditions import (
    LiveApplicationConditionVerifier,
)


class ApplicationConditionTests(unittest.TestCase):
    def test_file_hash_is_recomputed_from_disk_not_trusted_from_provider(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "main.py"
            path.write_bytes(b"print('safe')\n")
            expected = hashlib.sha256(path.read_bytes()).hexdigest()
            requirement = ConditionRequirement(
                "file.sha256", "file.sha256", "Saved bytes must match.",
            )
            proposal = ActionProposal(
                "proposal-save", ActionPreparationRequest(
                    "request-save", "instance-vscode", "vscode.document.save",
                    "grant-save", "Save file", {"document_uri": path.as_uri()},
                    path.as_uri(), "revision-before",
                ),
                {"operation": "save"}, Reversibility.IRREVERSIBLE,
                ConfirmationPolicy.ALWAYS, (requirement,),
            )
            provider = ActionResult(
                proposal.proposal_id, ActionStatus.VERIFIED,
                datetime.now(timezone.utc),
                (ConditionEvidence(
                    requirement.condition_id, requirement.verifier_id, True,
                    "provider assertion",
                ),),
                {"disk_sha256": expected}, "revision-before", "revision-after",
            )
            verifier = LiveApplicationConditionVerifier(None)
            self.assertTrue(verifier.verify(
                requirement, proposal, provider,
            ).passed)
            path.write_bytes(b"tampered\n")
            self.assertFalse(verifier.verify(
                requirement, proposal, provider,
            ).passed)


if __name__ == "__main__":
    unittest.main()
