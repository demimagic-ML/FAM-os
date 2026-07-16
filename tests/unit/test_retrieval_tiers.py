import hashlib
import unittest

from fam_os.adapters.ollama.retrieval_synthesizer import OllamaRetrievalSynthesizer
from fam_os.core.ports.embedding import EmbeddingResponse
from fam_os.core.ports.inference import InferenceResponse
from fam_os.experts.retrieval_tiers import VerifiedRetrievalPipeline
from fam_os.telemetry import InferenceMetrics
from fam_os.verification.retrieval import RetrievedSource


def source(source_id, content):
    return RetrievedSource(
        source_id, f"fixture://{source_id}", content,
        hashlib.sha256(content.encode()).hexdigest(), f"prov-{source_id}",
    )


class Runtime:
    def embed(self, request):
        vectors = ((1.0, 0.0), (0.9, 0.1), (0.0, 1.0))
        return EmbeddingResponse(request.model_ref, vectors, 9, 0.1)

    def chat(self, request):
        content = ('{"answer":"FAM is local.","claims":[{"text":"FAM is local",'
                   '"source_id":"a","quote":"FAM runs locally"}]}')
        return InferenceResponse(content, InferenceMetrics(request.model_ref, 0.2, 0, 0, 0))


class RetrievalTierTests(unittest.TestCase):
    def test_three_tiers_release_only_verified_synthesis(self):
        runtime = Runtime()
        pipeline = VerifiedRetrievalPipeline(
            runtime, "nomic-embed-text:latest",
            OllamaRetrievalSynthesizer(runtime, "llama3.2:3b"),
        )
        result = pipeline.run(
            "Where does FAM run?",
            (source("a", "FAM runs locally on the workstation."),
             source("b", "Cloud systems use remote servers.")),
            top_k=1,
        )
        self.assertEqual("a", result.ranked_sources[0].source.source_id)
        self.assertTrue(result.released)
        self.assertEqual(("claim-1",), result.verification.verified_claim_ids)

    def test_vector_count_must_cover_query_and_sources(self):
        class ShortRuntime(Runtime):
            def embed(self, request):
                return EmbeddingResponse(request.model_ref, ((1.0,),), 1, 0.1)

        pipeline = VerifiedRetrievalPipeline(
            ShortRuntime(), "embed", OllamaRetrievalSynthesizer(Runtime(), "chat"),
        )
        with self.assertRaisesRegex(ValueError, "wrong vector count"):
            pipeline.run("query", (source("a", "content"),))

    def test_synthesizer_rejects_non_source_quote(self):
        class BadRuntime(Runtime):
            def chat(self, request):
                content = ('{"answer":"x","claims":[{"text":"x",'
                           '"source_id":"a","quote":"invented"}]}')
                return InferenceResponse(content, InferenceMetrics("chat", 0.1, 0, 0, 0))

        ranked_pipeline = VerifiedRetrievalPipeline(
            BadRuntime(), "embed", OllamaRetrievalSynthesizer(BadRuntime(), "chat"),
        )
        with self.assertRaisesRegex(ValueError, "exact source substring"):
            ranked_pipeline.run(
                "query", (source("a", "trusted content"), source("b", "other")),
            )


if __name__ == "__main__":
    unittest.main()
