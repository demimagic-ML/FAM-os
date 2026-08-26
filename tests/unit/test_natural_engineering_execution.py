import hashlib
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace
from unittest.mock import patch

from fam_os.core.engineering import (
    CandidateBaselineEntry, CandidateChangesetStatus,
    CandidateContextDocument, CandidateEditStatus,
    CandidateEntryKind, CandidateGenerationContext,
    CandidateGenerationRecord, CandidateGenerationStatus,
    CandidateVerificationStatus, CandidateWorkspace, CheckpointPolicy,
    EngineeringAuthority, EngineeringOperation,
    EngineeringTaskDefinition, EngineeringTaskEnvelope,
    GeneratedCandidateOperation, GeneratedCandidateOperationKind,
    GeneratedCandidatePlan, engineering_task_digest,
)
from fam_os.product.natural_engineering_execution import (
    NaturalEngineeringExecutionCoordinator, _changeset_identity,
)
from fam_os.product.candidate_engineering_api import _profile
from fam_os.product.natural_engineering_repair import _feedback


NOW = datetime(2026, 7, 19, 11, 0, tzinfo=timezone.utc)


class NaturalEngineeringExecutionTests(unittest.TestCase):
    def test_identical_plans_in_different_tasks_never_alias_changesets(self):
        plan_digest = "a" * 64
        self.assertNotEqual(
            _changeset_identity("task-1", plan_digest),
            _changeset_identity("task-2", plan_digest),
        )

    def test_node_capable_profile_and_repair_feedback_preserve_diagnostic(self):
        definition, _preparation, _context, _record = _values()
        self.assertEqual(32, _profile(definition, "verification-1").process_limit)
        verification = SimpleNamespace(
            verification_id="verification-1", toolchain="node", passed=False,
            failure_code=None,
            receipt=SimpleNamespace(
                diagnostic="ReferenceError: require is not defined in ES module scope",
            ),
            evidence=SimpleNamespace(unresolved_risks=("tool recipe did not pass",)),
        )
        feedback = _feedback((verification,))
        self.assertTrue(any("ReferenceError" in item for item in feedback))

    def test_validated_generation_drives_edits_trusted_verification_and_checkpoint(self):
        definition, preparation, context, record = _values()
        loop = _Loop(preparation)
        coordinator = NaturalEngineeringExecutionCoordinator(
            loop, _ContextReader(context), _Generation(record),
        )
        with patch(
            "fam_os.product.natural_engineering_execution.encode_document",
            side_effect=lambda item: {"type": type(item).__name__},
        ):
            result = coordinator.execute(
                "owner-1", definition, session_id="session-1",
                principal_id="owner-1",
            )

        self.assertEqual("changeset_approval_required", result["outcome"])
        self.assertEqual(1, len(loop.edits))
        self.assertEqual("engineering.python.test", loop.recipe.recipe_id)
        self.assertEqual(
            {"used_tokens": 30, "used_wall_seconds": 2},
            loop.additional_budget,
        )
        self.assertTrue(loop.changeset_id.startswith("changeset-"))

    def test_failed_required_verifier_never_advances_or_previews(self):
        definition, preparation, context, record = _values()
        loop = _Loop(preparation, verification_passed=False)
        coordinator = NaturalEngineeringExecutionCoordinator(
            loop, _ContextReader(context), _Generation(record),
        )
        result = coordinator.execute(
            "owner-1", definition, session_id="session-1",
            principal_id="owner-1",
        )

        self.assertEqual("verification_failed", result["outcome"])
        self.assertFalse(loop.verifications_accepted)
        self.assertIsNone(loop.changeset_id)

    def test_verified_application_test_without_edits_finishes_without_changeset(self):
        definition, preparation, context, record = _values()
        task = replace(
            definition.task,
            authorities=(*definition.task.authorities, EngineeringAuthority.APPLICATION_TEST),
        )
        definition = replace(
            definition, task=task, task_sha256=engineering_task_digest(task),
        )
        loop = _Loop(preparation)
        agent = _ApplicationTestAgent()
        coordinator = NaturalEngineeringExecutionCoordinator(
            loop, _ContextReader(context), _Generation(record), agent=agent,
        )

        result = coordinator.execute(
            "owner-1", definition, session_id="session-1",
            principal_id="owner-1", goal_mode=True,
        )

        self.assertEqual("application_test_completed", result["outcome"])
        self.assertEqual("verified", result["stage"])
        self.assertEqual([], result["changed_paths"])
        self.assertEqual("completed", result["application_test"]["status"])
        self.assertEqual(["agent-verification-app"], result["agent_verification_evidence_ids"])
        self.assertEqual(0, loop.baseline_capture_count)
        self.assertIsNone(loop.changeset_id)


class _ApplicationTestAgent:
    def execute(self, *args, **kwargs):
        return SimpleNamespace(
            producer_id="application-test-turn",
            summary="All application checks passed.",
            agent_outcome=SimpleNamespace(model_steps=12),
            applied_edits=(),
            successful_verifications=("application-test:all-harness-checks-passed",),
            application_test={"status": "completed", "assertions": [{"passed": True}]},
        )


class _ContextReader:
    def __init__(self, context):
        self.context = context

    def read(self, candidate, query, preferred):
        return self.context


class _Generation:
    def __init__(self, record):
        self.record = record

    def generate(self, *args, **kwargs):
        return self.record

    def close(self):
        pass


