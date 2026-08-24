"""Strict contracts for bounded model-proposed candidate changes."""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
import hashlib
import json
from pathlib import PurePosixPath

from fam_os.core.engineering._validation import digest, relative_path, text, texts
from fam_os.core.engineering.version import ENGINEERING_CONTRACT_VERSION


class GeneratedCandidateOperationKind(StrEnum):
    CREATE_DIRECTORY = "create_directory"
    CREATE_FILE = "create_file"
    REPLACE_FILE = "replace_file"
    MOVE = "move"
    DELETE = "delete"


@dataclass(frozen=True, slots=True)
class CandidateContextDocument:
    path: str
    content_sha256: str
    content: str

    def __post_init__(self) -> None:
        _candidate_path(self.path, "context document path")
        digest(self.content_sha256, "context document digest", required=True)
        if hashlib.sha256(self.content.encode("utf-8")).hexdigest() != self.content_sha256:
            raise ValueError("candidate context document digest is invalid")


@dataclass(frozen=True, slots=True)
class CandidateGenerationContext:
    candidate_id: str
    baseline_tree_sha256: str
    inventory_paths: tuple[str, ...]
    documents: tuple[CandidateContextDocument, ...]
    truncated: bool
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        text(self.candidate_id, "candidate_id")
        digest(self.baseline_tree_sha256, "baseline_tree_sha256", required=True)
        texts(self.inventory_paths, "candidate inventory paths")
        if self.inventory_paths != tuple(sorted(self.inventory_paths)):
            raise ValueError("candidate inventory paths must be sorted")
        document_paths = tuple(item.path for item in self.documents)
        texts(document_paths, "candidate context paths")
        if not set(document_paths).issubset(self.inventory_paths):
            raise ValueError("candidate context document is absent from inventory")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("candidate generation context version is unsupported")


@dataclass(frozen=True, slots=True)
class GeneratedCandidateOperation:
    kind: GeneratedCandidateOperationKind
    path: str
    content: str | None = None
    source_path: str | None = None
    media_type: str | None = None

    def __post_init__(self) -> None:
        _candidate_path(self.path, "generated operation path")
        if self.source_path is not None:
            _candidate_path(self.source_path, "generated operation source_path")
        content_kind = self.kind in {
            GeneratedCandidateOperationKind.CREATE_FILE,
            GeneratedCandidateOperationKind.REPLACE_FILE,
        }
        if content_kind != (self.content is not None):
            raise ValueError("generated file operation content is inconsistent")
        if (self.kind is GeneratedCandidateOperationKind.MOVE) != (
            self.source_path is not None
        ):
            raise ValueError("generated move source is inconsistent")
        if self.media_type is not None:
            text(self.media_type, "generated operation media_type")
            if not content_kind or not _media_type(self.media_type):
                raise ValueError("generated operation media_type is invalid")


@dataclass(frozen=True, slots=True)
class GeneratedCandidatePlan:
    summary: str
    operations: tuple[GeneratedCandidateOperation, ...]
    contract_version: str = ENGINEERING_CONTRACT_VERSION

    def __post_init__(self) -> None:
        text(self.summary, "generated plan summary")
        if len(self.summary.encode("utf-8")) > 4_096:
            raise ValueError("generated plan summary exceeds its bound")
        if not self.operations:
            raise ValueError("generated candidate plan requires operations")
        paths = tuple(item.path for item in self.operations)
        if len(paths) != len(set(paths)):
            raise ValueError("generated candidate plan has duplicate targets")
        if self.contract_version != ENGINEERING_CONTRACT_VERSION:
            raise ValueError("generated candidate plan version is unsupported")


def parse_generated_candidate_plan(
    document: str, *, maximum_operations: int, maximum_content_bytes: int,
) -> GeneratedCandidatePlan:
    """Parse strict untrusted JSON without granting authority or trusting hashes."""
    if maximum_operations <= 0 or maximum_content_bytes <= 0:
        raise ValueError("generated plan bounds must be positive")
    if len(document.encode("utf-8")) > maximum_content_bytes + 65_536:
        raise ValueError("generated plan document exceeds its bound")
    value = json.loads(
        document, object_pairs_hook=_unique_object,
        parse_constant=lambda item: (_ for _ in ()).throw(
            ValueError(f"invalid JSON constant: {item}")
        ),
    )
    _exact_keys(value, {"contract_version", "summary", "operations"}, "plan")
    if value["contract_version"] != ENGINEERING_CONTRACT_VERSION:
        raise ValueError("generated candidate plan version is unsupported")
    rows = value["operations"]
    if not isinstance(rows, list) or not 0 < len(rows) <= maximum_operations:
        raise ValueError("generated candidate operation count is invalid")
    operations = tuple(_operation(row) for row in rows)
    content_bytes = sum(len((item.content or "").encode("utf-8")) for item in operations)
    if content_bytes > maximum_content_bytes:
        raise ValueError("generated candidate content exceeds its bound")
    return GeneratedCandidatePlan(value["summary"], operations)


def generated_candidate_plan_digest(plan: GeneratedCandidatePlan) -> str:
    value = {
        "contract_version": plan.contract_version,
        "operations": [
            {
                "content": item.content,
                "kind": item.kind.value,
                "media_type": item.media_type,
                "path": item.path,
                "source_path": item.source_path,
            }
            for item in plan.operations
        ],
        "summary": plan.summary,
    }
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def candidate_generation_context_digest(context: CandidateGenerationContext) -> str:
    value = {
        "baseline_tree_sha256": context.baseline_tree_sha256,
        "candidate_id": context.candidate_id,
        "documents": [
            {"path": item.path, "content_sha256": item.content_sha256}
            for item in context.documents
        ],
        "inventory_paths": list(context.inventory_paths),
        "truncated": context.truncated,
    }
    payload = json.dumps(value, sort_keys=True, separators=(",", ":")).encode()
    return hashlib.sha256(payload).hexdigest()


def _operation(value) -> GeneratedCandidateOperation:
    if not isinstance(value, dict):
        raise ValueError("generated candidate operation must be an object")
    required = {"kind", "path"}
    allowed = required | {"content", "source_path", "media_type"}
    if not required.issubset(value) or not set(value).issubset(allowed):
        raise ValueError("generated candidate operation fields are invalid")
    try:
        kind = GeneratedCandidateOperationKind(value["kind"])
    except (TypeError, ValueError) as error:
        raise ValueError("generated candidate operation kind is invalid") from error
    for name in allowed & set(value):
        if name == "kind":
            continue
        if value[name] is not None and not isinstance(value[name], str):
            raise ValueError(f"generated candidate operation {name} must be text or null")
    return GeneratedCandidateOperation(
        kind, value["path"], value.get("content"), value.get("source_path"),
        value.get("media_type"),
    )


def _unique_object(pairs):
    value = {}
    for key, item in pairs:
        if key in value:
            raise ValueError("generated candidate JSON has a duplicate key")
        value[key] = item
    return value


def _exact_keys(value, expected, label) -> None:
    if not isinstance(value, dict) or set(value) != expected:
        raise ValueError(f"generated candidate {label} fields are invalid")


def _candidate_path(value: str, label: str) -> None:
    relative_path(value, label)
    first = PurePosixPath(value).parts[0]
    if first in {".git", ".fam"}:
        raise PermissionError("generated candidate path enters protected metadata")


def _media_type(value: str) -> bool:
    return "/" in value and not any(character.isspace() for character in value)
