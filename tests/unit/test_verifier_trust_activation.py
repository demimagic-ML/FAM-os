import unittest
from dataclasses import replace

from fam_os.registry import ArtifactDigest, PackageMetadata, PackageTrustLevel
from fam_os.registry.trust_contracts import PackageValidationReport
from fam_os.verification import (
    DeterminismClass,
    VerifierActivationRequest,
    VerifierManifest,
    VerifierRuntimeBinding,
    VerifierTrustEvaluator,
    VerifierTrustPolicy,
)


DIGEST = ArtifactDigest("sha256", "a" * 64)


def manifest() -> VerifierManifest:
    package = PackageMetadata(
        "fam.verifier.test", "1.0.0", "fam-project", "Apache-2.0",
        PackageTrustLevel.BUILT_IN, DIGEST,
    )
    return VerifierManifest(
        package, "verifier.test", "Test verifier", "fam.verifier.python/v1",
        ("acceptance.test",), ("candidate.python/v1",), "evidence.tests/v1",
        DeterminismClass.DETERMINISTIC,
        ("isolation.process", "isolation.network-denied"), 10.0,
    )


def request() -> VerifierActivationRequest:
    item = manifest()
    binding = VerifierRuntimeBinding(
        item.package.package_id, item.package.package_version, item.verifier_id,
        item.runner_contract_id, "python.subprocess/v1", "fam_verifier:run", DIGEST,
    )
    report = PackageValidationReport(
        item.package.package_id, item.package.package_version, True, "accepted",
        PackageTrustLevel.BUILT_IN, DIGEST, "package-policy",
    )
    return VerifierActivationRequest(
        item, binding, report, "acceptance.test", "candidate.python/v1",
        "evidence.tests/v1", ("isolation.process", "isolation.network-denied"),
    )


def evaluator(**overrides) -> VerifierTrustEvaluator:
    values = dict(
        policy_id="verifier-policy", allowed_verifier_ids=("verifier.test",),
        allowed_runner_contract_ids=("fam.verifier.python/v1",),
        minimum_trust=PackageTrustLevel.SIGNED,
    )
    values.update(overrides)
    return VerifierTrustEvaluator(VerifierTrustPolicy(**values))


class VerifierTrustActivationTests(unittest.TestCase):
    def test_exact_trusted_runtime_is_activated_with_digest_evidence(self) -> None:
        decision = evaluator().evaluate(request())
        self.assertTrue(decision.allowed)
        self.assertEqual("accepted", decision.reason_code)
        self.assertEqual(DIGEST.value, decision.verified_artifact_digest)

    def test_artifact_identity_authority_and_isolation_fail_closed(self) -> None:
        base = request()
        cases = (
            (replace(base, binding=replace(base.binding, entry_point="other", expected_artifact_digest=ArtifactDigest("sha256", "b" * 64))), "runtime.binding_mismatch"),
            (replace(base, acceptance_id="acceptance.undeclared"), "authority.acceptance_undeclared"),
            (replace(base, candidate_schema_id="candidate.other/v1"), "authority.candidate_schema_undeclared"),
            (replace(base, evidence_schema_id="evidence.other/v1"), "authority.evidence_schema_mismatch"),
            (replace(base, available_isolation_capabilities=("isolation.process",)), "isolation.capability_missing"),
        )
        for changed, reason in cases:
            with self.subTest(reason=reason):
                decision = evaluator().evaluate(changed)
                self.assertFalse(decision.allowed)
                self.assertEqual(reason, decision.reason_code)
                self.assertIsNone(decision.verified_artifact_digest)

    def test_rejected_wrong_or_under_trusted_package_cannot_activate(self) -> None:
        base = request()
        rejected = replace(
            base.package_report, accepted=False, reason_code="artifact.digest_mismatch",
            effective_trust=None,
        )
        self.assertEqual(
            "package.validation_rejected",
            evaluator().evaluate(replace(base, package_report=rejected)).reason_code,
        )
        local = replace(
            base.package_report, effective_trust=PackageTrustLevel.LOCAL_UNVERIFIED,
        )
        self.assertEqual(
            "package.trust_below_minimum",
            evaluator().evaluate(replace(base, package_report=local)).reason_code,
        )

    def test_policy_allowlists_verifier_and_runner(self) -> None:
        self.assertEqual(
            "authority.verifier_denied",
            evaluator(allowed_verifier_ids=("verifier.other",)).evaluate(request()).reason_code,
        )
        self.assertEqual(
            "authority.runner_denied",
            evaluator(allowed_runner_contract_ids=("fam.verifier.other/v1",)).evaluate(request()).reason_code,
        )


if __name__ == "__main__":
    unittest.main()
