"""Dispatch typed Shell integration-environment lifecycle requests."""

from fam_os.shell.integration_environment_contracts import (
    ShellIntegrationEnvironmentControlRequest,
    ShellIntegrationEnvironmentOperation,
    ShellIntegrationEnvironmentQuery,
    ShellIntegrationEnvironmentRecord,
    ShellIntegrationStartIntentRecord,
    ShellIntegrationEnvironmentResponse,
    ShellIntegrationEnvironmentStartRequest,
)


class IntegrationEnvironmentUnavailable(RuntimeError):
    """The installed product has no integration-environment facade."""


def dispatch_integration_environment(api, command):
    if api is None:
        raise IntegrationEnvironmentUnavailable
    if isinstance(command, ShellIntegrationEnvironmentStartRequest):
        result = api.start(
            command.owner_id, command.plan, command.candidate, command.grant_id,
            command.principal_id, command.authority_session_id, lambda: False,
        )
        return ShellIntegrationEnvironmentResponse(
            command.request_id, ShellIntegrationEnvironmentOperation.START,
            start_result=result,
        )
    if isinstance(command, ShellIntegrationEnvironmentQuery):
        if command.operation is ShellIntegrationEnvironmentOperation.INTENT_LIST:
            return ShellIntegrationEnvironmentResponse(
                command.request_id, command.operation,
                intent_records=tuple(
                    _intent_record(item) for item in api.intents(command.owner_id)
                ),
            )
        if command.operation is ShellIntegrationEnvironmentOperation.INTENT_INSPECT:
            return ShellIntegrationEnvironmentResponse(
                command.request_id, command.operation,
                intent_record=_intent_record(api.inspect_intent(
                    command.owner_id, command.environment_id,
                )),
            )
        if command.operation is ShellIntegrationEnvironmentOperation.LIST:
            return ShellIntegrationEnvironmentResponse(
                command.request_id, command.operation,
                records=tuple(_record(item) for item in api.active(command.owner_id)),
            )
        if command.operation is ShellIntegrationEnvironmentOperation.AUDIT:
            return ShellIntegrationEnvironmentResponse(
                command.request_id, command.operation,
                receipts=api.receipts(command.owner_id, command.environment_id),
            )
        return ShellIntegrationEnvironmentResponse(
            command.request_id, command.operation,
            record=_record(api.inspect(command.owner_id, command.environment_id)),
        )
    if isinstance(command, ShellIntegrationEnvironmentControlRequest):
        method = (
            api.cleanup
            if command.operation is ShellIntegrationEnvironmentOperation.CLEANUP
            else api.reconcile
        )
        return ShellIntegrationEnvironmentResponse(
            command.request_id, command.operation,
            receipt=method(command.owner_id, command.environment_id),
        )
    raise ValueError("unsupported Shell integration environment request")


def _record(value):
    return ShellIntegrationEnvironmentRecord(
        value.state, value.plan, value.candidate, value.start_result,
        value.latest_receipt,
    )


def _intent_record(value):
    return ShellIntegrationStartIntentRecord(
        value.state, value.plan, value.candidate, value.permit,
        value.recovery_receipt,
    )
