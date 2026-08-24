"""Iterative agent tools backed by authorized candidate-edit operations."""

from __future__ import annotations

import os
from dataclasses import replace
from pathlib import Path
from typing import Protocol

from fam_os.core.agent import (
    AgentToolDescriptor, AgentToolEffect, AgentToolExecution, AgentToolRegistry,
)
from fam_os.core.engineering import (
    CandidateEditStatus,
    GeneratedCandidateOperation,
    GeneratedCandidateOperationKind,
    GeneratedCandidatePlan,
    bind_generated_candidate_plan,
)
from fam_os.product.agent_workspace_tools import WorkspaceAgentTools


_EPHEMERAL_DIRECTORIES = frozenset({
    ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox", ".venv",
    "__pycache__", "node_modules", "venv",
})


class _CommandTools(Protocol):
    def run_command(self, arguments: dict[str, object]) -> str: ...


class AuthorizedCandidateAgentTools:
    """Expose flexible tools while recording every candidate filesystem effect."""

    def __init__(
        self, loop, owner_id: str, task_id: str, session_id: str,
        principal_id: str, definition, preparation,
        command_tools: _CommandTools,
        command_effect: AgentToolEffect = AgentToolEffect.COMMAND,
    ) -> None:
        self._loop = loop
        self._owner_id = owner_id
        self._task_id = task_id
        self._session_id = session_id
        self._principal_id = principal_id
        self._definition = definition
        self._preparation = preparation
        self._workspace = WorkspaceAgentTools(
            Path(preparation.candidate.candidate_workspace),
        )
        self._repository = WorkspaceAgentTools(
            Path(preparation.candidate.owner_workspace),
        )
        self._commands = command_tools
        self._command_effect = command_effect
        self._sequence = 0
        self.applied_edits: list[object] = []
        self.successful_verifications: list[str] = []

    def register(self, registry: AgentToolRegistry) -> None:
        _register(registry, "list_directory", "List one candidate directory.",
                  AgentToolEffect.OBSERVE, self._workspace.list_directory,
                  {"path": {"type": "string"}})
        _register(registry, "read_file", "Read one candidate file and its digest.",
                  AgentToolEffect.OBSERVE, self._workspace.read_file,
                  {
                      "path": {"type": "string"},
                      "offset_bytes": {"type": "integer"},
                      "maximum_bytes": {"type": "integer"},
                  }, required=("path",))
        _register(registry, "search_text", "Search candidate files for literal text.",
                  AgentToolEffect.OBSERVE, self._workspace.search_text, {
                      "query": {"type": "string"}, "path": {"type": "string"},
                  }, required=("query",))
        if self._repository.git_available:
            _register(registry, "git_status", (
                "Show Git status for the owner repository. The editable candidate is "
                "a staged worktree snapshot and intentionally has no .git directory."
            ), AgentToolEffect.OBSERVE, self._repository.git_status, {})
            _register(registry, "git_diff", (
                "Show the owner repository Git diff. Candidate edits are recorded "
                "separately and are not visible here until approved and applied."
            ), AgentToolEffect.OBSERVE, self._repository.git_diff,
                      {"staged": {"type": "boolean"}})
        _register(registry, "write_file", "Create or replace a candidate UTF-8 file.",
                  AgentToolEffect.WORKSPACE_WRITE, self.write_file, {
                      "path": {"type": "string"}, "content": {"type": "string"},
                  }, required=("path", "content"))
        _register(registry, "create_directory", "Create a candidate directory.",
                  AgentToolEffect.WORKSPACE_WRITE, self.create_directory,
                  {"path": {"type": "string"}}, required=("path",))
        _register(registry, "delete_path", "Delete a candidate file or empty directory.",
                  AgentToolEffect.WORKSPACE_WRITE, self.delete_path,
                  {"path": {"type": "string"}}, required=("path",))
        _register(registry, "move_path", "Move a candidate path.",
                  AgentToolEffect.WORKSPACE_WRITE, self.move_path, {
                      "source": {"type": "string"},
                      "destination": {"type": "string"},
                  }, required=("source", "destination"))
        _register(registry, "run_command", (
            "Run a direct argv command (not a shell expression) from the candidate. "
            "Its isolation and OS reach follow the approved authority profile. "
            "Filesystem effects inside the candidate are detected "
            "and replayed through authorized candidate edits; ephemeral tool caches "
            "and virtual environments are not proposed as source changes."
        ), self._command_effect, self.run_command, {
            "command": {"type": "array", "items": {"type": "string"}},
            "timeout_seconds": {"type": "number"},
        }, required=("command",))
        _register(registry, "verify_command", (
            "Run a direct argv check whose zero exit status demonstrates that the "
            "requested implementation works. Use this for tests, builds, diagnostics, "
            "or focused behavioral assertions, not for setup or dependency installation."
        ), self._command_effect, self.verify_command, {
            "command": {"type": "array", "items": {"type": "string"}},
            "timeout_seconds": {"type": "number"},
        }, required=("command",))

    def write_file(self, arguments: dict[str, object]) -> str:
        path = _text(arguments, "path")
        content = _text(arguments, "content", allow_empty=True)
        current = self._current()
        existing = {item.path for item in current.entries}
        kind = (
            GeneratedCandidateOperationKind.REPLACE_FILE
            if path in existing else GeneratedCandidateOperationKind.CREATE_FILE
        )
        return self._apply((GeneratedCandidateOperation(
            kind, path, content, media_type=_media_type(path),
        ),), "Agent wrote a file.")

    def create_directory(self, arguments: dict[str, object]) -> AgentToolExecution:
        relative = _text(arguments, "path")
        output = self._apply((GeneratedCandidateOperation(
            GeneratedCandidateOperationKind.CREATE_DIRECTORY,
            relative,
        ),), "Agent created a directory.")
        path = self._workspace.root / relative
        verified = path.is_dir() and not path.is_symlink()
        if verified:
            self.successful_verifications.append(
                f"semantic:create_directory:path={relative}:exists=true:kind=directory"
            )
        return AgentToolExecution(output, {
            "verified": verified,
            "operation": "create_directory",
            "path": relative,
            "exists": path.exists(),
            "kind": "directory" if path.is_dir() else "other",
        })

    def delete_path(self, arguments: dict[str, object]) -> str:
        return self._apply((GeneratedCandidateOperation(
            GeneratedCandidateOperationKind.DELETE, _text(arguments, "path"),
        ),), "Agent deleted a path.")

    def move_path(self, arguments: dict[str, object]) -> str:
        return self._apply((GeneratedCandidateOperation(
            GeneratedCandidateOperationKind.MOVE,
            _text(arguments, "destination"),
            source_path=_text(arguments, "source"),
        ),), "Agent moved a path.")

    def run_command(self, arguments: dict[str, object]) -> str:
        return self._execute_command(arguments, verification=False)

    def verify_command(self, arguments: dict[str, object]) -> str:
        return self._execute_command(arguments, verification=True)

    def _execute_command(
        self, arguments: dict[str, object], *, verification: bool,
    ) -> str:
        before = _snapshot(self._workspace.root)
        output = self._commands.run_command(arguments)
        after = _snapshot(self._workspace.root)
        operations = _snapshot_operations(before, after)
        succeeded = _command_succeeded(output)
        if succeeded and verification:
            self.successful_verifications.append(output)
        if not operations:
            if not succeeded:
                raise RuntimeError(output)
            return output
        _restore(self._workspace.root, before, after)
        mutation = self._apply(
            operations,
            "Sandboxed command changed candidate files.",
        )
        result = f"{output}\nrecorded_filesystem_effects:\n{mutation}"
        if not succeeded:
            raise RuntimeError(result)
        return result

    def _current(self):
        return self._loop.current_candidate(self._owner_id, self._task_id)

    def _apply(self, operations, summary: str) -> str:
        current = self._current()
        task = self._preparation.candidate.task_id
        plan = GeneratedCandidatePlan(summary, tuple(operations))
        edits = bind_generated_candidate_plan(
            task, replace(self._preparation.candidate, entries=current.entries), plan,
            maximum_operations=self._definition.task.max_changed_files,
            maximum_content_bytes=self._definition.task.max_changed_bytes,
        )
        records = []
        for item in edits:
            self._sequence += 1
            record = self._loop.edit_candidate(
                self._owner_id, self._task_id,
                edit_id=f"agent-edit-{self._task_id}-{self._sequence}",
                session_id=self._session_id, principal_id=self._principal_id,
                operation=item.operation, artifact=item.artifact,
                content=item.content,
            )
            if record.status is not CandidateEditStatus.APPLIED:
                raise RuntimeError("authorized candidate edit did not apply")
            records.append(record)
            self.applied_edits.append(record)
        return "\n".join(
            f"{item.operation.kind.value}\t{item.operation.path}"
            for item in records
        )


