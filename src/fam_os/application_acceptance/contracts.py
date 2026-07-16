"""Measured evidence values for Phase 5 cross-application acceptance."""

from dataclasses import dataclass
from enum import StrEnum


class IntegrationLevel(StrEnum):
    NATIVE = "native_semantic"
    MCP = "mcp"
    DETERMINISTIC = "deterministic_os_tool"
    ACCESSIBILITY = "accessibility"


@dataclass(frozen=True, slots=True)
class OperationMeasurement:
    operation_id: str
    level: IntegrationLevel
    capability_id: str
    succeeded: bool
    latency_ms: float
    context_bytes: int
    cpu_ms: float
    read_bytes: int
    write_bytes: int
    rss_before_bytes: int
    rss_after_bytes: int
    error_code: str | None = None

    def __post_init__(self):
        if min(
            self.latency_ms, self.context_bytes, self.cpu_ms,
            self.read_bytes, self.write_bytes,
            self.rss_before_bytes, self.rss_after_bytes,
        ) < 0:
            raise ValueError("acceptance measurement cannot be negative")
        if self.succeeded == (self.error_code is not None):
            raise ValueError("acceptance measurement outcome is inconsistent")


@dataclass(frozen=True, slots=True)
class ScenarioEvidence:
    scenario_id: str
    succeeded: bool
    verified: bool
    reduced_fidelity: bool
    result: str
    capability_ids: tuple[str, ...]
    permission_grant_ids: tuple[str, ...]
    expert_ids: tuple[str, ...]
    measurements: tuple[OperationMeasurement, ...]
    audit_event_ids: tuple[str, ...] = ()
    failure_code: str | None = None

    def __post_init__(self):
        if self.verified and not self.succeeded:
            raise ValueError("verified acceptance scenario must succeed")
        if self.succeeded == (self.failure_code is not None):
            raise ValueError("acceptance scenario outcome is inconsistent")


@dataclass(frozen=True, slots=True)
class AcceptanceReport:
    report_id: str
    generated_at: str
    host_profile: dict
    scenarios: tuple[ScenarioEvidence, ...]
    integration_summary: dict
    exit_gate_passed: bool
