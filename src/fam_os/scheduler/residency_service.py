"""Revision-bound expert residency transitions and provider reconciliation."""

from __future__ import annotations

from dataclasses import dataclass, replace
from datetime import datetime

from fam_os.core.ports.inference import LoadedModel
from fam_os.scheduler.residency_contracts import (
    ExpertResidencyCatalog,
    ExpertResidencyRecord,
    ExpertResidencyState,
    ResidencyLease,
    ResidencyTransitionReason,
)
from fam_os.scheduler.residency_ports import (
    ExpertResidencyRepository,
    ModelResidencyRuntime,
    ResidencyTransitionError,
)


@dataclass(frozen=True, slots=True)
class ExpertResidencyService:
    repository: ExpertResidencyRepository

    def reconcile(
        self,
        loaded_models: tuple[LoadedModel, ...],
        observed_at: datetime,
        expected_revision: int,
    ) -> ExpertResidencyCatalog:
        _require_time(observed_at)
        current = self._current(expected_revision)
        loaded = _loaded_by_artifact(loaded_models)
        _require_no_active_absence(current, loaded)
        records = tuple(
            _reconciled_record(record, loaded.get(record.identity.runtime_artifact_id), observed_at)
            for record in current.records
        )
        if records == current.records:
            return current
        return self._store(current, records, observed_at)

    def acquire(
        self, expert_id: str, lease: ResidencyLease, expected_revision: int
    ) -> ExpertResidencyCatalog:
        current = self._current(expected_revision)
        record = current.require(expert_id)
        if record.state in (ExpertResidencyState.COLD, ExpertResidencyState.EVICTING):
            raise ResidencyTransitionError("expert residency cannot acquire a lease")
        if lease.expires_at <= lease.acquired_at:
            raise ResidencyTransitionError("residency lease is already expired")
        retained = tuple(item for item in record.active_leases if item.expires_at > lease.acquired_at)
        if any(item.lease_id == lease.lease_id for item in retained):
            raise ResidencyTransitionError("residency lease_id already exists")
        if any(item.request_id == lease.request_id for item in retained):
            raise ResidencyTransitionError("request already owns a residency lease")
        updated = _transition(
            record, ExpertResidencyState.ACTIVE, lease.acquired_at,
            ResidencyTransitionReason.LEASE_ACQUIRED,
            active_leases=retained + (lease,), eviction_id=None,
        )
        return self._replace_record(current, updated, lease.acquired_at)

    def release(
        self, expert_id: str, lease_id: str, released_at: datetime,
        expected_revision: int,
    ) -> ExpertResidencyCatalog:
        _require_time(released_at)
        current = self._current(expected_revision)
        record = current.require(expert_id)
        retained = tuple(item for item in record.active_leases if item.lease_id != lease_id)
        if len(retained) == len(record.active_leases):
            raise ResidencyTransitionError("residency lease does not exist")
        state = ExpertResidencyState.ACTIVE if retained else ExpertResidencyState.WARM
        updated = _transition(
            record, state, released_at, ResidencyTransitionReason.LEASE_RELEASED,
            active_leases=retained, eviction_id=None,
        )
        return self._replace_record(current, updated, released_at)

    def expire_leases(
        self, now: datetime, expected_revision: int
    ) -> ExpertResidencyCatalog:
        _require_time(now)
        current = self._current(expected_revision)
        records = tuple(_expire_record(record, now) for record in current.records)
        if records == current.records:
            return current
        return self._store(current, records, now)

    def begin_eviction(
        self, expert_id: str, eviction_id: str, started_at: datetime,
        expected_revision: int,
    ) -> ExpertResidencyCatalog:
        _require_text(eviction_id, "eviction_id")
        _require_time(started_at)
        current = self._current(expected_revision)
        record = current.require(expert_id)
        if record.state is not ExpertResidencyState.WARM:
            raise ResidencyTransitionError("only a warm expert can begin eviction")
        updated = _transition(
            record, ExpertResidencyState.EVICTING, started_at,
            ResidencyTransitionReason.EVICTION_STARTED,
            active_leases=(), eviction_id=eviction_id,
        )
        return self._replace_record(current, updated, started_at)

    def abort_eviction(
        self, expert_id: str, eviction_id: str, aborted_at: datetime,
        expected_revision: int,
    ) -> ExpertResidencyCatalog:
        return self._finish_eviction(
            expert_id, eviction_id, aborted_at, expected_revision,
            ExpertResidencyState.WARM, ResidencyTransitionReason.EVICTION_ABORTED,
        )

    def confirm_eviction(
        self, expert_id: str, eviction_id: str, confirmed_at: datetime,
        expected_revision: int,
    ) -> ExpertResidencyCatalog:
        return self._finish_eviction(
            expert_id, eviction_id, confirmed_at, expected_revision,
            ExpertResidencyState.COLD, ResidencyTransitionReason.EVICTION_CONFIRMED,
        )

    def _finish_eviction(self, expert_id, eviction_id, at, expected, state, reason):
        _require_time(at)
        current = self._current(expected)
        record = current.require(expert_id)
        if record.state is not ExpertResidencyState.EVICTING or record.eviction_id != eviction_id:
            raise ResidencyTransitionError("eviction identity does not match active transition")
        fields = {
            "active_leases": (), "eviction_id": None,
            "provider_observed_at": at,
        }
        if state is ExpertResidencyState.COLD:
            fields.update(resident_bytes=None, accelerator_bytes=None, context_tokens=None)
        updated = _transition(record, state, at, reason, **fields)
        return self._replace_record(current, updated, at)

    def _current(self, expected_revision):
        current = self.repository.read()
        if current.revision != expected_revision:
            raise ResidencyTransitionError("expected residency revision is stale")
        return current

    def _replace_record(self, current, updated, at):
        records = tuple(updated if item.identity == updated.identity else item for item in current.records)
        return self._store(current, records, at)

    def _store(self, current, records, at):
        replacement = replace(current, revision=current.revision + 1, updated_at=at, records=records)
        return self.repository.compare_and_swap(current.revision, replacement)


