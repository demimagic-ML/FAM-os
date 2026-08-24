"""Exact local fallback generation for query-bound grounded retrieval."""

from __future__ import annotations

import json

from fam_os.verification.declarations import RetrievalCitationsVerification
from fam_os.verification.retrieval import (
    missing_retrieval_terms,
    retrieval_query_obligation,
    retrieval_terms,
)
from fam_os.verification.retrieval_candidate import parse_retrieval_candidate


def normalize_local_retrieval_candidate(
    candidate: str,
    query: str,
    specification: RetrievalCitationsVerification,
) -> str:
    """Keep a valid covered candidate or derive one from exact declared bytes."""

    obligation = specification.query
    if obligation is None:
        return candidate
    try:
        parsed = parse_retrieval_candidate(candidate, specification)
        evidence = (parsed.answer,) + tuple(item.quote for item in parsed.claims)
        if not missing_retrieval_terms(evidence, obligation):
            return candidate
    except (KeyError, TypeError, ValueError):
        pass
    try:
        return deterministic_retrieval_candidate(query, specification)
    except ValueError:
        return candidate


def deterministic_retrieval_candidate(
    query: str,
    specification: RetrievalCitationsVerification,
) -> str:
    """Select exact declared source lines that cover every query obligation."""

    obligation = specification.query
    if obligation is None:
        raise ValueError("retrieval declaration is not query bound")
    if obligation != retrieval_query_obligation(query):
        raise ValueError("retrieval query does not match its declaration")
    available = [
        (source.source_id, line.strip())
        for source in specification.sources
        for line in source.content.splitlines()
        if line.strip()
    ]
    selected: list[tuple[str, str]] = []
    remaining = set(obligation.required_terms)
    while remaining:
        scored = tuple(
            (
                len(remaining.intersection(retrieval_terms(line))),
                index,
                source_id,
                line,
            )
            for index, (source_id, line) in enumerate(available)
        )
        score, index, source_id, line = max(
            scored,
            key=lambda item: (item[0], -item[1]),
            default=(0, -1, "", ""),
        )
        if score <= 0:
            raise ValueError(
                "declared retrieval sources cannot cover every required query term"
            )
        selected.append((source_id, line))
        remaining.difference_update(retrieval_terms(line))
        available.pop(index)
    claims = tuple(
        {"text": line, "source_id": source_id, "quote": line}
        for source_id, line in selected
    )
    document = json.dumps(
        {"answer": "\n".join(line for _, line in selected), "claims": claims},
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )
    parsed = parse_retrieval_candidate(document, specification)
    evidence = (parsed.answer,) + tuple(item.quote for item in parsed.claims)
    if missing_retrieval_terms(evidence, obligation):
        raise ValueError("deterministic retrieval candidate is query incomplete")
    return document
