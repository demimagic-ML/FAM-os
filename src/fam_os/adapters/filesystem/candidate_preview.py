"""Bounded text-diff and binary-asset candidate preview rendering."""

import difflib
import mimetypes

from fam_os.core.engineering.transactions import CandidateOperation, CandidateOperationKind


def media_type(path: str, content: bytes | None) -> str | None:
    if content is None:
        return None
    guessed = mimetypes.guess_type(path, strict=False)[0]
    return guessed or ("text/plain" if is_text(content) else "application/octet-stream")


def render_preview(
    before: bytes | None,
    after: bytes | None,
    detected_media_type: str | None,
    operation: CandidateOperation,
) -> tuple[str, tuple[str, ...]]:
    risks = []
    if operation.kind in {
        CandidateOperationKind.DELETE,
        CandidateOperationKind.MOVE,
        CandidateOperationKind.SET_EXECUTABLE,
    }:
        risks.append(operation.kind.value)
    if after is not None and is_text(after) and (before is None or is_text(before)):
        before_lines = before.decode().splitlines() if before else []
        after_lines = after.decode().splitlines()
        value = "\n".join(difflib.unified_diff(
            before_lines, after_lines, "before", "after", lineterm="",
        ))
    else:
        value = (
            f"binary asset: media_type={detected_media_type}; "
            f"before_bytes={len(before or b'')}; after_bytes={len(after or b'')}"
        )
        risks.append("binary_asset")
    return value[:65_536], tuple(risks or ("content_change",))


def is_text(content: bytes) -> bool:
    try:
        content.decode("utf-8")
        return b"\x00" not in content
    except UnicodeDecodeError:
        return False
