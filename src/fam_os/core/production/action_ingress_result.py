"""Typed, model-free Shell outcomes for action admission."""

from fam_os.core.contracts import ResultKind, ResultStatus
from fam_os.shell import ShellResult, ShellRunState, ShellSessionSnapshot


def action_ingress_result(request_id: str, kind: ResultKind, message: str):
    if kind not in {ResultKind.ACTION_PROPOSAL, ResultKind.CAPABILITY_UNAVAILABLE}:
        raise ValueError("action ingress result kind is invalid")
    return ShellSessionSnapshot(
        f"admission-{request_id}", request_id, 1, ShellRunState.TERMINAL,
        message=message,
        result=ShellResult(
            request_id, ResultStatus.WITHHELD, None, message,
            result_kind=kind,
        ),
    )
