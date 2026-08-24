"""Canonical wheelhouse manifest creation and verification."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any


def file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def build_manifest(requirements: Path, wheelhouse: Path) -> dict[str, Any]:
    wheels = tuple(sorted(
        (
            {
                "bytes": path.stat().st_size,
                "filename": path.name,
                "sha256": file_sha256(path),
            }
            for path in wheelhouse.iterdir()
            if path.is_file() and path.suffix == ".whl"
        ),
        key=lambda item: str(item["filename"]),
    ))
    if not wheels:
        raise ValueError("training wheelhouse contains no wheels")
    document = {
        "contract_version": "fam.factory.training-wheelhouse/v1alpha1",
        "requirements_sha256": file_sha256(requirements),
        "wheels": wheels,
    }
    document["manifest_sha256"] = manifest_digest(document)
    return document


def verify_manifest(
    document: dict[str, Any], requirements: Path, wheelhouse: Path,
) -> None:
    if set(document) != {
        "contract_version", "requirements_sha256", "wheels", "manifest_sha256",
    }:
        raise ValueError("training wheelhouse manifest fields are invalid")
    if document["contract_version"] != "fam.factory.training-wheelhouse/v1alpha1":
        raise ValueError("training wheelhouse manifest version is invalid")
    if document["requirements_sha256"] != file_sha256(requirements):
        raise ValueError("training requirements changed after wheel resolution")
    if document["manifest_sha256"] != manifest_digest(document):
        raise ValueError("training wheelhouse manifest digest does not match")
    expected = build_manifest(requirements, wheelhouse)
    if expected["wheels"] != tuple(document["wheels"]):
        raise ValueError("training wheelhouse files changed after resolution")


def manifest_digest(document: dict[str, Any]) -> str:
    values = {key: value for key, value in document.items() if key != "manifest_sha256"}
    return hashlib.sha256(
        json.dumps(values, sort_keys=True, separators=(",", ":")).encode(),
    ).hexdigest()
