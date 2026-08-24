"""Deterministic least-authority selection from a live application context."""

from dataclasses import replace
import re

from fam_os.applications import (
    CapabilityKind,
    WORKSPACE_MAP_CAPABILITY,
    WORKSPACE_PATCH_CAPABILITY,
    WORKSPACE_RETRIEVE_CAPABILITY,
)
from fam_os.shell import ShellContextKind


_ACTION_TERMS = {
    "undo": ("undo", "revert", "roll back"),
    "save": ("save", "write to disk", "persist"),
    "apply": ("edit", "change", "replace", "update", "fix", "modify", "apply"),
}
_GENERIC_WORDS = {"action", "application", "project", "workspace"}
_FILE_OBSERVATIONS = {"os.file.read"}
_DIRECTORY_OBSERVATIONS = {"os.directory.inspect", "os.directory.list"}
_WORKSPACE_OBSERVATIONS = {
    WORKSPACE_MAP_CAPABILITY, WORKSPACE_RETRIEVE_CAPABILITY,
}
_WORKSPACE_SYNTHESIS_TERMS = (
    "analyze", "architecture", "explain", "fix", "implement", "plan",
    "project", "repository", "review", "summarize",
)


class ApplicationCapabilityResolver:
    """Choose at most one action; observations remain authority-free context."""

    def __init__(self, provider) -> None:
        self._provider = provider

    def resolve(self, command, preferred_action_id: str | None = None):
        application = next((
            item for item in command.contexts
            if item.kind is ShellContextKind.APPLICATION
        ), None)
        if application is None:
            return command
        declared = tuple(
            self._provider.capability(application.resource_ref, capability_id)
            for capability_id in application.capability_ids
        )
        declared = tuple(item for item in declared if item is not None)
        entries = tuple(
            item for item in _provider_entries(self._provider)
            if item.instance_id == application.resource_ref
            and item.capability_id in application.capability_ids
        )
        has_resource = any(
            item.kind in {ShellContextKind.FILE, ShellContextKind.URI, ShellContextKind.SELECTION}
            for item in command.contexts
        )
        resource = next((
            item.resource_ref for item in command.contexts
            if item.kind in {
                ShellContextKind.FILE, ShellContextKind.URI,
                ShellContextKind.SELECTION,
            }
        ), None)
        action = _selected_action(command.prompt, entries, preferred_action_id)
        observations = _selected_observations(
            declared, has_resource, resource, command.prompt,
            None if action is None else action.capability_id,
        )
        selected = observations + (() if action is None else (action.capability_id,))
        contexts = tuple(
            replace(item, capability_ids=selected)
            if item.context_id == application.context_id else item
            for item in command.contexts
        )
        context_ids = set(application.capability_ids)
        explicit = tuple(
            item for item in command.required_capabilities if item not in context_ids
        )
        return replace(
            command, contexts=contexts,
            required_capabilities=tuple(dict.fromkeys((*explicit, *selected))),
        )


def _selected_action(prompt, entries, preferred_action_id=None):
    actions = tuple(
        item for item in entries if item.capability.kind is CapabilityKind.ACTION
    )
    if not actions:
        return None
    if preferred_action_id is not None:
        return next((
            item for item in actions
            if item.capability_id == preferred_action_id
        ), None)
    normalized = " ".join(prompt.casefold().split())
    ranked = sorted(
        ((_score(normalized, item), item.capability_id, item) for item in actions),
        key=lambda value: (-value[0], value[1]),
    )
    return ranked[0][2] if ranked[0][0] > 0 else None


def _provider_entries(provider):
    entries = provider.entries
    return entries() if callable(entries) else entries


def _score(prompt: str, entry) -> int:
    capability = entry.capability
    text = " ".join((capability.capability_id, capability.display_name)).casefold()
    score = 0
    for key, terms in _ACTION_TERMS.items():
        if key in text and any(_contains(prompt, term) for term in terms):
            score += 100
    words = tuple(
        word for word in re.findall(r"[a-z0-9]+", capability.display_name.casefold())
        if len(word) > 3 and word not in _GENERIC_WORDS
    )
    return score + sum(1 for word in words if _contains(prompt, word))


def _contains(text: str, term: str) -> bool:
    return re.search(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text) is not None


def _observation_matches_resource(
    capability_id: str, has_resource: bool, resource: str | None,
) -> bool:
    if capability_id in _FILE_OBSERVATIONS:
        return has_resource and resource is not None and not resource.endswith("/")
    if capability_id in _DIRECTORY_OBSERVATIONS | _WORKSPACE_OBSERVATIONS:
        return has_resource and resource is not None and resource.endswith("/")
    return True


def _selected_observations(
    declared, has_resource: bool, resource: str | None,
    prompt: str, action_capability_id: str | None,
) -> tuple[str, ...]:
    available = tuple(
        item.capability_id for item in declared
        if item.capability.kind is CapabilityKind.OBSERVATION
        and _observation_matches_resource(item.capability_id, has_resource, resource)
    )
    if resource is None or not resource.endswith("/"):
        return available
    normalized = " ".join(prompt.casefold().split())
    workspace_task = (
        action_capability_id == WORKSPACE_PATCH_CAPABILITY
        or any(term in normalized for term in _WORKSPACE_SYNTHESIS_TERMS)
    )
    wanted = _WORKSPACE_OBSERVATIONS if workspace_task else _DIRECTORY_OBSERVATIONS
    return tuple(item for item in available if item in wanted)
