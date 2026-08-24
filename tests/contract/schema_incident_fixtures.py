from datetime import datetime, timezone

from fam_os.core.engineering import (
    EngineeringIncidentReceiptKind, EngineeringIncidentStage,
    EngineeringIncidentState, build_engineering_incident_receipt,
)


NOW = datetime(2026, 7, 19, 23, 0, tzinfo=timezone.utc)


def incident_schema_values() -> tuple[object, ...]:
    state = EngineeringIncidentState(
        "incident-1", "task-1", EngineeringIncidentStage.DIAGNOSED, 2,
        NOW, NOW, ("symptom-1",), ("preservation-1",), ("diagnosis-1",),
        (), (), (), (), (), (), "a" * 64,
    )
    receipt = build_engineering_incident_receipt(
        "preservation-1", state.incident_id, state.task_id,
        EngineeringIncidentReceiptKind.PRESERVATION,
        state.symptom_evidence_ids, "task_evidence_snapshot_preserved", NOW,
    )
    return state, receipt
