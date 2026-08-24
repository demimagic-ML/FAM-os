"""Fail-closed routing of authority-bearing Shell requests before inference."""

from dataclasses import dataclass, replace
from pathlib import Path
from urllib.parse import unquote, urlsplit

from fam_os.applications import CapabilityKind
from fam_os.core.contracts import ResultKind
from fam_os.core.production.action_ingress_result import action_ingress_result
from fam_os.core.production.action_intent import (
    ActionIntentDecision,
    ActionIntentFirewall,
    CREATE_DIRECTORY_CAPABILITY,
)
from fam_os.core.production.application_intent import ApplicationCapabilityResolver
from fam_os.shell import ShellContext, ShellContextKind


@dataclass(frozen=True, slots=True)
class ActionIngressRoute:
    command: object
    action: ActionIntentDecision
    deterministic_parameters: str | None = None
    terminal_result: object | None = None


class ActionIngressRouter:
    """Resolve action intent to live capability authority or a typed refusal."""

    def __init__(self, applications) -> None:
        self._applications = applications
        self._firewall = ActionIntentFirewall()

    def route(self, command, session_id: str) -> ActionIngressRoute:
        action = self._firewall.inspect(
            command.prompt, session_id, self._workspace_path(command),
        )
        if action.needs_input:
            return self._terminal(command, action, ResultKind.ACTION_PROPOSAL)
        deterministic = None
        if self._needs_directory_resolution(command, action):
            resolved = self._directory_command(command, action.target_path)
            if resolved is None:
                return self._terminal(
                    command, action, ResultKind.CAPABILITY_UNAVAILABLE,
                )
            command = resolved
            deterministic = "{}"
        if (
            command.contexts and self._applications is not None
            and deterministic is None
        ):
            command = ApplicationCapabilityResolver(
                self._applications.provider,
            ).resolve(command, action.capability_id)
        if action.action_shaped and not self._has_action_capability(
            command, action.capability_id,
        ):
            return self._terminal(
                command, action, ResultKind.CAPABILITY_UNAVAILABLE,
            )
        return ActionIngressRoute(command, action, deterministic)

    def block_delegated(self, command, session_id: str):
        action = self._firewall.inspect(command.prompt, session_id)
        if not action.action_shaped:
            return None
        kind = (
            ResultKind.ACTION_PROPOSAL
            if action.needs_input else ResultKind.CAPABILITY_UNAVAILABLE
        )
        return self._result(command.request_id, kind, action.safe_message)

    def unavailable(self, request_id: str, message: str):
        return self._result(
            request_id, ResultKind.CAPABILITY_UNAVAILABLE, message,
        )

    @staticmethod
    def _needs_directory_resolution(command, action) -> bool:
        return (
            action.capability_id == CREATE_DIRECTORY_CAPABILITY
            and action.target_path is not None
        )

    def _workspace_path(self, command) -> Path | None:
        if self._applications is None:
            return None
        applications = tuple(
            item for item in command.contexts
            if item.kind is ShellContextKind.APPLICATION
        )
        resources = tuple(
            item.resource_ref for item in command.contexts
            if item.kind in {ShellContextKind.URI, ShellContextKind.FILE}
        )
        if len(applications) != 1 or len(resources) != 1:
            return None
        resource = resources[0]
        if not resource.endswith("/"):
            return None
        entry = self._applications.provider.capability(
            applications[0].resource_ref, CREATE_DIRECTORY_CAPABILITY,
        )
        if entry is None or not any(
            _uri_is_within(resource, scope) for scope in entry.resource_scopes
        ):
            return None
        parsed = urlsplit(resource)
        if parsed.scheme != "file" or parsed.netloc not in {"", "localhost"}:
            return None
        path = Path(unquote(parsed.path))
        return path if path.is_absolute() and ".." not in path.parts else None

    def _directory_command(self, command, target_path):
        if self._applications is None or target_path is None:
            return None
        entries = tuple(
            entry for entry in self._applications.provider.entries()
            if entry.capability_id == CREATE_DIRECTORY_CAPABILITY
            and entry.capability.kind is CapabilityKind.ACTION
        )
        if len(entries) != 1:
            return None
        entry = entries[0]
        resource_uri = target_path.as_uri()
        contexts = (
            ShellContext(
                f"application-{entry.instance_id}", ShellContextKind.APPLICATION,
                entry.instance_id, entry.application_id, (entry.capability_id,),
            ),
            ShellContext(
                f"resource-{command.request_id}", ShellContextKind.URI,
                resource_uri, resource_uri,
            ),
        )
        return replace(
            command, contexts=contexts,
            required_capabilities=(entry.capability_id,),
            verification_required=True,
        )

    def _has_action_capability(
        self, command, required_capability_id: str | None = None,
    ) -> bool:
        if self._applications is None:
            return False
        instance_ids = {
            context.resource_ref for context in command.contexts
            if context.kind is ShellContextKind.APPLICATION
        }
        requested = set(command.required_capabilities)
        requested.update(
            capability for context in command.contexts
            for capability in context.capability_ids
        )
        return any(
            entry.instance_id in instance_ids
            and entry.capability_id in requested
            and (
                required_capability_id is None
                or entry.capability_id == required_capability_id
            )
            and entry.capability.kind is CapabilityKind.ACTION
            for entry in self._applications.provider.entries()
        )

    def _terminal(self, command, action, kind):
        return ActionIngressRoute(
            command, action,
            terminal_result=self._result(
                command.request_id, kind, action.safe_message,
            ),
        )

    @staticmethod
    def _result(request_id, kind, message):
        safe = message or (
            "No authorized capability matched this machine action. "
            "No action was attempted."
        )
        return action_ingress_result(request_id, kind, safe)


def _uri_is_within(resource: str, scope: str) -> bool:
    resource_uri = urlsplit(resource)
    scope_uri = urlsplit(scope)
    if (
        resource_uri.scheme != "file" or scope_uri.scheme != "file"
        or resource_uri.netloc not in {"", "localhost"}
        or scope_uri.netloc not in {"", "localhost"}
    ):
        return False
    resource_path = Path(unquote(resource_uri.path))
    scope_path = Path(unquote(scope_uri.path))
    return resource_path == scope_path or resource_path.is_relative_to(scope_path)
