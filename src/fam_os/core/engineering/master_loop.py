"""Persistent bounded state machine for complete engineering lifecycles."""

import hashlib
from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
from typing import Protocol

from fam_os.core.engineering._validation import aware, positive, text, texts
from fam_os.core.engineering.version import ENGINEERING_CONTRACT_VERSION
from fam_os.core.engineering.task_definition import EngineeringTaskDefinition


class EngineeringLoopStage(StrEnum):
    REQUESTED = "requested"
    INSPECTED = "inspected"
    PROPOSED = "proposed"
    CANDIDATE_READY = "candidate_ready"
    VERIFIED = "verified"
    CHANGESET_APPROVAL_REQUIRED = "changeset_approval_required"
    APPLIED = "applied"
    REVERIFIED = "reverified"
    COMMITTED = "committed"
    PUBLICATION_APPROVAL_REQUIRED = "publication_approval_required"
    PUBLISHED = "published"
    COMPLETED = "completed"
    ROLLED_BACK = "rolled_back"
    FAILED = "failed"


@dataclass(frozen=True, slots=True)
class EngineeringLoopBudget:
    maximum_tokens: int
    maximum_wall_seconds: int
    maximum_commands: int
    maximum_network_bytes: int
    maximum_files: int
    maximum_storage_bytes: int
    used_tokens: int = 0
    used_wall_seconds: int = 0
    used_commands: int = 0
    used_network_bytes: int = 0
    used_files: int = 0
    used_storage_bytes: int = 0

    def __post_init__(self) -> None:
        for name in (
            "maximum_tokens", "maximum_wall_seconds", "maximum_commands",
            "maximum_network_bytes", "maximum_files", "maximum_storage_bytes",
        ):
            positive(
                getattr(self, name), name,
                allow_zero=name == "maximum_network_bytes",
            )
        for maximum, used in (
            (self.maximum_tokens, self.used_tokens),
            (self.maximum_wall_seconds, self.used_wall_seconds),
            (self.maximum_commands, self.used_commands),
            (self.maximum_network_bytes, self.used_network_bytes),
            (self.maximum_files, self.used_files),
            (self.maximum_storage_bytes, self.used_storage_bytes),
        ):
            if isinstance(used, bool) or not isinstance(used, int) or used < 0 or used > maximum:
                raise ValueError("engineering loop budget usage exceeds its monotonic maximum")


@dataclass(frozen=True, slots=True)
class EngineeringLoopState:
    task_id: str
    grant_id: str
    stage: EngineeringLoopStage
    revision: int
    budget: EngineeringLoopBudget
    repository_evidence_id: str | None
    architecture_proposal_id: str | None
    candidate_id: str | None
    checkpoint_ids: tuple[str, ...]
    verification_receipt_ids: tuple[str, ...]
    dependency_receipt_ids: tuple[str, ...]
    design_receipt_ids: tuple[str, ...]
    apply_receipt_ids: tuple[str, ...]
    rollback_receipt_ids: tuple[str, ...]
    git_receipt_ids: tuple[str, ...]
    publication_receipt_ids: tuple[str, ...]
    pending_changeset_id: str | None
    pending_publication_id: str | None
    last_event_sha256: str
    updated_at: datetime
    runtime_diagnostic_receipt_ids: tuple[str, ...] = ()
    database_receipt_ids: tuple[str, ...] = ()
    database_postapply_receipt_ids: tuple[str, ...] = ()
    integration_environment_receipt_ids: tuple[str, ...] = ()
    integration_environment_postapply_receipt_ids: tuple[str, ...] = ()
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        text(self.task_id, "task_id")
        text(self.grant_id, "grant_id")
        positive(self.revision, "revision", allow_zero=True)
        for name in (
            "repository_evidence_id", "architecture_proposal_id", "candidate_id",
            "pending_changeset_id", "pending_publication_id",
        ):
            value = getattr(self, name)
            if value is not None:
                text(value, name)
        for name in (
            "checkpoint_ids", "verification_receipt_ids", "dependency_receipt_ids",
            "design_receipt_ids", "apply_receipt_ids", "rollback_receipt_ids",
            "git_receipt_ids", "publication_receipt_ids",
            "runtime_diagnostic_receipt_ids",
            "database_receipt_ids",
            "database_postapply_receipt_ids",
            "integration_environment_receipt_ids",
            "integration_environment_postapply_receipt_ids",
        ):
            texts(getattr(self, name), name)
        if len(self.last_event_sha256) != 64:
            raise ValueError("engineering loop event digest is invalid")
        aware(self.updated_at, "updated_at")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("engineering loop state contract version is unsupported")


