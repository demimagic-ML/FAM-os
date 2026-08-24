"""Restart-safe engineering incident lifecycle contracts."""

from dataclasses import dataclass, replace
from datetime import datetime
from enum import StrEnum
import hashlib
import json
from typing import Protocol

from fam_os.core.engineering._validation import aware, text, texts
from fam_os.core.engineering.version import ENGINEERING_CONTRACT_VERSION


class EngineeringIncidentStage(StrEnum):
    DETECTED = "detected"
    EVIDENCE_PRESERVED = "evidence_preserved"
    DIAGNOSED = "diagnosed"
    REMEDIATION_PROPOSED = "remediation_proposed"
    REMEDIATED = "remediated"
    RECOVERY_MONITORED = "recovery_monitored"
    ROLLED_BACK = "rolled_back"
    REPORTED = "reported"
    CLOSED = "closed"


class EngineeringIncidentReceiptKind(StrEnum):
    PRESERVATION = "preservation"
    DIAGNOSIS = "diagnosis"
    REMEDIATION_PROPOSAL = "remediation_proposal"
    REMEDIATION = "remediation"
    RECOVERY_OBSERVATION = "recovery_observation"
    ROLLBACK = "rollback"
    REPORT = "report"
    CLOSURE = "closure"


@dataclass(frozen=True, slots=True)
class EngineeringIncidentEvidenceReceipt:
    receipt_id: str
    incident_id: str
    task_id: str
    kind: EngineeringIncidentReceiptKind
    source_evidence_ids: tuple[str, ...]
    conclusion_code: str
    recorded_at: datetime
    payload_sha256: str
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("receipt_id", "incident_id", "task_id", "conclusion_code"):
            text(getattr(self, name), name)
        texts(self.source_evidence_ids, "incident receipt source evidence")
        if not self.source_evidence_ids:
            raise ValueError("engineering incident receipt requires source evidence")
        aware(self.recorded_at, "recorded_at")
        if self.payload_sha256 != engineering_incident_receipt_digest(self):
            raise ValueError("engineering incident receipt digest is invalid")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("engineering incident receipt version is unsupported")


@dataclass(frozen=True, slots=True)
class EngineeringIncidentState:
    incident_id: str
    task_id: str
    stage: EngineeringIncidentStage
    revision: int
    detected_at: datetime
    updated_at: datetime
    symptom_evidence_ids: tuple[str, ...]
    preservation_receipt_ids: tuple[str, ...]
    diagnosis_receipt_ids: tuple[str, ...]
    remediation_changeset_ids: tuple[str, ...]
    remediation_receipt_ids: tuple[str, ...]
    recovery_observation_ids: tuple[str, ...]
    rollback_receipt_ids: tuple[str, ...]
    post_incident_report_ids: tuple[str, ...]
    closure_receipt_ids: tuple[str, ...]
    last_event_sha256: str
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        for name in ("incident_id", "task_id"):
            text(getattr(self, name), name)
        if self.revision < 0:
            raise ValueError("engineering incident revision is invalid")
        aware(self.detected_at, "detected_at")
        aware(self.updated_at, "updated_at")
        for name in (
            "symptom_evidence_ids", "preservation_receipt_ids",
            "diagnosis_receipt_ids", "remediation_changeset_ids",
            "remediation_receipt_ids", "recovery_observation_ids",
            "rollback_receipt_ids", "post_incident_report_ids",
            "closure_receipt_ids",
        ):
            texts(getattr(self, name), name)
        if len(self.last_event_sha256) != 64:
            raise ValueError("engineering incident event digest is invalid")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("engineering incident version is unsupported")


class EngineeringIncidentStore(Protocol):
    def load(self, incident_id: str) -> EngineeringIncidentState | None: ...
    def save(self, expected_revision: int, state: EngineeringIncidentState) -> None: ...
    def for_task(self, task_id: str) -> tuple[EngineeringIncidentState, ...]: ...
    def put_receipt(self, receipt: EngineeringIncidentEvidenceReceipt) -> None: ...
    def load_receipt(self, receipt_id: str) -> EngineeringIncidentEvidenceReceipt | None: ...
    def receipts_for_incident(self, incident_id: str) -> tuple[EngineeringIncidentEvidenceReceipt, ...]: ...


