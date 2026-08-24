from fam_os.core.engineering import (
    CandidateWorkspace, EngineeringPreparationResult,
)
from tests.contract.schema_repository_fixtures import repository_schema_values


def preparation_schema_values() -> tuple[object, ...]:
    evidence, _request, analysis, proposal, _graph, _event = repository_schema_values()
    candidate = CandidateWorkspace(
        "candidate-repository-1", evidence.task_id, "baseline-1",
        evidence.workspace_root, "/transactions/candidate-repository-1/workspace",
        evidence.captured_at, "copy", "a" * 64, (),
    )
    return (EngineeringPreparationResult(
        f"definition-{evidence.task_id}", evidence, analysis, proposal, candidate,
    ),)
