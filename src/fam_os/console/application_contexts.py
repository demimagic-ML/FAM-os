"""Workspace-specific Console views over registered application capabilities."""

from __future__ import annotations

from collections.abc import Iterable
from hashlib import sha256
from urllib.parse import unquote, urlsplit

from fam_os.applications import CapabilityKind, CapabilityRegistryEntry


def application_contexts(
    entries: Iterable[CapabilityRegistryEntry],
) -> list[dict[str, object]]:
    """Return one selectable context per application instance and resource scope."""
    grouped: dict[str, list[CapabilityRegistryEntry]] = {}
    for entry in entries:
        if entry.available:
            grouped.setdefault(entry.instance_id, []).append(entry)

    contexts = [
        _context(instance_id, scoped_entries, resource_scope)
        for instance_id, instance_entries in grouped.items()
        for resource_scope, scoped_entries in _scoped_entries(instance_entries)
    ]
    return sorted(
        contexts,
        key=lambda context: (
            str(context["application_id"]),
            str(context.get("workspace_resource_ref", "")),
        ),
    )


def _scoped_entries(
    entries: list[CapabilityRegistryEntry],
) -> tuple[tuple[str | None, list[CapabilityRegistryEntry]], ...]:
    scopes = sorted({scope for entry in entries for scope in entry.resource_scopes})
    if not scopes:
        return ((None, entries),)
    return tuple(
        (
            scope,
            [
                entry
                for entry in entries
                if not entry.resource_scopes or scope in entry.resource_scopes
            ],
        )
        for scope in scopes
    )


def _context(
    instance_id: str,
    entries: list[CapabilityRegistryEntry],
    resource_scope: str | None,
) -> dict[str, object]:
    application_id = entries[0].application_id
    capabilities = sorted({entry.capability_id for entry in entries})
    observations = sorted({
        entry.capability_id
        for entry in entries
        if entry.capability.kind is CapabilityKind.OBSERVATION
    })
    actions = sorted(set(capabilities) - set(observations))
    suffix = "" if resource_scope is None else f"-{_scope_id(resource_scope)}"
    context: dict[str, object] = {
        "context_id": f"application-{instance_id}{suffix}",
        "kind": "application",
        "resource_ref": instance_id,
        "application_id": application_id,
        "display_name": _display_name(application_id, resource_scope),
        "capability_ids": capabilities,
        "observation_capability_ids": observations,
        "action_capability_ids": actions,
        "resource_scopes": [] if resource_scope is None else [resource_scope],
    }
    if resource_scope is not None:
        context["workspace_resource_ref"] = resource_scope
    return context


def _scope_id(resource_scope: str) -> str:
    return sha256(resource_scope.encode("utf-8")).hexdigest()[:16]


def _display_name(application_id: str, resource_scope: str | None) -> str:
    if resource_scope is None:
        return application_id
    parsed = urlsplit(resource_scope)
    path = unquote(parsed.path).rstrip("/")
    label = path.rsplit("/", 1)[-1] if path else (parsed.netloc or resource_scope)
    return f"{application_id} — {label}"
