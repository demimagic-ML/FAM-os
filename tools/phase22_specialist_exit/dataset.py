"""Build the governed, reference-verified specialist dataset."""

from __future__ import annotations

import hashlib
import json
import subprocess
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from fam_os.expert_factory import (
    DatasetLeakageReport,
    FactoryCapabilityProposal,
    HeldOutEvaluationKind,
    HeldOutVerifierKind,
    SealedFactoryDataset,
    TrainingCaptureGrant,
    TrainingDataSensitivity,
    TrainingSourceKind,
    build_verified_failure_trace,
    discover_failure_clusters,
)
from fam_os.product.factory_datasets import (
    ProductFactoryDatasets,
)
from tools.phase22_specialist_exit.fixtures import (
    POLICY_COMPLETIONS,
    SAFETY_COMPLETIONS,
    SPLIT_POLICY,
    SourceFixture,
    dataset_fixtures,
)
from tools.phase22_specialist_exit.sample_plans import QUALITY256


@dataclass(frozen=True, slots=True)
class FixtureVerificationReceipt:
    source_id: str
    input_sha256: str
    completion_sha256: str
    verifier_id: str
    verifier_evidence_sha256: str
    passed: bool


@dataclass(frozen=True, slots=True)
class PreparedSpecialistDataset:
    sample_plan_id: str
    proposal: FactoryCapabilityProposal
    grant: TrainingCaptureGrant
    dataset: SealedFactoryDataset
    leakage: DatasetLeakageReport
    fixture_receipts: tuple[FixtureVerificationReceipt, ...]


def prepare_specialist_dataset(
    *, repositories: Any, blob_store: Any, verifier_script: Path,
    now: datetime, run_id: str, sample_plan_id: str = QUALITY256.plan_id,
) -> PreparedSpecialistDataset:
    proposal = _seed_proposal(repositories, now, run_id)
    fixtures = dataset_fixtures(sample_plan_id)
    receipts = verify_specialist_fixtures(verifier_script, sample_plan_id)
    if not all(item.passed for item in receipts):
        raise RuntimeError("specialist source fixture failed deterministic verification")
    grant = TrainingCaptureGrant(
        f"{run_id}-capture", proposal.proposal_id, proposal.capability_id,
        (TrainingSourceKind.VERIFIED_FIXTURE,),
        ("workspace:phase22-stable-toposort",),
        (TrainingDataSensitivity.PRIVATE,), 8 * 1024**2, len(fixtures),
        now, now + timedelta(hours=4), True,
    )
    datasets = ProductFactoryDatasets(
        repositories, SPLIT_POLICY, blob_store, now=lambda: now,
    )
    if not datasets.add_grant(grant):
        raise RuntimeError("specialist capture grant identity was reused")
    for item in fixtures:
        captured = datasets.capture_source(
            grant_id=grant.grant_id, source_id=item.source_id,
            source_family_id=item.source_family_id,
            source_kind=TrainingSourceKind.VERIFIED_FIXTURE,
            workspace_scope="workspace:phase22-stable-toposort",
            sensitivity=TrainingDataSensitivity.PRIVATE,
            license_id="owner-authored-stable-toposort-v1",
            input_text=item.input_text, reference_output=item.completion,
            evaluation_kind=HeldOutEvaluationKind(item.kind),
            evaluation_verifier=HeldOutVerifierKind(item.evaluation_verifier),
            evaluation_requirement_id=item.requirement_id,
        )
        if captured.partition is not item.partition:
            raise RuntimeError("captured source partition changed after verification")
    dataset, leakage = datasets.seal(
        dataset_id=f"{run_id}-dataset", grant_id=grant.grant_id,
    )
    if dataset is None or not leakage.passed:
        raise RuntimeError("specialist dataset failed leakage controls")
    return PreparedSpecialistDataset(
        sample_plan_id, proposal, grant, dataset, leakage, receipts,
    )


def verify_specialist_fixtures(
    verifier_script: Path, sample_plan_id: str = QUALITY256.plan_id,
) -> tuple[FixtureVerificationReceipt, ...]:
    """Recompute content-free source verification receipts deterministically."""
    return tuple(
        _verify(item, verifier_script)
        for item in dataset_fixtures(sample_plan_id)
    )


def _seed_proposal(
    repositories: Any, now: datetime, run_id: str,
) -> FactoryCapabilityProposal:
    traces = tuple(
        build_verified_failure_trace(
            verification_id=f"{run_id}-verification-{index}",
            request_id=f"{run_id}-request-{index}",
            candidate_id=f"{run_id}-candidate-{index}",
            capability_id="intent.code",
            failed_requirement_id="acceptance.python.stable-topological-sort",
            verifier_id="python.deterministic-tests.v1",
            verifier_artifact_sha256="a" * 64,
            candidate_sha256=hashlib.sha256(
                f"{run_id}-failed-candidate-{index}".encode(),
            ).hexdigest(),
            model_ref="qwen2.5-coder:7b", expert_tier="specialist",
            release_id="phase22-source-release", signer_key_id="phase22-source-key",
            observed_at=now + timedelta(microseconds=index),
        )
        for index in range(1, 5)
    )
    for trace in traces:
        repositories.factory_discovery.add_trace(trace)
    clusters, proposals = discover_failure_clusters(traces)
    if len(clusters) != 1 or len(proposals) != 1:
        raise RuntimeError("specialist failure discovery was not deterministic")
    repositories.factory_discovery.add_cluster(clusters[0])
    repositories.factory_discovery.add_proposal(proposals[0])
    return proposals[0]


def _verify(
    fixture: SourceFixture, verifier_script: Path,
) -> FixtureVerificationReceipt:
    if fixture.test_source is not None:
        payload = json.dumps({
            "candidate": fixture.completion, "tests": fixture.test_source,
        })
        result = subprocess.run(
            (sys.executable, "-I", "-S", str(verifier_script)),
            input=payload, text=True, capture_output=True, check=False, timeout=5,
        )
        passed = result.returncode == 0 and result.stdout.strip() == '{"passed":true}'
        verifier = "python.deterministic-tests.v1"
        evidence = fixture.test_source
    else:
        passed, verifier = _verify_text_fixture(fixture)
        evidence = fixture.completion
    return FixtureVerificationReceipt(
        fixture.source_id, _sha(fixture.input_text), _sha(fixture.completion),
        verifier, _sha(evidence), passed,
    )


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _verify_text_fixture(fixture: SourceFixture) -> tuple[bool, str]:
    if fixture.kind == "safety":
        return (
            fixture.completion in SAFETY_COMPLETIONS,
            "text.safe-refusal.v1",
        )
    if fixture.kind == "policy":
        return (
            fixture.completion in POLICY_COMPLETIONS,
            "text.honest-refusal.v1",
        )
    if fixture.kind == "unrelated":
        return fixture.completion.isdecimal(), "text.exact.v1"
    raise ValueError("non-code fixture kind has no deterministic verifier")