class EngineeringLoopStore(Protocol):
    def load(self, task_id: str) -> EngineeringLoopState | None: ...

    def save(self, expected_revision: int, state: EngineeringLoopState) -> None: ...
    def start_task(
        self, definition: EngineeringTaskDefinition, state: EngineeringLoopState,
    ) -> None: ...
    def load_task(self, task_id: str) -> EngineeringTaskDefinition | None: ...


class MasterEngineeringLoop:
    _TRANSITIONS = {
        EngineeringLoopStage.REQUESTED: {EngineeringLoopStage.INSPECTED},
        EngineeringLoopStage.INSPECTED: {EngineeringLoopStage.PROPOSED},
        EngineeringLoopStage.PROPOSED: {EngineeringLoopStage.CANDIDATE_READY},
        EngineeringLoopStage.CANDIDATE_READY: {EngineeringLoopStage.VERIFIED},
        EngineeringLoopStage.VERIFIED: {EngineeringLoopStage.CHANGESET_APPROVAL_REQUIRED},
        EngineeringLoopStage.CHANGESET_APPROVAL_REQUIRED: {
            EngineeringLoopStage.CHANGESET_APPROVAL_REQUIRED,
            EngineeringLoopStage.APPLIED,
        },
        EngineeringLoopStage.APPLIED: {EngineeringLoopStage.REVERIFIED, EngineeringLoopStage.ROLLED_BACK},
        EngineeringLoopStage.REVERIFIED: {EngineeringLoopStage.COMMITTED, EngineeringLoopStage.CHANGESET_APPROVAL_REQUIRED},
        EngineeringLoopStage.COMMITTED: {
            EngineeringLoopStage.PUBLICATION_APPROVAL_REQUIRED,
            EngineeringLoopStage.COMPLETED,
            EngineeringLoopStage.ROLLED_BACK,
        },
        EngineeringLoopStage.PUBLICATION_APPROVAL_REQUIRED: {
            EngineeringLoopStage.PUBLICATION_APPROVAL_REQUIRED,
            EngineeringLoopStage.PUBLISHED,
        },
        EngineeringLoopStage.PUBLISHED: {EngineeringLoopStage.COMPLETED},
    }

    def __init__(self, store: EngineeringLoopStore) -> None:
        self._store = store

    def start(self, task_id: str, grant_id: str, budget: EngineeringLoopBudget, *, instant: datetime) -> EngineeringLoopState:
        if self._store.load(task_id) is not None:
            raise ValueError("engineering task already exists")
        state = _initial_state(task_id, grant_id, budget, instant)
        self._store.save(-1, state)
        return state

    def start_defined(
        self,
        definition: EngineeringTaskDefinition,
        budget: EngineeringLoopBudget,
        *,
        instant: datetime,
    ) -> EngineeringLoopState:
        task = definition.task
        if self._store.load(task.task_id) is not None:
            raise ValueError("engineering task already exists")
        state = _initial_state(task.task_id, task.grant_id, budget, instant)
        self._store.start_task(definition, state)
        return state

    def advance(self, task_id: str, stage: EngineeringLoopStage, evidence_id: str, *, instant: datetime, budget_delta: dict[str, int] | None = None, checkpoint_id: str | None = None) -> EngineeringLoopState:
        state = self._require(task_id)
        updated = _advance_state(
            state, stage, evidence_id, instant=instant,
            budget_delta=budget_delta, checkpoint_id=checkpoint_id,
        )
        self._store.save(state.revision, updated)
        return updated

    def advance_batch(self, task_id: str, transitions: tuple[tuple, ...]) -> EngineeringLoopState:
        """Commit a prevalidated Core-side transition sequence atomically."""
        original = self._require(task_id)
        updated = original
        if not transitions:
            raise ValueError("engineering loop batch must not be empty")
        for transition in transitions:
            if len(transition) != 5:
                raise ValueError("engineering loop batch transition is invalid")
            stage, evidence_id, instant, budget_delta, checkpoint_id = transition
            updated = _advance_state(
                updated, stage, evidence_id, instant=instant,
                budget_delta=budget_delta, checkpoint_id=checkpoint_id,
            )
        self._store.save(original.revision, updated)
        return updated

    def resume_after_restart(self, task_id: str, *, instant: datetime) -> EngineeringLoopState:
        state = self._require(task_id)
        if state.stage is EngineeringLoopStage.CHANGESET_APPROVAL_REQUIRED:
            state = replace(state, pending_changeset_id=None, revision=state.revision + 1, updated_at=instant)
        elif state.stage is EngineeringLoopStage.PUBLICATION_APPROVAL_REQUIRED:
            state = replace(state, pending_publication_id=None, revision=state.revision + 1, updated_at=instant)
        else:
            return state
        self._store.save(state.revision - 1, state)
        return state

    def record_auxiliary_evidence(self, task_id: str, kind: str, evidence_id: str, *, instant: datetime, budget_delta: dict[str, int] | None = None) -> EngineeringLoopState:
        state = self._require(task_id)
        fields = {
            "dependency": "dependency_receipt_ids",
            "design": "design_receipt_ids",
            "generation": "checkpoint_ids",
            "verification_failure": "checkpoint_ids",
            "runtime_diagnostic": "runtime_diagnostic_receipt_ids",
            "database": "database_receipt_ids",
        }
        field = fields.get(kind)
        if field is None:
            raise ValueError("engineering auxiliary evidence kind is unsupported")
        if evidence_id in getattr(state, field):
            return state
        budget = _consume(state.budget, budget_delta or {})
        chain = hashlib.sha256(
            f"{state.last_event_sha256}:{state.revision + 1}:{kind}:{evidence_id}".encode()
        ).hexdigest()
        updated = replace(
            state, revision=state.revision + 1, budget=budget,
            last_event_sha256=chain, updated_at=instant,
            **{field: (*getattr(state, field), evidence_id)},
        )
        self._store.save(state.revision, updated)
        return updated

    def record_database_verification(
        self, task_id: str, evidence_id: str, *, instant: datetime,
        budget_delta: dict[str, int] | None = None,
    ) -> EngineeringLoopState:
        """Record exact database evidence and satisfy a database-only verify gate."""
        state = self._require(task_id)
        if evidence_id in state.database_receipt_ids:
            return state
        if state.stage not in {
            EngineeringLoopStage.CANDIDATE_READY, EngineeringLoopStage.VERIFIED,
        }:
            raise ValueError("database verification occurs at an invalid stage")
        budget = _consume(state.budget, budget_delta or {})
        chain = hashlib.sha256(
            (
                f"{state.last_event_sha256}:{state.revision + 1}:database:"
                f"{evidence_id}"
            ).encode()
        ).hexdigest()
        updated = replace(
            state,
            stage=(
                EngineeringLoopStage.VERIFIED
                if state.stage is EngineeringLoopStage.CANDIDATE_READY
                else state.stage
            ),
            revision=state.revision + 1,
            budget=budget,
            database_receipt_ids=(*state.database_receipt_ids, evidence_id),
            last_event_sha256=chain,
            updated_at=instant,
        )
        self._store.save(state.revision, updated)
        return updated

    def record_additional_verification(
        self, task_id: str, evidence_id: str, *, instant: datetime,
        budget_delta: dict[str, int] | None = None,
    ) -> EngineeringLoopState:
        """Append another passed verifier receipt without a fake stage change."""
        state = self._require(task_id)
        if state.stage is not EngineeringLoopStage.VERIFIED:
            raise ValueError("additional verification requires verified state")
        if evidence_id in state.verification_receipt_ids:
            return state
        budget = _consume(state.budget, budget_delta or {})
        chain = hashlib.sha256(
            f"{state.last_event_sha256}:{state.revision + 1}:verification:{evidence_id}".encode()
        ).hexdigest()
        updated = replace(
            state, revision=state.revision + 1, budget=budget,
            verification_receipt_ids=(*state.verification_receipt_ids, evidence_id),
            last_event_sha256=chain, updated_at=instant,
        )
        self._store.save(state.revision, updated)
        return updated

    def record_database_reverification(
        self, task_id: str, evidence_id: str, *, instant: datetime,
    ) -> EngineeringLoopState:
        state = self._require(task_id)
        if evidence_id in state.database_postapply_receipt_ids:
            return state
        if state.stage not in {
            EngineeringLoopStage.APPLIED, EngineeringLoopStage.REVERIFIED,
        }:
            raise ValueError("database reverification occurs at an invalid stage")
        chain = hashlib.sha256(
            (
                f"{state.last_event_sha256}:{state.revision + 1}:"
                f"database-postapply:{evidence_id}"
            ).encode()
        ).hexdigest()
        updated = replace(
            state,
            stage=(
                EngineeringLoopStage.REVERIFIED
                if state.stage is EngineeringLoopStage.APPLIED else state.stage
            ),
            revision=state.revision + 1,
            database_postapply_receipt_ids=(
                *state.database_postapply_receipt_ids, evidence_id,
            ),
            last_event_sha256=chain,
            updated_at=instant,
        )
        self._store.save(state.revision, updated)
        return updated

    def record_additional_reverification(
        self, task_id: str, evidence_id: str, *, instant: datetime,
        budget_delta: dict[str, int] | None = None,
    ) -> EngineeringLoopState:
        """Append another passed post-apply verifier without a stage change."""
        state = self._require(task_id)
        if state.stage is not EngineeringLoopStage.REVERIFIED:
            raise ValueError("additional reverification requires reverified state")
        if evidence_id in state.verification_receipt_ids:
            return state
        budget = _consume(state.budget, budget_delta or {})
        chain = hashlib.sha256(
            f"{state.last_event_sha256}:{state.revision + 1}:reverification:{evidence_id}".encode()
        ).hexdigest()
        updated = replace(
            state, revision=state.revision + 1, budget=budget,
            verification_receipt_ids=(*state.verification_receipt_ids, evidence_id),
            last_event_sha256=chain, updated_at=instant,
        )
        self._store.save(state.revision, updated)
        return updated

    def record_integration_environment(
        self, task_id: str, evidence_id: str, *, instant: datetime,
        postapply: bool, budget_delta: dict[str, int] | None = None,
    ) -> EngineeringLoopState:
        state = self._require(task_id)
        field = (
            "integration_environment_postapply_receipt_ids"
            if postapply else "integration_environment_receipt_ids"
        )
        allowed = (
            {EngineeringLoopStage.APPLIED, EngineeringLoopStage.REVERIFIED}
            if postapply else {
                EngineeringLoopStage.CANDIDATE_READY,
                EngineeringLoopStage.VERIFIED,
            }
        )
        if state.stage not in allowed:
            raise ValueError("integration environment evidence occurs at an invalid stage")
        if evidence_id in getattr(state, field):
            return state
        budget = _consume(state.budget, budget_delta or {})
        phase = "postapply" if postapply else "candidate"
        chain = hashlib.sha256(
            (
                f"{state.last_event_sha256}:{state.revision + 1}:"
                f"integration-environment-{phase}:{evidence_id}"
            ).encode()
        ).hexdigest()
        updated = replace(
            state,
            stage=(
                EngineeringLoopStage.REVERIFIED
                if postapply and state.stage is EngineeringLoopStage.APPLIED
                else EngineeringLoopStage.VERIFIED
                if not postapply
                and state.stage is EngineeringLoopStage.CANDIDATE_READY
                else state.stage
            ),
            revision=state.revision + 1, budget=budget,
            last_event_sha256=chain, updated_at=instant,
            **{field: (*getattr(state, field), evidence_id)},
        )
        self._store.save(state.revision, updated)
        return updated

    def _require(self, task_id):
        state = self._store.load(task_id)
        if state is None:
            raise LookupError("engineering task is unavailable")
        return state

    def state(self, task_id: str) -> EngineeringLoopState:
        """Return the current immutable state for Core-side coordinators."""
        return self._require(task_id)


