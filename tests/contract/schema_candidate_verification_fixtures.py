from fam_os.core.engineering import (
    CandidateVerificationRecord, CandidateVerificationStatus,
)
from tests.contract.schema_engineering_fixtures import engineering_schema_values
from tests.contract.schema_execution_fixtures import execution_schema_values


def candidate_verification_schema_values() -> tuple[object, ...]:
    profile = execution_schema_values()[1]
    receipt = execution_schema_values()[3]
    evidence = replace(
        engineering_schema_values()[10], tool_run_ids=(receipt.receipt_id,),
    )
    return (CandidateVerificationRecord(
        "verification-1", "definition-task-1", "task-1", "candidate-1",
        "session-1", "principal-1", "python3", receipt.recipe_id,
        "1.0.0", profile, ("decision-1",),
        CandidateVerificationStatus.COMPLETED, 2, receipt.started_at,
        receipt.completed_at, receipt, evidence, True,
    ),)
from dataclasses import replace
