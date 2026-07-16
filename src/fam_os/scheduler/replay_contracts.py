"""Digest-bound evidence for offline scheduler policy replay."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


POLICY_REPLAY_CONTRACT_VERSION = "fam.scheduler.policy-replay/v1alpha1"


class SchedulerPolicyKind(StrEnum):
    HOST_ADMISSION = "host_admission"
    GPU_PLACEMENT = "gpu_placement"
    CACHE_RETENTION = "cache_retention"


@dataclass(frozen=True, slots=True)
class SchedulerPolicyReplayRecord:
    case_id: str
    policy_kind: SchedulerPolicyKind
    policy_version: str
    input_schema_id: str
    output_schema_id: str
    input_digest_sha256: str
    recorded_output_digest_sha256: str
    replayed_output_digest_sha256: str
    matched: bool
    current_host_state_consulted: bool

    def __post_init__(self) -> None:
        for name in ("case_id", "policy_version", "input_schema_id", "output_schema_id"):
            _text(getattr(self, name), name)
        for value in (
            self.input_digest_sha256, self.recorded_output_digest_sha256,
            self.replayed_output_digest_sha256,
        ):
            _digest(value)
        expected = self.recorded_output_digest_sha256 == self.replayed_output_digest_sha256
        if self.matched != expected:
            raise ValueError("policy replay match flag is inconsistent")
        if self.current_host_state_consulted:
            raise ValueError("offline policy replay cannot consult current host state")


@dataclass(frozen=True, slots=True)
class SchedulerPolicyReplayReport:
    report_id: str
    replayed_at: datetime
    records: tuple[SchedulerPolicyReplayRecord, ...]
    all_matched: bool
    contract_version: str = POLICY_REPLAY_CONTRACT_VERSION

    def __post_init__(self) -> None:
        if self.contract_version != POLICY_REPLAY_CONTRACT_VERSION:
            raise ValueError("unsupported policy replay contract_version")
        _text(self.report_id, "report_id")
        _time(self.replayed_at)
        if not self.records or len({item.case_id for item in self.records}) != len(self.records):
            raise ValueError("policy replay cases must be non-empty and unique")
        required = set(SchedulerPolicyKind)
        if {item.policy_kind for item in self.records} != required:
            raise ValueError("policy replay report requires all scheduler policy kinds")
        if self.all_matched != all(item.matched for item in self.records):
            raise ValueError("policy replay report match summary is inconsistent")


def _text(value: str, name: str) -> None:
    if not value.strip():
        raise ValueError(f"{name} must not be empty")


def _digest(value: str) -> None:
    if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
        raise ValueError("policy replay digest must be lowercase SHA-256")


def _time(value: datetime) -> None:
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("replayed_at must be timezone-aware")
