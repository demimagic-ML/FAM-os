import tempfile
import threading
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path

from fam_os.adapters.filesystem.residency_state import JsonExpertResidencyRepository
from fam_os.core.ports.embedding import EmbeddingRequest, EmbeddingResponse
from fam_os.core.ports.inference import (
    InferenceMessage,
    InferenceRequest,
    InferenceResponse,
    LoadedModel,
    MessageRole,
)
from fam_os.core.production import ModelIntent, RuntimeModelEntry
from fam_os.core.production.model_catalog import (
    RuntimeModelCatalog,
    RuntimeModelProvenance,
)
from fam_os.core.production.model_selection import HostCapacity
from fam_os.product.model_residency import (
    ModelResidencyAdmissionError,
    ProductionModelResidency,
)
from fam_os.scheduler import (
    ContextMemoryModelProfile,
    ContextMemoryStrategy,
    ContextProfileSource,
    ExpertResidencyService,
    ExpertResidencyState,
    ResidencyLease,
    ResidencyTransitionReason,
)
from fam_os.telemetry.contracts import InferenceMetrics


GIB = 1024**3
NOW = datetime(2026, 7, 18, 8, 0, tzinfo=UTC)


class FakeProfileObserver:
    def __init__(self) -> None:
        self.policies = []
        self.on_observe = None

    def observe(self, policy):
        if self.on_observe is not None:
            self.on_observe(policy)
        self.policies.append(policy)
        encoder = policy.strategy is ContextMemoryStrategy.ENCODER_ACTIVATION_BOUND
        return ContextMemoryModelProfile(
            profile_id=policy.profile_id,
            expert_id=policy.expert_id,
            runtime_artifact_id=policy.model_ref,
            architecture="test",
            strategy=policy.strategy,
            maximum_context_tokens=policy.declared_maximum_context_tokens,
            layer_count=2,
            embedding_dimension=64,
            attention_head_count=4,
            key_value_head_count=None if encoder else 2,
            key_dimension=None if encoder else 16,
            value_dimension=None if encoder else 16,
            scalar_bytes=2,
            fixed_runtime_overhead_bytes=1_000,
            per_sequence_workspace_bytes=100,
            safety_margin_basis_points=0,
            source=ContextProfileSource.OBSERVED_METADATA,
            assumption_codes=("test.profile",),
        )


class FakeRuntime:
    def __init__(self, weights) -> None:
        self.weights = weights
        self.models = {}
        self.chat_calls = []
        self.embed_calls = []
        self.prewarmed = []
        self.embedding_prewarmed = []
        self.unloaded = []
        self.on_chat = None
        self.block_started = None
        self.block_release = None
        self.chat_failure = None

    def chat(self, request):
        self.chat_calls.append(request.model_ref)
        if self.on_chat is not None:
            self.on_chat()
        if self.block_started is not None:
            self.block_started.set()
            self.block_release.wait(5)
        if self.chat_failure is not None:
            raise self.chat_failure
        return InferenceResponse(
            f"answer:{request.model_ref}",
            InferenceMetrics(request.model_ref, 0.1, 0.0, 2, 1, 10.0),
        )

    def embed(self, request):
        self.embed_calls.append(request.model_ref)
        return EmbeddingResponse(
            request.model_ref,
            tuple((float(index), 1.0) for index, _ in enumerate(request.inputs)),
            sum(len(item) for item in request.inputs),
            0.1,
        )

    def unload(self, model_ref):
        self.unloaded.append(model_ref)
        self.models.pop(model_ref, None)

    def prewarm(self, model_ref, keep_alive="10m"):
        self.prewarmed.append((model_ref, keep_alive))
        self.models[model_ref] = LoadedModel(
            model_ref, self.weights.get(model_ref, GIB), 0, 2_048,
        )

    def prewarm_embedding(self, model_ref, keep_alive="10m"):
        self.embedding_prewarmed.append((model_ref, keep_alive))
        self.models[model_ref] = LoadedModel(
            model_ref, self.weights.get(model_ref, GIB), 0, 2_048,
        )

    def loaded_models(self):
        return tuple(self.models[key] for key in sorted(self.models))


class FakeLoader:
    def __init__(self) -> None:
        self.models = []

    def ensure_model(self, model_ref):
        self.models.append(model_ref)


class ProductModelResidencyTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.state_path = Path(self.temporary.name) / "residency.json"
        self.catalog = RuntimeModelCatalog((
            _entry("small:1", "economical", 2),
            _entry("strong:1", "escalation", 6),
            _entry("embed:1", "embedding", 1),
        ))
        self.runtime = FakeRuntime({
            "small:1": 2 * GIB,
            "strong:1": 6 * GIB,
            "embed:1": GIB,
        })
        self.loader = FakeLoader()
        self.profiles = FakeProfileObserver()

    def residency(
        self, *, available=20 * GIB, eviction_allowed=True,
    ) -> ProductionModelResidency:
        return ProductionModelResidency(
            self.state_path.absolute(),
            self.catalog,
            self.runtime,
            lambda: HostCapacity(available, reserved_host_bytes=0),
            self.loader,
            "http://unused.invalid",
            eviction_allowed=eviction_allowed,
            now=lambda: NOW,
            profile_observer=self.profiles,
        )

    def test_shared_model_uses_one_stable_runtime_residency_identity(self):
        entry = _entry("small:1", "economical", 2)
        self.catalog = RuntimeModelCatalog((entry,), (
            RuntimeModelProvenance(
                entry.model_ref, "expert.language", "language@1", "binding:1",
                entry.intents, entry.verifier_ids,
            ),
            RuntimeModelProvenance(
                entry.model_ref, "expert.retrieval", "retrieval@1", "binding:2",
                entry.intents, entry.verifier_ids,
            ),
        ))

        self.residency()

        snapshot = JsonExpertResidencyRepository(self.state_path.absolute()).read()
        self.assertEqual(1, len(snapshot.records))
        identity = snapshot.records[0].identity
        self.assertEqual(entry.model_ref, identity.runtime_artifact_id)
        self.assertTrue(identity.expert_id.startswith("expert.runtime."))

    def test_chat_loads_leases_and_releases_the_catalog_model(self):
        residency = self.residency()
        repository = JsonExpertResidencyRepository(self.state_path.absolute())
        observed_states = []
        self.profiles.on_observe = lambda _policy: self.assertIn(
            "small:1", self.loader.models,
        )
        self.runtime.on_chat = lambda: observed_states.append(
            next(
                item.state for item in repository.read().records
                if item.identity.runtime_artifact_id == "small:1"
            )
        )

        response = residency.chat_for_request("request-1", _request("small:1"))

        self.assertEqual(response.content, "answer:small:1")
        self.assertEqual(observed_states, [ExpertResidencyState.ACTIVE])
        record = next(
            item for item in repository.read().records
            if item.identity.runtime_artifact_id == "small:1"
        )
        self.assertEqual(record.state, ExpertResidencyState.WARM)
        self.assertEqual(record.active_leases, ())
        self.assertEqual(self.loader.models, ["small:1"])

    def test_failed_chat_still_releases_the_durable_lease(self):
        residency = self.residency()
        self.runtime.chat_failure = RuntimeError("provider failed")

        with self.assertRaisesRegex(RuntimeError, "provider failed"):
            residency.chat(_request("small:1"))

        record = next(
            item for item in JsonExpertResidencyRepository(
                self.state_path.absolute(),
            ).read().records
            if item.identity.runtime_artifact_id == "small:1"
        )
        self.assertEqual(record.state, ExpertResidencyState.WARM)
        self.assertEqual(record.active_leases, ())

    def test_concurrent_runtime_calls_are_serialized_across_models(self):
        residency = self.residency()
        self.runtime.block_started = threading.Event()
        self.runtime.block_release = threading.Event()
        errors = []

        first = threading.Thread(
            target=_capture, args=(errors, lambda: residency.chat(_request("small:1"))),
        )
        second = threading.Thread(
            target=_capture, args=(errors, lambda: residency.chat(_request("strong:1"))),
        )
        first.start()
        self.assertTrue(self.runtime.block_started.wait(2))
        second.start()
        self.assertEqual(self.runtime.chat_calls, ["small:1"])
        self.runtime.block_release.set()
        first.join(5)
        second.join(5)

        self.assertFalse(first.is_alive())
        self.assertFalse(second.is_alive())
        self.assertEqual(errors, [])
        self.assertEqual(self.runtime.chat_calls, ["small:1", "strong:1"])

    def test_embedding_uses_encoder_admission_and_releases_lease(self):
        residency = self.residency()
        self.profiles.on_observe = lambda _policy: self.assertIn(
            "embed:1", self.loader.models,
        )

        response = residency.embed(EmbeddingRequest("embed:1", ("one", "two")))

        self.assertEqual(len(response.vectors), 2)
        self.assertEqual(self.runtime.prewarmed, [])
        self.assertEqual(
            self.runtime.embedding_prewarmed, [("embed:1", "10m")],
        )
        self.assertEqual(
            self.profiles.policies[-1].strategy,
            ContextMemoryStrategy.ENCODER_ACTIVATION_BOUND,
        )
        record = next(
            item for item in JsonExpertResidencyRepository(
                self.state_path.absolute(),
            ).read().records
            if item.identity.runtime_artifact_id == "embed:1"
        )
        self.assertEqual(record.state, ExpertResidencyState.WARM)

    def test_managed_admission_evicts_only_confirmed_warm_model(self):
        self.runtime.prewarm("small:1")
        residency = self.residency(available=5 * GIB, eviction_allowed=True)
        initial = next(
            item for item in JsonExpertResidencyRepository(
                self.state_path.absolute(),
            ).read().records
            if item.identity.runtime_artifact_id == "small:1"
        )
        self.assertEqual(initial.state, ExpertResidencyState.WARM)
        self.assertEqual(initial.record_revision, 0)
        self.assertEqual(
            initial.transition_reason, ResidencyTransitionReason.PROVIDER_LOADED,
        )

        residency.chat(_request("strong:1"))

        self.assertEqual(self.runtime.unloaded, ["small:1"])
        self.assertEqual(residency.resident_models(), ("strong:1",))

    def test_external_runtime_rejects_shortfall_without_unloading(self):
        self.runtime.prewarm("small:1")
        residency = self.residency(available=5 * GIB, eviction_allowed=False)

        with self.assertRaisesRegex(
            ModelResidencyAdmissionError, "insufficient_after_safe_eviction",
        ):
            residency.chat(_request("strong:1"))

        self.assertEqual(self.runtime.unloaded, [])
        self.assertIn("small:1", self.runtime.models)

    def test_restart_recovers_unexpired_process_lease_before_reconcile(self):
        residency = self.residency()
        residency.prewarm("small:1")
        repository = JsonExpertResidencyRepository(self.state_path.absolute())
        service = ExpertResidencyService(repository)
        current = repository.read()
        record = next(
            item for item in current.records
            if item.identity.runtime_artifact_id == "small:1"
        )
        service.acquire(
            record.identity.expert_id,
            ResidencyLease(
                "lease-before-restart", "dead-request", NOW,
                NOW + timedelta(minutes=10),
            ),
            current.revision,
        )

        self.residency()

        recovered = repository.read().require(record.identity.expert_id)
        self.assertEqual(recovered.state, ExpertResidencyState.WARM)
        self.assertEqual(recovered.active_leases, ())
        self.assertIn(
            recovered.transition_reason,
            {
                ResidencyTransitionReason.PROCESS_LEASES_RECOVERED,
                ResidencyTransitionReason.PROVIDER_REFRESHED,
            },
        )

    def test_generation_context_must_leave_room_for_reserved_output(self):
        residency = self.residency()
        with self.assertRaisesRegex(
            ModelResidencyAdmissionError, "exceed the reserved output",
        ):
            residency.chat(_request("small:1", context=128, output=128))


def _entry(model_ref, tier, gib):
    return RuntimeModelEntry(
        model_ref, tier, (ModelIntent.CODE,), gib * GIB, 8_192, "0" * 64,
    )


def _request(model_ref, *, context=2_048, output=128):
    return InferenceRequest(
        model_ref,
        (InferenceMessage(MessageRole.USER, "test"),),
        context,
        output,
    )


def _capture(errors, operation):
    try:
        operation()
    except Exception as error:  # pragma: no cover - assertion reports details
        errors.append(error)


if __name__ == "__main__":
    unittest.main()
