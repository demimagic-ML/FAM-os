"""Default owner-home Application Fabric provider for verified directory actions."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import unquote, urlsplit
from uuid import uuid4

from fam_os.adapters.linux.scoped_directories import (
    ScopedDirectoryAdapter,
    ScopedDirectoryPolicy,
)
from fam_os.adapters.linux.scoped_files import ScopedFileAdapter, ScopedFilePolicy
from fam_os.applications import (
    ActionProposal, ActionResult, ActionStatus, ApplicationIdentity,
    ApplicationInstance, CapabilityRegistryEntry, ConditionEvidence,
    ConditionRequirement, ConfirmationPolicy, ConnectorRegistration,
    ConnectorTransportKind, ObservationResult, ObservationStatus, Reversibility,
    WORKSPACE_MAP_CAPABILITY, WORKSPACE_PATCH_CAPABILITY,
    WORKSPACE_RESTORE_CAPABILITY, WORKSPACE_RETRIEVE_CAPABILITY,
)
from fam_os.product.composition.owner_filesystem_capabilities import (
    filesystem_descriptors,
)
from fam_os.product.composition.owner_workspace_capabilities import (
    workspace_descriptors,
)
from fam_os.product.composition.workspace_observations import (
    WorkspaceObservationProvider,
)
from fam_os.product.composition.workspace_patch import WorkspacePatchProvider


CONNECTOR_ID = "owner-filesystem"
INSTANCE_ID = "owner-filesystem"
INSPECT_CAPABILITY = "os.directory.inspect"
LIST_CAPABILITY = "os.directory.list"
READ_CAPABILITY = "os.file.read"
CREATE_CAPABILITY = "os.directory.create"
REMOVE_CAPABILITY = "os.directory.remove-empty"


class OwnerFilesystem:
    def __init__(self, registry, root: Path) -> None:
        self._registry = registry
        self._adapter = ScopedDirectoryAdapter(ScopedDirectoryPolicy((root,)))
        self._files = ScopedFileAdapter(ScopedFilePolicy(
            (root,), maximum_read_bytes=262_144,
            maximum_write_bytes=65_536,
        ))
        self._workspace = WorkspaceObservationProvider(self._adapter, self._files)
        self._patches = WorkspacePatchProvider(self._files)
        self._registration = _registration(root)
        self._started = False

    def start(self) -> None:
        if self._started:
            return
        self._registry.register(self._registration)
        self._started = True

    def close(self) -> None:
        if self._started:
            self._registry.unregister(CONNECTOR_ID)
            self._started = False

    def transport(self, connector_id: str):
        return self if self._started and connector_id == CONNECTOR_ID else None

    def observation_parameters(
        self, capability_id: str, prompt: str, resource_uri: str | None,
    ) -> dict[str, object]:
        if capability_id == WORKSPACE_RETRIEVE_CAPABILITY:
            return {"query": prompt}
        return {}

    def observe(self, request):
        path = _path(request.resource_uri)
        if request.capability_id == INSPECT_CAPABILITY:
            observed = self._adapter.observe(path)
            payload = {
                "path": observed.path, "exists": observed.exists,
                "empty": observed.empty, "device": observed.device,
                "inode": observed.inode,
            }
            revision = observed.revision
        elif request.capability_id == LIST_CAPABILITY:
            listing = self._adapter.list_entries(path)
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
        elif request.capability_id == READ_CAPABILITY:
            observed = self._files.observe(path, include_content=True)
            payload = {
                "path": observed.path, "sha256": observed.sha256,
                "size_bytes": observed.size_bytes,
                "content": (observed.content or b"").decode(
                    "utf-8", errors="replace",
                ),
            }
            revision = f"sha256:{observed.sha256}"
        elif request.capability_id == WORKSPACE_MAP_CAPABILITY:
            payload, revision = self._workspace.map(path)
        elif request.capability_id == WORKSPACE_RETRIEVE_CAPABILITY:
            query = request.parameters.get("query", "")
            if not isinstance(query, str):
                raise ValueError("workspace retrieval query must be text")
            payload, revision = self._workspace.retrieve(path, query)
        else:
            raise PermissionError("filesystem capability is not an observation")
        return ObservationResult(
            request.request_id, ObservationStatus.OBSERVED, _now(), payload,
            request.resource_uri, revision,
        )

    def prepare_action(self, request):
        path = _path(request.resource_uri)
        if request.capability_id in {
            WORKSPACE_PATCH_CAPABILITY, WORKSPACE_RESTORE_CAPABILITY,
        }:
            return self._patches.prepare(request, path)
        if request.capability_id == CREATE_CAPABILITY:
            if request.parameters:
                raise ValueError("create-directory parameters must be empty")
            self._adapter.prepare_create(request.request_id, path)
            return ActionProposal(
                f"directory-proposal-{uuid4()}", request,
                {"operation": "create_directory", "path": str(path), "mode": "0700"},
                Reversibility.REVERSIBLE, ConfirmationPolicy.ALWAYS,
                (_condition("directory.exists-empty", "Directory must exist and be empty."),),
                (_condition("directory.absent", "Directory target must not exist."),),
                REMOVE_CAPABILITY,
            )
        if request.capability_id == REMOVE_CAPABILITY:
            device, inode = _token(request.parameters.get("reversal_token"))
            self._adapter.prepare_remove(request.request_id, path, device, inode)
            return ActionProposal(
                f"directory-reversal-{uuid4()}", request,
                {"operation": "remove_empty_directory", "path": str(path)},
                Reversibility.IRREVERSIBLE, ConfirmationPolicy.ALWAYS,
                (_condition("directory.absent", "Directory must no longer exist."),),
                (_condition(
                    "directory.reversal-ready",
                    "Directory must still be the created empty directory.",
                ),),
            )
        raise PermissionError("filesystem action capability is unavailable")

    def execute_action(self, proposal, confirmation):
        path = _path(proposal.request.resource_uri)
        if proposal.request.capability_id in {
            WORKSPACE_PATCH_CAPABILITY, WORKSPACE_RESTORE_CAPABILITY,
        }:
            return self._patches.execute(proposal)
        if proposal.request.capability_id == CREATE_CAPABILITY:
            observed = self._adapter.create(
                self._adapter.prepare_create(proposal.proposal_id, path),
            )
            token = json.dumps(
                {"device": observed.device, "inode": observed.inode},
                sort_keys=True, separators=(",", ":"),
            )
            return ActionResult(
                proposal.proposal_id, ActionStatus.VERIFIED, _now(),
                (_evidence("directory.exists-empty", True),),
                {"path": observed.path, "exists": True, "empty": True},
                after_revision=observed.revision, reversal_token=token,
            )
        if proposal.request.capability_id == REMOVE_CAPABILITY:
            device, inode = _token(proposal.request.parameters.get("reversal_token"))
            observed = self._adapter.remove_empty(
                self._adapter.prepare_remove(
                    proposal.proposal_id, path, device, inode,
                ),
            )
            return ActionResult(
                proposal.proposal_id, ActionStatus.VERIFIED, _now(),
                (_evidence("directory.absent", not observed.exists),),
                {"path": observed.path, "exists": observed.exists},
                before_revision=f"directory:{device}:{inode}",
                after_revision=observed.revision,
            )
        raise PermissionError("filesystem action capability is unavailable")


def directory_token(value) -> tuple[int, int]:
    return _token(value)


def _registration(root: Path) -> ConnectorRegistration:
    application = ApplicationIdentity(
        "fam.local.filesystem", "Local filesystem", "local-owner",
    )
    instance = ApplicationInstance(
        INSTANCE_ID, application, CONNECTOR_ID,
        workspace_uris=(_directory_uri(root),),
    )
    descriptors = (*filesystem_descriptors(), *workspace_descriptors())
    entries = tuple(
        CapabilityRegistryEntry(
            f"{INSTANCE_ID}:{item.capability_id}", CONNECTOR_ID, INSTANCE_ID,
            application.application_id, item, (_directory_uri(root),),
        )
        for item in descriptors
    )
    return ConnectorRegistration(
        CONNECTOR_ID, ConnectorTransportKind.OS_TOOL, "fam.owner-filesystem", "1",
        instance, entries, _now(),
    )
def _condition(identifier: str, description: str):
    return ConditionRequirement(identifier, identifier, description)


def _evidence(identifier: str, passed: bool):
    return ConditionEvidence(
        identifier, identifier, passed,
        "Provider observed the declared directory state.",
    )


def _token(value) -> tuple[int, int]:
    if not isinstance(value, str) or len(value) > 512:
        raise ValueError("directory reversal token is invalid")
    document = json.loads(value)
    if set(document) != {"device", "inode"}:
        raise ValueError("directory reversal token is invalid")
    device, inode = document["device"], document["inode"]
    if any(isinstance(item, bool) or not isinstance(item, int) or item < 0 for item in (device, inode)):
        raise ValueError("directory reversal token is invalid")
    return device, inode


def _path(uri: str | None) -> Path:
    if uri is None:
        raise ValueError("directory action requires a resource URI")
    parsed = urlsplit(uri)
    if parsed.scheme != "file" or parsed.netloc not in {"", "localhost"}:
        raise ValueError("directory resource is not a local file URI")
    path = Path(unquote(parsed.path))
    if not path.is_absolute() or ".." in path.parts:
        raise ValueError("directory resource path is invalid")
    return path


def _directory_uri(path: Path) -> str:
    uri = path.as_uri()
    return uri if uri.endswith("/") else uri + "/"


def _directory_revision(path: Path) -> str:
    details = path.stat(follow_symlinks=False)
    return f"directory:{details.st_dev}:{details.st_ino}:{details.st_mtime_ns}"


def _now() -> datetime:
    return datetime.now(timezone.utc)
