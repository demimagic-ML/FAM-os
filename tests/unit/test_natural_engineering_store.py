import hashlib
import sqlite3
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from fam_os.adapters.sqlite import SQLiteNaturalEngineeringProposalStore
from fam_os.core.engineering import NaturalLanguageEngineeringPlanner
from fam_os.product.storage.cipher import ProductPayloadCipher
from fam_os.product.storage.keys import OwnerMasterKey
from fam_os.product.storage.owner_contract_codec import OwnerBoundJsonCodec


class NaturalEngineeringProposalStoreTests(unittest.TestCase):
    def test_proposal_survives_restart_and_activation_is_single_use(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "proposals.sqlite3"
            proposal = NaturalLanguageEngineeringPlanner().propose(
                prompt="Implement the feature and run Python tests.",
                workspace_root="/workspace/project", owner_id="owner-1",
                principal_id="principal-1", task_id="task-1", grant_id="grant-1",
                toolchains=("python3",),
                now=datetime(2026, 7, 19, 9, 0, tzinfo=timezone.utc),
            )
            store = SQLiteNaturalEngineeringProposalStore(path)
            store.put(proposal)
            store.close()

            restarted = SQLiteNaturalEngineeringProposalStore(path)
            self.assertEqual(proposal, restarted.get(proposal.proposal_id))
            self.assertTrue(restarted.activate(proposal.proposal_id))
            self.assertFalse(restarted.activate(proposal.proposal_id))
            self.assertEqual("activating", restarted.status(proposal.proposal_id))
            restarted.mark_activated(proposal.proposal_id)
            self.assertEqual("activated", restarted.status(proposal.proposal_id))
            restarted.close()

    def test_running_activation_becomes_restart_resumable_not_consumed(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "proposals.sqlite3"
            proposal = NaturalLanguageEngineeringPlanner().propose(
                prompt="Implement the feature and run Python tests.",
                workspace_root="/workspace/project", owner_id="owner-1",
                principal_id="principal-1", task_id="task-1", grant_id="grant-1",
                toolchains=("python3",),
                now=datetime(2026, 7, 19, 9, 0, tzinfo=timezone.utc),
            )
            store = SQLiteNaturalEngineeringProposalStore(path)
            store.put(proposal)
            self.assertTrue(store.begin_activation(proposal.proposal_id))
            store.close()

            restarted = SQLiteNaturalEngineeringProposalStore(path)
            self.assertEqual("interrupted", restarted.status(proposal.proposal_id))
            self.assertTrue(restarted.begin_activation(proposal.proposal_id))
            restarted.mark_failed(proposal.proposal_id, "model_output_invalid")
            self.assertEqual("failed", restarted.status(proposal.proposal_id))
            self.assertEqual(
                "model_output_invalid", restarted.failure(proposal.proposal_id),
            )
            restarted.close()

    def test_exact_integration_resource_grant_survives_secure_restart(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "proposals.sqlite3"
            proposal = NaturalLanguageEngineeringPlanner().propose(
                prompt=(
                    "Update the API and run it end-to-end with network access "
                    "to api.example.com:443 using secret ref db/password."
                ),
                workspace_root="/workspace/project", owner_id="owner-1",
                principal_id="owner-1", task_id="task-resource",
                grant_id="grant-resource", toolchains=("python3",),
                now=datetime(2026, 7, 19, 9, 0, tzinfo=timezone.utc),
            )
            store = SQLiteNaturalEngineeringProposalStore(
                path, _owner_codec("owner-1"),
            )
            store.put(proposal)
            store.close()

            restarted = SQLiteNaturalEngineeringProposalStore(
                path, _owner_codec("owner-1"),
            )
            restored = restarted.get(proposal.proposal_id)
            self.assertEqual(proposal, restored)
            self.assertEqual(
                ("api.example.com:443",),
                restored.integration_resource_grant.scope.network_hosts,
            )
            self.assertEqual(
                ("db/password",),
                restored.integration_resource_grant.scope.secret_refs,
            )
            restarted.close()

    def test_secure_store_encrypts_intent_and_migrates_legacy_rows(self):
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "proposals.sqlite3"
            private_intent = "Implement PRIVATE_NATURAL_LANGUAGE_INTENT and test it."
            proposal = NaturalLanguageEngineeringPlanner().propose(
                prompt=private_intent, workspace_root="/workspace/project",
                owner_id="owner-1", principal_id="principal-1",
                task_id="task-secure", grant_id="grant-secure",
                toolchains=("python3",),
                now=datetime(2026, 7, 19, 9, 0, tzinfo=timezone.utc),
            )
            legacy = SQLiteNaturalEngineeringProposalStore(path)
            legacy.put(proposal)
            legacy.close()
            self.assertIn(private_intent.encode(), path.read_bytes())

            secure = SQLiteNaturalEngineeringProposalStore(
                path, _owner_codec("owner-1"),
            )
            self.assertEqual(proposal, secure.get(proposal.proposal_id))
            secure.close()
            connection = sqlite3.connect(path)
            self.assertEqual(
                0, connection.execute(
                    "SELECT count(*) FROM natural_engineering_proposals"
                ).fetchone()[0],
            )
            self.assertEqual(
                1, connection.execute(
                    "SELECT count(*) FROM natural_engineering_proposals_secure"
                ).fetchone()[0],
            )
            connection.close()
            self.assertNotIn(private_intent.encode(), path.read_bytes())

            wrong_owner = SQLiteNaturalEngineeringProposalStore(
                path, _owner_codec("owner-2"),
            )
            with self.assertRaises(Exception):
                wrong_owner.get(proposal.proposal_id)
            wrong_owner.close()


def _owner_codec(owner_id: str) -> OwnerBoundJsonCodec:
    key = bytes(range(32))
    key_id = "owner-key-" + hashlib.sha256(key).hexdigest()[:24]
    return OwnerBoundJsonCodec(
        ProductPayloadCipher(OwnerMasterKey(key_id, key)), owner_id,
        "natural-engineering-proposal",
    )


if __name__ == "__main__":
    unittest.main()
