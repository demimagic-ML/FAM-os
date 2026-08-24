"""Explicit FAM Shell commands for owner-controlled live adaptation."""

from fam_os.adaptation import AdaptationControlOperation
from fam_os.shell.adaptation_contracts import ShellAdaptationOperation
from fam_os.shell.adaptation_render import render_adaptation_response


def execute_adaptation_command(controller, values: list[str]) -> str:
    if not values:
        raise ValueError("adaptation subcommand is required")
    command, arguments = values[0].casefold(), values[1:]
    if command in {item.value for item in ShellAdaptationOperation}:
        operation = ShellAdaptationOperation(command)
        if operation is ShellAdaptationOperation.STATUS:
            if arguments:
                raise ValueError("adaptation status accepts no page")
            response = controller.adaptation_query(operation, 0, 1)
        else:
            offset, limit = _page(arguments)
            response = controller.adaptation_query(operation, offset, limit)
        return render_adaptation_response(response)
    if command in {"enable", "disable", "reset"}:
        if arguments != ["--confirm"]:
            raise ValueError("adaptation mutation requires --confirm")
        response = controller.adaptation_control(
            AdaptationControlOperation(command), True,
        )
        return render_adaptation_response(response)
    if command in {"evaluate", "rollback"}:
        if len(arguments) != 2 or arguments[-1] != "--confirm":
            raise ValueError("adaptation workflow mutation requires WORKFLOW --confirm")
        response = controller.adaptation_control(
            AdaptationControlOperation(command), True, arguments[0],
        )
        return render_adaptation_response(response)
    raise ValueError("invalid adaptation command or missing --confirm")


def _page(arguments: list[str]) -> tuple[int, int]:
    if len(arguments) > 2:
        raise ValueError("adaptation page accepts OFFSET and LIMIT")
    try:
        offset = int(arguments[0]) if arguments else 0
        limit = int(arguments[1]) if len(arguments) == 2 else 100
    except ValueError as error:
        raise ValueError("adaptation page values must be integers") from error
    return offset, limit
