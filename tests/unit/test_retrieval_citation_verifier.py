import hashlib
import unittest
from dataclasses import replace

from fam_os.verification import (
    RetrievalCitation, RetrievalCitationVerifier, RetrievalClaim, RetrievedSource,
)


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


CONTENT = "FAM verifies every cited span before releasing a retrieval answer."
SOURCE = RetrievedSource("source-1", "file:///docs/fam.md", CONTENT, digest(CONTENT), "capture-1")
QUOTE = "every cited span"
START = CONTENT.index(QUOTE)
CITATION = RetrievalCitation("citation-1", "source-1", START, START + len(QUOTE), digest(QUOTE))


class RetrievalCitationVerifierTests(unittest.TestCase):
    def test_exact_source_span_and_provenance_release_claim(self) -> None:
        report = RetrievalCitationVerifier().verify(
            "retrieval-1", (SOURCE,), (CITATION,), (RetrievalClaim("claim-1", ("citation-1",)),)
        )
        self.assertTrue(report.passed)
        self.assertEqual(("claim-1",), report.verified_claim_ids)

    def test_tampered_source_quote_and_missing_citation_withhold(self) -> None:
        cases = (
            ((replace(SOURCE, content=CONTENT + "!"),), (CITATION,)),
            ((SOURCE,), (replace(CITATION, quoted_text_sha256="0" * 64),)),
            ((SOURCE,), ()),
        )
        for sources, citations in cases:
            with self.subTest(citations=len(citations)):
                report = RetrievalCitationVerifier().verify(
                    "retrieval-2", sources, citations,
                    (RetrievalClaim("claim-1", ("citation-1",)),),
                )
                self.assertFalse(report.passed)
                self.assertEqual(("claim-1",), report.rejected_claim_ids)


if __name__ == "__main__":
    unittest.main()
