"""Serialized production model leases, admission, and confirmed eviction."""

from __future__ import annotations

from collections.abc import Callable, Iterator
from contextlib import contextmanager
from dataclasses import replace
from datetime import UTC, datetime, timedelta
import hashlib
from pathlib import Path
from threading import RLock
from uuid import uuid4

from fam_os.adapters.filesystem.residency_state import JsonExpertResidencyRepository
from fam_os.adapters.ollama.context_profile import (
    OllamaContextProfileObserver,
    OllamaContextProfilePolicy,
)
from fam_os.adapters.ollama.settings import OllamaSettings
from fam_os.adapters.ollama.transport import UrllibJsonTransport
from fam_os.core.ports.embedding import EmbeddingRequest
from fam_os.core.ports.inference import InferenceRequest
from fam_os.core.production.model_catalog import RuntimeModelCatalog
from fam_os.core.production.model_selection import HostCapacity
from fam_os.scheduler.admission_contracts import (
    AdmissionRequest,
    AdmissionStatus,
    EvictionCandidate,
    ResidentWeightEstimate,
    WeightEstimateSource,
)
from fam_os.scheduler.admission_policy import DeterministicAdmissionPolicy
from fam_os.scheduler.context_contracts import (
    ContextMemoryReservation,
    ContextMemoryStrategy,
)
from fam_os.scheduler.context_estimator import ContextMemoryEstimator
from fam_os.scheduler.live_contracts import ObservationStatus
from fam_os.scheduler.residency_contracts import (
    ExpertResidencyIdentity,
    ExpertResidencyState,
    ResidencyLease,
)
from fam_os.scheduler.residency_service import (
    ExpertResidencyService,
    ResidencyEvictionCoordinator,
    initial_observed_residency_catalog,
)


_LEASE_DURATION = timedelta(minutes=10)
_DEGRADED_CAPACITY_REASONS = {
    "cgroup.managed_snapshot_unavailable",
    "cgroup.managed_usage_unavailable",
}


class ModelResidencyAdmissionError(RuntimeError):
    """A local model session could not be admitted without unsafe eviction."""


