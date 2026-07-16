import unittest
from dataclasses import replace
from datetime import datetime, timezone
import tempfile
from pathlib import Path

from fam_os.adapters.filesystem import (
    DirectoryExpertBenchmarkSource,
    DirectoryExpertRoutingEmbeddingSource,
)
from fam_os.experts import (
    BenchmarkAttemptKind,
    BenchmarkOutcome,
    ExpertBenchmarkAttempt,
    ExpertBenchmarkIndex,
    ExpertBenchmarkResources,
    ExpertBenchmarkRun,
    ExpertCompatibilityStatus,
    ExpertPackageCoordinate,
    ExpertRoutingEmbedding,
    ExpertRoutingEmbeddingIndex,
    RoutingEmbeddingQuery,
    STABLE_TOPOSORT_REQUIREMENTS,
    VerifierContextDisclosure,
    require_full_host_evidence,
    require_stable_toposort_regression,
    require_successful_stable_toposort_regression,
    validate_routing_benchmark_links,
)
from fam_os.registry import ArtifactDigest, PackageTrustLevel
from fam_os.registry.lifecycle_contracts import (
    ExpertPackageInstallationState,
    InstalledExpertPackage,
    PackageLifecycleAction,
    PackageLifecycleEvent,
)
from fam_os.routing import RoutingRequest, SemanticExpertCandidateFinder
from fam_os.schemas import dumps_document


NOW = datetime(2026, 7, 16, 22, 0, tzinfo=timezone.utc)
COORDINATE = ExpertPackageCoordinate("package.code", "1.0.0")
DIGEST = ArtifactDigest("sha256", "a" * 64)


class ExpertRoutingEmbeddingTests(unittest.TestCase):
    def test_rank_is_space_capability_eligibility_and_similarity_bounded(self) -> None:
        near = self.embedding("near", (1.0, 0.0), ("code.generate.python",))
        far = self.embedding("far", (0.0, 1.0), ("code.generate.python",))
        other = replace(
            self.embedding("other", (1.0, 0.0), ("code.generate.python",)),
            coordinate=ExpertPackageCoordinate("package.other", "1.0.0"),
            expert_id="expert.other",
            embedding_space_id="other-space",
        )
        index = ExpertRoutingEmbeddingIndex()
        self.assertTrue(index.refresh((far, other, near)))
        query = RoutingEmbeddingQuery(
            "space-v1", (1.0, 0.0), ("code.generate.python",)
        )
        matches = index.rank(query, frozenset((COORDINATE,)))
        self.assertEqual(("near", "far"), tuple(item.embedding_id for item in matches))
        self.assertEqual((1.0, 0.0), tuple(item.cosine_similarity for item in matches))

    def test_rejects_non_normalized_wrong_dimension_and_changed_identity(self) -> None:
        with self.assertRaisesRegex(ValueError, "normalized"):
            self.embedding("bad", (1.0, 1.0), ("code.generate",))
        index = ExpertRoutingEmbeddingIndex()
        value = self.embedding("same", (1.0, 0.0), ("code.generate",))
        index.refresh((value,))
        with self.assertRaisesRegex(ValueError, "changed"):
            index.refresh((replace(value, vector=(0.0, 1.0)),))
        short = replace(
            value,
            embedding_id="short",
            vector=(1.0,),
        )
        with self.assertRaisesRegex(ValueError, "dimension"):
            index.refresh((value, short))

    def test_strict_bounded_directory_source_round_trips_into_index(self) -> None:
        value = self.embedding("stored", (1.0, 0.0), ("code.generate",))
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "embedding.json").write_text(dumps_document(value), encoding="utf-8")
            source = DirectoryExpertRoutingEmbeddingSource(root)
            index = ExpertRoutingEmbeddingIndex()
            self.assertTrue(index.refresh_from(source))
            self.assertEqual((value,), index.snapshot())

    def test_candidate_finder_only_returns_enabled_capable_installed_packages(self) -> None:
        value = self.embedding("enabled", (1.0, 0.0), ("code.generate.python",))
        index = ExpertRoutingEmbeddingIndex()
        index.refresh((value,))
        package = InstalledExpertPackage(
            COORDINATE, "expert.code", "package.code/1.0.0/artifact.bin",
            DIGEST, DIGEST, PackageTrustLevel.SIGNED,
            "policy", ExpertCompatibilityStatus.COMPATIBLE,
            "full-reference-workstation", NOW, True,
        )
        event = PackageLifecycleEvent(
            "install-1", 1, NOW, PackageLifecycleAction.INSTALL,
            COORDINATE, None, COORDINATE, "committed",
        )
        state = ExpertPackageInstallationState(1, (package,), (), (event,))
        embedder = _FakeEmbedder((1.0, 0.0))
        finder = SemanticExpertCandidateFinder(index, embedder, "space-v1")
        request = RoutingRequest("request-1", "write Python", ("code.generate.python",))
        self.assertEqual(("enabled",), tuple(item.embedding_id for item in finder.find(request, state)))
        self.assertEqual(("space-v1", "write Python"), embedder.call)

    @staticmethod
    def embedding(name, vector, capabilities):
        return ExpertRoutingEmbedding(
            name,
            COORDINATE,
            "expert.code",
            "publisher.fam",
            "space-v1",
            "generator.local",
            "1.0.0",
            vector,
            capabilities,
            DIGEST,
            NOW,
            ("run-1",),
        )


