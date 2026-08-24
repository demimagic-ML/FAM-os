"""Serialize secret mutation with exact integration-environment cleanup."""

from contextlib import contextmanager
from threading import RLock


class EngineeringSecretLifecycleCoordinator:
    """Own the lock joining secret materialization and secret retirement."""

    def __init__(self) -> None:
        self._lock = RLock()

    @contextmanager
    def locked(self):
        with self._lock:
            yield

    def drain_reference(self, secret_ref, owner_id, environments):
        """Clean every active environment whose immutable plan uses a reference."""
        cleaned = []
        with self._lock:
            for stored in environments.active(owner_id):
                if not _plan_uses_reference(stored.plan, secret_ref):
                    continue
                cleaned.append(
                    environments.cleanup(
                        owner_id, stored.plan.environment_id,
                    )
                )
            pending = getattr(environments, "pending", lambda _owner: ())(
                owner_id,
            )
            for intent in pending:
                if not _plan_uses_reference(intent.plan, secret_ref):
                    continue
                receipt = environments.recover_pending(
                    owner_id, intent.plan.environment_id,
                )
                if receipt is not None:
                    cleaned.append(receipt)
        return tuple(cleaned)


class UnavailableIntegrationEnvironmentLifecycle:
    """Expose persisted actives while failing closed when cleanup is unavailable."""

    def __init__(self, owner_id, repository) -> None:
        self._owner_id = owner_id
        self._repository = repository

    def active(self, owner_id):
        if owner_id != self._owner_id:
            raise PermissionError("integration environment owner is invalid")
        return self._repository.active()

    def cleanup(self, owner_id, environment_id):
        self.active(owner_id)
        raise RuntimeError(
            "integration environment cleanup is unavailable; secret mutation denied"
        )

    def pending(self, owner_id):
        if owner_id != self._owner_id:
            raise PermissionError("integration environment owner is invalid")
        return self._repository.pending_intents()

    def recover_pending(self, owner_id, environment_id):
        self.pending(owner_id)
        raise RuntimeError(
            "integration environment recovery is unavailable; secret mutation denied"
        )


def _plan_uses_reference(plan, secret_ref) -> bool:
    return any(
        secret_ref in service.secret_refs
        for service in plan.services
    )