class ProductionModelResidency:
    """Own one serialized local inference/eviction critical section."""

    def __init__(
        self,
        state_path: Path,
        catalog: RuntimeModelCatalog,
        runtime,
        capacity: Callable[[], HostCapacity],
        model_loader,
        ollama_url: str,
        *,
        eviction_allowed: bool,
        now: Callable[[], datetime] | None = None,
        profile_observer=None,
    ) -> None:
        self._catalog = catalog
        self._runtime = runtime
        self._capacity = capacity
        self._loader = model_loader
        self._eviction_allowed = eviction_allowed
        self._now = now or (lambda: datetime.now(UTC))
        self._lock = RLock()
        self._repository = JsonExpertResidencyRepository(state_path)
        instant = self._now()
        loaded_at_start = self._runtime.loaded_models()
        created = not state_path.exists()
        if created:
            self._repository.initialize(initial_observed_residency_catalog(
                "production-model-residency",
                self._identities(),
                loaded_at_start,
                instant,
            ))
        self._service = ExpertResidencyService(self._repository)
        self._eviction = ResidencyEvictionCoordinator(self._service, runtime)
        self._profiles = profile_observer or OllamaContextProfileObserver(
            OllamaSettings(ollama_url, 30), UrllibJsonTransport(),
        )
        with self._lock:
            current = self._repository.read()
            self._service.recover_process_leases(instant, current.revision)
            if not created:
                self._refresh(instant, loaded_at_start)

    def chat(self, request: InferenceRequest):
        """Run every catalog inference under admission and a durable lease."""

        return self.chat_for_request(f"runtime-chat-{uuid4()}", request)

    def chat_for_request(self, request_id: str, request: InferenceRequest):
        if self._catalog.get(request.model_ref) is None:
            # Factory canaries are intentionally temporary and are never eviction
            # candidates, but still share the same provider critical section.
            with self._lock:
                return self._runtime.chat(request)
        with self.session(
            request_id,
            request.model_ref,
            request.context_tokens,
            request.max_output_tokens,
        ):
            return self._runtime.chat(request)

    def embed(self, request: EmbeddingRequest):
        """Serialize embedding use and lease its signed catalog model."""

        request_id = f"runtime-embed-{uuid4()}"
        with self._lock:
            if self._loader is not None:
                self._loader.ensure_model(request.model_ref)
            expert_id = self._expert_id(request.model_ref)
            context = self._embedding_context_estimate(
                request_id, expert_id, request.model_ref, request.inputs,
            )
            with self._admitted_session(
                request_id, expert_id, request.model_ref, context,
                prewarmer=self._runtime.prewarm_embedding,
            ):
                return self._runtime.embed(request)

    def ensure_model(self, model_ref: str) -> None:
        """Serialize provider artifact installation with runtime operations."""

        with self._lock:
            if self._loader is not None:
                self._loader.ensure_model(model_ref)

    def prewarm(self, model_ref: str, keep_alive: str = "10m") -> None:
        """Serialize speculative loads and reconcile known catalog residency."""

        with self._lock:
            if self._loader is not None:
                self._loader.ensure_model(model_ref)
            self._runtime.prewarm(model_ref, keep_alive)
            if self._catalog.get(model_ref) is not None:
                self._refresh(self._now())

    def unload(self, model_ref: str) -> None:
        """Unload only through confirmed eviction when the model is governed."""

        with self._lock:
            if not self._eviction_allowed:
                raise ModelResidencyAdmissionError(
                    "external runtime does not grant model eviction authority"
                )
            entry = self._catalog.get(model_ref)
            if entry is None:
                self._runtime.unload(model_ref)
                return
            catalog = self._refresh(self._now())
            record = catalog.require(self._expert_id(model_ref))
            if record.state is ExpertResidencyState.COLD:
                return
            if record.state is not ExpertResidencyState.WARM:
                raise ModelResidencyAdmissionError(
                    "only an unleased warm model can be unloaded"
                )
            self._execute_evictions((record.identity.expert_id,), catalog)

    def loaded_models(self):
        """Expose one serialized provider observation to runtime consumers."""

        with self._lock:
            return self._runtime.loaded_models()

    def capacity_for_selection(self) -> HostCapacity:
        with self._lock:
            capacity = self._capacity()
            catalog = self._refresh(self._now())
            if not self._eviction_allowed:
                return capacity
            host = 0
            vram = 0
            for record in catalog.records:
                if record.state is not ExpertResidencyState.WARM:
                    continue
                accelerator = record.accelerator_bytes or 0
                resident = record.resident_bytes or self._declared_bytes(
                    record.identity.runtime_artifact_id,
                )
                host += max(0, resident - accelerator)
                vram += accelerator
            return replace(
                capacity,
                reclaimable_host_bytes=host,
                reclaimable_vram_bytes=vram,
            )

    def resident_models(self) -> tuple[str, ...]:
        with self._lock:
            catalog = self._refresh(self._now())
            return tuple(
                record.identity.runtime_artifact_id for record in catalog.records
                if record.state in {
                    ExpertResidencyState.WARM,
                    ExpertResidencyState.ACTIVE,
                }
            )

    @contextmanager
    def session(
        self,
        request_id: str,
        model_ref: str,
        context_tokens: int,
        maximum_output_tokens: int,
    ) -> Iterator[None]:
        with self._lock:
            if self._loader is not None:
                self._loader.ensure_model(model_ref)
            expert_id = self._expert_id(model_ref)
            context = self._context_estimate(
                request_id, expert_id, model_ref,
                context_tokens, maximum_output_tokens,
            )
            with self._admitted_session(
                request_id, expert_id, model_ref, context,
            ):
                yield

    @contextmanager
    def _admitted_session(
        self, request_id: str, expert_id: str, model_ref: str, context,
        *, prewarmer: Callable[[str, str], None] | None = None,
    ) -> Iterator[None]:
        with self._lock:
            lease_id = None
            try:
                instant = self._now()
                capacity = self._capacity()
                catalog = self._refresh(instant)
                record = catalog.require(expert_id)
                if record.state is ExpertResidencyState.ACTIVE:
                    raise ModelResidencyAdmissionError(
                        "selected model already has an active durable lease"
                    )
                decision = DeterministicAdmissionPolicy().decide(
                    f"admission-{uuid4()}",
                    self._admission_request(
                        request_id, expert_id, model_ref, capacity, catalog,
                        context,
                    ),
                )
                if decision.status is not AdmissionStatus.ADMITTED:
                    raise ModelResidencyAdmissionError(
                        "model admission rejected: " + ",".join(decision.reason_codes)
                    )
                catalog = self._execute_evictions(
                    decision.eviction_expert_ids, catalog,
                )
                record = catalog.require(expert_id)
                if record.state is ExpertResidencyState.COLD:
                    (prewarmer or self._runtime.prewarm)(model_ref, "10m")
                    catalog = self._service.reconcile(
                        self._runtime.loaded_models(), self._now(), catalog.revision,
                    )
                lease_id = f"lease-{uuid4()}"
                acquired = self._now()
                catalog = self._service.acquire(
                    expert_id,
                    ResidencyLease(
                        lease_id, request_id, acquired,
                        acquired + _LEASE_DURATION,
                    ),
                    catalog.revision,
                )
                yield
            finally:
                if lease_id is not None:
                    current = self._repository.read()
                    record = current.require(expert_id)
                    if any(
                        item.lease_id == lease_id for item in record.active_leases
                    ):
                        self._service.release(
                            expert_id, lease_id, self._now(), current.revision,
                        )

    def _refresh(self, instant: datetime, loaded_models=None):
        current = self._repository.read()
        current = self._service.expire_leases(instant, current.revision)
        current = self._service.synchronize(
            self._identities(), instant, current.revision,
        )
        return self._service.reconcile(
            (
                self._runtime.loaded_models()
                if loaded_models is None
                else loaded_models
            ),
            instant,
            current.revision,
        )

    def _execute_evictions(self, expert_ids, catalog):
        if expert_ids and not self._eviction_allowed:
            raise ModelResidencyAdmissionError(
                "external runtime does not grant model eviction authority"
            )
        for expert_id in expert_ids:
            instant = self._now()
            catalog = self._eviction.evict(
                expert_id, f"eviction-{uuid4()}", instant, instant,
                catalog.revision,
            )
        return catalog

    def _admission_request(
        self, request_id, expert_id, model_ref, capacity, catalog, context,
    ):
        entry = self._require_entry(model_ref)
        record = catalog.require(expert_id)
        candidates = tuple(
            EvictionCandidate(
                item.identity.expert_id,
                item.state,
                self._host_reclaimable(item),
                self._retention_priority(item.identity.runtime_artifact_id),
                item.transitioned_at,
            )
            for item in catalog.records
            if item.identity.expert_id != expert_id and self._eviction_allowed
        )
        degraded = bool(_DEGRADED_CAPACITY_REASONS & set(capacity.reason_codes))
        return AdmissionRequest(
            request_id,
            f"live-capacity-{uuid4()}",
            ObservationStatus.DEGRADED if degraded else ObservationStatus.COMPLETE,
            not degraded,
            capacity.schedulable_host_bytes,
            catalog.catalog_id,
            catalog.revision,
            expert_id,
            record.state,
            ResidentWeightEstimate(
                expert_id, model_ref, entry.estimated_resident_bytes,
                WeightEstimateSource.DECLARED_CONSERVATIVE,
                "signed runtime model catalog estimated_resident_bytes",
            ),
            context.estimate_id,
            context.total_context_bytes,
            True,
            candidates,
        )

    def _context_estimate(
        self, request_id, expert_id, model_ref, context_tokens, output_tokens,
    ):
        if output_tokens <= 0 or context_tokens <= output_tokens:
            raise ModelResidencyAdmissionError(
                "context capacity must exceed the reserved output"
            )
        entry = self._require_entry(model_ref)
        profile_id = self._profile_id(model_ref, "generation")
        profile = self._profiles.observe(OllamaContextProfilePolicy(
            profile_id,
            expert_id,
            model_ref,
            ContextMemoryStrategy.AUTOREGRESSIVE_KV,
            entry.max_context_tokens,
        ))
        if context_tokens > profile.maximum_context_tokens:
            raise ModelResidencyAdmissionError(
                "requested context exceeds observed model capacity"
            )
        input_tokens = context_tokens - output_tokens
        reservation = ContextMemoryReservation(
            f"context-reservation-{request_id}",
            profile.profile_id,
            input_tokens,
            output_tokens,
        )
        return ContextMemoryEstimator().estimate(
            f"context-estimate-{uuid4()}", profile, reservation,
        )

    def _embedding_context_estimate(
        self, request_id, expert_id, model_ref, inputs,
    ):
        entry = self._require_entry(model_ref)
        profile = self._profiles.observe(OllamaContextProfilePolicy(
            self._profile_id(model_ref, "embedding"),
            expert_id,
            model_ref,
            ContextMemoryStrategy.ENCODER_ACTIVATION_BOUND,
            entry.max_context_tokens,
        ))
        input_tokens = max(len(value.encode("utf-8")) for value in inputs)
        if input_tokens > profile.maximum_context_tokens:
            raise ModelResidencyAdmissionError(
                "embedding input exceeds observed model capacity"
            )
        reservation = ContextMemoryReservation(
            f"context-reservation-{request_id}",
            profile.profile_id,
            input_tokens,
            0,
            len(inputs),
        )
        return ContextMemoryEstimator().estimate(
            f"context-estimate-{uuid4()}", profile, reservation,
        )

    @staticmethod
    def _profile_id(model_ref: str, workload: str) -> str:
        digest = hashlib.sha256(f"{workload}:{model_ref}".encode()).hexdigest()[:16]
        return f"context.{workload}.{digest}"

    def _identities(self) -> tuple[ExpertResidencyIdentity, ...]:
        provenance: dict[str, list[str]] = {}
        for item in self._catalog.provenances():
            provenance.setdefault(item.model_ref, []).append(item.expert_id)
        identities = tuple(
            ExpertResidencyIdentity(
                (
                    provenance[entry.model_ref][0]
                    if len(provenance.get(entry.model_ref, ())) == 1
                    else _fallback_expert_id(entry.model_ref)
                ),
                entry.model_ref,
            )
            for entry in self._catalog.entries()
        )
        if not identities:
            raise ModelResidencyAdmissionError("runtime catalog has no local models")
        return identities

    def _expert_id(self, model_ref: str) -> str:
        return next(
            item.expert_id for item in self._identities()
            if item.runtime_artifact_id == model_ref
        )

    def _require_entry(self, model_ref: str):
        entry = self._catalog.get(model_ref)
        if entry is None:
            raise ModelResidencyAdmissionError("selected model is outside the catalog")
        return entry

    def _declared_bytes(self, model_ref: str) -> int:
        entry = self._catalog.get(model_ref)
        return 0 if entry is None else entry.estimated_resident_bytes

    def _host_reclaimable(self, record) -> int:
        accelerator = record.accelerator_bytes or 0
        resident = record.resident_bytes or self._declared_bytes(
            record.identity.runtime_artifact_id,
        )
        return max(0, resident - accelerator)

    def _retention_priority(self, model_ref: str) -> int:
        entry = self._catalog.get(model_ref)
        if entry is None:
            return 0
        return {
            "embedding": 30,
            "economical": 20,
            "specialist": 10,
            "escalation": 0,
        }[entry.tier]


def _fallback_expert_id(model_ref: str) -> str:
    digest = hashlib.sha256(model_ref.encode()).hexdigest()[:24]
    return f"expert.runtime.{digest}"