class _Loop:
    def __init__(self, preparation, verification_passed=True):
        self.preparation_value = preparation
        self.edits = []
        self.recipe = SimpleNamespace(
            recipe_id="engineering.python.test", recipe_version="1.0.0",
        )
        self.additional_budget = None
        self.changeset_id = None
        self.verification_passed = verification_passed
        self.verifications_accepted = False
        self.verification_count = 0
        self.baseline_capture_count = 0

    def preparation(self, owner_id, task_id):
        return self.preparation_value

    def capture_runtime_performance_baseline(self, *args, **kwargs):
        self.baseline_capture_count += 1
        return (), ()

    def accept_agent_verification(self, owner_id, task_id, turn_id, changed_paths):
        self.asserted_agent_verification = (turn_id, changed_paths)
        return "agent-verification-app"

    def database_engineering_requested(self, owner_id, task_id):
        return False

    def run_runtime_diagnostics(self, *args, **kwargs):
        return (), ()

    def remaining_budget(self, owner_id, task_id):
        return {
            "tokens": 1_000, "wall_seconds": 300, "commands": 8,
            "network_bytes": 1, "files": 8, "storage_bytes": 10_000,
        }

    def edit_candidate(self, owner_id, task_id, **kwargs):
        self.edits.append(kwargs["operation"])
        return SimpleNamespace(
            status=CandidateEditStatus.APPLIED,
            operation=kwargs["operation"], edit_id=kwargs["edit_id"],
        )

    def select_verification_recipes(self, owner_id, task_id):
        return (("python3", self.recipe),)

    def verify_candidate(self, owner_id, task_id, **kwargs):
        self.verification_count += 1
        return SimpleNamespace(
            verification_id=kwargs["verification_id"],
            task_id=task_id, toolchain=kwargs["toolchain"],
            status=CandidateVerificationStatus.COMPLETED,
            passed=self.verification_passed,
            failure_code=None,
            evidence=SimpleNamespace(
                unresolved_risks=(
                    () if self.verification_passed else ("fixture failure",)
                ),
            ),
        )

    def record_generation_budget(self, owner_id, task_id, generation):
        self.additional_budget = {
            "used_tokens": generation.consumed_tokens,
            "used_wall_seconds": generation.consumed_wall_seconds,
        }

    def accept_candidate_verifications(
        self, owner_id, task_id, records, additional_budget=None,
    ):
        self.verifications_accepted = True

    def record_failed_candidate_verifications(self, owner_id, task_id, records):
        pass

    def record_incident(self, owner_id, task_id, failure_code, evidence_ids):
        return None

    def current_candidate(self, owner_id, task_id):
        return self.preparation_value.candidate

    def preview_candidate(self, owner_id, task_id, changeset_id, **kwargs):
        self.changeset_id = changeset_id
        return SimpleNamespace(status=CandidateChangesetStatus.PREVIEWED)

    def inspect(self, owner_id, task_id):
        return {"task_id": task_id, "stage": "changeset_approval_required"}


def _values():
    task = EngineeringTaskEnvelope(
        "task-1", "owner-1", "grant-1", "Fix app", NOW,
        NOW + timedelta(hours=1), ("/workspace/project",),
        (
            EngineeringAuthority.OBSERVE, EngineeringAuthority.PROPOSE,
            EngineeringAuthority.MODIFY, EngineeringAuthority.EXECUTE,
        ),
        (
            EngineeringOperation.READ, EngineeringOperation.REPLACE,
            EngineeringOperation.RUN_TOOL,
        ),
        (), (".git/**", ".fam/**"), ("python3",), (), (), 300, 8, 8,
        10_000, None, None, CheckpointPolicy.EVERY_CHANGESET,
    )
    definition = EngineeringTaskDefinition(
        "definition-task-1", task, "acceptance", NOW,
        engineering_task_digest(task),
    )
    candidate = CandidateWorkspace(
        "candidate-1", "task-1", "baseline-1", "/workspace/project",
        "/tmp/candidate-1/workspace", NOW, "copy", "b" * 64,
        (CandidateBaselineEntry(
            "app.py", CandidateEntryKind.FILE, "a" * 64, 10, False,
        ),),
    )
    analysis = SimpleNamespace(
        relevant_paths=("app.py",), affected_test_paths=(),
    )
    preparation = SimpleNamespace(candidate=candidate, analysis=analysis)
    content = "VALUE = 1\n"
    context = CandidateGenerationContext(
        "candidate-1", "b" * 64, ("app.py",),
        (CandidateContextDocument(
            "app.py", hashlib.sha256(content.encode()).hexdigest(), content,
        ),), False,
    )
    plan = GeneratedCandidatePlan("Fix app", (
        GeneratedCandidateOperation(
            GeneratedCandidateOperationKind.REPLACE_FILE,
            "app.py", "VALUE = 2\n", media_type="text/x-python",
        ),
    ))
    record = CandidateGenerationRecord(
        "generation-task-1-1", "definition-task-1", "task-1", "candidate-1",
        "session-1", "owner-1", "c" * 64, "d" * 64, "model:1",
        CandidateGenerationStatus.PLAN_VALIDATED, 1, 30, 2, 1, NOW, NOW, plan,
    )
    return definition, preparation, context, record


if __name__ == "__main__":
    unittest.main()
