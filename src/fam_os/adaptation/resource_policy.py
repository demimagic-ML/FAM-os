"""Battery, thermal, foreground-load, and idle adaptation policy."""

from dataclasses import dataclass

from fam_os.experts import ExpertTier

RESOURCE_ADAPTATION_CONTRACT_VERSION = "fam.adaptation.resource-policy/v1alpha1"


@dataclass(frozen=True, slots=True)
class OperatingState:
    battery_percent: float | None
    charging: bool | None
    thermal_celsius: float
    foreground_load: float
    idle_seconds: float

    def __post_init__(self) -> None:
        if self.battery_percent is not None and not 0 <= self.battery_percent <= 100:
            raise ValueError("battery percent must be normalized")
        if self.thermal_celsius < -20 or not 0 <= self.foreground_load <= 1 or self.idle_seconds < 0:
            raise ValueError("operating-state values are invalid")


@dataclass(frozen=True, slots=True)
class OperatingPolicyDecision:
    maximum_expert_tier: ExpertTier
    speculative_prefetch_allowed: bool
    background_adaptation_allowed: bool
    reason_codes: tuple[str, ...]
    contract_version: str = RESOURCE_ADAPTATION_CONTRACT_VERSION


class OperatingStatePolicy:
    def decide(self, state: OperatingState) -> OperatingPolicyDecision:
        tier, prefetch, background, reasons = ExpertTier.ESCALATION, True, False, []
        if state.battery_percent is not None and state.battery_percent < 20 and not state.charging:
            tier, prefetch = ExpertTier.ECONOMICAL, False
            reasons.append("battery.conserve")
        if state.thermal_celsius >= 85:
            tier, prefetch = ExpertTier.MICRO, False
            reasons.append("thermal.protect")
        if state.foreground_load >= .8:
            prefetch = False
            reasons.append("foreground.protect")
        if state.idle_seconds >= 300 and not reasons:
            background = True
            reasons.append("idle.background-adaptation")
        return OperatingPolicyDecision(tier, prefetch, background, tuple(reasons))
