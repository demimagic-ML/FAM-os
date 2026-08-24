import tempfile
import unittest
from importlib import resources
from pathlib import Path

from fam_os.product.composition.verifier_unit import _source_packages
from fam_os.registry import ArtifactDigest, PackageTrustLevel
from fam_os.verification.artifact import verifier_tree_digest


ROOT = Path(__file__).parents[2]
DIRECTORIES = ("verifiers", "verifier-bindings")


class PackagedVerifierConfigurationTests(unittest.TestCase):
    def test_packaged_documents_are_exact_copies_of_canonical_configuration(self) -> None:
        packaged = resources.files("fam_os.product.resources")
        for directory in DIRECTORIES:
            canonical = ROOT / "configs/packages" / directory
            names = tuple(path.name for path in sorted(canonical.glob("production-*.json")))
            self.assertTrue(names)
            self.assertEqual(
                names,
                tuple(
                    item.name for item in sorted(
                        packaged.joinpath(directory).iterdir(),
                        key=lambda candidate: candidate.name,
                    )
                    if item.name.endswith(".json")
                ),
            )
            for name in names:
                with self.subTest(directory=directory, name=name):
                    self.assertEqual(
                        (canonical / name).read_bytes(),
                        packaged.joinpath(directory, name).read_bytes(),
                    )

    def test_wheel_style_root_falls_back_to_packaged_verifier_defaults(self) -> None:
        digest = ArtifactDigest(
            "sha256", verifier_tree_digest(ROOT / "src/fam_os/verification"),
        )
        with tempfile.TemporaryDirectory() as directory:
            packages, trust = _source_packages(Path(directory), digest)

        self.assertEqual(PackageTrustLevel.LOCAL_UNVERIFIED, trust)
        self.assertEqual(5, len(packages))
        self.assertTrue(all(item.package_report.accepted for item in packages))


if __name__ == "__main__":
    unittest.main()
