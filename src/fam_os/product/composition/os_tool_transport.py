"""Core-owned scoped file and bounded command Application Fabric transport."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit
from uuid import uuid4

from fam_os.adapters.linux.bounded_command import BoundedSubprocessRunner
from fam_os.adapters.linux.mime_types import ScopedMimeTypeAdapter
from fam_os.adapters.linux.scoped_files import ScopedFileAdapter
from fam_os.adapters.linux.scoped_directories import ScopedDirectoryAdapter
from fam_os.applications import (
    ActionProposal, ActionResult, ActionStatus, ApplicationFailure,
    ApplicationFailureCategory, ApplicationRetryDisposition, ConditionEvidence,
    ConditionRequirement, ConfirmationPolicy, ObservationResult,
    ObservationStatus, Reversibility,
)


class DeterministicOsTransport:
    def __init__(
        self, registration, files: ScopedFileAdapter,
        directories: ScopedDirectoryAdapter,
        commands: dict[str, tuple[str, ...]], runner=None,
    ) -> None:
        self.registration = registration
        self._files = files
        self._directories = directories
        self._mime = ScopedMimeTypeAdapter(files.policy)
        self._commands = commands
        self._runner = runner or BoundedSubprocessRunner()

    @property
    def connector_id(self) -> str:
        return self.registration.connector_id

    def observe(self, request):
        path = _file_path(request.resource_uri)
        if request.capability_id == "os.directory.list":
            listing = self._directories.list_entries(path)
            payload = {
                "path": listing.path,
                "entries": [
                    {
                        "name": item.name, "kind": item.kind,
                        "size_bytes": item.size_bytes,
                    }
                    for item in listing.entries
                ],
                "truncated": listing.truncated,
                "maximum_entries": listing.maximum_entries,
            }
            revision = _directory_revision(path)
        elif request.capability_id == "os.file.read":
            observed = self._files.observe(path, include_content=True)
            mime = self._mime.observe(path)
            content = (observed.content or b"").decode("utf-8", errors="replace")
            payload = {
                "path": observed.path, "sha256": observed.sha256,
                "size_bytes": observed.size_bytes, "mime_type": mime.mime_type,
                "content": content,
            }
            revision = f"sha256:{observed.sha256}"
        else:
            raise PermissionError("OS capability is not an observation")
        return ObservationResult(
            request.request_id, ObservationStatus.OBSERVED, _now(), payload,
            request.resource_uri, revision,
        )

    def prepare_action(self, request):
        command = self._commands.get(request.capability_id)
        if command is None:
            raise PermissionError("OS command is not allowlisted")
        if request.parameters:
            raise ValueError("fixed OS command accepts no model-controlled arguments")
        condition = ConditionRequirement(
            "process.exit-zero", "process.exit-zero",
            "The bounded command must exit successfully.",
        )
        return ActionProposal(
            f"os-proposal-{uuid4()}", request,
            {"executable": command[0], "arguments": list(command[1:])},
            Reversibility.IRREVERSIBLE, ConfirmationPolicy.ALWAYS, (condition,),
        )

    def execute_action(self, proposal, confirmation):
        command = self._commands.get(proposal.request.capability_id)
        if command is None:
            raise PermissionError("OS command is not allowlisted")
        result = self._runner.run(
            command, cwd=self._files.policy.roots[0],
            environment={"LANG": "C.UTF-8", "LC_ALL": "C.UTF-8", "PATH": "/usr/bin:/bin"},
        )
        passed = result.succeeded
        evidence = (ConditionEvidence(
            "process.exit-zero", "process.exit-zero", passed,
            f"exit_code:{result.exit_code};timed_out:{result.timed_out};"
            f"output_limited:{result.output_limited}",
        ),)
        output = {
            "exit_code": result.exit_code, "stdout": result.stdout,
            "stderr": result.stderr, "timed_out": result.timed_out,
            "output_limited": result.output_limited,
        }
        if passed:
            return ActionResult(
                proposal.proposal_id, ActionStatus.VERIFIED, _now(), evidence, output,
            )
        return ActionResult(
            proposal.proposal_id, ActionStatus.POSTCONDITION_FAILED, _now(), evidence,
            output, error=ApplicationFailure(
                ApplicationFailureCategory.POSTCONDITION_FAILED,
                "os.command.failed", "The bounded command did not pass.",
                ApplicationRetryDisposition.AFTER_STATE_CHANGE,
            ),
        )


def _file_path(uri: str | None) -> Path:
    if uri is None:
        raise ValueError("file observation requires a resource")
    parsed = urlsplit(uri)
    if parsed.scheme != "file" or parsed.netloc not in {"", "localhost"}:
        raise ValueError("resource is not a local file URI")
    return Path(unquote(parsed.path))


def _directory_revision(path: Path) -> str:
    details = path.stat(follow_symlinks=False)
    return f"directory:{details.st_dev}:{details.st_ino}:{details.st_mtime_ns}"


def _now() -> datetime:
    return datetime.now(timezone.utc)
