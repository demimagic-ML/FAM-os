from dataclasses import replace

from fam_os.core.engineering import (
    CandidateChangesetRecord, CandidateChangesetStatus, candidate_preview_digest,
)
from tests.contract.schema_engineering_fixtures import engineering_schema_values
from tests.contract.schema_transaction_fixtures import transaction_schema_values


def candidate_changeset_schema_values() -> tuple[object, ...]:
    artifact, operation, candidate, preview, receipt, _policy = transaction_schema_values()
    decision = replace(
        engineering_schema_values()[9], task_id=candidate.task_id,
        proposal_id=preview.transaction_id, checkpoint_id=preview.transaction_id,
        proposal_sha256=candidate_preview_digest(preview),
    )
    return (CandidateChangesetRecord(
        preview.transaction_id, f"definition-{candidate.task_id}", candidate.task_id,
        candidate.candidate_id, preview, (operation,), (artifact,),
        ("authorization-1",), CandidateChangesetStatus.APPLIED, 3,
        preview.generated_at, receipt.completed_at, decision, receipt,
    ),)
