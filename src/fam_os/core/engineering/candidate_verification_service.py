"""Core policy for exact-authority signed candidate verification."""

from dataclasses import replace
from datetime import datetime, timezone
from typing import Protocol
from uuid import uuid4

from fam_os.core.engineering.authority import EngineeringAuthority, EngineeringOperation
from fam_os.core.engineering.candidate_verification import (
    CandidateVerificationRecord, CandidateVerificationStatus,
)
from fam_os.core.engineering.diagnostic_redaction import (
    sanitize_diagnostic_evidence,
)
from fam_os.core.engineering.evidence import EngineeringEvidence, EngineeringOutcome
from fam_os.core.engineering.execution import EngineeringSandboxProfile, EngineeringToolReceipt
from fam_os.core.engineering.execution_policy import SignedToolRecipeCatalog
from fam_os.core.engineering.grants import (
    EngineeringAuthorizationDecision, EngineeringAuthorizationRequest,
    EngineeringResourceImpact,
)
from fam_os.core.engineering.preparation import EngineeringPreparationResult
from fam_os.core.engineering.task_definition import EngineeringTaskDefinition


class VerificationStore(Protocol):
    def begin(self, record: CandidateVerificationRecord) -> None: ...
    def save(self, expected_revision: int, record: CandidateVerificationRecord) -> None: ...


class VerificationRunner(Protocol):
    def run(self, task_id, candidate, recipe_id, recipe_version, profile) -> EngineeringToolReceipt: ...


class ReceiptVerifier(Protocol):
    def verify(self, receipt, recipe_version): ...


class DecisionAuthorizer(Protocol):
    def authorize(self, request: EngineeringAuthorizationRequest) -> EngineeringAuthorizationDecision: ...


class CandidateVerificationService:
    def __init__(self, authorizer: DecisionAuthorizer, recipes: SignedToolRecipeCatalog, runner: VerificationRunner, verifier: ReceiptVerifier, store: VerificationStore, *, clock=None, identifier=None) -> None:
        self._authorizer = authorizer
        self._recipes = recipes
        self._runner = runner
        self._verifier = verifier
        self._store = store
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._identifier = identifier or (lambda: str(uuid4()))

    def verify(self, definition: EngineeringTaskDefinition, preparation: EngineeringPreparationResult, *, verification_id: str, session_id: str, principal_id: str, toolchain: str, recipe_id: str, recipe_version: str, profile: EngineeringSandboxProfile) -> CandidateVerificationRecord:
        self._validate(definition, preparation, toolchain, recipe_id, recipe_version, profile)
        first = self._authorize(
            definition, preparation, verification_id, session_id,
            principal_id, toolchain, profile,
        )
        now = self._clock()
        record = CandidateVerificationRecord(
            verification_id, definition.definition_id, definition.task.task_id,
            preparation.candidate.candidate_id, session_id, principal_id,
            toolchain, recipe_id, recipe_version, profile,
            (first.decision_id,), CandidateVerificationStatus.INTENT_RECORDED,
            0, now, now,
        )
        self._store.begin(record)
        live = self._authorize(
            definition, preparation, verification_id, session_id,
            principal_id, toolchain, profile,
        )
        record = replace(
            record, authorization_decision_ids=(live.decision_id,), revision=1,
            updated_at=self._clock(),
        )
        self._store.save(0, record)
        try:
            receipt = self._runner.run(
                definition.task.task_id, preparation.candidate,
                recipe_id, recipe_version, profile,
            )
        except Exception:
            return self._recovery(record, "sandbox_run_interrupted")
        verdict = self._verifier.verify(receipt, recipe_version)
        evidence = self._evidence(definition, preparation, receipt, verdict)
        completed = replace(
            record, status=CandidateVerificationStatus.COMPLETED,
            revision=record.revision + 1, updated_at=self._clock(),
            receipt=receipt, evidence=evidence, passed=verdict.passed,
        )
        self._store.save(record.revision, completed)
        return completed

    def _authorize(self, definition, preparation, verification_id, session_id, principal_id, toolchain, profile):
        request = EngineeringAuthorizationRequest(
            self._identifier(), definition.task.grant_id, principal_id,
            EngineeringAuthority.EXECUTE, definition.task.task_id, session_id,
            verification_id, None, preparation.candidate.owner_workspace,
            None, toolchain, None, None, None, None, None,
            EngineeringResourceImpact(
                profile.wall_seconds, 1, profile.process_limit, 0, 0, 0,
            ),
        )
        decision = self._authorizer.authorize(request)
        if not decision.allowed or decision.request_id != request.request_id or decision.grant_id != request.grant_id or decision.authority is not request.authority:
            raise PermissionError("candidate verification lacks exact live execute authority")
        return decision

    def _evidence(self, definition, preparation, receipt, verdict):
        return EngineeringEvidence(
            f"evidence-{self._identifier()}", definition.task.task_id,
            self._clock(),
            EngineeringOutcome.SUCCEEDED if verdict.passed else EngineeringOutcome.FAILED,
            (preparation.candidate.baseline_id,), (preparation.proposal.proposal_id,),
            (), (receipt.receipt_id,), tuple(verdict.verifier_ids),
            receipt.artifact_digests,
            (),
            () if verdict.passed else (sanitize_diagnostic_evidence(verdict.reason),),
        )

    def _recovery(self, record, code):
        updated = replace(
            record, status=CandidateVerificationStatus.RECOVERY_REQUIRED,
            revision=record.revision + 1, updated_at=self._clock(),
            failure_code=code,
        )
        self._store.save(record.revision, updated)
        return updated

    def _validate(self, definition, preparation, toolchain, recipe_id, recipe_version, profile):
        task = definition.task
        if preparation.definition_id != definition.definition_id or preparation.candidate.task_id != task.task_id:
            raise ValueError("candidate verification differs from durable task")
        if EngineeringAuthority.EXECUTE not in task.authorities or EngineeringOperation.RUN_TOOL not in task.permitted_operations:
            raise PermissionError("candidate verification is outside durable task authority")
        if toolchain not in task.toolchains:
            raise PermissionError("candidate verification toolchain is outside durable task scope")
        recipe = self._recipes.get(recipe_id, recipe_version)
        names = {recipe.ecosystem.value, recipe.executable_path.rsplit("/", 1)[-1]}
        if toolchain not in names:
            raise PermissionError("signed recipe does not match the admitted toolchain")
        if profile.network_mode.value != "denied" or profile.wall_seconds > task.max_wall_seconds:
            raise PermissionError("candidate verification profile exceeds durable task scope")