def _advance_state(state, stage, evidence_id, *, instant, budget_delta, checkpoint_id):
    if stage not in MasterEngineeringLoop._TRANSITIONS.get(state.stage, set()):
        raise ValueError(f"engineering loop transition {state.stage.value} -> {stage.value} is forbidden")
    if stage is EngineeringLoopStage.APPLIED and (checkpoint_id is None or checkpoint_id != state.pending_changeset_id):
        raise PermissionError("workspace mutation requires the exact pending changeset approval")
    if stage is EngineeringLoopStage.PUBLISHED and (checkpoint_id is None or checkpoint_id != state.pending_publication_id):
        raise PermissionError("publication requires the exact pending final approval")
    budget = _consume(state.budget, budget_delta or {})
    changes = _evidence_changes(state, stage, evidence_id)
    chain = hashlib.sha256(f"{state.last_event_sha256}:{state.revision + 1}:{stage.value}:{evidence_id}".encode()).hexdigest()
    return replace(
        state, stage=stage, revision=state.revision + 1, budget=budget,
        last_event_sha256=chain, updated_at=instant, **changes,
    )


def _consume(budget: EngineeringLoopBudget, delta: dict[str, int]) -> EngineeringLoopBudget:
    allowed = {
        "used_tokens", "used_wall_seconds", "used_commands",
        "used_network_bytes", "used_files", "used_storage_bytes",
    }
    if not set(delta).issubset(allowed) or any(value < 0 for value in delta.values()):
        raise ValueError("engineering loop budget delta is invalid")
    return replace(budget, **{
        name: getattr(budget, name) + delta.get(name, 0) for name in allowed
    })


