import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fam_os.adapters.shell.natural_engineering import NaturalEngineeringShellAdapter
from fam_os.shell import (
    ShellAskCommand, ShellContext, ShellContextKind, ShellDecision,
    ShellDecisionCommand, ShellRunState,
)


class NaturalEngineeringShellAdapterTests(unittest.TestCase):
    def test_plain_language_workspace_request_uses_two_exact_approvals(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary).resolve()
            api = _Api(workspace)
            adapter = NaturalEngineeringShellAdapter(api)
            command = ShellAskCommand(
                "request-1", "Fix the Python bug and run tests.",
                (ShellContext(
                    "workspace-1", ShellContextKind.URI, str(workspace),
                    "Project",
                ),),
            )
            self.assertTrue(adapter.handles_ask(command))
            proposed = adapter.propose(command)
            self.assertEqual(ShellRunState.WAITING_APPROVAL, proposed.state)
            self.assertEqual("engineering.grant.activate", proposed.approval.capability_id)

            checkpoint = adapter.decide(ShellDecisionCommand(
                proposed.session_id, proposed.revision,
                proposed.approval.approval_id, ShellDecision.APPROVE,
            ))
            self.assertEqual(ShellRunState.WAITING_APPROVAL, checkpoint.state)
            self.assertEqual("changeset-1", checkpoint.approval.approval_id)
            self.assertIn("app.py", checkpoint.approval.summary)

            completed = adapter.decide(ShellDecisionCommand(
                checkpoint.session_id, checkpoint.revision,
                checkpoint.approval.approval_id, ShellDecision.APPROVE,
            ))
            self.assertEqual(ShellRunState.TERMINAL, completed.state)
            self.assertTrue(completed.result.verified)
            self.assertEqual(("verify-1", "git-1"), completed.result.evidence_ids)

    def test_integration_resources_use_a_distinct_approval_before_task_grant(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary).resolve()
            api = _Api(workspace)
            api.offer_resources = True
            adapter = NaturalEngineeringShellAdapter(api)
            proposed = adapter.propose(ShellAskCommand(
                "request-resources",
                (
                    "Run the API end-to-end with network access to "
                    "api.example.com:443 using secret ref db/password."
                ),
                (ShellContext(
                    "workspace-1", ShellContextKind.URI, str(workspace),
                    "Project",
                ),),
            ))
            self.assertEqual(
                "engineering.integration.resources.activate",
                proposed.approval.capability_id,
            )
            self.assertIn("api.example.com:443", proposed.approval.summary)
            self.assertIn("db/password", proposed.approval.summary)

            task_grant = adapter.decide(ShellDecisionCommand(
                proposed.session_id, proposed.revision,
                proposed.approval.approval_id, ShellDecision.APPROVE,
            ))
            self.assertEqual(1, task_grant.revision)
            self.assertEqual(
                "engineering.grant.activate",
                task_grant.approval.capability_id,
            )
            checkpoint = adapter.decide(ShellDecisionCommand(
                task_grant.session_id, task_grant.revision,
                task_grant.approval.approval_id, ShellDecision.APPROVE,
            ))
            self.assertEqual(
                "engineering.changeset.apply", checkpoint.approval.capability_id,
            )

    def test_application_capability_request_is_not_stolen_by_workspace_route(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary).resolve()
            adapter = NaturalEngineeringShellAdapter(_Api(workspace))
            command = ShellAskCommand(
                "request-application", "Create folder Ivan.",
                (
                    ShellContext(
                        "filesystem", ShellContextKind.APPLICATION,
                        "owner-filesystem", "Local filesystem",
                        ("os.directory.create",),
                    ),
                    ShellContext(
                        "workspace", ShellContextKind.URI, str(workspace),
                        "Project",
                    ),
                ),
            )

            self.assertFalse(adapter.handles_ask(command))

    def test_failed_proposal_is_terminal_and_never_reoffered_for_approval(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary).resolve()
            api = _Api(workspace)
            api.failed = True
            adapter = NaturalEngineeringShellAdapter(api)
            snapshot = adapter.propose(ShellAskCommand(
                "request-2", "Fix the Python bug.",
                (ShellContext(
                    "workspace-1", ShellContextKind.URI, str(workspace),
                    "Project",
                ),),
            ))
            failed = adapter.snapshot(type("Query", (), {
                "session_id": snapshot.session_id,
            })())
            self.assertEqual(ShellRunState.TERMINAL, failed.state)
            self.assertEqual("model_output_invalid", failed.result.reason)
            self.assertIsNone(failed.approval)

    def test_failed_task_reports_durable_incident_identity_and_evidence(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary).resolve()
            api = _Api(workspace)
            adapter = NaturalEngineeringShellAdapter(api)
            snapshot = adapter.propose(ShellAskCommand(
                "request-incident", "Fix the Python bug and run tests.",
                (ShellContext(
                    "workspace-1", ShellContextKind.URI, str(workspace),
                    "Project",
                ),),
            ))
            api.task = {
                "task_id": "task-1", "outcome": "verification_failed",
                "failure_code": "signed_candidate_verification_failed",
                "incident": {"payload": {
                    "incident_id": "incident-1", "stage": "detected",
                    "symptom_evidence_ids": ["verification-1"],
                }},
            }
            failed = adapter.snapshot(type("Query", (), {
                "session_id": snapshot.session_id,
            })())
            self.assertEqual(ShellRunState.TERMINAL, failed.state)
            self.assertIn("incident incident-1 is detected", failed.result.reason)
            self.assertIn("verification-1", failed.result.reason)

    def test_optional_rollback_uses_a_third_exact_approval(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary).resolve()
            api = _Api(workspace)
            api.offer_rollback = True
            adapter = NaturalEngineeringShellAdapter(api)
            proposed = adapter.propose(ShellAskCommand(
                "request-3", "Fix the Python bug and run tests.",
                (ShellContext(
                    "workspace-1", ShellContextKind.URI, str(workspace),
                    "Project",
                ),),
            ))
            checkpoint = adapter.decide(ShellDecisionCommand(
                proposed.session_id, proposed.revision,
                proposed.approval.approval_id, ShellDecision.APPROVE,
            ))
            rollback = adapter.decide(ShellDecisionCommand(
                checkpoint.session_id, checkpoint.revision,
                checkpoint.approval.approval_id, ShellDecision.APPROVE,
            ))
            self.assertEqual(ShellRunState.WAITING_APPROVAL, rollback.state)
            self.assertEqual(
                "engineering.changeset.rollback", rollback.approval.capability_id,
            )
            completed = adapter.decide(ShellDecisionCommand(
                rollback.session_id, rollback.revision,
                rollback.approval.approval_id, ShellDecision.APPROVE,
            ))
            self.assertEqual(ShellRunState.TERMINAL, completed.state)
            self.assertTrue(completed.result.verified)
            self.assertEqual(("rollback-1", "git-1"), completed.result.evidence_ids)

    def test_postapply_failure_offers_precommit_rollback_and_reports_no_commit(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary).resolve()
            api = _Api(workspace)
            api.fail_postapply = True
            adapter = NaturalEngineeringShellAdapter(api)
            proposed = adapter.propose(ShellAskCommand(
                "request-recovery", "Fix the Python bug and run tests.",
                (ShellContext(
                    "workspace-1", ShellContextKind.URI, str(workspace),
                    "Project",
                ),),
            ))
            checkpoint = adapter.decide(ShellDecisionCommand(
                proposed.session_id, proposed.revision,
                proposed.approval.approval_id, ShellDecision.APPROVE,
            ))
            recovery = adapter.decide(ShellDecisionCommand(
                checkpoint.session_id, checkpoint.revision,
                checkpoint.approval.approval_id, ShellDecision.APPROVE,
            ))
            self.assertEqual(ShellRunState.WAITING_APPROVAL, recovery.state)
            self.assertEqual(
                "engineering.changeset.rollback", recovery.approval.capability_id,
            )
            self.assertIn("Do not create a Git commit", recovery.approval.summary)
            self.assertEqual("failed", recovery.steps[2].state.value)

            completed = adapter.decide(ShellDecisionCommand(
                recovery.session_id, recovery.revision,
                recovery.approval.approval_id, ShellDecision.APPROVE,
            ))
            self.assertEqual(ShellRunState.TERMINAL, completed.state)
            self.assertTrue(completed.result.verified)
            self.assertIn("left Git history unchanged", completed.result.content)
            self.assertEqual(("rollback-1",), completed.result.evidence_ids)

    def test_requested_publication_uses_a_distinct_third_approval(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary).resolve()
            api = _Api(workspace)
            api.offer_publication = True
            adapter = NaturalEngineeringShellAdapter(api)
            proposed = adapter.propose(ShellAskCommand(
                "request-4", "Fix, test, push, and open a pull request.",
                (ShellContext(
                    "workspace-1", ShellContextKind.URI, str(workspace),
                    "Project",
                ),),
            ))
            checkpoint = adapter.decide(ShellDecisionCommand(
                proposed.session_id, proposed.revision,
                proposed.approval.approval_id, ShellDecision.APPROVE,
            ))
            publication = adapter.decide(ShellDecisionCommand(
                checkpoint.session_id, checkpoint.revision,
                checkpoint.approval.approval_id, ShellDecision.APPROVE,
            ))
            self.assertEqual(ShellRunState.WAITING_APPROVAL, publication.state)
            self.assertEqual(
                "engineering.git.publish", publication.approval.capability_id,
            )
            self.assertIn("refs/heads/feature/fam", publication.approval.summary)
            completed = adapter.decide(ShellDecisionCommand(
                publication.session_id, publication.revision,
                publication.approval.approval_id, ShellDecision.APPROVE,
            ))
            self.assertEqual(ShellRunState.TERMINAL, completed.state)
            self.assertTrue(completed.result.verified)
            self.assertIn("publication-receipt-1", completed.result.evidence_ids)

    def test_blocking_review_uses_exact_reduced_assurance_waiver(self):
        with tempfile.TemporaryDirectory() as temporary:
            workspace = Path(temporary).resolve()
            api = _Api(workspace)
            api.offer_review = True
            adapter = NaturalEngineeringShellAdapter(api)
            proposed = adapter.propose(ShellAskCommand(
                "request-review", "Fix the Python security issue.",
                (ShellContext(
                    "workspace-1", ShellContextKind.URI, str(workspace),
                    "Project",
                ),),
            ))
            review = adapter.decide(ShellDecisionCommand(
                proposed.session_id, proposed.revision,
                proposed.approval.approval_id, ShellDecision.APPROVE,
            ))
            self.assertEqual("engineering.review.waive", review.approval.capability_id)
            self.assertIn("does not claim resolution", review.approval.summary)
            changeset = adapter.decide(ShellDecisionCommand(
                review.session_id, review.revision,
                review.approval.approval_id, ShellDecision.APPROVE,
            ))
            self.assertEqual("engineering.changeset.apply", changeset.approval.capability_id)
            self.assertEqual(("a" * 64), api.waived_consequences)