def _register(
    registry, tool_id, description, effect, implementation, properties, *,
    required=(),
):
    registry.register(AgentToolDescriptor(
        tool_id, description, effect,
        {
            "type": "object", "properties": properties,
            "required": list(required), "additionalProperties": False,
        },
    ), implementation)


def _snapshot(root: Path) -> dict[str, bytes | None]:
    values: dict[str, bytes | None] = {".": None}
    for current, directories, files in os.walk(root, followlinks=False):
        directories[:] = sorted(
            name for name in directories
            if name not in {".git", ".fam"} | _EPHEMERAL_DIRECTORIES
            and not (Path(current) / name).is_symlink()
        )
        relative = Path(current).relative_to(root)
        if relative.parts:
            values[relative.as_posix()] = None
        for name in sorted(files):
            path = Path(current) / name
            if path.is_symlink():
                continue
            values[path.relative_to(root).as_posix()] = path.read_bytes()
    return values


def _snapshot_operations(before, after):
    operations = []
    before_paths, after_paths = set(before) - {"."}, set(after) - {"."}
    deleted = sorted(before_paths - after_paths, key=lambda item: (-item.count("/"), item))
    for path in deleted:
        operations.append(GeneratedCandidateOperation(
            GeneratedCandidateOperationKind.DELETE, path,
        ))
    created_directories = sorted(
        (path for path in after_paths - before_paths if after[path] is None),
        key=lambda item: (item.count("/"), item),
    )
    for path in created_directories:
        operations.append(GeneratedCandidateOperation(
            GeneratedCandidateOperationKind.CREATE_DIRECTORY, path,
        ))
    for path in sorted(after_paths):
        content = after[path]
        if content is None or before.get(path) == content:
            continue
        kind = (
            GeneratedCandidateOperationKind.CREATE_FILE
            if path not in before else GeneratedCandidateOperationKind.REPLACE_FILE
        )
        try:
            text = content.decode("utf-8")
        except UnicodeDecodeError as error:
            raise ValueError(
                f"command changed unsupported binary file: {path}"
            ) from error
        operations.append(GeneratedCandidateOperation(
            kind, path, text, media_type=_media_type(path),
        ))
    return tuple(operations)


def _restore(root: Path, before, after) -> None:
    for relative in sorted(
        set(after) - set(before), key=lambda item: (-item.count("/"), item),
    ):
        path = root / relative
        if path.is_file():
            path.unlink()
        elif path.is_dir():
            path.rmdir()
    for relative, content in before.items():
        if relative == ".":
            continue
        path = root / relative
        if content is None:
            path.mkdir(parents=True, exist_ok=True)
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(content)


def _text(arguments, name, *, allow_empty=False):
    value = arguments.get(name)
    if not isinstance(value, str) or (not allow_empty and not value.strip()):
        raise ValueError(f"{name} must be text")
    return value


def _media_type(path: str) -> str:
    if path.endswith(".json"):
        return "application/json"
    if path.endswith((".html", ".css", ".js", ".ts", ".py", ".md", ".txt")):
        return "text/plain"
    return "text/plain"


def _command_succeeded(output: str) -> bool:
    return "status=completed" in output and "exit_code=0" in output
