"""Read-only Console projection of the bounded master engineering loop."""

from dataclasses import dataclass

from fam_os.core.engineering.master_loop import EngineeringLoopState


@dataclass(frozen=True, slots=True)
class EngineeringConsoleView:
    task_id: str
    stage: str
    revision: int
    task_graph_evidence_id: str | None
    candidate_id: str | None
    diff_checkpoint_id: str | None
    test_receipt_ids: tuple[str, ...]
    runtime_diagnostic_receipt_ids: tuple[str, ...]
    database_receipt_ids: tuple[str, ...]
    database_postapply_receipt_ids: tuple[str, ...]
    integration_environment_receipt_ids: tuple[str, ...]
    integration_environment_postapply_receipt_ids: tuple[str, ...]
    dependency_receipt_ids: tuple[str, ...]
    design_preview_receipt_ids: tuple[str, ...]
    rollback_receipt_ids: tuple[str, ...]
    git_receipt_ids: tuple[str, ...]
    publication_approval_id: str | None
    budget: dict[str, int]


def project_engineering_task(state: EngineeringLoopState) -> EngineeringConsoleView:
    budget = state.budget
    return EngineeringConsoleView(
        state.task_id, state.stage.value, state.revision,
        state.repository_evidence_id, state.candidate_id,
        state.pending_changeset_id, state.verification_receipt_ids,
        state.runtime_diagnostic_receipt_ids,
        state.database_receipt_ids, state.database_postapply_receipt_ids,
        state.integration_environment_receipt_ids,
        state.integration_environment_postapply_receipt_ids,
        state.dependency_receipt_ids, state.design_receipt_ids,
        state.rollback_receipt_ids, state.git_receipt_ids,
        state.pending_publication_id,
        {
            "tokens": budget.used_tokens,
            "wall_seconds": budget.used_wall_seconds,
            "commands": budget.used_commands,
            "network_bytes": budget.used_network_bytes,
            "files": budget.used_files,
            "storage_bytes": budget.used_storage_bytes,
        },
    )
