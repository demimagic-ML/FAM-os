"""Dispatch typed Shell engineering-secret requests."""

from datetime import datetime

from fam_os.shell.engineering_secret_contracts import (
    ShellEngineeringSecretAuditEvent, ShellEngineeringSecretMetadata,
    ShellEngineeringSecretMutation, ShellEngineeringSecretOperation,
    ShellEngineeringSecretQuery, ShellEngineeringSecretResponse,
)


class EngineeringSecretUnavailable(RuntimeError): pass


def dispatch_engineering_secret(api, command):
    if api is None: raise EngineeringSecretUnavailable
    if isinstance(command, ShellEngineeringSecretQuery):
        if command.operation is ShellEngineeringSecretOperation.LIST:
            return ShellEngineeringSecretResponse(
                command.request_id, command.operation,
                items=tuple(_metadata(item) for item in api.list()),
            )
        if command.operation is ShellEngineeringSecretOperation.AUDIT:
            result = api.audit(command.secret_ref)
            return ShellEngineeringSecretResponse(
                command.request_id, command.operation,
                events=tuple(_event(item) for item in result["events"]),
                secret_ref=result["secret_ref"],
            )
        return ShellEngineeringSecretResponse(
            command.request_id, command.operation,
            metadata=_metadata(api.inspect(command.secret_ref)),
        )
    if isinstance(command, ShellEngineeringSecretMutation):
        document = {
            "owner_id": command.owner_id, "secret_ref": command.secret_ref,
            "authentication_context_id": command.authentication_context_id,
            "confirmed": command.confirmed,
        }
        if command.operation is ShellEngineeringSecretOperation.PROVISION:
            document |= {"tool_key": command.tool_key, "consumer_id": command.consumer_id, "value": command.value}
            result = api.provision(document, command.authority_session_id)
        elif command.operation is ShellEngineeringSecretOperation.ROTATE:
            result = api.rotate(document | {"value": command.value}, command.authority_session_id)
        elif command.operation is ShellEngineeringSecretOperation.DELETE:
            result = api.delete(document, command.authority_session_id)
        else: raise ValueError("unsupported Shell secret mutation")
        return ShellEngineeringSecretResponse(
            command.request_id, command.operation, metadata=_metadata(result),
        )
    raise ValueError("unsupported Shell engineering secret request")


def _metadata(value):
    return ShellEngineeringSecretMetadata(
        value["secret_ref"], value["tool_key"], value["consumer_id"],
        value["state"], value["generation"], datetime.fromisoformat(value["created_at"]),
        datetime.fromisoformat(value["updated_at"]),
    )


def _event(value):
    return ShellEngineeringSecretAuditEvent(
        value["event_id"], value["action"], value["generation"],
        datetime.fromisoformat(value["occurred_at"]),
    )
