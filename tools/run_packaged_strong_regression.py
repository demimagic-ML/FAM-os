#!/usr/bin/env python3
"""Run one enabled strong expert package through the strict workstation regression."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime
from pathlib import Path

from fam_os.experts import (
    STABLE_TOPOSORT_REQUIREMENTS,
    BenchmarkAttemptKind,
    BenchmarkOutcome,
    ExpertBenchmarkAttempt,
    ExpertBenchmarkResources,
    ExpertBenchmarkRun,
    ExpertRuntimeBinding,
    ExpertTier,
    InstalledExpertCandidateResolver,
    LocalExpertRegistry,
    VerifierContextDisclosure,
    require_stable_toposort_regression,
)
from fam_os.adapters.filesystem import DirectoryExpertManifestSource
from fam_os.registry import ArtifactDigest
from fam_os.registry.lifecycle_contracts import ExpertPackageInstallationState
from fam_os.schemas import dumps_document, loads_document
from tools.parity.composition import load_benchmark_composition
from tools.parity.historical_config import load_verified_fixture
from tools.run_verified_parity import run_verified_parity
from tools.workstation.evidence import WorkstationEvidenceCollector


def run(args) -> tuple[Path, Path]:
    binding = _load(args.binding, ExpertRuntimeBinding)
    state = _load(args.installation_state, ExpertPackageInstallationState)
    package = next(
        (item for item in state.packages if item.coordinate == binding.coordinate), None
    )
    if package is None or not package.enabled:
        raise ValueError("strong regression package must be installed and enabled")
    if package.artifact_digest != binding.expected_artifact_digest:
        raise ValueError("installed package digest does not match runtime binding")
    manifests = DirectoryExpertManifestSource(args.package_root / "experts").load()
    all_bindings = tuple(
        _load(path, ExpertRuntimeBinding)
        for path in sorted((args.package_root / "bindings").glob("*.json"))
    )
    registry = LocalExpertRegistry()
    registry.refresh(manifests)
    candidates = InstalledExpertCandidateResolver(registry, all_bindings).resolve(
        "code.generate.python", state, ExpertTier.ESCALATION
    )
    if binding.coordinate not in {item.runtime_binding.coordinate for item in candidates}:
        raise ValueError("package is not selectable by declared escalation capability")
    fixture = load_verified_fixture(args.config)
    if {fixture.economical_model, fixture.escalation_model} != {binding.artifact_ref}:
        raise ValueError("benchmark config must use only the bound package model")
    composition = load_benchmark_composition(args.profile, args.effective_budget)
    output, report = run_verified_parity(
        args.config, args.trusted_tests, args.output_dir, composition,
        WorkstationEvidenceCollector(),
    )
    report["benchmark"] = "phase6-installed-package-stable-toposort-v2"
    report["package_evidence"] = {
        "package_id": binding.coordinate.package_id,
        "package_version": binding.coordinate.package_version,
        "expert_id": binding.expert_id,
        "model_ref": binding.artifact_ref,
        "artifact_digest": binding.expected_artifact_digest.value,
        "installation_state_revision": state.revision,
        "enabled": package.enabled,
        "effective_trust": package.effective_trust.value,
        "selection_capability": "code.generate.python",
        "selection_tier": "escalation",
    }
    _rewrite_report(output, report)
    metadata = _metadata(report, output, binding, fixture, args.trusted_tests)
    require_stable_toposort_regression(metadata, binding.artifact_ref)
    metadata_path = args.output_dir / f"benchmark-metadata-{output.stem}.json"
    metadata_path.write_text(dumps_document(metadata) + "\n", encoding="utf-8")
    return output, metadata_path


def _metadata(report, output, binding, fixture, tests_path):
    attempts = tuple(
        _attempt(item, index, fixture, tests_path)
        for index, item in enumerate(report["attempts"])
    )
    outcome = _outcome(report, attempts)
    return ExpertBenchmarkRun(
        f"phase6-{binding.expert_id}-{output.stem.rsplit('-', 2)[-1]}",
        "stable-toposort", "2", binding.coordinate, binding.expert_id,
        "full-reference-workstation", "stable-toposort-v2",
        datetime.fromisoformat(report["captured_at"]), outcome,
        tuple(sorted(STABLE_TOPOSORT_REQUIREMENTS)), attempts,
        _resources(report), _digest_file(output),
    )


def _attempt(item, index, fixture, tests_path):
    raw_kind = item["kind"]
    kind = BenchmarkAttemptKind.REPAIR if raw_kind == "repair" else BenchmarkAttemptKind.INITIAL
    disclosure = (
        VerifierContextDisclosure.TRUSTED_TESTS_AND_EXAMPLES
        if kind is BenchmarkAttemptKind.REPAIR else VerifierContextDisclosure.NONE
    )
    context_digest = _repair_context_digest(fixture, tests_path) if disclosure.value != "none" else None
    verification = item["verification"]
    metrics = item["metrics"]
    passed = verification["status"] == "passed"
    return ExpertBenchmarkAttempt(
        index, kind, item["model_ref"], disclosure, context_digest, passed,
        () if passed else _failure_codes(verification),
        metrics["wall_seconds"], metrics["prompt_tokens"], metrics["output_tokens"],
    )


def _resources(report):
    evidence = report["workstation_evidence"]
    resources = report["resources"]
    accelerator = evidence["accelerator_deltas"][0]
    transfer = evidence["model_transfers"][0]
    storage = evidence["storage_io_delta"]
    return ExpertBenchmarkResources(
        resources["cpu_usage_microseconds"], resources["memory_peak_bytes"],
        accelerator["max_observed_memory_used_bytes"],
        transfer["resident_set_delta_bytes"],
        transfer["accelerator_residency_delta_bytes"],
        storage["read_bytes"], storage["write_bytes"],
    )


def _outcome(report, attempts):
    if not report["result"]["verified"]:
        return BenchmarkOutcome.FAILED
    return (
        BenchmarkOutcome.VERIFIED_INITIAL
        if attempts[-1].kind is BenchmarkAttemptKind.INITIAL
        else BenchmarkOutcome.VERIFIED_AFTER_REPAIR
    )


def _failure_codes(verification):
    text = (verification.get("reason", "") + " " + verification.get("evidence", {}).get("stderr", "")).lower()
    codes = []
    if any(name in text for name in ("set", "min", "sorted")):
        codes.append("forbidden_calls.no_set_min_sorted")
    if "neighbor_only" in text or "neighbor-only" in text:
        codes.append("neighbor_only.initialization")
    if "expected ['b', 'a', 'd']" in text or "input-order" in text:
        codes.append("stable_order.input_order")
    return tuple(codes or ("verifier.tests_failed",))


def _repair_context_digest(fixture, tests_path):
    source = tests_path.read_text(encoding="utf-8")
    examples = json.dumps(fixture.repair_examples, separators=(",", ":"))
    return ArtifactDigest("sha256", hashlib.sha256((source + "\0" + examples).encode()).hexdigest())


def _digest_file(path):
    return ArtifactDigest("sha256", hashlib.sha256(path.read_bytes()).hexdigest())


def _rewrite_report(path, report):
    path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")


def _load(path, expected_type):
    value = loads_document(path.read_text(encoding="utf-8"))
    if not isinstance(value, expected_type):
        raise ValueError(f"unexpected document type: {path}")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--binding", type=Path, required=True)
    parser.add_argument("--installation-state", type=Path, required=True)
    parser.add_argument("--package-root", type=Path, default=Path("configs/packages"))
    parser.add_argument("--trusted-tests", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--effective-budget", type=Path, required=True)
    args = parser.parse_args()
    report, metadata = run(args)
    print(json.dumps({"report": str(report), "metadata": str(metadata)}, indent=2))


if __name__ == "__main__":
    main()
