#!/usr/bin/env python3
"""Capture canonical fail-closed verifier trust activation evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from dataclasses import asdict, replace
from pathlib import Path

from fam_os.adapters.crypto import Ed25519PackageSignatureVerifier
from fam_os.registry import (
    ArtifactDigest,
    BuiltInPackageAnchor,
    PackageMetadata,
    PackageTrustLevel,
    PackageTrustPolicy,
)
from fam_os.verification import (
    DeterminismClass,
    VerifierActivationRequest,
    VerifierManifest,
    VerifierPackageValidationRequest,
    VerifierPackageValidator,
    VerifierRuntimeBinding,
    VerifierTrustEvaluator,
    VerifierTrustPolicy,
)


def build_manifest(artifact: Path) -> VerifierManifest:
    digest = ArtifactDigest("sha256", hashlib.sha256(artifact.read_bytes()).hexdigest())
    package = PackageMetadata(
        "fam.verifier.python.runtime", "1.0.0", "fam-project", "Apache-2.0",
        PackageTrustLevel.BUILT_IN, digest,
    )
    return VerifierManifest(
        package, "verifier.python.runtime", "FAM Python verifier runtime",
        "fam.verifier.python/v1", ("python.strict-tests",),
        ("candidate.python.source/v1",), "evidence.python.tests/v1",
        DeterminismClass.DETERMINISTIC,
        ("isolation.process", "isolation.network-denied", "isolation.temporary-directory"),
        30.0,
    )


def capture(root: Path) -> dict[str, object]:
    artifact = root / "src/fam_os/verification/python/verifier.py"
    manifest = build_manifest(artifact)
    package = manifest.package
    package_policy = PackageTrustPolicy(
        "phase8-verifier-package-policy", ("Apache-2.0",),
        built_in_anchors=(BuiltInPackageAnchor(
            package.package_id, package.package_version, package.publisher_id,
            package.artifact_digest,
        ),),
    )
    report = VerifierPackageValidator(
        package_policy, Ed25519PackageSignatureVerifier(),
    ).validate(VerifierPackageValidationRequest(manifest, package.artifact_digest))
    binding = VerifierRuntimeBinding(
        package.package_id, package.package_version, manifest.verifier_id,
        manifest.runner_contract_id, "python.subprocess/v1",
        "fam_os.verification.python.verifier:StrictPythonVerifier",
        package.artifact_digest,
    )
    policy = VerifierTrustPolicy(
        "phase8-verifier-activation-policy", (manifest.verifier_id,),
        (manifest.runner_contract_id,), PackageTrustLevel.BUILT_IN,
    )
    request = VerifierActivationRequest(
        manifest, binding, report, manifest.acceptance_ids[0],
        manifest.candidate_schema_ids[0], manifest.evidence_schema_id,
        manifest.required_isolation_capabilities,
    )
    evaluator = VerifierTrustEvaluator(policy)
    accepted = evaluator.evaluate(request)
    tampered = evaluator.evaluate(replace(
        request,
        binding=replace(binding, expected_artifact_digest=ArtifactDigest("sha256", "0" * 64)),
    ))
    return {
        "phase": "8.1",
        "artifact": str(artifact.relative_to(root)),
        "artifact_sha256": package.artifact_digest.value,
        "package_validation": asdict(report),
        "activation": asdict(accepted),
        "tampered_activation": asdict(tampered),
        "acceptance": accepted.allowed and not tampered.allowed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    document = capture(root)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(json.dumps(document, indent=2, sort_keys=True))
    return 0 if document["acceptance"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