class ExpertBenchmarkMetadataTests(unittest.TestCase):
    def test_preserves_initial_repair_disclosure_conformance_and_full_resources(self) -> None:
        run = self.repaired_run()
        require_full_host_evidence(run)
        require_stable_toposort_regression(run, "laguna-xs.2:q4_K_M")
        require_successful_stable_toposort_regression(run, "laguna-xs.2:q4_K_M")
        self.assertEqual(BenchmarkOutcome.VERIFIED_AFTER_REPAIR, run.outcome)
        self.assertEqual(("stable_order.input_order",), run.attempts[0].conformance_failure_codes)
        self.assertEqual(
            VerifierContextDisclosure.TRUSTED_TESTS_AND_EXAMPLES,
            run.attempts[1].verifier_context_disclosure,
        )

    def test_outcome_disclosure_resource_and_attempt_invariants_fail_closed(self) -> None:
        run = self.repaired_run()
        with self.assertRaisesRegex(ValueError, "outcome"):
            replace(run, outcome=BenchmarkOutcome.VERIFIED_INITIAL)
        with self.assertRaisesRegex(ValueError, "cannot disclose"):
            replace(
                run.attempts[0],
                verifier_context_disclosure=VerifierContextDisclosure.EXAMPLES,
                disclosed_context_digest=DIGEST,
            )
        incomplete = ExpertBenchmarkResources(
            None, 2, 3, 4, 3, 5, 1, unavailable_measurements=("cpu",)
        )
        with self.assertRaisesRegex(ValueError, "every resource"):
            require_full_host_evidence(replace(run, resources=incomplete))
        failed = replace(
            run,
            outcome=BenchmarkOutcome.FAILED,
            attempts=(replace(run.attempts[0], conformance_failure_codes=("failed",)),),
        )
        require_stable_toposort_regression(failed, "laguna-xs.2:q4_K_M")
        with self.assertRaisesRegex(ValueError, "did not pass"):
            require_successful_stable_toposort_regression(
                failed, "laguna-xs.2:q4_K_M"
            )

    def test_benchmark_index_is_immutable_and_queryable_by_package_and_suite(self) -> None:
        run = self.repaired_run()
        index = ExpertBenchmarkIndex()
        self.assertTrue(index.refresh((run,)))
        self.assertFalse(index.refresh((run,)))
        self.assertEqual((run,), index.for_package(COORDINATE))
        self.assertEqual((run,), index.for_suite("stable-toposort", "2"))
        with self.assertRaisesRegex(ValueError, "changed"):
            index.refresh((replace(run, suite_version="3"),))

    def test_embedding_benchmark_links_are_exact_package_evidence(self) -> None:
        run = self.repaired_run()
        embedding = ExpertRoutingEmbeddingTests.embedding(
            "linked", (1.0, 0.0), ("code.generate",)
        )
        embedding = replace(
            embedding,
            expert_id=run.expert_id,
            benchmark_run_ids=(run.run_id,),
        )
        validate_routing_benchmark_links((embedding,), (run,))
        with self.assertRaisesRegex(ValueError, "another expert package"):
            validate_routing_benchmark_links(
                (replace(embedding, coordinate=ExpertPackageCoordinate("other", "1")),),
                (run,),
            )

    def test_strict_bounded_benchmark_source_rejects_wrong_document_kind(self) -> None:
        run = self.repaired_run()
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            path = root / "run.json"
            path.write_text(dumps_document(run), encoding="utf-8")
            source = DirectoryExpertBenchmarkSource(root)
            index = ExpertBenchmarkIndex()
            self.assertTrue(index.refresh_from(source))
            path.write_text(
                dumps_document(ExpertRoutingEmbeddingTests.embedding(
                    "wrong", (1.0, 0.0), ("code.generate",)
                )),
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "wrong document type"):
                source.load()

    @staticmethod
    def repaired_run():
        initial = ExpertBenchmarkAttempt(
            0, BenchmarkAttemptKind.INITIAL, "laguna-xs.2:q4_K_M",
            VerifierContextDisclosure.NONE, None, False,
            ("stable_order.input_order",), 11.04, 357, 301,
        )
        repair = ExpertBenchmarkAttempt(
            1, BenchmarkAttemptKind.REPAIR, "laguna-xs.2:q4_K_M",
            VerifierContextDisclosure.TRUSTED_TESTS_AND_EXAMPLES,
            DIGEST, True, (), 9.72, 1486, 438,
        )
        resources = ExpertBenchmarkResources(
            44_237_587, 3_152_941_056, 15_557_722_112,
            23_523_688_048, 13_483_219_353, 1_732_894_720, 50_495_488,
        )
        return ExpertBenchmarkRun(
            "laguna-stable-toposort-1", "stable-toposort", "2", COORDINATE,
            "expert.code.laguna", "full-reference-workstation",
            "stable-toposort-v2", NOW, BenchmarkOutcome.VERIFIED_AFTER_REPAIR,
            tuple(sorted(STABLE_TOPOSORT_REQUIREMENTS)),
            (initial, repair), resources, DIGEST,
        )


class _FakeEmbedder:
    def __init__(self, vector):
        self.vector = vector
        self.call = None

    def embed(self, embedding_space_id, text):
        self.call = (embedding_space_id, text)
        return self.vector


if __name__ == "__main__":
    unittest.main()
