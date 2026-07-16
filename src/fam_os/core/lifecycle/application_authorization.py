"""Shared Core authorization checks for application plan steps."""

from pathlib import PurePosixPath
from urllib.parse import unquote, urlsplit

from fam_os.applications import (
    ApplicationAuthority, CapabilityKind, CapabilityRegistryEntry, PermissionGrant,
)
from fam_os.core.lifecycle.contracts import PlanRejection


def snapshot_rejection(snapshot, expected_revision):
    if snapshot is None:
        return PlanRejection.NOT_FOUND
    if snapshot.revision != expected_revision:
        return PlanRejection.REVISION_CONFLICT
    if snapshot.terminal:
        return PlanRejection.TERMINAL
    return None


def route_context_matches(snapshot, routed) -> bool:
    return (
        snapshot.plan.request_id == routed.request_id
        and snapshot.plan.route == routed.routing.decision
        and snapshot.authority_binding.admission_id == routed.admitted.admission_id
        and snapshot.authority_binding.valid_until == routed.admitted.permission.valid_until
        and snapshot.plan.route.required_capabilities
        == routed.admitted.permission.authorized_capabilities
    )


def valid_capability(entry, kind, instance_id, capability_id) -> bool:
    return (
        isinstance(entry, CapabilityRegistryEntry)
        and entry.available
        and entry.instance_id == instance_id
        and entry.capability_id == capability_id
        and entry.capability.kind is kind
    )


def grant_allows(grant, routed, entry, authority, resource_uri, now) -> bool:
    if not isinstance(grant, PermissionGrant):
        return False
    if not grant.active_at(now) or authority not in grant.authorities:
        return False
    if grant.subject_id != routed.admitted.permission.principal_id:
        return False
    scope = grant.scope
    checks = (
        (scope.application_ids, entry.application_id),
        (scope.instance_ids, entry.instance_id),
        (scope.capability_ids, entry.capability_id),
    )
    if any(values and target not in values for values, target in checks):
        return False
    if entry.resource_scopes:
        if resource_uri is None or not any(
            _resource_scope_allows(value, resource_uri)
            for value in entry.resource_scopes
        ):
            return False
    if scope.resource_uris:
        return resource_uri is not None and resource_uri in scope.resource_uris
    return True


def _resource_scope_allows(scope: str, resource_uri: str) -> bool:
    if scope == resource_uri:
        return True
    if not scope.endswith("/"):
        return False
    declared, requested = urlsplit(scope), urlsplit(resource_uri)
    if (
        declared.scheme != "file" or requested.scheme != "file"
        or declared.netloc != requested.netloc
        or declared.query or declared.fragment or requested.query or requested.fragment
    ):
        return False
    root = PurePosixPath(unquote(declared.path))
    target = PurePosixPath(unquote(requested.path))
    if ".." in root.parts or ".." in target.parts:
        return False
    return target != root and target.is_relative_to(root)


def action_capability(entry, instance_id, capability_id) -> bool:
    return valid_capability(entry, CapabilityKind.ACTION, instance_id, capability_id)


def required_action_authority(entry) -> ApplicationAuthority:
    return entry.capability.required_authority