class _Api:
    owner_id = "owner-1"

    def __init__(self, workspace):
        self.workspace = workspace
        self.task = None
        self.failed = False
        self.offer_rollback = False
        self.offer_publication = False
        self.fail_postapply = False
        self.offer_review = False
        self.offer_resources = False
        self.resources_approved = False
        self.waived_consequences = None

    def propose(
        self, owner_id, prompt, workspace, *, transport_session_id=None,
    ):
        return _proposal(
            self.workspace, resources=self.offer_resources,
            resources_approved=self.resources_approved,
        )

    def progress(self, owner_id, proposal_id):
        proposal = _proposal(
            self.workspace, resources=self.offer_resources,
            resources_approved=self.resources_approved,
        )
        if self.failed:
            proposal.update({
                "status": "failed", "failure_code": "model_output_invalid",
            })
        return {"proposal": proposal, "engineering_task": self.task}

    def activate(self, owner_id, proposal_id, session_id, confirmed):
        self.task = _review_checkpoint() if self.offer_review else _checkpoint()
        return {"proposal": self.progress(owner_id, proposal_id)["proposal"], "engineering_task": self.task}

    def approve_integration_resources(
        self, owner_id, proposal_id, session_id, confirmed,
    ):
        self.resources_approved = True
        return self.progress(owner_id, proposal_id)

    def approve_changeset(
        self, owner_id, proposal_id, changeset_id, session_id, confirmed,
    ):
        if self.fail_postapply:
            self.task = {
                "task_id": "task-1", "stage": "applied",
                "outcome": "postapply_verification_failed",
                "failure_code": "signed_postapply_verification_failed",
                "rollback_checkpoint": {
                    "rollback_id": "rollback-changeset-1",
                    "paths": ["app.py"],
                    "consequences": [
                        "Restore unchanged FAM-owned paths",
                        "Do not create a Git commit",
                    ],
                },
                "incident": {"payload": {
                    "incident_id": "incident-1",
                    "stage": "remediation_proposed",
                }},
                "incident_evidence": [{"payload": {"receipt_id": "evidence-1"}}],
            }
            return {
                "proposal": _proposal(self.workspace),
                "engineering_task": self.task,
            }
        self.task = {
            "task_id": "task-1", "stage": "committed",
            "outcome": "local_commit_completed",
            "test_receipt_ids": ["verify-1"], "git_receipt_ids": ["git-1"],
        }
        if self.offer_rollback:
            self.task["rollback_checkpoint"] = {
                "rollback_id": "rollback-changeset-1",
                "paths": ["app.py"],
            }
        if self.offer_publication:
            self.task.update(_publication_task())
        return {"proposal": _proposal(self.workspace), "engineering_task": self.task}

    def approve_publication(
        self, owner_id, proposal_id, publication_id, session_id, confirmed,
    ):
        self.task = {
            "task_id": "task-1", "stage": "completed",
            "outcome": "publication_completed",
            "test_receipt_ids": ["verify-1"], "git_receipt_ids": ["git-1"],
            "publication_receipt": {"payload": {
                "receipt_id": "publication-receipt-1",
                "change_request_url": "https://git.example/draft/1",
            }},
        }
        return {"proposal": _proposal(self.workspace), "engineering_task": self.task}

    def rollback(
        self, owner_id, proposal_id, rollback_id, session_id, confirmed,
    ):
        self.task = {
            "task_id": "task-1", "stage": "rolled_back",
            "outcome": "rollback_completed",
            "rollback_receipt_ids": ["rollback-1"],
            "git_receipt_ids": [] if self.fail_postapply else ["git-1"],
        }
        if not self.fail_postapply:
            self.task["git_rollback_delivery"] = {"payload": {"delivery_id": "git-1"}}
        return {"proposal": _proposal(self.workspace), "engineering_task": self.task}

    def waive_review(
        self, owner_id, proposal_id, checkpoint_id, finding_id,
        consequences_sha256, session_id, confirmed,
    ):
        self.waived_consequences = consequences_sha256
        self.task = _checkpoint()
        return {"proposal": _proposal(self.workspace), "engineering_task": self.task}

    def decline(self, owner_id, proposal_id):
        pass