class EngineeringIncidentService:
    _TRANSITIONS = {
        EngineeringIncidentStage.DETECTED: {EngineeringIncidentStage.EVIDENCE_PRESERVED},
        EngineeringIncidentStage.EVIDENCE_PRESERVED: {EngineeringIncidentStage.DIAGNOSED},
        EngineeringIncidentStage.DIAGNOSED: {EngineeringIncidentStage.REMEDIATION_PROPOSED},
        EngineeringIncidentStage.REMEDIATION_PROPOSED: {
            EngineeringIncidentStage.REMEDIATED, EngineeringIncidentStage.ROLLED_BACK,
        },
        EngineeringIncidentStage.REMEDIATED: {
            EngineeringIncidentStage.RECOVERY_MONITORED, EngineeringIncidentStage.ROLLED_BACK,
        },
        EngineeringIncidentStage.RECOVERY_MONITORED: {
            EngineeringIncidentStage.RECOVERY_MONITORED,
            EngineeringIncidentStage.ROLLED_BACK, EngineeringIncidentStage.REPORTED,
        },
        EngineeringIncidentStage.ROLLED_BACK: {EngineeringIncidentStage.REPORTED},
        EngineeringIncidentStage.REPORTED: {EngineeringIncidentStage.CLOSED},
    }

    def __init__(self, store: EngineeringIncidentStore) -> None:
        self._store = store

    def close(self):
        close = getattr(self._store, "close", None)
        if close is not None:
            close()

    def detect(self, incident_id, task_id, symptom_evidence_ids, *, instant):
        if self._store.load(incident_id) is not None or not symptom_evidence_ids:
            raise ValueError("engineering incident identity or symptom evidence is invalid")
        state = EngineeringIncidentState(
            incident_id, task_id, EngineeringIncidentStage.DETECTED, 0,
            instant, instant, tuple(symptom_evidence_ids), (), (), (), (), (), (), (), (),
            "0" * 64,
        )
        self._store.save(-1, state)
        return state

    def inspect(self, incident_id):
        state = self._store.load(incident_id)
        if state is None:
            raise KeyError("engineering incident is unavailable")
        return state

    def for_task(self, task_id):
        return self._store.for_task(task_id)

    def receipt(self, receipt_id):
        value = self._store.load_receipt(receipt_id)
        if value is None:
            raise KeyError("engineering incident evidence is unavailable")
        return value

    def receipts(self, incident_id):
        self.inspect(incident_id)
        return self._store.receipts_for_incident(incident_id)

    def advance_with_receipt(self, receipt, *, instant):
        state = self.inspect(receipt.incident_id)
        self._validate_receipt(state, receipt)
        stage = _RECEIPT_STAGES[receipt.kind]
        field = _STAGE_FIELDS[stage]
        if receipt.receipt_id in getattr(state, field):
            self._store.put_receipt(receipt)
            return state
        if stage not in self._TRANSITIONS.get(state.stage, set()):
            raise ValueError("engineering incident receipt transition is forbidden")
        self._store.put_receipt(receipt)
        return self.advance(
            state.incident_id, stage, receipt.receipt_id, instant=instant,
        )

    def advance(self, incident_id, stage, evidence_id, *, instant):
        state = self._store.load(incident_id)
        if state is None:
            raise KeyError("engineering incident is unavailable")
        if stage not in self._TRANSITIONS.get(state.stage, set()):
            raise ValueError("engineering incident transition is forbidden")
        field = _STAGE_FIELDS.get(stage)
        if field is None:
            raise ValueError("engineering incident stage lacks evidence policy")
        text(evidence_id, "incident evidence_id")
        revision = state.revision + 1
        chain = hashlib.sha256(
            f"{state.last_event_sha256}:{revision}:{stage.value}:{evidence_id}".encode()
        ).hexdigest()
        changes = {} if field is None else {field: (*getattr(state, field), evidence_id)}
        updated = replace(
            state, stage=stage, revision=revision, updated_at=instant,
            last_event_sha256=chain, **changes,
        )
        self._store.save(state.revision, updated)
        return updated

    @staticmethod
    def _validate_receipt(state, receipt):
        if receipt.incident_id != state.incident_id or receipt.task_id != state.task_id:
            raise PermissionError("engineering incident receipt identity differs")
        available = {
            EngineeringIncidentReceiptKind.PRESERVATION: state.symptom_evidence_ids,
            EngineeringIncidentReceiptKind.DIAGNOSIS: state.preservation_receipt_ids,
            EngineeringIncidentReceiptKind.REMEDIATION_PROPOSAL: state.diagnosis_receipt_ids,
            EngineeringIncidentReceiptKind.REMEDIATION: state.remediation_changeset_ids,
            EngineeringIncidentReceiptKind.RECOVERY_OBSERVATION: (
                *state.remediation_receipt_ids, *state.recovery_observation_ids,
            ),
            EngineeringIncidentReceiptKind.ROLLBACK: (
                *state.remediation_changeset_ids, *state.remediation_receipt_ids,
            ),
            EngineeringIncidentReceiptKind.REPORT: (
                *state.recovery_observation_ids, *state.rollback_receipt_ids,
            ),
            EngineeringIncidentReceiptKind.CLOSURE: state.post_incident_report_ids,
        }[receipt.kind]
        if not set(receipt.source_evidence_ids).issubset(set(available)):
            raise PermissionError("engineering incident receipt lacks prior evidence")


