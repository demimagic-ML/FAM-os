"""Natural-loop incident binding for exact rollback outcomes."""

import hashlib

from fam_os.core.engineering import (
    EngineeringIncidentReceiptKind, EngineeringIncidentStage,
)
from fam_os.schemas import encode_document


class NaturalEngineeringIncidentCoordinator:
    def __init__(self, loop) -> None:
        self._loop = loop

    def propose_rollback(self, owner_id, incident, checkpoint):
        if incident.stage is not EngineeringIncidentStage.DIAGNOSED:
            return incident
        conclusion = f"rollback_checkpoint_{checkpoint['approval_sha256']}"
        return self._loop.record_incident_evidence(
            owner_id, incident.incident_id,
            EngineeringIncidentReceiptKind.REMEDIATION_PROPOSAL,
            incident.diagnosis_receipt_ids, conclusion,
        )

    def propose_repair(
        self, owner_id, incident, generation_id, verification_ids,
    ):
        if incident.stage is not EngineeringIncidentStage.DIAGNOSED:
            return incident
        digest = _digest(generation_id, *verification_ids)
        return self._loop.record_incident_evidence(
            owner_id, incident.incident_id,
            EngineeringIncidentReceiptKind.REMEDIATION_PROPOSAL,
            incident.diagnosis_receipt_ids,
            f"candidate_repair_{digest}",
        )

    def record_remediation(self, owner_id, incident, edit_ids):
        if incident.stage is not EngineeringIncidentStage.REMEDIATION_PROPOSED:
            return incident
        edit_ids = tuple(edit_ids)
        if not edit_ids:
            raise ValueError("incident remediation requires candidate edits")
        return self._loop.record_incident_evidence(
            owner_id, incident.incident_id,
            EngineeringIncidentReceiptKind.REMEDIATION,
            incident.remediation_changeset_ids,
            f"candidate_repair_edits_{_digest(*edit_ids)}",
        )

    def complete_recovery(self, owner_id, incident, verification_ids):
        values = tuple(verification_ids)
        if not values:
            raise ValueError("incident recovery requires verification evidence")
        if (
            incident.stage is EngineeringIncidentStage.REMEDIATED
            or (
                incident.stage is EngineeringIncidentStage.RECOVERY_MONITORED
                and len(incident.recovery_observation_ids) < 2
            )
        ):
            sources = (
                incident.remediation_receipt_ids
                if not incident.recovery_observation_ids
                else (incident.recovery_observation_ids[-1],)
            )
            incident = self._loop.record_incident_evidence(
                owner_id, incident.incident_id,
                EngineeringIncidentReceiptKind.RECOVERY_OBSERVATION,
                sources,
                f"signed_recovery_{len(incident.recovery_observation_ids) + 1}_"
                f"{_digest(*values)}",
            )
        if (
            incident.stage is EngineeringIncidentStage.RECOVERY_MONITORED
            and len(incident.recovery_observation_ids) >= 2
        ):
            incident = self._loop.record_incident_evidence(
                owner_id, incident.incident_id,
                EngineeringIncidentReceiptKind.REPORT,
                incident.recovery_observation_ids,
                f"repair_post_incident_report_{_digest(*incident.recovery_observation_ids)}",
            )
        if incident.stage is EngineeringIncidentStage.REPORTED:
            incident = self._loop.record_incident_evidence(
                owner_id, incident.incident_id,
                EngineeringIncidentReceiptKind.CLOSURE,
                incident.post_incident_report_ids,
                "verified_repair_monitored_reported_and_closed",
            )
        return incident

    def complete_task_recovery(self, owner_id, task_id, verification_ids):
        values = tuple(
            item for item in self._loop.incidents_for_task(owner_id, task_id)
            if item.stage in {
                EngineeringIncidentStage.REMEDIATED,
                EngineeringIncidentStage.RECOVERY_MONITORED,
                EngineeringIncidentStage.REPORTED,
            }
        )
        if not values:
            return None
        incident = sorted(values, key=lambda item: item.updated_at)[-1]
        return self.complete_recovery(
            owner_id, incident, verification_ids,
        )

    def complete_rollback(self, owner_id, task_id, changeset):
        incident = self._active_rollback_incident(owner_id, task_id)
        if incident is None:
            return None
        if incident.stage is EngineeringIncidentStage.REMEDIATION_PROPOSED:
            if changeset.rollback_receipt is None:
                return incident
            incident = self._loop.record_incident_evidence(
                owner_id, incident.incident_id,
                EngineeringIncidentReceiptKind.ROLLBACK,
                incident.remediation_changeset_ids,
                f"candidate_rollback_{changeset.rollback_receipt.journal_sha256}",
            )
        if incident.stage is EngineeringIncidentStage.ROLLED_BACK:
            report_digest = hashlib.sha256(
                f"{incident.incident_id}:"
                f"{':'.join(incident.rollback_receipt_ids)}".encode("utf-8")
            ).hexdigest()
            incident = self._loop.record_incident_evidence(
                owner_id, incident.incident_id,
                EngineeringIncidentReceiptKind.REPORT,
                incident.rollback_receipt_ids,
                f"rollback_post_incident_report_{report_digest}",
            )
        if incident.stage is EngineeringIncidentStage.REPORTED:
            incident = self._loop.record_incident_evidence(
                owner_id, incident.incident_id,
                EngineeringIncidentReceiptKind.CLOSURE,
                incident.post_incident_report_ids,
                "verified_rollback_reported_and_closed",
            )
        return incident

    def attach(self, response, owner_id, task_id, incident=None):
        if incident is None:
            incidents = self._loop.incidents_for_task(owner_id, task_id)
            if incidents:
                incident = sorted(
                    incidents, key=lambda item: item.updated_at,
                )[-1]
        if incident is not None:
            response["incident"] = encode_document(incident)
        evidence = self._loop.incident_evidence_for_task(owner_id, task_id)
        if evidence:
            response["incident_evidence"] = [
                encode_document(item) for item in evidence
            ]

    def _active_rollback_incident(self, owner_id, task_id):
        values = tuple(
            item for item in self._loop.incidents_for_task(owner_id, task_id)
            if item.stage in {
                EngineeringIncidentStage.REMEDIATION_PROPOSED,
                EngineeringIncidentStage.ROLLED_BACK,
                EngineeringIncidentStage.REPORTED,
                EngineeringIncidentStage.CLOSED,
            }
        )
        if not values:
            return None
        return sorted(values, key=lambda item: item.updated_at)[-1]


def _digest(*values):
    return hashlib.sha256("\0".join(values).encode("utf-8")).hexdigest()
