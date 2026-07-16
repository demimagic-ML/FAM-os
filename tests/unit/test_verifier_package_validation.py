import unittest

from fam_os.adapters.crypto import Ed25519PackageSignatureVerifier
from fam_os.registry import BuiltInPackageAnchor, PackageTrustPolicy
from fam_os.verification import VerifierPackageValidationRequest, VerifierPackageValidator
from tests.unit.test_verifier_trust_activation import DIGEST, manifest


class VerifierPackageValidationTests(unittest.TestCase):
    def test_exact_built_in_anchor_accepts_and_digest_tampering_rejects(self) -> None:
        item = manifest()
        package = item.package
        policy = PackageTrustPolicy(
            "verifier-packages", ("Apache-2.0",),
            built_in_anchors=(BuiltInPackageAnchor(
                package.package_id, package.package_version, package.publisher_id, DIGEST,
            ),),
        )
        validator = VerifierPackageValidator(policy, Ed25519PackageSignatureVerifier())
        accepted = validator.validate(VerifierPackageValidationRequest(item, DIGEST))
        self.assertTrue(accepted.accepted)
        changed = type(DIGEST)("sha256", "f" * 64)
        rejected = validator.validate(VerifierPackageValidationRequest(item, changed))
        self.assertEqual("artifact.digest_mismatch", rejected.reason_code)


if __name__ == "__main__":
    unittest.main()
