"""Exact final candidates for observations that need no model synthesis."""

from __future__ import annotations

import json
from collections.abc import Mapping

from fam_os.core.lifecycle import CandidateEvidenceRecord
from fam_os.core.production.contracts import InferenceExecutionState
from fam_os.core.production.execution_state import replace_execution


_SYNTHESIS_WORDS = (
    "analyze", "explain", "review", "summarize", "architecture", "problem",
)
_LISTING_PHRASES = (
    "list ", "what is in", "what's in", "whats in", "show files",
    "folder contents", "directory contents", "top-level files",
)
_WORKSPACE_PHRASES = (
    "current workspace", "selected workspace", "which workspace",
    "what workspace", "what's your workspace", "whats your workspace",
)


def seed_exact_observation_candidate(repositories, application, inference):
    """Persist an exact listing candidate when prose inference adds no value."""

    prompt = application.routed.admitted.request.prompt
    content = exact_directory_listing(prompt, application.observations)
    if content is None:
        return None
    candidate_id = f"candidate-{application.request_id}-exact-observation"
    candidate = CandidateEvidenceRecord(
        candidate_id, application.request_id,
        f"plan-{application.request_id}", content,
    )
    if not repositories.final_evidence.add_candidate(candidate):
        existing = repositories.final_evidence.candidate(candidate_id)
        if existing != candidate:
            raise RuntimeError("exact observation candidate identity conflict")
    return replace_execution(
        repositories, inference,
        state=InferenceExecutionState.CANDIDATE_READY,
        candidate_id=candidate_id,
    )


def exact_directory_listing(prompt: str, observations) -> str | None:
    """Render an observed directory listing without rewriting its names."""

    normalized = " ".join(prompt.casefold().split())
    workspace_question = any(phrase in normalized for phrase in _WORKSPACE_PHRASES)
    if any(word in normalized for word in _SYNTHESIS_WORDS) or not (
        workspace_question or any(phrase in normalized for phrase in _LISTING_PHRASES)
    ):
        return None
    listing = next(
        (
            item.payload for item in reversed(observations)
            if isinstance(item.payload, Mapping)
            and isinstance(item.payload.get("entries"), (list, tuple))
        ),
        None,
    )
    if listing is None:
        return None
    entries = tuple(_entry(item) for item in listing["entries"])
    if any(item is None for item in entries):
        return None
    exact = tuple(item for item in entries if item is not None)
    path = listing.get("path")
    if workspace_question and isinstance(path, str):
        heading = f"The selected workspace is {_quoted(path)}. Its observed top-level contents are:"
    else:
        heading = (
            f"Observed top-level contents of {_quoted(path)}:"
            if isinstance(path, str) else "Observed top-level contents:"
        )
    lines = [heading]
    for kind, label in (("directory", "Directories"), ("file", "Files")):
        names = tuple(name for name, entry_kind in exact if entry_kind == kind)
        if names:
            lines.extend(("", f"{label} ({len(names)}):"))
            lines.extend(f"- {_quoted(name)}" for name in names)
    other = tuple(name for name, kind in exact if kind not in {"directory", "file"})
    if other:
        lines.extend(("", f"Other entries ({len(other)}):"))
        lines.extend(f"- {_quoted(name)}" for name in other)
    if listing.get("truncated") is True:
        lines.extend(("", "The bounded observation was truncated."))
    return "\n".join(lines)


def _entry(value) -> tuple[str, str] | None:
    if not isinstance(value, Mapping):
        return None
    name, kind = value.get("name"), value.get("kind")
    if not isinstance(name, str) or not isinstance(kind, str):
        return None
    return name, kind


def _quoted(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)
