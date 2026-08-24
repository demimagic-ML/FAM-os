"""Owner-scoped incident attachment for master engineering tasks."""

import hashlib
from datetime import datetime, timedelta, timezone

from fam_os.core.engineering import (
    EngineeringIncidentReceiptKind, EngineeringIncidentStage,
    build_engineering_incident_receipt,
)


class ProductEngineeringIncidentApi:
    def __init__(self, owner_id, task_store, service=None) -> None:
        self._owner_id = owner_id
        self._tasks = task_store
        self._service = service

    def record_failure(
        self, owner_id, task_id, failure_code, evidence_ids,
    ):
        self._require_owner(owner_id)
        if self._service is None:
            return None
        if self._tasks.load(task_id) is None:
            raise KeyError("engineering incident task is unavailable")
        evidence = tuple(dict.fromkeys(evidence_ids))
        if not evidence:
            raise ValueError("engineering incident requires concrete symptom evidence")
        token = hashlib.sha256(
            f"{task_id}:{failure_code}:{':'.join(evidence)}".encode("utf-8")
        ).hexdigest()[:32]
        incident_id = f"incident-{token}"
        try:
            state = self._service.inspect(incident_id)
        except KeyError:
            state = self._service.detect(
                incident_id, task_id, evidence,
                instant=datetime.now(timezone.utc),
            )
        return self._preserve_and_diagnose(state, failure_code)

    def inspect(self, owner_id, incident_id):
        self._require_owner(owner_id)
        self._require_composed()
        return self._service.inspect(incident_id)

    def for_task(self, owner_id, task_id):
        self._require_owner(owner_id)
        if self._service is None:
            return ()
        return self._service.for_task(task_id)

    def receipts_for_task(self, owner_id, task_id):
        self._require_owner(owner_id)
        if self._service is None:
            return ()
        values = []
        for incident in self._service.for_task(task_id):
            values.extend(self._service.receipts(incident.incident_id))
        return tuple(values)

    def advance(self, owner_id, incident_id, stage, evidence_id):
        self._require_owner(owner_id)
        self._require_composed()
        incident = self._service.inspect(incident_id)
        if self._tasks.load(incident.task_id) is None:
            raise KeyError("engineering incident task is unavailable")
        receipt = self._service.receipt(evidence_id)
        expected = _RECEIPT_STAGES[receipt.kind]
        if receipt.incident_id != incident_id or stage is not expected:
            raise PermissionError("engineering incident evidence does not match stage")
        return self._service.advance_with_receipt(
            receipt, instant=datetime.now(timezone.utc),
        )

    def record_evidence(
        self, owner_id, incident_id, kind, source_evidence_ids, conclusion_code,
    ):
        self._require_owner(owner_id)
        self._require_composed()
        incident = self._service.inspect(incident_id)
        if self._tasks.load(incident.task_id) is None:
            raise KeyError("engineering incident task is unavailable")
        receipt = _receipt(
            incident, kind, tuple(source_evidence_ids), conclusion_code,
            instant=incident.updated_at + timedelta(microseconds=1),
        )
        return self._service.advance_with_receipt(
            receipt, instant=receipt.recorded_at,
        )

    def close(self):
        if self._service is not None:
            self._service.close()

    def _require_owner(self, owner_id):
        if owner_id != self._owner_id:
            raise PermissionError("engineering incident owner is invalid")

    def _require_composed(self):
        if self._service is None:
            raise RuntimeError("engineering incident service was not composed")

    def _preserve_and_diagnose(self, state, failure_code):
        if state.stage is EngineeringIncidentStage.DETECTED:
            receipt = _receipt(
                state, EngineeringIncidentReceiptKind.PRESERVATION,
                state.symptom_evidence_ids, "task_evidence_snapshot_preserved",
                instant=state.detected_at,
            )
            state = self._service.advance_with_receipt(
                receipt, instant=receipt.recorded_at,
            )
        if state.stage is EngineeringIncidentStage.EVIDENCE_PRESERVED:
            receipt = _receipt(
                state, EngineeringIncidentReceiptKind.DIAGNOSIS,
                state.preservation_receipt_ids, failure_code,
                instant=state.detected_at,
            )
            state = self._service.advance_with_receipt(
                receipt, instant=receipt.recorded_at,
            )
        return state


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


def _receipt(incident, kind, sources, conclusion, *, instant=None):
    instant = instant or datetime.now(timezone.utc)
    token = hashlib.sha256(
        f"{incident.incident_id}:{kind.value}:{conclusion}:"
        f"{':'.join(sources)}".encode()
    ).hexdigest()[:32]
    return build_engineering_incident_receipt(
        f"incident-evidence-{token}", incident.incident_id, incident.task_id,
        kind, sources, conclusion, instant,
    )
