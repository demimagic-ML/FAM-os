from fam_os.core.engineering import CandidateEditRecord, CandidateEditStatus
from tests.contract.schema_transaction_fixtures import transaction_schema_values


def candidate_edit_schema_values() -> tuple[object, ...]:
    artifact, operation, candidate, _preview, _receipt, _policy = transaction_schema_values()
    return (CandidateEditRecord(
        "edit-1", f"definition-{candidate.task_id}", candidate.task_id,
        candidate.candidate_id, "session-1", "principal-1", operation,
        artifact, ("decision-1",), artifact.size_bytes,
        CandidateEditStatus.APPLIED, 2, candidate.created_at,
        candidate.created_at, artifact.content_sha256,
    ),)
