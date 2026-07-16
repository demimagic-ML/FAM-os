import base64
import hashlib
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

from fam_os.adapters.crypto import Ed25519PackageSignatureVerifier
from fam_os.adapters.filesystem import Sha256FileArtifactHasher
from fam_os.registry import (
    ArtifactDigest,
    BuiltInPackageAnchor,
    PackageSignature,
    PackageTrustLevel,
    PackageTrustPolicy,
    PublisherKeyStatus,
    SignatureAlgorithm,
    TrustedPublisherKey,
    validate_spdx_expression,
)
from fam_os.registry.signing_payload import expert_package_signing_payload
from fam_os.registry.validation import ExpertPackageValidator, PackageValidationRequest
from tests.unit.test_package_expert_manifests import _manifest, _package


ARTIFACT = b"bounded expert package artifact"
DIGEST = ArtifactDigest("sha256", hashlib.sha256(ARTIFACT).hexdigest())


class PackageTrustValidationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.private_key = Ed25519PrivateKey.generate()
        public = self.private_key.public_key().public_bytes(
            serialization.Encoding.Raw,
            serialization.PublicFormat.Raw,
        )
        self.key = TrustedPublisherKey(
            "fam-release-key-1",
            "fam-project",
            SignatureAlgorithm.ED25519,
            base64.b64encode(public).decode("ascii"),
        )
        self.manifest = _manifest(package=_package(artifact_digest=DIGEST))

    def test_accepts_valid_detached_signature_and_derives_signed_trust(self) -> None:
        signature = self.signature(self.manifest)
        report = self.validator().validate(
            PackageValidationRequest(self.manifest, DIGEST, signature)
        )
        self.assertTrue(report.accepted)
        self.assertEqual(PackageTrustLevel.SIGNED, report.effective_trust)
        self.assertEqual(self.key.key_id, report.verified_key_id)

    def test_digest_manifest_signature_and_key_tampering_fail_closed(self) -> None:
        valid_signature = self.signature(self.manifest)
        cases = (
            (
                PackageValidationRequest(
                    self.manifest,
                    ArtifactDigest("sha256", "0" * 64),
                    valid_signature,
                ),
                "artifact.digest_mismatch",
            ),
            (
                PackageValidationRequest(
                    replace(self.manifest, display_name="Tampered"),
                    DIGEST,
                    valid_signature,
                ),
                "signature.invalid",
            ),
            (
                PackageValidationRequest(
                    self.manifest,
                    DIGEST,
                    replace(valid_signature, signature_base64=base64.b64encode(b"x" * 64).decode()),
                ),
                "signature.invalid",
            ),
        )
        for request, reason in cases:
            with self.subTest(reason=reason):
                self.assertEqual(reason, self.validator().validate(request).reason_code)

        revoked = replace(self.key, status=PublisherKeyStatus.REVOKED)
        self.assertEqual(
            "signature.key_revoked",
            self.validator(keys=(revoked,)).validate(
                PackageValidationRequest(self.manifest, DIGEST, valid_signature)
            ).reason_code,
        )

    def test_license_policy_rejects_invalid_and_unapproved_expressions(self) -> None:
        validate_spdx_expression("MIT OR Apache-2.0")
        for license_id, reason in (
            ("Apache-2.0 OR", "license.invalid_expression"),
            ("MIT", "license.denied"),
        ):
            manifest = replace(
                self.manifest,
                package=replace(self.manifest.package, license_id=license_id),
            )
            report = self.validator().validate(
                PackageValidationRequest(manifest, DIGEST, self.signature(manifest))
            )
            self.assertEqual(reason, report.reason_code)

    def test_built_in_requires_exact_anchor_and_local_unverified_requires_policy(self) -> None:
        built_package = replace(
            self.manifest.package,
            trust_level=PackageTrustLevel.BUILT_IN,
            signature_key_id=None,
        )
        built = replace(self.manifest, package=built_package)
        anchor = BuiltInPackageAnchor(
            built_package.package_id,
            built_package.package_version,
            built_package.publisher_id,
            DIGEST,
        )
        accepted = self.validator(anchors=(anchor,)).validate(
            PackageValidationRequest(built, DIGEST)
        )
        self.assertEqual(PackageTrustLevel.BUILT_IN, accepted.effective_trust)
        self.assertEqual(
            "trust.built_in_unanchored",
            self.validator().validate(PackageValidationRequest(built, DIGEST)).reason_code,
        )

        local_package = replace(
            self.manifest.package,
            trust_level=PackageTrustLevel.LOCAL_UNVERIFIED,
            signature_key_id=None,
        )
        local = replace(self.manifest, package=local_package)
        denied = self.validator().validate(PackageValidationRequest(local, DIGEST))
        allowed = self.validator(allow_local=True).validate(
            PackageValidationRequest(local, DIGEST)
        )
        self.assertEqual("trust.local_unverified_denied", denied.reason_code)
        self.assertEqual(PackageTrustLevel.LOCAL_UNVERIFIED, allowed.effective_trust)

    def test_file_artifact_hasher_observes_real_bytes_and_rejects_symlink(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "package.bin"
            path.write_bytes(ARTIFACT)
            self.assertEqual(DIGEST, Sha256FileArtifactHasher().digest(path))
            linked = Path(directory) / "linked.bin"
            linked.symlink_to(path)
            with self.assertRaises(OSError):
                Sha256FileArtifactHasher().digest(linked)

    def signature(self, manifest) -> PackageSignature:
        encoded = self.private_key.sign(expert_package_signing_payload(manifest))
        return PackageSignature(
            self.key.key_id,
            SignatureAlgorithm.ED25519,
            base64.b64encode(encoded).decode("ascii"),
        )

    def validator(self, *, keys=None, anchors=(), allow_local=False):
        policy = PackageTrustPolicy(
            "test-policy",
            ("Apache-2.0",),
            publisher_keys=(self.key,) if keys is None else keys,
            built_in_anchors=anchors,
            allow_local_unverified=allow_local,
        )
        return ExpertPackageValidator(policy, Ed25519PackageSignatureVerifier())


if __name__ == "__main__":
    unittest.main()
