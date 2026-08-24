"""Terminal Core result assembly and client projection."""

from __future__ import annotations

from fam_os.core.ingress.shell_views import project_shell_snapshot
from fam_os.core.lifecycle import FinalResultPolicy
from fam_os.core.contracts import ResultKind
from fam_os.core.production.grounded_result import GroundedResultPresenter


class TerminalResultProjector:
    def __init__(self, repositories, memory=None, outcomes=None) -> None:
        self._repositories = repositories
        self._memory = memory
        self._outcomes = outcomes
        self._grounded = GroundedResultPresenter(repositories.verifications)

    def project(self, record, snapshot):
        result = None if self._outcomes is None else self._outcomes.result(record.request_id)
        if result is None:
            outcome = FinalResultPolicy(
                self._repositories.final_evidence,
            ).assemble(snapshot)
            if outcome.result is None:
                raise RuntimeError(outcome.rejection_code or "final result rejected")
            result = self._grounded.present(outcome.result)
            transitioned = (
                self._repositories.requests.update_state(
                    record.request_id, "running", "terminal",
                )
                if self._outcomes is None else
                self._outcomes.finalize(record, snapshot, result)
            )
            if self._outcomes is not None and not transitioned:
                stored = self._outcomes.result(record.request_id)
                if stored is None:
                    raise RuntimeError("terminal result finalization did not persist")
                result = stored
        else:
            transitioned = False
        if transitioned and result.content is not None and self._memory is not None:
            self._memory.record_assistant(
                record.request_id, result.content, result.assurance.value,
            )
        return project_shell_snapshot(
            record.instance_id, snapshot, snapshot.revision + 1,
            result=result,
            message=_terminal_message(result, record),
        )


def _terminal_message(result, record):
    if result.result_kind is ResultKind.ACTION_RECEIPT:
        return "Requested machine action completed and was independently verified."
    if result.result_kind is ResultKind.GROUNDED_ANSWER:
        return "Grounded answer generated from authorized evidence."
    if result.content is not None:
        return (
            f"Model response generated; no machine action completed; "
            f"{record.assurance.value}; {record.selection.model_ref}"
        )
    return record.failure_code or "The request ended without released content."
