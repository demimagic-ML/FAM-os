#!/usr/bin/env python3
"""Capture exact citation and provenance verification evidence."""

import argparse
import hashlib
import json
from dataclasses import asdict, replace
from pathlib import Path

from fam_os.verification import RetrievalCitation, RetrievalCitationVerifier, RetrievalClaim, RetrievedSource


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    content = "Resident Neural Fabric verifies cited source spans before release."
    quote = "verifies cited source spans"
    start = content.index(quote)
    source = RetrievedSource("source-1", "file:///FAM_OS/README.md", content, digest(content), "capture-local-1")
    citation = RetrievalCitation("citation-1", source.source_id, start, start + len(quote), digest(quote))
    claim = RetrievalClaim("claim-1", (citation.citation_id,))
    verifier = RetrievalCitationVerifier()
    accepted = verifier.verify("retrieval-good", (source,), (citation,), (claim,))
    tampered = verifier.verify("retrieval-tampered", (replace(source, content=content + " changed"),), (citation,), (claim,))
    report = {"phase": "8.6", "accepted": asdict(accepted), "tampered": asdict(tampered), "acceptance": accepted.passed and not tampered.passed}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["acceptance"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
