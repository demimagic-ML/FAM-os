import tempfile
import unittest
from dataclasses import replace
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

from fam_os.adapters.sqlite import SQLiteCandidateVerificationStore
from fam_os.core.engineering import (
    CandidateVerificationService, CandidateVerificationStatus,
    EngineeringAuthority, EngineeringEcosystem, EngineeringOperation,
    EngineeringSandboxProfile, EngineeringTaskDefinition,
    EngineeringToolReceipt, SandboxNetworkMode, ToolQualificationStatus,
    engineering_task_digest,
)
from fam_os.core.engineering.grants import EngineeringAuthorizationDecision
from fam_os.core.engineering.preparation import EngineeringPreparationResult
from tests.contract.schema_repository_fixtures import repository_schema_values
from tests.contract.schema_task_definition_fixtures import task_definition_schema_values
from tests.contract.schema_transaction_fixtures import transaction_schema_values


NOW = datetime(2026, 7, 19, 13, 0, tzinfo=timezone.utc)


class CandidateVerificationServiceTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.store = SQLiteCandidateVerificationStore(
            Path(self.temporary.name) / "verification.sqlite3",
        )
        self.definition = _definition()
        self.preparation = _preparation(self.definition)
        self.profile = EngineeringSandboxProfile(
            "profile-1", 256 * 1024**2, 2, 10, 8, 65_536, 1024**2,
            SandboxNetworkMode.DENIED, (), (("PATH", "/usr/bin:/bin"),),
        )

    def tearDown(self):
        self.store.close()
        self.temporary.cleanup()

    def test_signed_receipt_is_persisted_and_aggregated_as_lifecycle_evidence(self):
        authorizer = _Authorizer()
        runner = _Runner(self.preparation)
        service = self._service(authorizer, runner, _Verifier(True))
        record = service.verify(
            self.definition, self.preparation, verification_id="verification-1",
            session_id="session-1", principal_id="principal-1",
            toolchain="python3", recipe_id="engineering.python.test",
            recipe_version="1.0.0", profile=self.profile,
        )
        self.assertEqual(CandidateVerificationStatus.COMPLETED, record.status)
        self.assertTrue(record.passed)
        self.assertEqual((record.receipt.receipt_id,), record.evidence.tool_run_ids)
        self.assertEqual((record,), self.store.for_task(self.definition.task.task_id))
        self.assertEqual(2, len(authorizer.requests))
        self.assertEqual("python3", authorizer.requests[-1].toolchain)

    def test_revocation_after_intent_prevents_sandbox_launch(self):
        authorizer = _Authorizer(deny_at=2)
        runner = _Runner(self.preparation)
        with self.assertRaises(PermissionError):
            self._service(authorizer, runner, _Verifier(True)).verify(
                self.definition, self.preparation,
                verification_id="verification-revoked", session_id="session-1",
                principal_id="principal-1", toolchain="python3",
                recipe_id="engineering.python.test", recipe_version="1.0.0",
                profile=self.profile,
            )
        self.assertEqual(0, runner.calls)
        self.assertEqual(
            CandidateVerificationStatus.INTENT_RECORDED,
            self.store.for_task(self.definition.task.task_id)[0].status,
        )

    def test_interrupted_sandbox_is_recovery_required_and_never_claims_evidence(self):
        record = self._service(
            _Authorizer(), _Runner(self.preparation, fail=True), _Verifier(True),
        ).verify(
            self.definition, self.preparation,
            verification_id="verification-crash", session_id="session-1",
            principal_id="principal-1", toolchain="python3",
            recipe_id="engineering.python.test", recipe_version="1.0.0",
            profile=self.profile,
        )
        self.assertEqual(CandidateVerificationStatus.RECOVERY_REQUIRED, record.status)
        self.assertIsNone(record.evidence)
        self.assertFalse(record.passed)

    def test_failed_verdict_is_completed_but_not_successful(self):
        record = self._service(
            _Authorizer(), _Runner(self.preparation), _Verifier(False),
        ).verify(
            self.definition, self.preparation,
            verification_id="verification-failed", session_id="session-1",
            principal_id="principal-1", toolchain="python3",
            recipe_id="engineering.python.test", recipe_version="1.0.0",
            profile=self.profile,
        )
        self.assertEqual(CandidateVerificationStatus.COMPLETED, record.status)
        self.assertFalse(record.passed)
        self.assertEqual("verification failed", record.evidence.unresolved_risks[0])

    def test_secret_bearing_verifier_reason_is_never_persisted(self):
        verifier = _Verifier(False)
        verifier.reason = "failure token=credential-value"
        record = self._service(
            _Authorizer(), _Runner(self.preparation), verifier,
        ).verify(
            self.definition, self.preparation,
            verification_id="verification-secret", session_id="session-1",
            principal_id="principal-1", toolchain="python3",
            recipe_id="engineering.python.test", recipe_version="1.0.0",
            profile=self.profile,
        )

        self.assertIn("REDACTED_DIAGNOSTIC", record.evidence.unresolved_risks[0])
        self.assertNotIn("credential-value", record.evidence.unresolved_risks[0])

    def _service(self, authorizer, runner, verifier):
        return CandidateVerificationService(
            authorizer, _Catalog(), runner, verifier, self.store,
            clock=lambda: NOW, identifier=_ids(),
        )


