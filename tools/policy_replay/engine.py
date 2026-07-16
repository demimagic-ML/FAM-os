"""Replay actual pure scheduler policies and bind inputs/outputs by digest."""

from __future__ import annotations

import hashlib
from pathlib import Path

from fam_os.scheduler import (
    ADMISSION_CONTRACT_VERSION,
    CACHE_POLICY_VERSION,
    GPU_PLACEMENT_CONTRACT_VERSION,
    AdmissionDecision,
    CachePolicyDecision,
    DeterministicAdmissionPolicy,
    DeterministicCacheRetentionPolicy,
    DeterministicGpuPlacementPolicy,
    GpuPlacementDecision,
    SchedulerPolicyKind,
    SchedulerPolicyReplayRecord,
)
from fam_os.schemas import descriptor_for_type, dumps_document


def replay_case(case_id: str, request, expected, output: Path):
    replayed, kind, version = execute_policy(expected, request)
    input_text = dumps_document(request)
    expected_text = dumps_document(expected)
    replayed_text = dumps_document(replayed)
    case_root = output / case_id
    case_root.mkdir(parents=True, exist_ok=False)
    _write(case_root / "input.json", input_text)
    _write(case_root / "recorded-output.json", expected_text)
    _write(case_root / "replayed-output.json", replayed_text)
    return SchedulerPolicyReplayRecord(
        case_id, kind, version, _schema_id(request), _schema_id(expected),
        _digest(input_text), _digest(expected_text), _digest(replayed_text),
        expected_text == replayed_text, False,
    )


def execute_policy(expected, request):
    if isinstance(expected, AdmissionDecision):
        value = DeterministicAdmissionPolicy().decide(expected.decision_id, request)
        return value, SchedulerPolicyKind.HOST_ADMISSION, ADMISSION_CONTRACT_VERSION
    if isinstance(expected, GpuPlacementDecision):
        value = DeterministicGpuPlacementPolicy().decide(expected.decision_id, request)
        return value, SchedulerPolicyKind.GPU_PLACEMENT, GPU_PLACEMENT_CONTRACT_VERSION
    if isinstance(expected, CachePolicyDecision):
        value = DeterministicCacheRetentionPolicy().decide(expected.decision_id, request)
        return value, SchedulerPolicyKind.CACHE_RETENTION, CACHE_POLICY_VERSION
    raise TypeError(f"unsupported scheduler policy output: {type(expected).__name__}")


def _schema_id(value) -> str:
    descriptor = descriptor_for_type(type(value))
    if descriptor is None:
        raise TypeError(f"unregistered replay contract: {type(value).__name__}")
    return descriptor.schema_id


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _write(path: Path, value: str) -> None:
    path.write_text(value + "\n", encoding="utf-8")