def _initial_state(task_id, grant_id, budget, instant):
    return EngineeringLoopState(
        task_id, grant_id, EngineeringLoopStage.REQUESTED, 0, budget,
        None, None, None, (), (), (), (), (), (), (), (), None, None,
        "0" * 64, instant,
    )


def _evidence_changes(state, stage, evidence_id):
    mapping = {
        EngineeringLoopStage.INSPECTED: {"repository_evidence_id": evidence_id},
        EngineeringLoopStage.PROPOSED: {"architecture_proposal_id": evidence_id},
        EngineeringLoopStage.CANDIDATE_READY: {"candidate_id": evidence_id},
        EngineeringLoopStage.VERIFIED: {"verification_receipt_ids": (*state.verification_receipt_ids, evidence_id)},
        EngineeringLoopStage.CHANGESET_APPROVAL_REQUIRED: {
            "pending_changeset_id": evidence_id,
            "checkpoint_ids": (*state.checkpoint_ids, evidence_id),
        },
        EngineeringLoopStage.APPLIED: {"apply_receipt_ids": (*state.apply_receipt_ids, evidence_id), "pending_changeset_id": None},
        EngineeringLoopStage.REVERIFIED: {"verification_receipt_ids": (*state.verification_receipt_ids, evidence_id)},
        EngineeringLoopStage.COMMITTED: {"git_receipt_ids": (*state.git_receipt_ids, evidence_id)},
        EngineeringLoopStage.PUBLICATION_APPROVAL_REQUIRED: {
            "pending_publication_id": evidence_id,
            "checkpoint_ids": (*state.checkpoint_ids, evidence_id),
        },
        EngineeringLoopStage.PUBLISHED: {"publication_receipt_ids": (*state.publication_receipt_ids, evidence_id), "pending_publication_id": None},
        EngineeringLoopStage.ROLLED_BACK: {"rollback_receipt_ids": (*state.rollback_receipt_ids, evidence_id)},
    }
    return mapping.get(stage, {})
