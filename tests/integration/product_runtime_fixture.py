"""Protocol-complete provider fixtures for product composition tests."""

from fam_os.core.ports.inference import LoadedModel
from fam_os.scheduler import (
    ContextMemoryModelProfile,
    ContextMemoryStrategy,
    ContextProfileSource,
)


class ResidentRuntimeFixture:
    """Supply observable prewarm/unload semantics to specialized fake runtimes."""

    def __init__(self) -> None:
        self._resident = {}

    def prewarm(self, model_ref, keep_alive="10m"):
        self._resident[model_ref] = LoadedModel(
            model_ref, 1024**3, 0, 8_192,
        )

    def prewarm_embedding(self, model_ref, keep_alive="10m"):
        self.prewarm(model_ref, keep_alive)

    def unload(self, model_ref):
        self._resident.pop(model_ref, None)

    def loaded_models(self):
        return tuple(self._resident[key] for key in sorted(self._resident))


class ContextProfileFixture:
    """Return deterministic observed metadata without an Ollama HTTP process."""

    def observe(self, policy):
        encoder = policy.strategy is ContextMemoryStrategy.ENCODER_ACTIVATION_BOUND
        return ContextMemoryModelProfile(
            policy.profile_id,
            policy.expert_id,
            policy.model_ref,
            "test",
            policy.strategy,
            policy.declared_maximum_context_tokens,
            2,
            64,
            4,
            None if encoder else 2,
            None if encoder else 16,
            None if encoder else 16,
            2,
            1_000,
            100,
            0,
            ContextProfileSource.OBSERVED_METADATA,
            ("test.profile",),
        )
