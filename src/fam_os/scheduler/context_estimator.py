"""Pure provider-neutral context-memory estimation."""

from dataclasses import dataclass

from fam_os.scheduler.context_contracts import (
    ContextMemoryEstimate,
    ContextMemoryModelProfile,
    ContextMemoryReservation,
    ContextMemoryStrategy,
)


@dataclass(frozen=True, slots=True)
class ContextMemoryEstimator:
    def estimate(
        self,
        estimate_id: str,
        profile: ContextMemoryModelProfile,
        reservation: ContextMemoryReservation,
    ) -> ContextMemoryEstimate:
        _validate_reservation(profile, reservation)
        if profile.strategy is ContextMemoryStrategy.AUTOREGRESSIVE_KV:
            persistent, growth, attention = _autoregressive_parts(profile, reservation)
        else:
            persistent, growth, attention = _encoder_parts(profile, reservation)
        sequence_workspace = (
            profile.per_sequence_workspace_bytes * reservation.concurrent_sequences
        )
        parts = (
            persistent, growth, attention, sequence_workspace,
            profile.fixed_runtime_overhead_bytes,
        )
        subtotal = sum(parts)
        margin = _basis_point_ceiling(subtotal, profile.safety_margin_basis_points)
        return ContextMemoryEstimate(
            estimate_id, reservation.reservation_id, profile.profile_id,
            profile.strategy,
            reservation.input_token_upper_bound + reservation.output_token_reservation,
            reservation.concurrent_sequences,
            persistent, growth, attention, sequence_workspace,
            profile.fixed_runtime_overhead_bytes, subtotal, margin,
            subtotal + margin, True, profile.assumption_codes,
        )


def _validate_reservation(profile, reservation):
    if reservation.profile_id != profile.profile_id:
        raise ValueError("context reservation references another profile")
    tokens = reservation.input_token_upper_bound + reservation.output_token_reservation
    if tokens > profile.maximum_context_tokens:
        raise ValueError("context reservation exceeds model context capacity")
    if (
        profile.strategy is ContextMemoryStrategy.ENCODER_ACTIVATION_BOUND
        and reservation.output_token_reservation != 0
    ):
        raise ValueError("encoder context reservation cannot reserve output tokens")


def _autoregressive_parts(profile, reservation):
    heads = profile.key_value_head_count
    key_per_token = profile.layer_count * heads * profile.key_dimension * profile.scalar_bytes
    value_per_token = profile.layer_count * heads * profile.value_dimension * profile.scalar_bytes
    sequences = reservation.concurrent_sequences
    persistent = reservation.input_token_upper_bound * (key_per_token + value_per_token) * sequences
    growth = reservation.output_token_reservation * (key_per_token + value_per_token) * sequences
    return persistent, growth, 0


def _encoder_parts(profile, reservation):
    tokens = reservation.input_token_upper_bound
    sequences = reservation.concurrent_sequences
    hidden = tokens * profile.embedding_dimension * profile.scalar_bytes * 3 * sequences
    attention = (
        profile.attention_head_count * tokens * tokens * profile.scalar_bytes * sequences
    )
    return hidden, 0, attention


def _basis_point_ceiling(value: int, basis_points: int) -> int:
    return (value * basis_points + 9_999) // 10_000
