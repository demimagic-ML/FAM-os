"""Workspace-scoped file and Git tools for the iterative agent runtime."""

from __future__ import annotations

import hashlib
import os
import subprocess
from pathlib import Path, PurePosixPath

from fam_os.core.agent import (
    AgentToolDescriptor,
    AgentToolEffect,
    AgentToolExecution,
    AgentToolRegistry,
)


class WorkspaceAgentTools:
    def __init__(
        self,
        workspace_root: Path,
        *,
        maximum_read_bytes: int = 24_576,
        maximum_result_bytes: int = 16_384,
    ) -> None:
        root = workspace_root.resolve(strict=True)
        if not root.is_dir() or root.is_symlink():
            raise PermissionError("agent workspace must be a real directory")
        self.root = root
        self.maximum_read_bytes = maximum_read_bytes
        self.maximum_result_bytes = maximum_result_bytes

    @property
    def git_available(self) -> bool:
        return self._git_available()

    def register(self, registry: AgentToolRegistry) -> None:
        registry.register(_descriptor(
            "list_directory", "List one relative workspace directory; globs are not accepted.",
            AgentToolEffect.OBSERVE,
            {"path": {"type": "string", "description": (
                "Directory relative to the selected workspace; use '.' for "
                "the selected folder itself."
            )}},
        ), self.list_directory)
        registry.register(_descriptor(
            "read_file", (
                "Read a bounded page of one relative UTF-8 workspace file. Use "
                "next_offset from the result to continue large files; globs are not accepted."
            ),
            AgentToolEffect.OBSERVE,
            {
                "path": {"type": "string", "description": (
                    "File path relative to the selected workspace."
                )},
                "offset_bytes": {"type": "integer"},
                "maximum_bytes": {"type": "integer"},
            }, required=("path",),
        ), self.read_file)
        registry.register(_descriptor(
            "search_text", (
                "Search a relative workspace file or directory recursively for a literal "
                "string. Use '.' for the whole workspace; globs are not accepted."
            ),
            AgentToolEffect.OBSERVE,
            {"query": {"type": "string"}, "path": {"type": "string"}},
            required=("query", "path"),
        ), self.search_text)
        registry.register(_descriptor(
            "write_file", "Create or replace one UTF-8 workspace file.",
            AgentToolEffect.WORKSPACE_WRITE,
            {
                "path": {"type": "string"},
                "content": {"type": "string"},
                "expected_sha256": {"type": ["string", "null"]},
            }, required=("path", "content"),
        ), self.write_file)
        registry.register(_descriptor(
            "create_directory", "Create one relative workspace directory.",
            AgentToolEffect.WORKSPACE_WRITE,
            {"path": {"type": "string"}}, required=("path",),
        ), self.create_directory)
        registry.register(_descriptor(
            "apply_patch", "Apply a unified Git patch inside the workspace.",
            AgentToolEffect.WORKSPACE_WRITE,
            {"patch": {"type": "string"}}, required=("patch",),
        ), self.apply_patch)
        registry.register(_descriptor(
            "delete_path", "Delete one workspace file or empty directory.",
            AgentToolEffect.WORKSPACE_WRITE,
            {"path": {"type": "string"}}, required=("path",),
        ), self.delete_path)
        registry.register(_descriptor(
            "move_path", "Move a file or directory inside the workspace.",
            AgentToolEffect.WORKSPACE_WRITE,
            {"source": {"type": "string"}, "destination": {"type": "string"}},
            required=("source", "destination"),
        ), self.move_path)
        if self._git_available():
            registry.register(_descriptor(
                "git_status", "Show the workspace Git status.",
                AgentToolEffect.OBSERVE, {},
            ), self.git_status)
            registry.register(_descriptor(
                "git_diff", "Show the current workspace Git diff.",
                AgentToolEffect.OBSERVE,
                {"staged": {"type": "boolean"}},
            ), self.git_diff)

    def list_directory(self, arguments: dict[str, object]) -> str:
        path = self._path(_text(arguments, "path", default="."), must_exist=True)
        if not path.is_dir():
            raise ValueError("list_directory path is not a directory")
        rows = []
        for item in sorted(path.iterdir(), key=lambda value: value.name):
            if item.is_symlink():
                kind = "symlink"
            elif item.is_dir():
                kind = "directory"
            elif item.is_file():
                kind = "file"
            else:
                kind = "other"
            rows.append(f"{kind}\t{item.name}")
        return _bounded(
            "\n".join(rows) or "Directory is empty.",
            self.maximum_result_bytes,
        )

    def read_file(self, arguments: dict[str, object]) -> str:
        _exact(arguments, {"path", "offset_bytes", "maximum_bytes"}, optional=True)
        path = self._path(_text(arguments, "path"), must_exist=True)
        if not path.is_file() or path.is_symlink():
            raise ValueError("read_file path is not a regular file")
        offset = arguments.get("offset_bytes", 0)
        maximum = arguments.get("maximum_bytes", self.maximum_read_bytes)
        if not isinstance(offset, int) or isinstance(offset, bool) or offset < 0:
            raise ValueError("read_file offset_bytes must be a non-negative integer")
        if (
            not isinstance(maximum, int) or isinstance(maximum, bool)
            or not 1 <= maximum <= self.maximum_read_bytes
        ):
            raise ValueError("read_file maximum_bytes is outside its bound")
        size = path.stat().st_size
        if offset > size:
            raise ValueError("read_file offset exceeds file size")
        with path.open("rb") as stream:
            digest = hashlib.file_digest(stream, "sha256").hexdigest()
            stream.seek(offset)
            content = stream.read(maximum)
        text = content.decode("utf-8", "replace")
        end = offset + len(content)
        next_offset = end if end < size else None
        return (
            f"sha256={digest}\nbytes={offset}-{end}/{size}\n"
            f"next_offset={next_offset}\n{text}"
        )

    def search_text(self, arguments: dict[str, object]) -> str:
        query = _text(arguments, "query")
        start = self._path(_text(arguments, "path", default="."), must_exist=True)
        files = (start,) if start.is_file() else self._walk_files(start)
        rows: list[str] = []
        used = 0
        for path in files:
            try:
                content = path.read_bytes()
                if len(content) > self.maximum_read_bytes or b"\0" in content:
                    continue
                lines = content.decode("utf-8").splitlines()
            except (OSError, UnicodeDecodeError):
                continue
            relative = path.relative_to(self.root).as_posix()
            for number, line in enumerate(lines, 1):
                if query in line:
                    row = f"{relative}:{number}:{line}"
                    encoded = len(row.encode("utf-8")) + 1
                    if used + encoded > self.maximum_result_bytes:
                        return "\n".join((*rows, "[results truncated]"))
                    rows.append(row)
                    used += encoded
        return "\n".join(rows) or "No matches."

    def write_file(self, arguments: dict[str, object]) -> AgentToolExecution:
        path = self._path(_text(arguments, "path"), must_exist=False)
        content = _text(arguments, "content", allow_empty=True).encode("utf-8")
        expected = arguments.get("expected_sha256")
        if expected is not None and not isinstance(expected, str):
            raise ValueError("expected_sha256 must be text or null")
        if path.exists():
            if not path.is_file() or path.is_symlink():
                raise ValueError("write_file target is not a regular file")
            actual = hashlib.sha256(path.read_bytes()).hexdigest()
            if expected is not None and actual != expected:
                raise RuntimeError("write_file precondition changed")
        elif expected is not None:
            raise RuntimeError("write_file expected an existing file")
        self._ensure_parent(path)
        temporary = path.with_name(f".{path.name}.fam-agent-{os.getpid()}")
        try:
            temporary.write_bytes(content)
            os.replace(temporary, path)
        finally:
            temporary.unlink(missing_ok=True)
        relative = path.relative_to(self.root).as_posix()
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        return AgentToolExecution(
            f"wrote {relative} ({len(content)} bytes)", {
                "verified": path.is_file() and not path.is_symlink(),
                "operation": "write_file", "path": relative,
                "exists": path.exists(), "kind": "file", "sha256": digest,
                "bytes": len(content),
            },
        )

    def create_directory(self, arguments: dict[str, object]) -> AgentToolExecution:
        path = self._path(_text(arguments, "path"), must_exist=False)
        if path.exists() and not path.is_dir():
            raise FileExistsError("create_directory target is not a directory")
        path.mkdir(parents=True, exist_ok=True)
        relative = path.relative_to(self.root).as_posix()
        verified = path.is_dir() and not path.is_symlink()
        return AgentToolExecution(f"created directory {relative}", {
            "verified": verified, "operation": "create_directory",
            "path": relative, "exists": path.exists(), "kind": "directory",
        })

    def apply_patch(self, arguments: dict[str, object]) -> str:
        patch = _text(arguments, "patch").encode("utf-8")
        if len(patch) > self.maximum_result_bytes:
            raise ValueError("patch exceeds its bound")
        process = subprocess.run(
            ("git", "apply", "--whitespace=nowarn", "-"),
            cwd=self.root, input=patch, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=30, check=False,
        )
        output = (process.stdout + process.stderr).decode("utf-8", "replace")
        if process.returncode != 0:
            raise RuntimeError(_bounded(output or "git apply failed", 16_384))
        return _bounded(output or "patch applied", self.maximum_result_bytes)

    def delete_path(self, arguments: dict[str, object]) -> AgentToolExecution:
        path = self._path(_text(arguments, "path"), must_exist=True)
        relative = path.relative_to(self.root).as_posix()
        if path.is_symlink() or path.is_file():
            path.unlink()
        elif path.is_dir():
            path.rmdir()
        else:
            raise ValueError("delete_path target is unsupported")
        return AgentToolExecution(f"deleted {relative}", {
            "verified": not path.exists(), "operation": "delete_path",
            "path": relative, "exists": path.exists(),
        })

    def move_path(self, arguments: dict[str, object]) -> AgentToolExecution:
        source = self._path(_text(arguments, "source"), must_exist=True)
        destination = self._path(_text(arguments, "destination"), must_exist=False)
        if destination.exists():
            raise FileExistsError("move destination already exists")
        self._ensure_parent(destination)
        source.rename(destination)
        source_relative = source.relative_to(self.root).as_posix()
        destination_relative = destination.relative_to(self.root).as_posix()
        return AgentToolExecution(
            f"moved {source_relative} to {destination_relative}", {
                "verified": destination.exists() and not source.exists(),
                "operation": "move_path", "source": source_relative,
                "destination": destination_relative,
                "source_exists": source.exists(),
                "destination_exists": destination.exists(),
            },
        )

    def git_status(self, arguments: dict[str, object]) -> str:
        _exact(arguments, set())
        return self._git("status", "--short")

    def git_diff(self, arguments: dict[str, object]) -> str:
        _exact(arguments, {"staged"}, optional=True)
        staged = arguments.get("staged", False)
        if not isinstance(staged, bool):
            raise ValueError("git_diff staged must be boolean")
        command = ("diff", "--cached") if staged else ("diff",)
        return self._git(*command)

    def _git(self, *arguments: str) -> str:
        process = subprocess.run(
            ("git", *arguments), cwd=self.root, stdout=subprocess.PIPE,
            stderr=subprocess.PIPE, timeout=30, check=False,
        )
        output = (process.stdout + process.stderr).decode("utf-8", "replace")
        if process.returncode != 0:
            raise RuntimeError(_bounded(output, 16_384))
        return _bounded(output or "No output.", self.maximum_result_bytes)

    def _git_available(self) -> bool:
        process = subprocess.run(
            ("git", "rev-parse", "--is-inside-work-tree"), cwd=self.root,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL,
            timeout=5, check=False,
        )
        return process.returncode == 0 and process.stdout.strip() == b"true"

    def _path(self, relative: str, *, must_exist: bool) -> Path:
        if relative == ".":
            return self.root
        value = PurePosixPath(relative)
        if value.is_absolute() or ".." in value.parts or not value.parts:
            raise PermissionError("agent path must stay inside the workspace")
        path = self.root.joinpath(*value.parts)
        parent = path if path.exists() and path.is_dir() else path.parent
        self._reject_symlink_chain(parent)
        if must_exist and not path.exists():
            raise FileNotFoundError(relative)
        return path

    def _ensure_parent(self, path: Path) -> None:
        relative = path.parent.relative_to(self.root)
        current = self.root
        for part in relative.parts:
            current = current / part
            if current.exists() and current.is_symlink():
                raise PermissionError("agent path traverses a symlink")
            current.mkdir(exist_ok=True)

    def _reject_symlink_chain(self, path: Path) -> None:
        try:
            relative = path.relative_to(self.root)
        except ValueError as error:
            raise PermissionError("agent path escapes workspace") from error
        current = self.root
        for part in relative.parts:
            current = current / part
            if current.is_symlink():
                raise PermissionError("agent path traverses a symlink")
            if not current.exists():
                break

    def _walk_files(self, start: Path):
        for current, directories, files in os.walk(start, followlinks=False):
            directories[:] = sorted(
                name for name in directories
                if name not in {".git", ".fam", "node_modules", "__pycache__"}
                and not (Path(current) / name).is_symlink()
            )
            for name in sorted(files):
                path = Path(current) / name
                if not path.is_symlink():
                    yield path


def _descriptor(tool_id, description, effect, properties, *, required=()):
    return AgentToolDescriptor(tool_id, description, effect, {
        "type": "object", "properties": properties, "required": list(required),
    })


def _text(arguments, name, *, default=None, allow_empty=False):
    _exact(arguments, set(arguments), optional=True)
    value = arguments.get(name, default)
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise ValueError(f"{name} must be text")
    return value


def _exact(arguments, allowed, *, optional=False):
    if not isinstance(arguments, dict):
        raise ValueError("tool arguments must be an object")
    if optional:
        if not set(arguments).issubset(allowed):
            raise ValueError("tool arguments contain unsupported fields")
    elif set(arguments) != allowed:
        raise ValueError("tool arguments fields are invalid")


def _bounded(value: str, maximum: int) -> str:
    payload = value.encode("utf-8")
    if len(payload) <= maximum:
        return value
    return payload[:maximum - 16].decode("utf-8", "ignore") + "\n[truncated]"
