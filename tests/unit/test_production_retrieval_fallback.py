"""Production retrieval fallback tests outside the signed verifier package."""

import json
import hashlib
import unittest

from fam_os.core.production.retrieval_fallback import (
    deterministic_retrieval_candidate,
    normalize_local_retrieval_candidate,
)
from fam_os.verification.declarations import RetrievalCitationsVerification
from fam_os.verification.retrieval import (
    RetrievedSource,
    retrieval_query_obligation,
)
from fam_os.verification.retrieval_candidate import parse_retrieval_candidate


def _source(source_id: str, content: str) -> RetrievedSource:
    return RetrievedSource(
        source_id,
        f"file:///workspace/{source_id}.txt",
        content,
        hashlib.sha256(content.encode("utf-8")).hexdigest(),
        f"provenance-{source_id}",
    )


class ProductionRetrievalFallbackTests(unittest.TestCase):
    def test_exact_declared_lines_cover_query_without_model_claims(self) -> None:
        query = "What is the PHASE23 workspace fact?"
        specification = RetrievalCitationsVerification(
            (_source("workspace", "PHASE23 workspace fact is locally verified."),),
            retrieval_query_obligation(query),
        )

        candidate = deterministic_retrieval_candidate(query, specification)
        parsed = parse_retrieval_candidate(candidate, specification)

        self.assertEqual(parsed.answer, "PHASE23 workspace fact is locally verified.")
        self.assertEqual(parsed.claims[0].quote, parsed.answer)

    def test_valid_query_covered_candidate_is_preserved(self) -> None:
        query = "What is the PHASE23 workspace fact?"
        source = _source("workspace", "PHASE23 workspace fact is locally verified.")
        specification = RetrievalCitationsVerification(
            (source,), retrieval_query_obligation(query),
        )
        candidate = json.dumps({
            "answer": source.content,
            "claims": [{
                "text": source.content,
                "source_id": source.source_id,
                "quote": source.content,
            }],
        })

        self.assertEqual(
            normalize_local_retrieval_candidate(candidate, query, specification),
            candidate,
        )

    def test_unbound_declaration_does_not_change_model_candidate(self) -> None:
        specification = RetrievalCitationsVerification(
            (_source("workspace", "unbound source"),),
        )

        self.assertEqual(
            normalize_local_retrieval_candidate("model output", "query", specification),
            "model output",
        )
        with self.assertRaisesRegex(ValueError, "not query bound"):
            deterministic_retrieval_candidate("query", specification)

    def test_mismatched_query_cannot_reuse_declared_sources(self) -> None:
        specification = RetrievalCitationsVerification(
            (_source("workspace", "PHASE23 workspace fact is locally verified."),),
            retrieval_query_obligation("What is the PHASE23 workspace fact?"),
        )

        with self.assertRaisesRegex(ValueError, "does not match"):
            deterministic_retrieval_candidate("What is another fact?", specification)


if __name__ == "__main__":
    unittest.main()