class _Catalog:
    recipe = SimpleNamespace(
        ecosystem=EngineeringEcosystem.PYTHON,
        executable_path="/usr/bin/python3",
    )

    def get(self, recipe_id, recipe_version):
        if (recipe_id, recipe_version) != ("engineering.python.test", "1.0.0"):
            raise LookupError("recipe unavailable")
        return self.recipe


class _Authorizer:
    def __init__(self, deny_at=None):
        self.deny_at = deny_at
        self.requests = []

    def authorize(self, request):
        self.requests.append(request)
        allowed = len(self.requests) != self.deny_at
        return EngineeringAuthorizationDecision(
            f"decision-{len(self.requests)}", request.request_id, request.grant_id,
            request.authority, NOW, allowed, "authorized" if allowed else "revoked",
        )


class _Runner:
    def __init__(self, preparation, fail=False):
        self.preparation = preparation
        self.fail = fail
        self.calls = 0

    def run(self, task_id, candidate, recipe_id, recipe_version, profile):
        self.calls += 1
        if self.fail:
            raise RuntimeError("sandbox interrupted")
        return EngineeringToolReceipt(
            "receipt-1", task_id, candidate.candidate_id, recipe_id,
            "a" * 64, profile.profile_id, "b" * 64, NOW, NOW, 0,
            "c" * 64, "d" * 64, (), (),
            ("bubblewrap-unshare-all", "cgroup-v2-systemd", "bounded-rlimits"),
            ToolQualificationStatus.PASSED,
        )


class _Verifier:
    def __init__(self, passed):
        self.passed = passed
        self.reason = "passed" if passed else "verification failed"

    def verify(self, receipt, recipe_version):
        return SimpleNamespace(
            passed=self.passed, verifier_ids=("verifier-1",),
            reason=self.reason,
        )


def _definition():
    base = task_definition_schema_values()[0]
    task = replace(
        base.task, task_id="task-repository-1", created_at=NOW - timedelta(minutes=1),
        expires_at=NOW + timedelta(hours=1), workspace_roots=("/workspace",),
        authorities=(EngineeringAuthority.OBSERVE, EngineeringAuthority.PROPOSE,
                     EngineeringAuthority.MODIFY, EngineeringAuthority.EXECUTE),
        permitted_operations=(EngineeringOperation.READ, EngineeringOperation.CREATE,
                              EngineeringOperation.RUN_TOOL),
        toolchains=("python3",), network_hosts=(), package_registries=(),
        git_remote=None, git_branch=None,
    )
    return EngineeringTaskDefinition(
        "definition-task-repository-1", task, "acceptance-1", NOW,
        engineering_task_digest(task),
    )


def _preparation(definition):
    evidence, _request, analysis, proposal, _graph, _event = repository_schema_values()
    candidate = replace(
        transaction_schema_values()[2], task_id=definition.task.task_id,
        owner_workspace="/workspace",
    )
    return EngineeringPreparationResult(
        definition.definition_id, evidence, analysis, proposal, candidate,
    )


def _ids():
    values = iter(f"id-{index}" for index in range(20))
    return lambda: next(values)


if __name__ == "__main__":
    unittest.main()
