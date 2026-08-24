import tempfile
import unittest
from pathlib import Path

from fam_os.adapters.sqlite import SQLiteGitPublicationProposalStore
from fam_os.core.engineering import GitPublicationProposal, GitPublicationReceipt
from fam_os.schemas import dumps_document, loads_document
from tests.contract.schema_git_fixtures import git_schema_values


class GitPublicationProposalStoreTests(unittest.TestCase):
    def test_decline_is_durable_and_cannot_be_reapproved(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "proposals.sqlite3"
            proposal = git_schema_values()[9]
            first = _store(path)
            first.put(proposal)
            self.assertTrue(first.decline(proposal.proposal_id))
            first.close()
            restarted = _store(path)
            self.assertEqual("declined", restarted.status(proposal.proposal_id))
            self.assertFalse(restarted.begin_approval(proposal.proposal_id))
            restarted.close()

    def test_restart_turns_unfinished_confirmation_into_recovery_state(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "proposals.sqlite3"
            proposal = git_schema_values()[9]
            first = _store(path)
            first.put(proposal)
            self.assertTrue(first.begin_approval(proposal.proposal_id))
            first.close()

            restarted = _store(path)
            self.assertEqual(
                "recovery_required", restarted.status(proposal.proposal_id),
            )
            self.assertFalse(restarted.begin_approval(proposal.proposal_id))
            self.assertIsNone(restarted.receipt(proposal.proposal_id))
            restarted.close()

    def test_published_receipt_survives_restart_without_reapproval(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "proposals.sqlite3"
            proposal, receipt = git_schema_values()[9], git_schema_values()[4]
            receipt = type(receipt)(
                receipt.receipt_id, f"approval-{proposal.proposal_id}",
                receipt.provider_id, receipt.remote_name, proposal.target_ref,
                receipt.observed_old_object_id, proposal.proposed_new_object_id,
                receipt.change_request_url, receipt.draft, receipt.completed_at,
                receipt.provider_evidence_sha256,
            )
            first = _store(path)
            first.put(proposal)
            self.assertTrue(first.begin_approval(proposal.proposal_id))
            first.mark_published(proposal.proposal_id, receipt)
            first.close()

            restarted = _store(path)
            self.assertEqual("published", restarted.status(proposal.proposal_id))
            self.assertEqual(receipt, restarted.receipt(proposal.proposal_id))
            self.assertFalse(restarted.begin_approval(proposal.proposal_id))
            restarted.close()


class _Codec:
    def __init__(self, expected):
        self.expected = expected

    def encode(self, identity, value):
        return dumps_document(value)

    def decode(self, identity, token):
        value = loads_document(token)
        if not isinstance(value, self.expected):
            raise TypeError("unexpected publication store fixture")
        return value


def _store(path):
    return SQLiteGitPublicationProposalStore(
        path, _Codec(GitPublicationProposal), _Codec(GitPublicationReceipt),
    )


if __name__ == "__main__":
    unittest.main()