def _proposal(workspace, *, resources=False, resources_approved=False):
    expires = datetime.now(timezone.utc) + timedelta(hours=1)
    proposal = {
        "proposal_id": "proposal-1", "status": "proposed",
        "separately_confirmed_authorities": (
            ["network", "secret_use"] if resources else []
        ),
        "grant": {"payload": {
            "authorities": ["observe", "propose", "modify", "execute"],
            "expires_at": expires.isoformat(),
            "scope": {"workspace_roots": [str(workspace)]},
        }},
    }
    proposal["integration_resource_grant"] = (
        None if not resources else {
            "status": "approved" if resources_approved else "approval_required",
            "approval_sha256": "a" * 64,
            "document": {"payload": {
                "grant_id": "grant-1-integration-resources",
                "authorities": ["execute", "network", "secret_use"],
                "expires_at": expires.isoformat(),
                "scope": {
                    "scope_id": "task-1",
                    "workspace_roots": [str(workspace)],
                    "network_hosts": ["api.example.com:443"],
                    "secret_refs": ["db/password"],
                },
                "resource_impact": {
                    "max_network_bytes": 16777216,
                    "max_changed_bytes": 0,
                },
            }},
        }
    )
    return proposal


def _publication_task():
    expires = datetime.now(timezone.utc) + timedelta(minutes=5)
    return {
        "outcome": "publication_approval_required",
        "publication_proposal": {
            "approval_sha256": "a" * 64,
            "document": {"payload": {
                "proposal_id": "publication-1",
                "remote_name": "origin",
                "source_ref": "refs/heads/feature/fam",
                "target_ref": "refs/heads/feature/fam",
                "expected_old_object_id": None,
                "proposed_new_object_id": "1" * 40,
                "commit_object_ids": ["1" * 40],
                "complete_diff_sha256": "b" * 64,
                "verification_evidence_ids": ["verify-1"],
                "title": "Fix bug", "body": "Verified change",
                "credential_ref": "secret.git.origin",
                "consequence_preview": ["Push one new branch"],
                "expires_at": expires.isoformat(),
            }},
        },
    }


def _checkpoint():
    return {
        "task_id": "task-1", "stage": "changeset_approval_required",
        "outcome": "changeset_approval_required",
        "changeset": {"payload": {
            "changeset_id": "changeset-1",
            "preview": {"items": [{
                "operation_kind": "patch_file", "path": "app.py",
                "preview": "- VALUE = 1 + VALUE = 2", "risk_codes": [],
            }]},
        }},
    }


def _review_checkpoint():
    return {
        "task_id": "task-1", "stage": "changeset_approval_required",
        "outcome": "independent_review_blocked",
        "review_waiver_checkpoint": {
            "checkpoint_id": "review-1", "finding_id": "finding-1",
            "discipline": "security", "severity": "high",
            "title": "Explicit security risk", "path": "app.py",
            "consequences_sha256": "a" * 64,
            "truthful_assurance_after_waiver": "review_waived",
        },
    }


if __name__ == "__main__":
    unittest.main()
