"""Observe provider-neutral context profiles from Ollama model metadata."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from fam_os.adapters.ollama.settings import OllamaSettings
from fam_os.adapters.ollama.transport import JsonTransport
from fam_os.scheduler.context_contracts import (
    ContextMemoryModelProfile,
    ContextMemoryStrategy,
    ContextProfileSource,
)


@dataclass(frozen=True, slots=True)
class OllamaContextProfilePolicy:
    profile_id: str
    expert_id: str
    model_ref: str
    strategy: ContextMemoryStrategy
    declared_maximum_context_tokens: int
    scalar_bytes: int = 2
    fixed_runtime_overhead_bytes: int = 256 * 1024**2
    per_sequence_workspace_bytes: int = 64 * 1024**2
    safety_margin_basis_points: int = 2_500

    def __post_init__(self) -> None:
        if any(not value.strip() for value in (self.profile_id, self.expert_id, self.model_ref)):
            raise ValueError("Ollama context profile identity must not be empty")
        if self.declared_maximum_context_tokens <= 0 or self.scalar_bytes <= 0:
            raise ValueError("Ollama context profile dimensions must be positive")
        if self.fixed_runtime_overhead_bytes < 0 or self.per_sequence_workspace_bytes < 0:
            raise ValueError("Ollama context profile overhead cannot be negative")
        if not 0 <= self.safety_margin_basis_points <= 10_000:
            raise ValueError("Ollama context safety margin is invalid")


class OllamaContextProfileObserver:
    def __init__(
        self, settings: OllamaSettings, transport: JsonTransport
    ) -> None:
        self._settings = settings
        self._transport = transport

    def observe(self, policy: OllamaContextProfilePolicy) -> ContextMemoryModelProfile:
        response = self._transport.request(
            "POST", self._settings.endpoint("/api/show"),
            {"model": policy.model_ref}, self._settings.timeout_seconds,
        )
        return parse_ollama_context_profile(response, policy)


def parse_ollama_context_profile(
    response: Mapping[str, object], policy: OllamaContextProfilePolicy
) -> ContextMemoryModelProfile:
    info = response.get("model_info")
    if not isinstance(info, Mapping):
        raise ValueError("Ollama show response lacks model_info")
    architecture = _text(info, "general.architecture")
    prefix = f"{architecture}."
    assumptions = ["runtime_overhead.policy_bound"]
    layers = _positive_int(info, prefix + "block_count")
    embedding = _positive_int(info, prefix + "embedding_length")
    heads = _attention_heads(info, prefix, policy.strategy, assumptions)
    observed_maximum = _positive_int(info, prefix + "context_length")
    if observed_maximum > policy.declared_maximum_context_tokens:
        assumptions.append("context_capacity.clamped_to_declared_package")
    maximum = min(observed_maximum, policy.declared_maximum_context_tokens)
    kv_heads, key_dimension, value_dimension = _strategy_dimensions(
        info, prefix, policy.strategy, embedding, heads, assumptions
    )
    if policy.strategy is ContextMemoryStrategy.AUTOREGRESSIVE_KV:
        assumptions.extend((
            "kv_cache.scalar_bytes_policy",
            "full_context_cache.no_sliding_window_discount",
        ))
    return ContextMemoryModelProfile(
        policy.profile_id, policy.expert_id, policy.model_ref, architecture,
        policy.strategy, maximum, layers, embedding, heads,
        kv_heads, key_dimension, value_dimension, policy.scalar_bytes,
        policy.fixed_runtime_overhead_bytes, policy.per_sequence_workspace_bytes,
        policy.safety_margin_basis_points, ContextProfileSource.OBSERVED_METADATA,
        tuple(assumptions),
    )


def _strategy_dimensions(info, prefix, strategy, embedding, heads, assumptions):
    if strategy is ContextMemoryStrategy.ENCODER_ACTIVATION_BOUND:
        assumptions.append("encoder_attention.full_matrix_bound")
        return None, None, None
    kv_heads = _optional_positive_int(info, prefix + "attention.head_count_kv")
    if kv_heads is None:
        kv_heads = heads
        assumptions.append("kv_heads.fallback_attention_heads")
    key = _optional_positive_int(info, prefix + "attention.key_length")
    if key is None:
        key = _dimension_from_embedding(embedding, heads, "key", assumptions)
    value = _optional_positive_int(info, prefix + "attention.value_length")
    if value is None:
        value = _dimension_from_embedding(embedding, heads, "value", assumptions)
    return kv_heads, key, value


def _attention_heads(info, prefix, strategy, assumptions):
    heads = _optional_positive_int(info, prefix + "attention.head_count")
    if heads is not None:
        return heads
    kv_heads = _optional_positive_int(info, prefix + "attention.head_count_kv")
    if strategy is ContextMemoryStrategy.AUTOREGRESSIVE_KV and kv_heads is not None:
        assumptions.append("attention_heads.fallback_kv_heads")
        return kv_heads
    raise ValueError(f"Ollama model metadata lacks {prefix}attention.head_count")


def _dimension_from_embedding(embedding, heads, name, assumptions):
    if embedding % heads:
        raise ValueError(f"cannot derive {name} dimension from Ollama metadata")
    assumptions.append(f"{name}_dimension.derived_embedding_per_head")
    return embedding // heads


def _positive_int(values, key):
    value = _optional_positive_int(values, key)
    if value is None:
        raise ValueError(f"Ollama model metadata lacks {key}")
    return value


def _optional_positive_int(values, key):
    value = values.get(key)
    if value is None:
        return None
    if type(value) is not int or value <= 0:
        raise ValueError(f"Ollama model metadata has invalid {key}")
    return value


def _text(values, key):
    value = values.get(key)
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Ollama model metadata lacks {key}")
    return value
