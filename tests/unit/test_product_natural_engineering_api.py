import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
from types import SimpleNamespace

from fam_os.adapters.sqlite import SQLiteNaturalEngineeringProposalStore
from fam_os.core.agent import AgentAuthorityProfile
from fam_os.product.natural_engineering_api import (
    ProductNaturalEngineeringApi,
    _toolchains,
)
from fam_os.core.engineering import (
    EngineeringFindingDisposition, EngineeringFindingSeverity,
    EngineeringReviewCheckpoint, EngineeringReviewDiscipline,
    EngineeringReviewFinding, EngineeringReviewStatus,
    NaturalEngineeringConversation,
    review_waiver_consequences_digest,
)
from fam_os.core.engineering.repository import (
    ArchitectureArea, ArchitectureDecision, ArchitectureProposal,
)


NOW = datetime(2026, 7, 19, 9, 0, tzinfo=timezone.utc)


class ProductNaturalEngineeringApiTests(unittest.TestCase):
    def test_full_os_profile_requires_and_activates_exact_break_glass_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "project"
            workspace.mkdir()
            authorizer = _Authorizer()
            api = ProductNaturalEngineeringApi(
                "owner-1",
                SQLiteNaturalEngineeringProposalStore(Path(temporary) / "p.sqlite3"),
                _Authentication(), authorizer, _AuthorizingLoop(authorizer), _Observer(),
                clock=lambda: NOW, identifier=lambda: "full",
            )
            proposal = api.propose(
                "owner-1", "Implement the feature and run tests.", str(workspace),
                authority_profile=AgentAuthorityProfile.FULL_OS,
            )

            result = api.activate(
                "owner-1", proposal["proposal_id"], "console-session-1",
                confirmed=True,
            )

            self.assertEqual("candidate_ready", result["engineering_task"]["stage"])
            self.assertIsNotNone(authorizer.challenge)
            self.assertEqual(
                authorizer.grant.break_glass_decision_id,
                authorizer.decision.decision_id,
            )
            api.close()

    def test_manifest_toolchain_outranks_unrelated_source_file_languages(self):
        evidence = SimpleNamespace(
            manifests=(SimpleNamespace(ecosystem="node"),),
            files=(
                SimpleNamespace(language="typescript"),
                SimpleNamespace(language="python"),
            ),
        )

        self.assertEqual(("node",), _toolchains(evidence))

    def test_source_languages_are_fallback_when_no_manifest_is_recognized(self):
        evidence = SimpleNamespace(
            manifests=(SimpleNamespace(ecosystem="unknown"),),
            files=(SimpleNamespace(language="python"),),
        )

        self.assertEqual(("python3",), _toolchains(evidence))

    def test_approved_analysis_plan_resolves_same_session_follow_up(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "project"
            workspace.mkdir()
            identifiers = iter(("plan", "implementation"))
            api = ProductNaturalEngineeringApi(
                "owner-1",
                SQLiteNaturalEngineeringProposalStore(Path(temporary) / "p.sqlite3"),
                _Authentication(), _Authorizer(), _PlanningLoop(), _Observer(),
                clock=lambda: NOW, identifier=lambda: next(identifiers),
                conversation=NaturalEngineeringConversation(),
            )
            proposal = api.propose(
                "owner-1", "Analyze this repository and propose an improvement plan.",
                str(workspace), transport_session_id="console-session-1",
            )
            result = api.activate(
                "owner-1", proposal["proposal_id"], "console-session-1",
                confirmed=True,
            )
            self.assertEqual(
                "Decision-complete design for improve this project",
                result["engineering_task"]["architecture_plan"]["title"],
            )

            follow_up = api.propose(
                "owner-1", "Ok, implement the plan.", str(workspace),
                transport_session_id="console-session-1",
            )
            task = follow_up["definition"]["payload"]["task"]
            self.assertIn("Referenced repository plan", task["intent"])
            self.assertIn("src/app.py", task["intent"])
            self.assertEqual(
                ["observe", "propose", "modify", "execute"],
                follow_up["grant"]["payload"]["authorities"],
            )
            api.close()

    def test_prompt_proposes_then_confirmed_session_activates_and_prepares(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "project"
            workspace.mkdir()
            api = ProductNaturalEngineeringApi(
                "owner-1",
                SQLiteNaturalEngineeringProposalStore(Path(temporary) / "p.sqlite3"),
                _Authentication(), _Authorizer(), _Loop(), _Observer(),
                clock=lambda: NOW, identifier=lambda: "one",
            )
            proposal = api.propose(
                "owner-1", "Implement the Python feature and run tests.",
                str(workspace),
            )
            self.assertEqual("proposed", proposal["status"])
            self.assertEqual(
                ["observe", "propose", "modify", "execute"],
                proposal["grant"]["payload"]["authorities"],
            )
            self.assertEqual(0, proposal["budget"]["maximum_network_bytes"])
            self.assertIn(
                "git_write",
                proposal["definition"]["payload"]["task"]["permitted_operations"],
            )

            result = api.activate(
                "owner-1", proposal["proposal_id"], "console-session-1",
                confirmed=True,
            )
            self.assertEqual("candidate_ready", result["engineering_task"]["stage"])
            with self.assertRaisesRegex(PermissionError, "consumed"):
                api.activate(
                    "owner-1", proposal["proposal_id"], "console-session-1",
                    confirmed=True,
                )
            api.close()

    def test_high_risk_request_requires_separate_ceremonies(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "project"
            workspace.mkdir()
            api = ProductNaturalEngineeringApi(
                "owner-1",
                SQLiteNaturalEngineeringProposalStore(Path(temporary) / "p.sqlite3"),
                _Authentication(), _Authorizer(), _Loop(), _Observer(),
                clock=lambda: NOW, identifier=lambda: "two",
            )
            proposal = api.propose(
                "owner-1", "Fix it and push to production.", str(workspace),
            )
            self.assertEqual(
                ["publish", "production_mutate"],
                proposal["separately_confirmed_authorities"],
            )
            with self.assertRaisesRegex(PermissionError, "separate owner"):
                api.activate(
                    "owner-1", proposal["proposal_id"], "session-1", confirmed=True,
                )
            api.close()

    def test_exact_integration_resources_require_their_own_owner_ceremony(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "project"
            workspace.mkdir()
            authentication = _Authentication()
            grants = _Authorizer()
            api = ProductNaturalEngineeringApi(
                "owner-1",
                SQLiteNaturalEngineeringProposalStore(
                    Path(temporary) / "p.sqlite3",
                ),
                authentication, grants, _Loop(), _Observer(),
                clock=lambda: NOW, identifier=lambda: "resources",
                grant_reader=grants,
            )
            proposal = api.propose(
                "owner-1",
                (
                    "Update api.py and preview the API end-to-end with network "
                    "access to api.example.com:443 using secret ref db/password."
                ),
                str(workspace),
            )
            resource = proposal["integration_resource_grant"]
            self.assertEqual("approval_required", resource["status"])
            self.assertEqual(
                ["api.example.com:443"],
                resource["document"]["payload"]["scope"]["network_hosts"],
            )
            self.assertEqual(
                ["db/password"],
                resource["document"]["payload"]["scope"]["secret_refs"],
            )
            with self.assertRaisesRegex(PermissionError, "separate owner"):
                api.activate(
                    "owner-1", proposal["proposal_id"], "console-session-1",
                    confirmed=True,
                )

            approved = api.approve_integration_resources(
                "owner-1", proposal["proposal_id"], "console-session-1",
                confirmed=True,
            )
            self.assertEqual(
                "approved",
                approved["proposal"]["integration_resource_grant"]["status"],
            )
            self.assertEqual(
                "engineering-integration-resource-grant",
                authentication.purpose,
            )
            result = api.activate(
                "owner-1", proposal["proposal_id"], "console-session-1",
                confirmed=True,
            )
            self.assertEqual("candidate_ready", result["engineering_task"]["stage"])
            api.close()

    def test_confirmed_activation_runs_composed_execution_to_checkpoint(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "project"
            workspace.mkdir()
            executor = _Executor()
            api = ProductNaturalEngineeringApi(
                "owner-1",
                SQLiteNaturalEngineeringProposalStore(Path(temporary) / "p.sqlite3"),
                _Authentication(), _Authorizer(), _Loop(), _Observer(),
                executor=executor, clock=lambda: NOW, identifier=lambda: "three",
            )
            proposal = api.propose(
                "owner-1", "Implement and test the Python feature.",
                str(workspace),
            )
            result = api.activate(
                "owner-1", proposal["proposal_id"], "console-session-1",
                confirmed=True,
            )
            self.assertEqual(
                "changeset_approval_required",
                result["engineering_task"]["stage"],
            )
            self.assertEqual("console-session-1", executor.session_id)
            api.close()
            self.assertTrue(executor.closed)

    def test_interrupted_execution_remains_resumable(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "project"
            workspace.mkdir()
            executor = _InterruptingExecutor()
            loop = _ResumableLoop()
            store = SQLiteNaturalEngineeringProposalStore(
                Path(temporary) / "p.sqlite3",
            )
            api = ProductNaturalEngineeringApi(
                "owner-1", store, _Authentication(), _Authorizer(), loop,
                _Observer(), executor=executor, clock=lambda: NOW,
                identifier=lambda: "four",
            )
            proposal = api.propose(
                "owner-1", "Implement and test the Python feature.",
                str(workspace),
            )
            with self.assertRaisesRegex(RuntimeError, "interrupted"):
                api.activate(
                    "owner-1", proposal["proposal_id"], "console-session-1",
                    confirmed=True,
                )
            self.assertEqual("interrupted", store.status(proposal["proposal_id"]))
            result = api.activate(
                "owner-1", proposal["proposal_id"], "console-session-1",
                confirmed=True,
            )
            self.assertEqual(
                "changeset_approval_required",
                result["engineering_task"]["stage"],
            )
            self.assertEqual(1, loop.starts)
            api.close()

    def test_exact_review_finding_requires_authenticated_truthful_waiver(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary) / "project"
            workspace.mkdir()
            authentication = _Authentication()
            loop = _ReviewLoop()
            api = ProductNaturalEngineeringApi(
                "owner-1",
                SQLiteNaturalEngineeringProposalStore(Path(temporary) / "p.sqlite3"),
                authentication, _Authorizer(), loop, _Observer(),
                executor=_Executor(), clock=lambda: NOW,
                identifier=lambda: "review",
            )
            proposal = api.propose(
                "owner-1", "Fix the Python security boundary and test it.",
                str(workspace),
            )
            api.activate(
                "owner-1", proposal["proposal_id"], "console-session-1",
                confirmed=True,
            )
            checkpoint = loop.checkpoint
            finding = checkpoint.findings[0]
            consequences = review_waiver_consequences_digest(checkpoint, finding)
            with self.assertRaisesRegex(PermissionError, "consequences changed"):
                api.waive_review(
                    "owner-1", proposal["proposal_id"], checkpoint.checkpoint_id,
                    finding.finding_id, "0" * 64, "console-session-1",
                    confirmed=True,
                )
            result = api.waive_review(
                "owner-1", proposal["proposal_id"], checkpoint.checkpoint_id,
                finding.finding_id, consequences, "console-session-1",
                confirmed=True,
            )
            self.assertEqual("engineering-review-waiver", authentication.purpose)
            self.assertEqual(consequences, authentication.digest)
            self.assertEqual(
                "review_waived",
                result["engineering_task"]["review_waiver"]["payload"][
                    "truthful_assurance"
                ],
            )
            self.assertEqual(EngineeringReviewStatus.WAIVED, loop.checkpoint.status)
            api.close()


class _Observer:
    def observe(self, task_id, workspace_root):
        return SimpleNamespace(
            manifests=(SimpleNamespace(ecosystem="python"),), files=(),
        )


class _Authentication:
    def issue(self, owner_id, purpose, digest, transport_session_id=None):
        self.purpose = purpose
        self.digest = digest
        return SimpleNamespace(context_id="context-1")

    def belongs_to_session(self, context_id, session_id):
        return context_id == "context-1" and session_id.startswith("console-")


class _Authorizer:
    def __init__(self):
        self.grants = {}

    def activate(self, grant, approval, challenge=None, decision=None):
        self.grant = grant
        self.challenge = challenge
        self.decision = decision
        self.grants[grant.grant_id] = grant

    def usable(self, grant_id):
        return self.grants.get(grant_id)


class _Loop:
    def start(self, owner_id, definition, budget):
        return SimpleNamespace(task_id=definition.task.task_id)

    def prepare(self, owner_id, task_id):
        return {"task_id": task_id, "stage": "candidate_ready"}

    def database_results(self, owner_id, task_id):
        return ()

    def database_postapply_receipts(self, owner_id, task_id):
        return ()


class _AuthorizingLoop(_Loop):
    def __init__(self, authorizer):
        self.authorizer = authorizer

    def start(self, owner_id, definition, budget):
        if self.authorizer.usable(definition.task.grant_id) is None:
            raise PermissionError("grant required")
        return super().start(owner_id, definition, budget)


class _PlanningLoop(_Loop):
    def preparation(self, owner_id, task_id):
        decisions = tuple(
            ArchitectureDecision(
                area, True, f"Improve {area.value} in src/app.py.",
                ("src/app.py", "tests/test_app.py"),
            )
            for area in ArchitectureArea
        )
        proposal = ArchitectureProposal(
            f"architecture-{task_id}", task_id, f"analysis-{task_id}", NOW,
            "Decision-complete design for improve this project", decisions,
            ("tests/test_app.py",), True,
        )
        return SimpleNamespace(proposal=proposal)


class _Executor:
    def __init__(self):
        self.session_id = None
        self.closed = False

    def execute(self, owner_id, definition, session_id, principal_id):
        self.session_id = session_id
        return {
            "task_id": definition.task.task_id,
            "stage": "changeset_approval_required",
        }

    def close(self):
        self.closed = True


class _InterruptingExecutor(_Executor):
    def __init__(self):
        super().__init__()
        self.calls = 0

    def execute(self, owner_id, definition, session_id, principal_id):
        self.calls += 1
        if self.calls == 1:
            raise RuntimeError("interrupted after durable preparation")
        return super().execute(owner_id, definition, session_id, principal_id)


class _ResumableLoop(_Loop):
    def __init__(self):
        self.started = False
        self.starts = 0

    def start(self, owner_id, definition, budget):
        if self.started:
            raise RuntimeError("engineering task already exists")
        self.started = True
        self.starts += 1
        return super().start(owner_id, definition, budget)

    def inspect(self, owner_id, task_id):
        if not self.started:
            raise KeyError("missing")
        return {"task_id": task_id, "stage": "candidate_ready"}


class _ReviewLoop(_Loop):
    def start(self, owner_id, definition, budget):
        self.started = True
        self.task_id = definition.task.task_id
        finding = EngineeringReviewFinding(
            "finding-review-1", EngineeringReviewDiscipline.SECURITY,
            EngineeringFindingSeverity.HIGH, "Explicit security risk",
            "src/security.py", ("evidence-1",),
            EngineeringFindingDisposition.OPEN,
        )
        self.checkpoint = EngineeringReviewCheckpoint(
            "checkpoint-review-1", self.task_id, "candidate-1", "a" * 64,
            "generation-1", "reviewer-1", "signed-reviewer-1",
            (EngineeringReviewDiscipline.SECURITY,), (finding,),
            EngineeringReviewStatus.BLOCKED, NOW,
        )
        self.evidence = []
        return super().start(owner_id, definition, budget)

    def inspect(self, owner_id, task_id):
        if not getattr(self, "started", False):
            raise KeyError("missing")
        return {"task_id": task_id, "stage": "candidate_ready"}

    def reviews_for_task(self, owner_id, task_id):
        return (self.checkpoint,)

    def review_evidence_for_task(self, owner_id, task_id):
        return tuple(self.evidence)

    def waive_review_finding(self, owner_id, decision):
        finding = replace(
            self.checkpoint.findings[0],
            disposition=EngineeringFindingDisposition.WAIVED,
            waiver_decision_id=decision.decision_id,
        )
        self.checkpoint = replace(
            self.checkpoint, findings=(finding,),
            status=EngineeringReviewStatus.WAIVED, revision=1,
        )
        self.evidence.append(decision)
        return self.checkpoint


if __name__ == "__main__":
    unittest.main()