_STAGE_FIELDS = {
    EngineeringIncidentStage.EVIDENCE_PRESERVED: "preservation_receipt_ids",
    EngineeringIncidentStage.DIAGNOSED: "diagnosis_receipt_ids",
    EngineeringIncidentStage.REMEDIATION_PROPOSED: "remediation_changeset_ids",
    EngineeringIncidentStage.REMEDIATED: "remediation_receipt_ids",
    EngineeringIncidentStage.RECOVERY_MONITORED: "recovery_observation_ids",
    EngineeringIncidentStage.ROLLED_BACK: "rollback_receipt_ids",
    EngineeringIncidentStage.REPORTED: "post_incident_report_ids",
    EngineeringIncidentStage.CLOSED: "closure_receipt_ids",
}

_RECEIPT_STAGES = {
    EngineeringIncidentReceiptKind.PRESERVATION: EngineeringIncidentStage.EVIDENCE_PRESERVED,
    EngineeringIncidentReceiptKind.DIAGNOSIS: EngineeringIncidentStage.DIAGNOSED,
    EngineeringIncidentReceiptKind.REMEDIATION_PROPOSAL: EngineeringIncidentStage.REMEDIATION_PROPOSED,
    EngineeringIncidentReceiptKind.REMEDIATION: EngineeringIncidentStage.REMEDIATED,
    EngineeringIncidentReceiptKind.RECOVERY_OBSERVATION: EngineeringIncidentStage.RECOVERY_MONITORED,
    EngineeringIncidentReceiptKind.ROLLBACK: EngineeringIncidentStage.ROLLED_BACK,
    EngineeringIncidentReceiptKind.REPORT: EngineeringIncidentStage.REPORTED,
    EngineeringIncidentReceiptKind.CLOSURE: EngineeringIncidentStage.CLOSED,
}


def engineering_incident_receipt_digest(receipt) -> str:
    return _receipt_digest(
        receipt.receipt_id, receipt.incident_id, receipt.task_id, receipt.kind,
        receipt.source_evidence_ids, receipt.conclusion_code,
        receipt.recorded_at,
    )


def build_engineering_incident_receipt(
    receipt_id, incident_id, task_id, kind, source_evidence_ids,
    conclusion_code, recorded_at,
) -> EngineeringIncidentEvidenceReceipt:
    sources = tuple(source_evidence_ids)
    return EngineeringIncidentEvidenceReceipt(
        receipt_id, incident_id, task_id, kind, sources, conclusion_code,
        recorded_at,
        _receipt_digest(
            receipt_id, incident_id, task_id, kind, sources, conclusion_code,
            recorded_at,
        ),
    )


def _receipt_digest(
    receipt_id, incident_id, task_id, kind, sources, conclusion, recorded_at,
):
    return hashlib.sha256(json.dumps({
        "conclusion_code": conclusion,
        "incident_id": incident_id,
        "kind": kind.value,
        "receipt_id": receipt_id,
        "recorded_at": recorded_at.isoformat(),
        "source_evidence_ids": list(sources),
        "task_id": task_id,
    }, sort_keys=True, separators=(",", ":")).encode()).hexdigest()
