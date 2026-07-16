"""Fail-closed monotonic reducer for snapshots received from Core."""

from fam_os.shell.contracts import ShellRunState, ShellSessionSnapshot


def accept_snapshot(
    previous: ShellSessionSnapshot | None,
    incoming: ShellSessionSnapshot,
) -> ShellSessionSnapshot:
    if previous is None:
        return incoming
    if (previous.session_id, previous.request_id) != (
        incoming.session_id, incoming.request_id
    ):
        raise ValueError("shell snapshot identity changed")
    if incoming.revision < previous.revision:
        raise ValueError("shell snapshot revision regressed")
    if incoming.revision == previous.revision:
        if incoming != previous:
            raise ValueError("same shell revision changed content")
        return previous
    if previous.state is ShellRunState.TERMINAL:
        raise ValueError("terminal shell snapshot is absorbing")
    _stable_plan(previous, incoming)
    return incoming


def _stable_plan(previous, incoming) -> None:
    if not previous.steps:
        return
    before = tuple((item.step_id, item.kind, item.description) for item in previous.steps)
    after = tuple((item.step_id, item.kind, item.description) for item in incoming.steps)
    if before != after:
        raise ValueError("shell plan identity changed")