@dataclass(frozen=True, slots=True)
class ResidencyEvictionCoordinator:
    service: ExpertResidencyService
    runtime: ModelResidencyRuntime

    def evict(self, expert_id, eviction_id, started_at, confirmed_at, expected_revision):
        started = self.service.begin_eviction(
            expert_id, eviction_id, started_at, expected_revision
        )
        artifact = started.require(expert_id).identity.runtime_artifact_id
        try:
            self.runtime.unload(artifact)
        except Exception:
            try:
                loaded = self.runtime.loaded_models()
            except Exception:
                raise
            if all(item.model_ref != artifact for item in loaded):
                return self.service.confirm_eviction(
                    expert_id, eviction_id, confirmed_at, started.revision
                )
            self.service.abort_eviction(
                expert_id, eviction_id, confirmed_at, started.revision
            )
            raise
        return self.service.confirm_eviction(
            expert_id, eviction_id, confirmed_at, started.revision
        )


def _reconciled_record(record, loaded, observed_at):
    if loaded is None:
        if record.state is ExpertResidencyState.COLD:
            return record
        reason = (
            ResidencyTransitionReason.EVICTION_CONFIRMED
            if record.state is ExpertResidencyState.EVICTING
            else ResidencyTransitionReason.PROVIDER_ABSENT
        )
        return _transition(
            record, ExpertResidencyState.COLD, observed_at, reason,
            active_leases=(), eviction_id=None, provider_observed_at=observed_at,
            resident_bytes=None, accelerator_bytes=None, context_tokens=None,
        )
    state = ExpertResidencyState.WARM if record.state is ExpertResidencyState.COLD else record.state
    reason = (
        ResidencyTransitionReason.PROVIDER_LOADED
        if record.state is ExpertResidencyState.COLD
        else ResidencyTransitionReason.PROVIDER_REFRESHED
    )
    return _transition(
        record, state, observed_at, reason, provider_observed_at=observed_at,
        resident_bytes=loaded.resident_bytes, accelerator_bytes=loaded.accelerator_bytes,
        context_tokens=loaded.context_tokens,
    )


def _transition(record, state, at, reason, **changes):
    if at < record.transitioned_at:
        raise ResidencyTransitionError("residency transition time cannot move backward")
    return replace(
        record, state=state, record_revision=record.record_revision + 1,
        transitioned_at=at, transition_reason=reason, **changes,
    )


def _expire_record(record, now):
    if record.state is not ExpertResidencyState.ACTIVE:
        return record
    retained = tuple(item for item in record.active_leases if item.expires_at > now)
    if retained == record.active_leases:
        return record
    state = ExpertResidencyState.ACTIVE if retained else ExpertResidencyState.WARM
    return _transition(
        record, state, now, ResidencyTransitionReason.LEASES_EXPIRED,
        active_leases=retained,
    )


def _loaded_by_artifact(models):
    result = {}
    for model in models:
        if model.model_ref in result:
            raise ResidencyTransitionError("provider returned duplicate loaded model")
        result[model.model_ref] = model
    return result


def _require_no_active_absence(catalog, loaded):
    for record in catalog.records:
        if (
            record.state is ExpertResidencyState.ACTIVE
            and record.identity.runtime_artifact_id not in loaded
        ):
            raise ResidencyTransitionError("active expert disappeared from provider")


def _require_time(value):
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("residency transition time must be timezone-aware")


def _require_text(value, name):
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
