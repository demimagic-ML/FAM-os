"""Strict Console JSON translation into typed verifier declarations."""

from __future__ import annotations

import hashlib

from fam_os.verification import (
    ExactTextVerification,
    MathEquivalenceVerification,
    MediaArtifactTextVerification,
    PythonTestsVerification,
    RetrievalCitationsVerification,
    RetrievedSource,
    VerificationDeclaration,
    VerificationKind,
    contract_for_kind,
    retrieval_query_obligation,
)


def declaration_from_document(
    request_id: str, prompt: str, document: object,
) -> VerificationDeclaration:
    if not isinstance(document, dict):
        raise ValueError("verification must be an object")
    raw_kind = document.get("kind")
    if not isinstance(raw_kind, str):
        raise ValueError("verification kind must be text")
    kind = VerificationKind(raw_kind)
    specification = _specification(kind, prompt, document)
    return VerificationDeclaration(
        f"declaration-{request_id}", request_id,
        contract_for_kind(kind), specification,
    )


def _specification(kind: VerificationKind, prompt: str, document: dict):
    if kind is VerificationKind.EXACT_TEXT:
        _fields(document, {"kind", "expected_text"})
        return ExactTextVerification(_text(document, "expected_text"))
    if kind is VerificationKind.PYTHON_TESTS:
        _fields(document, {"kind", "bundle_id", "test_source"})
        source = _text(document, "test_source")
        return PythonTestsVerification(
            _text(document, "bundle_id"), source, _digest(source.encode("utf-8")),
        )
    if kind is VerificationKind.RETRIEVAL_CITATIONS:
        _fields(document, {"kind", "sources"})
        sources = document["sources"]
        if not isinstance(sources, list):
            raise ValueError("retrieval sources must be an array")
        return RetrievalCitationsVerification(
            tuple(_source(item) for item in sources),
            retrieval_query_obligation(prompt),
        )
    if kind is VerificationKind.MATH_EQUIVALENCE:
        _fields(document, {
            "kind", "reference_expression", "variable", "sample_points",
            "absolute_tolerance", "precision_digits",
        })
        points = document["sample_points"]
        precision = document["precision_digits"]
        if not isinstance(points, list) or any(not isinstance(item, str) for item in points):
            raise ValueError("math sample_points must be a string array")
        if not isinstance(precision, int) or isinstance(precision, bool):
            raise ValueError("math precision_digits must be an integer")
        return MathEquivalenceVerification(
            _text(document, "reference_expression"), _text(document, "variable"),
            tuple(points), _text(document, "absolute_tolerance"), precision,
        )
    if kind is VerificationKind.MEDIA_ARTIFACT_TEXT:
        _fields(document, {
            "kind", "artifact_path", "artifact_sha256", "expected_text",
            "maximum_artifact_bytes",
        })
        maximum = document["maximum_artifact_bytes"]
        if not isinstance(maximum, int) or isinstance(maximum, bool):
            raise ValueError("maximum_artifact_bytes must be an integer")
        return MediaArtifactTextVerification(
            _text(document, "artifact_path"), _text(document, "artifact_sha256"),
            _text(document, "expected_text"), maximum,
        )
    raise ValueError("verification kind is unsupported")


def _source(value: object) -> RetrievedSource:
    if not isinstance(value, dict):
        raise ValueError("retrieval source must be an object")
    _fields(value, {"source_id", "locator", "content", "provenance_id"})
    content = _text(value, "content")
    return RetrievedSource(
        _text(value, "source_id"), _text(value, "locator"), content,
        _digest(content.encode("utf-8")), _text(value, "provenance_id"),
    )


def _fields(document: dict, expected: set[str]) -> None:
    if set(document) != expected:
        raise ValueError("verification fields must match the selected kind exactly")


def _text(document: dict, name: str) -> str:
    value = document.get(name)
    if not isinstance(value, str):
        raise ValueError(f"verification {name} must be text")
    return value


def _digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()
