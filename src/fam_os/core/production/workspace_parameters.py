"""Bind model-proposed workspace changes to exact authorized observations."""

from __future__ import annotations

from collections.abc import Mapping

from fam_os.applications import WORKSPACE_PATCH_CAPABILITY


class WorkspacePatchScopeUnsupported(ValueError):
    """The requested operation cannot be represented by the bounded patch tool."""


def bind_workspace_patch_parameters(
    capability_id: str, parameters: dict, observations,
) -> dict:
    if capability_id != WORKSPACE_PATCH_CAPABILITY:
        return parameters
    if set(parameters) == {"unavailable_reason"}:
        reason = parameters["unavailable_reason"]
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("workspace patch unavailable reason must be nonempty text")
        raise WorkspacePatchScopeUnsupported(reason.strip())
    if set(parameters) != {"plan", "changes"}:
        raise ValueError("workspace patch candidate must contain plan and changes")
    plan = parameters["plan"]
    if (
        not isinstance(plan, list)
        or not 1 <= len(plan) <= 12
        or any(not isinstance(item, str) or not item.strip() for item in plan)
    ):
        raise ValueError("workspace patch plan must contain one to twelve text steps")
    changes = parameters["changes"]
    if not isinstance(changes, list) or not 1 <= len(changes) <= 4:
        raise ValueError("workspace patch must contain one to four changes")
    observed = _observed_documents(observations)
    bound = []
    for change in changes:
        if not isinstance(change, dict) or set(change) != {"path", "content"}:
            raise ValueError("workspace patch change must contain path and content")
        path = change.get("path")
        if not isinstance(path, str) or path not in observed:
            raise ValueError("workspace patch may modify only an observed document")
        content = change.get("content")
        if not isinstance(content, str):
            raise ValueError("workspace patch content must be complete UTF-8 text")
        bound.append({
            "path": path,
            "content": content,
            "expected_sha256": observed[path],
        })
    paths = tuple(item["path"] for item in bound)
    plan = [
        f"Update observed file {path} using the approved diff."
        for path in paths
    ]
    plan.append(
        "Re-observe and verify every changed file after the atomic write."
    )
    return {"plan": plan, "changes": bound}


def workspace_parameter_feedback(
    error: ValueError, observations, *, escalation: bool,
) -> str:
    marker = (
        "[workspace-parameter-escalation]"
        if escalation else "[workspace-parameter-repair]"
    )
    paths = tuple(sorted(_observed_documents(observations)))
    allowed = "\n".join(f"- {path}" for path in paths[:32]) or "- none"
    return (
        f"{marker}\n"
        "Core rejected the previous workspace action object. "
        f"Exact structural error: {str(error)[:500]}\n"
        "Return only strict JSON. Use exactly one to four of these observed paths:\n"
        f"{allowed}\n"
        "Each change requires exactly path and content; content is the complete new "
        "UTF-8 file. If the request needs a new or deleted file, commands, or cannot "
        "fit those observed paths, return exactly "
        '{"unavailable_reason":"brief factual reason"}.'
    )


def workspace_candidate_instruction(capability_ids: tuple[str, ...]) -> str:
    if WORKSPACE_PATCH_CAPABILITY not in capability_ids:
        return (
            "Return only a JSON object accepted by the requested action capability. "
            "Do not include Markdown fences or explanation."
        )
    return (
        "Return only one JSON object. For an executable existing-file edit use "
        "exactly this shape: "
        '{"plan":["specific step derived from the current request"],"changes":['
        '{"path":"exact/observed/relative/path","content":"complete UTF-8 file"}]}. '
        "Never copy schema placeholders literally. Use one to twelve concise plan "
        "steps and one to four changes. Paths must be "
        "copied exactly from retrieved workspace documents. Content must be the complete "
        "new file content, not a diff. Modify only existing observed files. Do not include "
        "hashes, Markdown fences, commands, commentary, or claims that work already ran. "
        "If the request requires creating or deleting files, running commands, modifying "
        "more than four files, or lacks enough detail to produce complete content, return "
        'exactly {"unavailable_reason":"brief factual reason"}.'
    )


def _observed_documents(observations) -> dict[str, str]:
    values: dict[str, str] = {}
    for observation in observations:
        payload = observation.payload
        documents = payload.get("documents") if isinstance(payload, Mapping) else None
        if not isinstance(documents, (list, tuple)):
            continue
        for document in documents:
            if not isinstance(document, Mapping):
                continue
            path, digest = document.get("path"), document.get("sha256")
            if isinstance(path, str) and isinstance(digest, str) and len(digest) == 64:
                values[path] = digest
    return values
