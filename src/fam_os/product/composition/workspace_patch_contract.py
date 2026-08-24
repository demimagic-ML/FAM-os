"""Validation and serialization helpers for bounded workspace patches."""

from __future__ import annotations

import base64
import difflib
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path, PurePosixPath
from typing import Literal, Sequence, TypedDict, cast
from urllib.parse import unquote, urlsplit

from fam_os.applications.payloads import JsonObject


MAXIMUM_CHANGES = 4
MAXIMUM_FILE_BYTES = 32_768
MAXIMUM_TOTAL_BYTES = 65_536
MAXIMUM_PLAN_STEPS = 12


class PatchChange(TypedDict):
    path: str
    content: str
    expected_sha256: str


class RevisionRecord(TypedDict):
    path: str
    before_sha256: str
    after_sha256: str


class PatchRecord(RevisionRecord):
    target: Path
    before_content: bytes
    after_content: bytes


class ReversalChange(RevisionRecord):
    before_content_base64: str


class RestoreRecord(RevisionRecord):
    target: Path
    before_content: bytes


def patch_parameters(parameters: Mapping) -> tuple[tuple[str, ...], tuple[PatchChange, ...]]:
    if set(parameters) != {"plan", "changes"}:
        raise ValueError("workspace patch parameters are not exact")
    plan = parameters["plan"]
    changes = parameters["changes"]
    if (
        not isinstance(plan, (list, tuple))
        or not 1 <= len(plan) <= MAXIMUM_PLAN_STEPS
        or any(
            not isinstance(item, str) or not item.strip() or len(item) > 500
            for item in plan
        )
    ):
        raise ValueError("workspace patch plan is invalid")
    if (
        not isinstance(changes, (list, tuple))
        or not 1 <= len(changes) <= MAXIMUM_CHANGES
    ):
        raise ValueError("workspace patch change count is invalid")
    parsed: list[PatchChange] = []
    total = 0
    for change in changes:
        if not isinstance(change, Mapping) or set(change) != {
            "path", "content", "expected_sha256",
        }:
            raise ValueError("workspace patch change is invalid")
        path, content, expected = (
            change["path"], change["content"], change["expected_sha256"],
        )
        if not isinstance(path, str) or not isinstance(content, str):
            raise ValueError("workspace patch path and content must be text")
        if not isinstance(expected, str) or len(expected) != 64:
            raise ValueError("workspace patch expected hash is invalid")
        size = len(content.encode("utf-8"))
        total += size
        if size > MAXIMUM_FILE_BYTES or total > MAXIMUM_TOTAL_BYTES:
            raise ValueError("workspace patch content exceeds its byte bound")
        relative_path(path)
        parsed.append({"path": path, "content": content, "expected_sha256": expected})
    if len({item["path"] for item in parsed}) != len(parsed):
        raise ValueError("workspace patch paths must be unique")
    return tuple(plan), tuple(parsed)


def restore_token(parameters: Mapping, workspace: Path) -> tuple[ReversalChange, ...]:
    if set(parameters) != {"reversal_token"} or not isinstance(
        parameters["reversal_token"], str,
    ):
        raise ValueError("workspace restore parameters are invalid")
    value = json.loads(parameters["reversal_token"])
    if not isinstance(value, dict) or set(value) != {"workspace", "changes"}:
        raise ValueError("workspace restore token is invalid")
    if value["workspace"] != str(workspace):
        raise PermissionError("workspace restore token has a different scope")
    if (
        not isinstance(value["changes"], list)
        or not 1 <= len(value["changes"]) <= MAXIMUM_CHANGES
    ):
        raise ValueError("workspace restore token change count is invalid")
    for change in value["changes"]:
        if not isinstance(change, dict) or set(change) != {
            "path", "before_sha256", "after_sha256", "before_content_base64",
        }:
            raise ValueError("workspace restore token change is invalid")
        relative_path(change["path"])
        if any(not isinstance(change[key], str) for key in change):
            raise ValueError("workspace restore token values must be text")
        if len(change["before_sha256"]) != 64 or len(change["after_sha256"]) != 64:
            raise ValueError("workspace restore token hashes are invalid")
    return tuple(cast(ReversalChange, item) for item in value["changes"])


def encode_token(workspace: Path, records: Sequence[PatchRecord]) -> str:
    return json.dumps({
        "workspace": str(workspace),
        "changes": [
            {
                "path": item["path"],
                "before_sha256": item["before_sha256"],
                "after_sha256": item["after_sha256"],
                "before_content_base64": base64.b64encode(
                    item["before_content"],
                ).decode("ascii"),
            }
            for item in records
        ],
    }, sort_keys=True, separators=(",", ":"))


def decode_before_content(change: ReversalChange) -> bytes:
    content = base64.b64decode(
        change["before_content_base64"].encode("ascii"), validate=True,
    )
    if hashlib.sha256(content).hexdigest() != change["before_sha256"]:
        raise ValueError("workspace restore token content changed")
    return content


def file_preview(record: PatchRecord) -> JsonObject:
    before = record["before_content"].decode("utf-8")
    after = record["after_content"].decode("utf-8")
    lines = list(difflib.unified_diff(
        before.splitlines(), after.splitlines(),
        fromfile=f"a/{record['path']}", tofile=f"b/{record['path']}", lineterm="",
    ))
    return {
        "path": record["path"],
        "before_sha256": record["before_sha256"],
        "after_sha256": record["after_sha256"],
        "diff": "\n".join(lines[:400]),
        "diff_truncated": len(lines) > 400,
    }


def target_path(workspace: Path, relative: str) -> Path:
    target = workspace.joinpath(*relative_path(relative).parts)
    if not target.is_file():
        raise ValueError("workspace patch can modify only observed existing files")
    return target


def relative_path(value: str) -> PurePosixPath:
    path = PurePosixPath(value)
    if (
        not value or len(value.encode("utf-8")) > 4096 or path.is_absolute()
        or any(part in {"", ".", ".."} for part in path.parts)
        or "\\" in value
    ):
        raise ValueError("workspace patch path is invalid")
    return path


def workspace_path(uri: str | None) -> Path:
    if not isinstance(uri, str):
        raise ValueError("workspace patch resource is absent")
    parsed = urlsplit(uri)
    if parsed.scheme != "file" or parsed.netloc not in {"", "localhost"}:
        raise ValueError("workspace patch resource must be a local file URI")
    path = Path(unquote(parsed.path))
    if not path.is_absolute() or not path.is_dir():
        raise ValueError("workspace patch resource must be a directory")
    return path


def combined_revision(
    records: Sequence[RevisionRecord],
    key: Literal["before_sha256", "after_sha256"],
) -> str:
    content = "\n".join(f"{item['path']}:{item[key]}" for item in records).encode()
    return f"workspace-patch:sha256:{hashlib.sha256(content).hexdigest()}"
