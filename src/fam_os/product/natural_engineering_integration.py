"""Attach bounded integration environments to the natural engineering loop."""

from dataclasses import dataclass
from datetime import datetime, timezone
import socket

from fam_os.adapters.integration import natural_integration_environment_id
from fam_os.core.engineering import (
    EngineeringAuthorityGrant,
    IntegrationEnvironmentStatus,
    natural_integration_resource_grant_id,
)


@dataclass(frozen=True, slots=True)
class NaturalIntegrationEnvironmentResult:
    plan: object
    start_result: object
    cleanup_receipt: object
    postapply: bool
    postgresql_plan: object | None = None
    postgresql_verification: object | None = None


class NaturalEngineeringIntegrationCoordinator:
    def __init__(
        self, loop, environments, planner, *, clock=None, port_allocator=None,
        resource_grant_resolver=None, postgresql_planner=None,
        postgresql_verifier=None,
    ) -> None:
        self._loop = loop
        self._environments = environments
        self._planner = planner
        self._clock = clock or (lambda: datetime.now(timezone.utc))
        self._port_allocator = port_allocator or _available_loopback_port
        self._resource_grant_resolver = resource_grant_resolver
        if (postgresql_planner is None) != (postgresql_verifier is None):
            raise ValueError(
                "natural PostgreSQL planner and verifier must be composed together"
            )
        self._postgresql_planner = postgresql_planner
        self._postgresql_verifier = postgresql_verifier

    def requested(self, definition) -> bool:
        return self._planner.requested(definition.task.intent)

    def run_candidate(
        self, owner_id, definition, candidate, changed_paths, changeset_id, *,
        session_id, principal_id,
    ) -> NaturalIntegrationEnvironmentResult:
        return self._run(
            owner_id, definition, candidate, changed_paths, changeset_id,
            session_id=session_id, principal_id=principal_id,
            postapply=False,
        )

    def run_postapply(
        self, owner_id, definition, changeset_id, *, session_id, principal_id,
    ) -> NaturalIntegrationEnvironmentResult:
        existing = self._existing(
            owner_id, definition.task.task_id, changeset_id, postapply=True,
        )
        if existing is not None:
            return self._finish_existing(
                owner_id, existing, definition, postapply=True,
            )
        candidate = self._loop.fresh_owner_candidate(
            owner_id, definition.task.task_id,
        )
        changed_paths = (
            self._changeset_paths(
                owner_id, definition.task.task_id, changeset_id,
            )
            if self._postgresql_requested(definition, postapply=True)
            else ()
        )
        return self._run(
            owner_id, definition, candidate, changed_paths, changeset_id,
            session_id=session_id, principal_id=principal_id,
            postapply=True,
        )

    def for_task(self, owner_id, task_id):
        return self._environments.for_task(owner_id, task_id)

    def _run(
        self, owner_id, definition, candidate, changed_paths, changeset_id, *,
        session_id, principal_id, postapply,
    ):
        existing = self._existing(
            owner_id, definition.task.task_id, changeset_id,
            postapply=postapply,
        )
        if existing is not None:
            if not postapply and existing.candidate.candidate_id != candidate.candidate_id:
                raise RuntimeError("natural integration candidate recovery is mismatched")
            if self._postgresql_requested(definition, postapply=postapply):
                if existing.state == "active":
                    self._environments.cleanup(
                        owner_id, existing.plan.environment_id,
                    )
                raise RuntimeError(
                    "recovered PostgreSQL environment has no persisted migration evidence"
                )
            return self._finish_existing(
                owner_id, existing, definition, postapply=postapply,
            )
        if not postapply:
            candidate = self._current_candidate(
                owner_id, definition.task.task_id, candidate,
            )
        port_count = self._planner.required_port_count(
            definition, candidate, changed_paths,
        )
        ports = tuple(self._port_allocator() for _item in range(port_count))
        if len(set(ports)) != len(ports):
            raise RuntimeError("natural integration port allocation collided")
        resource_grant = self._resource_grant(definition)
        plan = self._planner.build(
            definition, candidate, changed_paths, changeset_id,
            ports, postapply=postapply, now=self._clock(),
            resource_grant=resource_grant,
        )
        start = self._environments.start(
            owner_id, plan, candidate,
            (
                definition.task.grant_id
                if resource_grant is None else resource_grant.grant_id
            ),
            principal_id, session_id, lambda: False,
        )
        if start.receipt.status is not IntegrationEnvironmentStatus.READY:
            raise RuntimeError("natural integration environment did not become ready")
        postgresql_plan = postgresql_verification = None
        try:
            if self._postgresql_requested(definition, postapply=postapply):
                if resource_grant is None:
                    raise PermissionError(
                        "natural PostgreSQL verification requires its resource grant"
                    )
                postgresql_plan = self._postgresql_planner.build(
                    definition,
                    candidate,
                    candidate.entries,
                    tuple(changed_paths),
                    plan,
                    now=self._clock(),
                )
                if postgresql_plan is None:
                    raise RuntimeError(
                        "natural PostgreSQL migration plan is unavailable"
                    )
                postgresql_verification = self._postgresql_verifier.execute(
                    postgresql_plan,
                    candidate,
                    plan,
                    start,
                    definition.task.grant_id,
                    resource_grant.grant_id,
                    principal_id,
                    session_id,
                    lambda: False,
                )
                if not postgresql_verification.passed:
                    raise RuntimeError(
                        "natural PostgreSQL verification did not pass"
                    )
        finally:
            cleanup = self._environments.cleanup(owner_id, plan.environment_id)
        result = NaturalIntegrationEnvironmentResult(
            plan,
            start,
            cleanup,
            postapply,
            postgresql_plan,
            postgresql_verification,
        )
        self._record(owner_id, definition.task.task_id, result)
        return result

    def _resource_grant(self, definition):
        if self._resource_grant_resolver is None:
            return None
        grant = self._resource_grant_resolver(
            natural_integration_resource_grant_id(
                definition.task.grant_id,
            )
        )
        if grant is not None and not isinstance(grant, EngineeringAuthorityGrant):
            raise TypeError("natural integration resource grant is invalid")
        return grant

    def _postgresql_requested(self, definition, *, postapply):
        return (
            self._postgresql_planner is not None
            and self._postgresql_planner.requested(definition.task.intent)
        )

    def _changeset_paths(self, owner_id, task_id, changeset_id):
        reader = getattr(self._loop, "candidate_changesets", None)
        if reader is None:
            raise RuntimeError(
                "post-apply PostgreSQL verification lacks changeset evidence"
            )
        matches = tuple(
            item for item in reader(owner_id, task_id)
            if item.changeset_id == changeset_id
        )
        if len(matches) != 1 or matches[0].status.value != "applied":
            raise RuntimeError(
                "post-apply PostgreSQL changeset is not exactly applied"
            )
        return tuple(
            item.source_path or item.path for item in matches[0].operations
        )

    def _current_candidate(self, owner_id, task_id, candidate):
        reader = getattr(self._loop, "current_candidate", None)
        if reader is None:
            return candidate
        current = reader(owner_id, task_id)
        if (
            current.task_id != candidate.task_id
            or current.candidate_id != candidate.candidate_id
            or current.candidate_workspace != candidate.candidate_workspace
        ):
            raise RuntimeError("natural integration current candidate is mismatched")
        return current

    def _existing(self, owner_id, task_id, changeset_id, *, postapply):
        identity = natural_integration_environment_id(
            task_id, postapply=postapply,
        )
        try:
            stored = self._environments.inspect(owner_id, identity)
        except KeyError:
            return None
        if (
            stored.plan.task_id != task_id
            or stored.plan.approved_changeset_id != changeset_id
        ):
            raise RuntimeError("natural integration recovery scope is mismatched")
        return stored

    def _finish_existing(self, owner_id, stored, definition, *, postapply):
        if stored.state == "active":
            cleanup = self._environments.cleanup(
                owner_id, stored.plan.environment_id,
            )
        elif stored.state == "cleaned":
            cleanup = stored.latest_receipt
        else:
            raise RuntimeError("natural integration environment is not recoverable")
        result = NaturalIntegrationEnvironmentResult(
            stored.plan, stored.start_result, cleanup, postapply,
        )
        self._record(owner_id, definition.task.task_id, result)
        return result

    def _record(self, owner_id, task_id, result) -> None:
        self._loop.record_integration_environment(
            owner_id, task_id, result.plan, result.start_result,
            result.cleanup_receipt, postapply=result.postapply,
        )


def _available_loopback_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as stream:
        stream.bind(("127.0.0.1", 0))
        return stream.getsockname()[1]
