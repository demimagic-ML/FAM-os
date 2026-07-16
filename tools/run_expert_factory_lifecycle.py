#!/usr/bin/env python3
import hashlib
import json
import shutil
from dataclasses import asdict
from pathlib import Path

from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fam_os.expert_factory import FailureTrace, cluster_failures
from fam_os.expert_factory.lifecycle import FactoryLifecycleReport
from fam_os.expert_factory.objective import HardwareObjectiveWeights, HardwareTrainingMetrics, hardware_objective
from fam_os.expert_factory.quantization import QuantizedVariant
from fam_os.expert_factory.regression import evaluate_regression
from fam_os.expert_factory.release import sign_and_publish, verify_published
from fam_os.expert_factory.training import LabeledExample, train_micro_expert


def main():
    root = Path(__file__).parents[1] / "artifacts/expert_factory/phase13"
    published, installed = root / "published", root / "installed"
    shutil.rmtree(root, ignore_errors=True)
    published.mkdir(parents=True)
    installed.mkdir()
    traces = tuple(FailureTrace(
        f"trace-{i}", "routing.stable-order", "stable-order", "fixture-verifier",
        f"{i:x}" * 64, True,
    ) for i in (10, 11))
    clusters, proposals = cluster_failures(traces)
    routing, complexity, specialist = _train()
    quality = sum(specialist.predict(text) == label for text, label in (
        ("preserve original ordering", "stable"), ("alphabetically sort roots", "unstable"),
    )) / 2
    score = hardware_objective(HardwareTrainingMetrics(quality, 40, 2048, .002, .05),
                               HardwareObjectiveWeights(1e-6, 1e-7, .01, .001))
    artifact = json.dumps({"routing": asdict(routing), "complexity": asdict(complexity),
                           "specialist": asdict(specialist)}, sort_keys=True).encode()
    artifact_sha = hashlib.sha256(artifact).hexdigest()
    variant = QuantizedVariant("stable-order-int4", specialist.expert_id, "int4", 4,
                               artifact_sha, len(artifact), "c" * 64, quality, .05, quality >= .95)
    gate = evaluate_regression("stable-order-v1", .95, quality, .1, .002, 1, .05, quality == 1)
    manifest = {"proposal": asdict(proposals[0]), "cluster": asdict(clusters[0]),
                "variant": asdict(variant), "objective": score, "gate": asdict(gate)}
    key = Ed25519PrivateKey.generate()
    package = sign_and_publish("stable-order-expert", manifest, "factory-key", key, published)
    verified_manifest = verify_published(Path(package.publication_path), key.public_key())
    installed_path = installed / "stable-order-expert.json"
    shutil.copy2(package.publication_path, installed_path)
    selected = specialist.predict("preserve input ordering") == "stable"
    installed_ok = verify_published(installed_path, key.public_key()) == verified_manifest
    installed_path.unlink()
    report = FactoryLifecycleReport(
        "phase13-lifecycle-v1", bool(proposals), quality == 1, score < quality,
        variant.passed, package.signature_verified, installed_ok, selected, gate.passed,
        not installed_path.exists(), artifact_sha, package.manifest_sha256, gate.gate_id, True,
    )
    (root / "factory-lifecycle.json").write_text(
        json.dumps(asdict(report), indent=2, sort_keys=True) + "\n",
    )


def _train():
    routing = train_micro_expert("routing-v1", "routing.classify", "fam.micro/v1", (
        LabeledExample("write code", "code"), LabeledExample("summarize text", "language")))
    complexity = train_micro_expert("complexity-v1", "routing.complexity", "fam.micro/v1", (
        LabeledExample("short easy", "low"), LabeledExample("complex algorithm", "high")))
    specialist = train_micro_expert("stable-order-v1", "routing.stable-order",
                                    "fam.specialist.classifier/v1", (
        LabeledExample("preserve input original stable ordering", "stable"),
        LabeledExample("alphabetically sort roots", "unstable")))
    return routing, complexity, specialist


if __name__ == "__main__":
    main()
