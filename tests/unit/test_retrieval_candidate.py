import hashlib
import json
import unittest

from fam_os.verification import (
    RetrievalCitationsVerification,
    RetrievedSource,
    retrieval_query_obligation,
)
from fam_os.verification.retrieval_candidate import parse_retrieval_candidate


CONTENT = "FAM_OS runs as local operating-system intelligence above Linux."


def _digest(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _specification() -> RetrievalCitationsVerification:
    return RetrievalCitationsVerification(
        (RetrievedSource(
            "source-1", "package://identity", CONTENT, _digest(CONTENT), "package-1",
        ),),
        retrieval_query_obligation("What is FAM_OS?"),
    )


class RetrievalCandidateTests(unittest.TestCase):
    def test_answer_is_exact_ordered_extractive_claim_text(self) -> None:
        candidate = json.dumps({
            "answer": CONTENT,
            "claims": [
                {"text": CONTENT, "source_id": "source-1", "quote": CONTENT},
            ],
        })

        parsed = parse_retrieval_candidate(candidate, _specification())

        self.assertEqual(1, len(parsed.claims))
        self.assertEqual("citation-1", parsed.claims[0].citation.citation_id)
        self.assertEqual(CONTENT, parsed.answer)

    def test_rejects_unclaimed_answer_fabricated_quote_or_paraphrase(self) -> None:
        cases = (
            {
                "answer": "FAM_OS is local. Extra unsupported sentence.",
                "claims": [{
                    "text": "FAM_OS is local.", "source_id": "source-1",
                    "quote": "FAM_OS runs as local",
                }],
            },
            {
                "answer": "FAM_OS is local.",
                "claims": [{
                    "text": "FAM_OS is local.", "source_id": "source-1",
                    "quote": "not in the source",
                }],
            },
            {
                "answer": "FAM_OS is local.",
                "claims": [{
                    "text": "FAM_OS is local.", "source_id": "source-1",
                    "quote": "FAM_OS runs as local",
                }],
            },
        )
        for value in cases:
            with self.subTest(value=value["answer"]):
                with self.assertRaises(ValueError):
                    parse_retrieval_candidate(json.dumps(value), _specification())

    def test_rejects_unknown_candidate_or_claim_fields(self) -> None:
        value = {
            "answer": "FAM_OS is local.",
            "claims": [{
                "text": "FAM_OS is local.", "source_id": "source-1",
                "quote": "FAM_OS runs as local", "confidence": 1,
            }],
        }
        with self.assertRaisesRegex(ValueError, "claim fields"):
            parse_retrieval_candidate(json.dumps(value), _specification())


if __name__ == "__main__":
    unittest.main()
