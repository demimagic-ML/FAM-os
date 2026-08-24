"""Production derivation of content-free learning from verified final results."""

from __future__ import annotations

import hashlib
import json
import logging

from fam_os.adaptation import VerifiedLearningOutcome, context_token_bucket
from fam_os.core.contracts import ResultAssurance, ResultStatus, TerminalDisposition
from fam_os.core.lifecycle import PlanEvidenceKind
from fam_os.core.production import AssuranceLevel, InferenceExecutionState
from fam_os.schemas import dumps_document


LOGGER = logging.getLogger(__name__)


class ProductVerifiedOutcomeLearning:
    def __init__(self, repositories, observer=None) -> None:
        self._repositories = repositories
        self._observer = observer

    def result(self, request_id: str):
        return self._repositories.terminal_outcomes.result(request_id)

    def records(self) -> tuple[VerifiedLearningOutcome, ...]:
        return self._repositories.terminal_outcomes.learning_records()

    def finalize(self, record, snapshot, result) -> bool:
        request = self._repositories.requests.get(record.request_id)
        if request is None:
            raise RuntimeError("terminal request content is unavailable")
        learning = self._learning(record, snapshot, result, request.prompt)
        finalized = self._repositories.terminal_outcomes.finalize(request, result, learning)
        if finalized and self._observer is not None:
            self._notify_observer(record, snapshot, result, learning)
        return finalized

    def _notify_observer(self, record, snapshot, result, learning) -> None:
        try:
            terminal = getattr(self._observer, "terminal_committed", None)
            if terminal is not None:
                terminal(record, snapshot, result, learning)
            elif learning is not None:
                self._observer.learning_committed(learning)
        except Exception:
            LOGGER.exception(
                "live adaptation terminal observation failed for request %s",
                record.request_id,
            )

    def _learning(self, record, snapshot, result, prompt):
        if not _eligible(record, snapshot, result):
            return None
        candidate_id = _one_reference(snapshot, PlanEvidenceKind.RELEASE_CANDIDATE)
        acceptance_id = _one_reference(snapshot, PlanEvidenceKind.VERIFICATION_PASS)
        acceptance = self._repositories.final_evidence.acceptance(acceptance_id)
        if (
            acceptance is None
            or not acceptance.passed
            or acceptance.candidate_id != candidate_id
        ):
            raise RuntimeError("verified learning source evidence is invalid")
        evidence_sha256 = _evidence_digest(record, snapshot, acceptance)
        identifier = hashlib.sha256(
            f"{acceptance_id}\0{candidate_id}".encode("utf-8"),
        ).hexdigest()
        escalation_used = record.selection.tier == "escalation" or any(
            reference.kind is PlanEvidenceKind.ESCALATION_ATTEMPT
            for event in snapshot.events for reference in event.evidence_refs
        )
        return VerifiedLearningOutcome(
            f"verified-learning-{identifier}",
            f"intent:{record.intent.value}",
            record.intent.value,
            record.selection.model_ref,
            record.selection.tier,
            snapshot.events[-1].occurred_at,
            context_token_bucket(prompt),
            escalation_used,
            acceptance_id,
            candidate_id,
            evidence_sha256,
        )


def _eligible(record, snapshot, result) -> bool:
    return (
        record.state is InferenceExecutionState.TERMINAL
        and record.assurance is AssuranceLevel.VERIFIED
        and snapshot.terminal_disposition is TerminalDisposition.RELEASE
        and result.status is ResultStatus.VERIFIED
        and result.assurance is ResultAssurance.VERIFIED
        and result.verified
    )


def _one_reference(snapshot, kind: PlanEvidenceKind) -> str:
    values = tuple(
        reference.reference_id
        for reference in snapshot.events[-1].evidence_refs
        if reference.kind is kind
    )
    if len(values) != 1:
        raise RuntimeError("verified learning requires one terminal evidence reference")
    return values[0]


def _evidence_digest(record, snapshot, acceptance) -> str:
    document = {
        "acceptance": dumps_document(acceptance),
        "expert_id": record.selection.model_ref,
        "expert_tier": record.selection.tier,
        "intent": record.intent.value,
        "terminal_revision": snapshot.revision,
    }
    encoded = json.dumps(document, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(encoded).hexdigest()
