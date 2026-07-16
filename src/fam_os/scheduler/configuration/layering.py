"""Deterministic profile selection and monotonic restriction application."""

from __future__ import annotations

from dataclasses import fields, replace
from datetime import datetime

from fam_os.scheduler.configuration.audit import (
    ConfigurationDecision,
    ConfigurationDecisionKind,
    ConfigurationLayer,
)
from fam_os.scheduler.configuration.policy import (
    ResourcePolicy,
    ResourceRestriction,
    SchedulerDefaults,
    SessionResourceOverride,
    UserResourcePolicy,
    ValidationProfileConfiguration,
)
from fam_os.scheduler.resources import ValidationProfileRef


def resolve_policy(
    defaults: SchedulerDefaults,
    profile: ValidationProfileConfiguration | None,
    user_policy: UserResourcePolicy | None,
    session_override: SessionResourceOverride | None,
    instant: datetime,
) -> tuple[ValidationProfileRef, ResourcePolicy, tuple[ConfigurationDecision, ...]]:
    selected_profile = defaults.default_profile
    policy = defaults.policy
    audit = [_selection(defaults.configuration_id, selected_profile.profile_id)]
    if profile is not None:
        selected_profile = profile.profile
        policy = profile.policy
        audit.append(_profile_selection(profile))
    if user_policy is not None:
        policy, entries = _apply_restriction(
            policy, user_policy.restriction, ConfigurationLayer.USER_POLICY, user_policy.policy_id
        )
        audit.extend(entries)
    if session_override is not None:
        if session_override.active_at(instant):
            policy, entries = _apply_restriction(
                policy,
                session_override.restriction,
                ConfigurationLayer.SESSION_OVERRIDE,
                session_override.override_id,
            )
            audit.extend(entries)
        else:
            audit.append(_expired_session(session_override.override_id))
    return selected_profile, policy, tuple(audit)


def _apply_restriction(
    policy: ResourcePolicy,
    restriction: ResourceRestriction,
    layer: ConfigurationLayer,
    source_id: str,
) -> tuple[ResourcePolicy, tuple[ConfigurationDecision, ...]]:
    updates: dict[str, object] = {}
    decisions: list[ConfigurationDecision] = []
    mapping = _restriction_mapping()
    for field in fields(restriction):
        requested = getattr(restriction, field.name)
        if requested is None:
            continue
        target, mode = mapping[field.name]
        previous = getattr(policy, target)
        effective = _restricted_value(previous, requested, mode)
        updates[target] = effective
        kind = ConfigurationDecisionKind.RESTRICTED if effective != previous else ConfigurationDecisionKind.IGNORED
        decisions.append(_decision(layer, source_id, target, requested, effective, kind))
    return replace(policy, **updates), tuple(decisions)


def _restricted_value(previous: object, requested: object, mode: str) -> object:
    if mode == "allow":
        return bool(previous) and bool(requested)
    if previous is None:
        return requested
    if mode == "minimum":
        return max(previous, requested)
    return min(previous, requested)


def _restriction_mapping() -> dict[str, tuple[str, str]]:
    return {
        "max_cpu_cores": ("max_cpu_cores", "maximum"),
        "max_memory_bytes": ("max_memory_bytes", "maximum"),
        "minimum_memory_headroom_bytes": ("memory_headroom_bytes", "minimum"),
        "max_swap_bytes": ("max_swap_bytes", "maximum"),
        "accelerator_allowed": ("accelerator_allowed", "allow"),
        "max_accelerator_memory_bytes": ("max_accelerator_memory_bytes", "maximum"),
        "minimum_accelerator_reserve_bytes": ("accelerator_reserved_memory_bytes", "minimum"),
        "max_storage_cache_bytes": ("max_storage_cache_bytes", "maximum"),
        "minimum_storage_reserve_bytes": ("storage_reserved_free_bytes", "minimum"),
        "max_storage_read_bytes_per_second": ("storage_read_limit_bytes_per_second", "maximum"),
        "max_storage_write_bytes_per_second": ("storage_write_limit_bytes_per_second", "maximum"),
    }


def _decision(
    layer: ConfigurationLayer,
    source_id: str,
    setting: str,
    requested: object,
    effective: object,
    kind: ConfigurationDecisionKind,
) -> ConfigurationDecision:
    return ConfigurationDecision(
        layer,
        source_id,
        setting,
        str(requested),
        str(effective),
        kind,
        "restriction_applied" if kind is ConfigurationDecisionKind.RESTRICTED else "no_authority_expansion",
    )


def _selection(source_id: str, profile_id: str) -> ConfigurationDecision:
    return ConfigurationDecision(
        ConfigurationLayer.DEFAULTS,
        source_id,
        "validation_profile",
        profile_id,
        profile_id,
        ConfigurationDecisionKind.SELECTED,
        "safe_default_selected",
    )


def _profile_selection(profile: ValidationProfileConfiguration) -> ConfigurationDecision:
    return ConfigurationDecision(
        ConfigurationLayer.VALIDATION_PROFILE,
        profile.configuration_id,
        "validation_profile",
        profile.profile.profile_id,
        profile.profile.profile_id,
        ConfigurationDecisionKind.OVERRIDDEN,
        "trusted_profile_selected",
    )


def _expired_session(source_id: str) -> ConfigurationDecision:
    return ConfigurationDecision(
        ConfigurationLayer.SESSION_OVERRIDE,
        source_id,
        "session_override",
        "inactive",
        "ignored",
        ConfigurationDecisionKind.IGNORED,
        "session_override_inactive",
    )
