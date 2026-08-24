"""Explicit owner-approved deterministic project adapters."""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from fam_os.adapters.linux.scoped_files import ScopedFileAdapter, ScopedFilePolicy
from fam_os.adapters.linux.scoped_directories import (
    ScopedDirectoryAdapter, ScopedDirectoryPolicy,
)
from fam_os.applications import (
    ApplicationAuthority, ApplicationIdentity, ApplicationInstance,
    CapabilityDescriptor, CapabilityKind, CapabilityRegistryEntry,
    ConfirmationPolicy, ConnectorRegistration, ConnectorTransportKind,
    Reversibility,
)
from fam_os.product.composition.os_tool_transport import DeterministicOsTransport


OS_TOOLS_CONFIG_VERSION = "fam.product.os-tools/v1alpha1"


class ProductOsTools:
    def __init__(self, registry, definitions) -> None:
        self._registry = registry
        self._definitions = definitions
        self._transports: dict[str, DeterministicOsTransport] = {}

    @classmethod
    def from_file(cls, registry, path: Path) -> "ProductOsTools":
        if not path.exists():
            return cls(registry, ())
        _require_private(path)
        document = json.loads(path.read_text(encoding="utf-8"))
        if document.get("contract_version") != OS_TOOLS_CONFIG_VERSION:
            raise ValueError("OS tool configuration version is unsupported")
        projects = document.get("projects")
        if not isinstance(projects, list) or len(projects) > 64:
            raise ValueError("OS tool project configuration is invalid")
        return cls(registry, tuple(_definition(item) for item in projects))

    def start(self) -> None:
        try:
            for registration, files, directories, commands in self._definitions:
                transport = DeterministicOsTransport(
                    registration, files, directories, commands,
                )
                self._registry.register(registration)
                self._transports[registration.connector_id] = transport
        except BaseException:
            self.close()
            raise

    def transport(self, connector_id: str):
        return self._transports.get(connector_id)

    def close(self) -> None:
        for connector_id in tuple(self._transports):
            self._registry.unregister(connector_id)
        self._transports.clear()


def _definition(value):
    if not isinstance(value, dict):
        raise ValueError("OS tool project must be an object")
    project_id = value["project_id"]
    root = Path(value["root"])
    files = ScopedFileAdapter(ScopedFilePolicy(
        (root,), int(value.get("maximum_read_bytes", 4_194_304)),
        int(value.get("maximum_write_bytes", 4_194_304)),
    ))
    directories = ScopedDirectoryAdapter(ScopedDirectoryPolicy((root,)))
    connector_id = f"os-tools-{project_id}"
    instance_id = f"project-{project_id}"
    application = ApplicationIdentity(
        f"fam.project.{project_id}", value["display_name"], "local-owner",
    )
    instance = ApplicationInstance(
        instance_id, application, connector_id,
        workspace_uris=(_directory_uri(root),),
    )
    descriptors = [_directory_capability(), _file_capability()]
    commands = {}
    for item in value.get("commands", ()):
        descriptor, command = _command(item)
        descriptors.append(descriptor)
        commands[descriptor.capability_id] = command
    entries = tuple(
        CapabilityRegistryEntry(
            f"{instance_id}:{item.capability_id}", connector_id, instance_id,
            application.application_id, item,
            (_directory_uri(root),)
            if item.kind is CapabilityKind.OBSERVATION else (),
        )
        for item in descriptors
    )
    registration = ConnectorRegistration(
        connector_id, ConnectorTransportKind.OS_TOOL, "fam.os-tools", "1",
        instance, entries, datetime.now(timezone.utc),
    )
    return registration, files, directories, commands


def _directory_capability():
    return CapabilityDescriptor(
        "os.directory.list", "List project directory",
        "List bounded entries from this project.",
        CapabilityKind.OBSERVATION, ApplicationAuthority.OBSERVE,
        "fam.os.directory-list.input.v1", "fam.os.directory-list.output.v1",
    )


def _file_capability():
    return CapabilityDescriptor(
        "os.file.read", "Read scoped file", "Read bounded bytes from this project.",
        CapabilityKind.OBSERVATION, ApplicationAuthority.OBSERVE,
        "fam.os.file-read.input.v1", "fam.os.file-read.output.v1",
    )


def _command(value):
    if not isinstance(value, dict):
        raise ValueError("OS command must be an object")
    executable = Path(value["executable"])
    arguments = tuple(value.get("arguments", ()))
    if not executable.is_absolute() or not executable.is_file() or not os.access(executable, os.X_OK):
        raise ValueError("OS command executable must be an executable absolute file")
    if any(not isinstance(item, str) or "\0" in item for item in arguments):
        raise ValueError("OS command arguments must be bounded strings")
    capability_id = value["capability_id"]
    descriptor = CapabilityDescriptor(
        capability_id, value["display_name"], value.get(
            "description", "Run an owner-approved bounded project command.",
        ), CapabilityKind.ACTION, ApplicationAuthority.EXECUTE,
        f"{capability_id}.input.v1", f"{capability_id}.output.v1",
        Reversibility.IRREVERSIBLE, ConfirmationPolicy.ALWAYS,
        ("process.exit-zero",),
    )
    return descriptor, (str(executable), *arguments)


def _directory_uri(path: Path) -> str:
    uri = path.as_uri()
    return uri if uri.endswith("/") else uri + "/"


def _require_private(path: Path) -> None:
    details = path.stat()
    if path.is_symlink() or not path.is_file() or details.st_uid != os.geteuid():
        raise PermissionError("OS tool configuration must be owner controlled")
    if details.st_mode & 0o077:
        raise PermissionError("OS tool configuration must be mode 0600")
