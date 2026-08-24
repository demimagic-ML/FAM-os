"""Server-side mapping from Shell adaptation requests to the owner service."""

from fam_os.adaptation import LiveAdaptationControlRequest
from fam_os.shell.adaptation_contracts import (
    ShellAdaptationOperation,
    ShellAdaptationQuery,
    ShellAdaptationResponse,
)


class AdaptationServiceUnavailable(RuntimeError):
    """The installed service has no live adaptation control surface."""


def dispatch_adaptation(adaptation, command) -> ShellAdaptationResponse:
    if adaptation is None:
        raise AdaptationServiceUnavailable
    if isinstance(command, LiveAdaptationControlRequest):
        receipt = adaptation.apply_control(command)
        values = adaptation.control_receipts()
        offset = max(0, len(values) - 1)
        return ShellAdaptationResponse(
            command.request_id, ShellAdaptationOperation.RECEIPTS,
            offset, len(values), control_receipts=(receipt,),
        )
    if not isinstance(command, ShellAdaptationQuery):
        raise ValueError("unsupported Shell adaptation request")
    return _query(adaptation, command)


def _query(adaptation, command) -> ShellAdaptationResponse:
    operation = command.operation
    if operation is ShellAdaptationOperation.STATUS:
        return ShellAdaptationResponse(
            command.request_id, operation, 0, 1, state=adaptation.control_state(),
        )
    values = {
        ShellAdaptationOperation.SNAPSHOTS: adaptation.snapshots,
        ShellAdaptationOperation.PREWARMS: adaptation.receipts,
        ShellAdaptationOperation.HEALTH: adaptation.health,
        ShellAdaptationOperation.DRIFT: adaptation.drift_reports,
        ShellAdaptationOperation.RECEIPTS: adaptation.control_receipts,
    }[operation]()
    page = values[command.offset:command.offset + command.limit]
    fields = {
        ShellAdaptationOperation.SNAPSHOTS: {"snapshots": page},
        ShellAdaptationOperation.PREWARMS: {"prewarms": page},
        ShellAdaptationOperation.HEALTH: {"health": page},
        ShellAdaptationOperation.DRIFT: {"drift_reports": page},
        ShellAdaptationOperation.RECEIPTS: {"control_receipts": page},
    }[operation]
    return ShellAdaptationResponse(
        command.request_id, operation, command.offset, len(values), **fields,
    )
