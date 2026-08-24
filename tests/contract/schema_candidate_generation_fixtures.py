import hashlib
from datetime import datetime, timezone

from fam_os.core.engineering import (
    CandidateContextDocument, CandidateGenerationContext,
    CandidateGenerationRecord, CandidateGenerationStatus,
    GeneratedCandidateOperation, GeneratedCandidateOperationKind,
    GeneratedCandidatePlan,
)


NOW = datetime(2026, 7, 19, 11, 0, tzinfo=timezone.utc)


def candidate_generation_schema_values():
    content = "VALUE = 1\n"
    context = CandidateGenerationContext(
        "candidate-1", "a" * 64, ("app.py",),
        (CandidateContextDocument(
            "app.py", hashlib.sha256(content.encode()).hexdigest(), content,
        ),), False,
    )
    plan = GeneratedCandidatePlan("Update app", (
        GeneratedCandidateOperation(
            GeneratedCandidateOperationKind.REPLACE_FILE,
            "app.py", "VALUE = 2\n", media_type="text/x-python",
        ),
    ))
    record = CandidateGenerationRecord(
        "generation-1", "definition-task-1", "task-1", "candidate-1",
        "session-1", "owner-1", "b" * 64, "c" * 64, "model:1",
        CandidateGenerationStatus.PLAN_VALIDATED, 1, 20, 1, 1,
        NOW, NOW, plan,
    )
    return context, plan, record
