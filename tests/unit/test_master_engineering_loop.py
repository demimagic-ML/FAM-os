import tempfile
import unittest
from pathlib import Path

from fam_os.adapters.sqlite import SQLiteEngineeringLoopStore
from fam_os.console.engineering import project_engineering_task
from fam_os.core.engineering import (
    EngineeringLoopBudget,
    EngineeringLoopStage,
    MasterEngineeringLoop,
)
from tests.contract.schema_engineering_fixtures import NOW


class MasterEngineeringLoopTests(unittest.TestCase):
    def test_complete_lifecycle_is_persistent_budgeted_and_separately_approved(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "engineering.sqlite3"
            store = SQLiteEngineeringLoopStore(path)
            loop = MasterEngineeringLoop(store)
            loop.start(
                "task-1", "grant-1",
                EngineeringLoopBudget(1000, 100, 20, 1000, 20, 10_000),
                instant=NOW,
            )
            stages = (
                (EngineeringLoopStage.INSPECTED, "repository-1"),
                (EngineeringLoopStage.PROPOSED, "architecture-1"),
                (EngineeringLoopStage.CANDIDATE_READY, "candidate-1"),
                (EngineeringLoopStage.VERIFIED, "verify-candidate-1"),
                (EngineeringLoopStage.CHANGESET_APPROVAL_REQUIRED, "checkpoint-1"),
            )
            for stage, evidence in stages:
                state = loop.advance(
                    "task-1", stage, evidence, instant=NOW,
                    budget_delta={"used_commands": 1},
                )
            state = loop.record_auxiliary_evidence(
                "task-1", "dependency", "dependency-1", instant=NOW,
                budget_delta={"used_network_bytes": 10},
            )
            state = loop.record_auxiliary_evidence(
                "task-1", "design", "design-preview-1", instant=NOW,
            )
            with self.assertRaisesRegex(PermissionError, "exact"):
                loop.advance("task-1", EngineeringLoopStage.APPLIED, "apply-1", instant=NOW)
            loop.advance(
                "task-1", EngineeringLoopStage.APPLIED, "apply-1",
                checkpoint_id="checkpoint-1", instant=NOW,
            )
            loop.advance("task-1", EngineeringLoopStage.REVERIFIED, "verify-owner-1", instant=NOW)
            loop.advance("task-1", EngineeringLoopStage.COMMITTED, "commit-1", instant=NOW)
            loop.advance(
                "task-1", EngineeringLoopStage.PUBLICATION_APPROVAL_REQUIRED,
                "publish-approval-1", instant=NOW,
            )
            store.close()

            restarted_store = SQLiteEngineeringLoopStore(path)
            restarted = MasterEngineeringLoop(restarted_store)
            state = restarted.resume_after_restart("task-1", instant=NOW)
            self.assertIsNone(state.pending_publication_id)
            with self.assertRaises(PermissionError):
                restarted.advance(
                    "task-1", EngineeringLoopStage.PUBLISHED, "publish-1",
                    checkpoint_id="publish-approval-1", instant=NOW,
                )
            restarted.advance(
                "task-1", EngineeringLoopStage.PUBLICATION_APPROVAL_REQUIRED,
                "publish-approval-2", instant=NOW,
            )
            restarted.advance(
                "task-1", EngineeringLoopStage.PUBLISHED, "publish-1",
                checkpoint_id="publish-approval-2", instant=NOW,
            )
            final = restarted.advance(
                "task-1", EngineeringLoopStage.COMPLETED, "complete-1", instant=NOW,
            )
            view = project_engineering_task(final)
            self.assertEqual("completed", view.stage)
            self.assertEqual(("commit-1",), view.git_receipt_ids)
            self.assertEqual(("publish-1",), final.publication_receipt_ids)
            self.assertEqual(("dependency-1",), final.dependency_receipt_ids)
            self.assertEqual(("design-preview-1",), final.design_receipt_ids)
            self.assertGreater(final.budget.used_commands, 0)
            restarted_store.close()

    def test_budget_never_resets_across_multiple_checkpoints(self):
        with tempfile.TemporaryDirectory() as directory:
            store = SQLiteEngineeringLoopStore(Path(directory) / "loop.sqlite3")
            loop = MasterEngineeringLoop(store)
            loop.start(
                "task-2", "grant-2", EngineeringLoopBudget(10, 10, 2, 10, 2, 10),
                instant=NOW,
            )
            loop.advance(
                "task-2", EngineeringLoopStage.INSPECTED, "repo",
                instant=NOW, budget_delta={"used_commands": 2},
            )
            with self.assertRaises(ValueError):
                loop.advance(
                    "task-2", EngineeringLoopStage.PROPOSED, "proposal",
                    instant=NOW, budget_delta={"used_commands": 1},
                )
            store.close()

    def test_candidate_and_postapply_integration_evidence_are_distinct_and_durable(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "loop.sqlite3"
            store = SQLiteEngineeringLoopStore(path)
            loop = MasterEngineeringLoop(store)
            loop.start(
                "task-integration", "grant-integration",
                EngineeringLoopBudget(100, 100, 10, 0, 10, 1000),
                instant=NOW,
            )
            for stage, evidence in (
                (EngineeringLoopStage.INSPECTED, "repository"),
                (EngineeringLoopStage.PROPOSED, "proposal"),
                (EngineeringLoopStage.CANDIDATE_READY, "candidate"),
                (EngineeringLoopStage.VERIFIED, "verification"),
            ):
                loop.advance("task-integration", stage, evidence, instant=NOW)
            loop.record_integration_environment(
                "task-integration", "integration-candidate", instant=NOW,
                postapply=False, budget_delta={"used_commands": 2},
            )
            loop.advance(
                "task-integration",
                EngineeringLoopStage.CHANGESET_APPROVAL_REQUIRED,
                "changeset", instant=NOW,
            )
            loop.advance(
                "task-integration", EngineeringLoopStage.APPLIED, "apply",
                checkpoint_id="changeset", instant=NOW,
            )
            state = loop.record_integration_environment(
                "task-integration", "integration-postapply", instant=NOW,
                postapply=True, budget_delta={"used_commands": 2},
            )
            self.assertEqual(
                ("integration-candidate",),
                state.integration_environment_receipt_ids,
            )
            self.assertEqual(
                ("integration-postapply",),
                state.integration_environment_postapply_receipt_ids,
            )
            store.close()
            restarted = SQLiteEngineeringLoopStore(path)
            self.assertEqual(state, restarted.load("task-integration"))
            restarted.close()


if __name__ == "__main__":
    unittest.main()
