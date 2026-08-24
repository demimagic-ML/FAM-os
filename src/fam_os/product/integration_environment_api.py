"""Owner-scoped persistent lifecycle for product integration environments."""

from dataclasses import dataclass
from pathlib import Path

from fam_os.core.engineering import IntegrationEnvironmentStatus


@dataclass(frozen=True, slots=True)
class IntegrationRecoveryOutcome:
    environment_id: str
    cleaned: bool
    diagnostic: str


class ProductIntegrationEnvironmentApi:
    def __init__(
        self, owner_id, service, adapter, repository, lifecycle=None,
    ) -> None:
        if not owner_id.strip():
            raise ValueError("integration environment owner is empty")
        self._owner_id = owner_id
        self._service = service
        self._adapter = adapter
        self._repository = repository
        self._lifecycle = lifecycle

    @property
    def owner_id(self) -> str:
        return self._owner_id

    def start(
        self, owner_id, plan, candidate, grant_id, principal_id, session_id,
        cancelled,
    ):
        self._require_owner(owner_id)
        if self._lifecycle is not None:
            with self._lifecycle.locked():
                return self._start(
                    plan, candidate, grant_id, principal_id, session_id,
                    cancelled,
                )
        return self._start(
            plan, candidate, grant_id, principal_id, session_id, cancelled,
        )

    def _start(
        self, plan, candidate, grant_id, principal_id, session_id, cancelled,
    ):
        self._repository.begin_start(plan, candidate)
        try:
            result = self._service.start(
                plan, candidate, grant_id, principal_id, session_id, cancelled,
                self._repository.record_permit,
            )
        except BaseException:
            self._repository.record_interrupted(plan.environment_id)
            raise
        try:
            self._repository.put_started(plan, candidate, result)
        except BaseException as persistence_error:
            try:
                receipt = self._service.cleanup(
                    plan, candidate, result.receipt, result.permit,
                )
            except BaseException as cleanup_error:
                self._repository.record_interrupted(plan.environment_id)
                raise RuntimeError(
                    "integration start persistence and compensation both failed"
                ) from cleanup_error
            self._repository.record_intent_recovery(
                plan.environment_id, receipt,
            )
            raise persistence_error
        return result

    def inspect(self, owner_id, environment_id):
        self._require_owner(owner_id)
        stored = self._repository.get(environment_id)
        if stored is None:
            raise KeyError("integration environment is unavailable")
        return stored

    def active(self, owner_id):
        self._require_owner(owner_id)
        return self._repository.active()

    def for_task(self, owner_id, task_id):
        self._require_owner(owner_id)
        if not task_id.strip():
            raise ValueError("integration environment task identity is empty")
        return self._repository.for_task(task_id)

    def pending(self, owner_id):
        self._require_owner(owner_id)
        return self._repository.pending_intents()

    def intents(self, owner_id):
        self._require_owner(owner_id)
        return self._repository.intents()

    def inspect_intent(self, owner_id, environment_id):
        self._require_owner(owner_id)
        intent = self._repository.intent(environment_id)
        if intent is None:
            raise KeyError("integration start intent is unavailable")
        return intent

    def recover_pending(self, owner_id, environment_id):
        self._require_owner(owner_id)
        intent = next((
            item for item in self._repository.pending_intents()
            if item.plan.environment_id == environment_id
        ), None)
        if intent is None:
            raise KeyError("integration start intent is unavailable")
        return self._recover_intent(intent)

    def cleanup(self, owner_id, environment_id):
        if self._lifecycle is not None:
            with self._lifecycle.locked():
                return self._cleanup(owner_id, environment_id)
        return self._cleanup(owner_id, environment_id)

    def _cleanup(self, owner_id, environment_id):
        stored = self.inspect(owner_id, environment_id)
        if stored.state != "active":
            raise PermissionError("only an active integration environment can clean up")
        receipt = self._service.cleanup(
            stored.plan, stored.candidate, stored.latest_receipt,
            stored.start_result.permit,
        )
        self._validate_cleanup(environment_id, stored, receipt)
        self._repository.record_cleanup(
            environment_id, receipt, reconciled=False,
        )
        return receipt

    def reconcile(self, owner_id, environment_id):
        if self._lifecycle is not None:
            with self._lifecycle.locked():
                return self._reconcile(owner_id, environment_id)
        return self._reconcile(owner_id, environment_id)

    def _reconcile(self, owner_id, environment_id):
        stored = self.inspect(owner_id, environment_id)
        if stored.state != "active":
            raise PermissionError("only an active integration environment can reconcile")
        receipt = self._adapter.reconcile(
            stored.plan, Path(stored.candidate.candidate_workspace),
            stored.start_result.permit,
        )
        self._validate_cleanup(environment_id, stored, receipt)
        self._repository.record_cleanup(
            environment_id, receipt, reconciled=True,
        )
        return receipt

    def reconcile_active(self) -> tuple[IntegrationRecoveryOutcome, ...]:
        outcomes = []
        for stored in self._repository.active():
            identity = stored.plan.environment_id
            try:
                self.reconcile(self._owner_id, identity)
            except (OSError, PermissionError, RuntimeError, ValueError) as error:
                outcomes.append(IntegrationRecoveryOutcome(
                    identity, False, f"{type(error).__name__}: {error}",
                ))
            else:
                outcomes.append(IntegrationRecoveryOutcome(
                    identity, True, "reconciled and cleaned",
                ))
        return tuple(outcomes)

    def recover_incomplete(self) -> tuple[IntegrationRecoveryOutcome, ...]:
        outcomes = []
        for intent in self._repository.pending_intents():
            identity = intent.plan.environment_id
            try:
                receipt = self._recover_intent(intent)
            except (OSError, PermissionError, RuntimeError, ValueError) as error:
                outcomes.append(IntegrationRecoveryOutcome(
                    identity, False, f"{type(error).__name__}: {error}",
                ))
            else:
                outcomes.append(IntegrationRecoveryOutcome(
                    identity, True,
                    (
                        "prelaunch intent closed without effects"
                        if receipt is None
                        else "interrupted launch recovered and cleaned"
                    ),
                ))
        return tuple(outcomes)

    def _recover_intent(self, intent):
        identity = intent.plan.environment_id
        if intent.permit is None:
            self._repository.record_prelaunch_failed(identity)
            return None
        recover = getattr(self._adapter, "recover", self._adapter.reconcile)
        receipt = recover(
            intent.plan, Path(intent.candidate.candidate_workspace),
            intent.permit,
        )
        self._validate_intent_recovery(intent, receipt)
        self._repository.record_intent_recovery(identity, receipt)
        return receipt

    def receipts(self, owner_id, environment_id):
        self.inspect(owner_id, environment_id)
        return self._repository.receipts(environment_id)

    def _require_owner(self, owner_id) -> None:
        if owner_id != self._owner_id:
            raise PermissionError("integration environment owner is invalid")

    @staticmethod
    def _validate_cleanup(environment_id, stored, receipt) -> None:
        if (
            receipt.status is not IntegrationEnvironmentStatus.CLEANED
            or receipt.environment_id != environment_id
            or receipt.permit_id != stored.start_result.permit.permit_id
            or not receipt.cleanup_evidence_ids
        ):
            raise RuntimeError("integration cleanup returned invalid evidence")

    @staticmethod
    def _validate_intent_recovery(intent, receipt) -> None:
        if (
            receipt.status is not IntegrationEnvironmentStatus.CLEANED
            or receipt.environment_id != intent.plan.environment_id
            or receipt.permit_id != intent.permit.permit_id
            or not receipt.cleanup_evidence_ids
        ):
            raise RuntimeError("integration intent recovery returned invalid evidence")
