"""Provider-neutral context-memory profile, reservation, and estimate contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum


CONTEXT_MEMORY_CONTRACT_VERSION = "fam.scheduler.context-memory/v1alpha1"


class ContextMemoryStrategy(StrEnum):
    AUTOREGRESSIVE_KV = "autoregressive_kv"
    ENCODER_ACTIVATION_BOUND = "encoder_activation_bound"


class ContextProfileSource(StrEnum):
    OBSERVED_METADATA = "observed_metadata"
    CALIBRATED = "calibrated"
    DECLARED_CONSERVATIVE = "declared_conservative"


@dataclass(frozen=True, slots=True)
class ContextMemoryModelProfile:
    profile_id: str
    expert_id: str
    runtime_artifact_id: str
    architecture: str
    strategy: ContextMemoryStrategy
    maximum_context_tokens: int
    layer_count: int
    embedding_dimension: int
    attention_head_count: int
    key_value_head_count: int | None
    key_dimension: int | None
    value_dimension: int | None
    scalar_bytes: int
    fixed_runtime_overhead_bytes: int
    per_sequence_workspace_bytes: int
    safety_margin_basis_points: int
    source: ContextProfileSource
    assumption_codes: tuple[str, ...] = ()
    contract_version: str = CONTEXT_MEMORY_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != CONTEXT_MEMORY_CONTRACT_VERSION:
            raise ValueError("unsupported context-memory contract_version")
        for name in ("profile_id", "expert_id", "runtime_artifact_id", "architecture"):
            _require_text(getattr(self, name), name)
        positive = (
            self.maximum_context_tokens, self.layer_count,
            self.embedding_dimension, self.attention_head_count, self.scalar_bytes,
        )
        if any(value <= 0 for value in positive):
            raise ValueError("context profile dimensions must be positive")
        optional = (self.key_value_head_count, self.key_dimension, self.value_dimension)
        if any(value is not None and value <= 0 for value in optional):
            raise ValueError("optional context profile dimensions must be positive")
        if self.fixed_runtime_overhead_bytes < 0 or self.per_sequence_workspace_bytes < 0:
            raise ValueError("context profile overhead cannot be negative")
        if not 0 <= self.safety_margin_basis_points <= 10_000:
            raise ValueError("context safety margin must be between zero and 10000 bps")
        if len(set(self.assumption_codes)) != len(self.assumption_codes):
            raise ValueError("context assumption codes must be unique")
        if any(not code.strip() for code in self.assumption_codes):
            raise ValueError("context assumption codes must not be empty")
        self._validate_strategy_dimensions()

    def _validate_strategy_dimensions(self) -> None:
        dimensions = (
            self.key_value_head_count, self.key_dimension, self.value_dimension
        )
        if self.strategy is ContextMemoryStrategy.AUTOREGRESSIVE_KV:
            if any(value is None for value in dimensions):
                raise ValueError("autoregressive context profile requires KV dimensions")
        elif any(value is not None for value in dimensions):
            raise ValueError("encoder context profile must not claim persistent KV dimensions")


@dataclass(frozen=True, slots=True)
class ContextMemoryReservation:
    reservation_id: str
    profile_id: str
    input_token_upper_bound: int
    output_token_reservation: int
    concurrent_sequences: int = 1
    contract_version: str = CONTEXT_MEMORY_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != CONTEXT_MEMORY_CONTRACT_VERSION:
            raise ValueError("unsupported context-memory contract_version")
        _require_text(self.reservation_id, "reservation_id")
        _require_text(self.profile_id, "profile_id")
        if self.input_token_upper_bound <= 0 or self.output_token_reservation < 0:
            raise ValueError("context token reservation is invalid")
        if self.concurrent_sequences <= 0:
            raise ValueError("concurrent_sequences must be positive")


@dataclass(frozen=True, slots=True)
class ContextMemoryEstimate:
    estimate_id: str
    reservation_id: str
    profile_id: str
    strategy: ContextMemoryStrategy
    tokens_per_sequence: int
    concurrent_sequences: int
    persistent_context_bytes: int
    reserved_growth_bytes: int
    attention_workspace_bytes: int
    sequence_workspace_bytes: int
    fixed_runtime_overhead_bytes: int
    subtotal_bytes: int
    safety_margin_bytes: int
    total_context_bytes: int
    model_resident_bytes_excluded: bool
    assumption_codes: tuple[str, ...]
    contract_version: str = CONTEXT_MEMORY_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != CONTEXT_MEMORY_CONTRACT_VERSION:
            raise ValueError("unsupported context-memory contract_version")
        for name in ("estimate_id", "reservation_id", "profile_id"):
            _require_text(getattr(self, name), name)
        if self.tokens_per_sequence <= 0 or self.concurrent_sequences <= 0:
            raise ValueError("context estimate token dimensions must be positive")
        parts = (
            self.persistent_context_bytes, self.reserved_growth_bytes,
            self.attention_workspace_bytes, self.sequence_workspace_bytes,
            self.fixed_runtime_overhead_bytes,
        )
        if any(value < 0 for value in parts) or self.safety_margin_bytes < 0:
            raise ValueError("context estimate bytes cannot be negative")
        if self.subtotal_bytes != sum(parts):
            raise ValueError("context estimate subtotal is inconsistent")
        if self.total_context_bytes != self.subtotal_bytes + self.safety_margin_bytes:
            raise ValueError("context estimate total is inconsistent")
        if not self.model_resident_bytes_excluded:
            raise ValueError("context estimate must exclude model resident bytes")
        if len(set(self.assumption_codes)) != len(self.assumption_codes):
            raise ValueError("context estimate assumption codes must be unique")


def _require_text(value: str, name: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} must not be empty")
