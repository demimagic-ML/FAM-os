"""Unambiguous decoding of the signed Expert component archive."""

from __future__ import annotations

import tarfile
from pathlib import Path, PurePosixPath

from fam_os.experts import (
    ExpertManifest,
    ExpertRuntimeBinding,
    validate_runtime_binding,
)
from fam_os.schemas import loads_document

ExpertCoordinate = tuple[str, str, str]
AvailableExperts = dict[
    ExpertCoordinate, tuple[ExpertManifest, ExpertRuntimeBinding]
]


def load_signed_expert_archive(archive: Path) -> tuple[str, AvailableExperts]:
    with tarfile.open(archive, "r") as source:
        members = _members_by_name(source)
        catalog = _member_text(source, members, "runtime/model-catalog.json")
        manifests = _documents(source, members, "experts/", ExpertManifest)
        bindings = _documents(source, members, "bindings/", ExpertRuntimeBinding)
    return catalog, _available_experts(manifests, bindings)


def _members_by_name(source: tarfile.TarFile) -> dict[str, tarfile.TarInfo]:
    members: dict[str, tarfile.TarInfo] = {}
    for member in source.getmembers():
        _require_canonical_member_name(member.name)
        if member.name in members:
            raise ValueError("signed expert archive contains duplicate member paths")
        members[member.name] = member
    return members


def _require_canonical_member_name(name: str) -> None:
    path = PurePosixPath(name)
    if (
        not name or path.is_absolute() or path.as_posix() != name
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ValueError("signed expert archive member path is unsafe")


def _member_text(
    source: tarfile.TarFile,
    members: dict[str, tarfile.TarInfo],
    name: str,
) -> str:
    member = members.get(name)
    if member is None:
        raise ValueError(f"signed expert archive member is absent: {name}")
    if not member.isfile() or member.issym() or member.islnk():
        raise ValueError("signed expert archive member is unsafe")
    stream = source.extractfile(member)
    if stream is None:
        raise ValueError("signed expert archive member is unreadable")
    return stream.read().decode("utf-8")


def _documents(source, members, prefix: str, expected_type) -> tuple:
    values = []
    for name in sorted(members):
        if not name.startswith(prefix) or not name.endswith(".json"):
            continue
        value = loads_document(_member_text(source, members, name))
        if not isinstance(value, expected_type):
            raise ValueError("signed expert archive document has the wrong type")
        values.append(value)
    return tuple(values)


def _available_experts(manifests, bindings) -> AvailableExperts:
    manifest_map = {_manifest_coordinate(item): item for item in manifests}
    if len(manifest_map) != len(manifests):
        raise ValueError("signed expert archive contains duplicate manifests")
    available: AvailableExperts = {}
    for binding in bindings:
        coordinate = _binding_coordinate(binding)
        manifest = manifest_map.get(coordinate)
        if manifest is None:
            raise ValueError("signed expert binding lacks its exact manifest")
        if coordinate in available:
            raise ValueError("signed expert archive contains duplicate bindings")
        validate_runtime_binding(manifest, binding)
        available[coordinate] = (manifest, binding)
    return available


def _manifest_coordinate(manifest: ExpertManifest) -> ExpertCoordinate:
    return (
        manifest.package.package_id,
        manifest.package.package_version,
        manifest.expert_id,
    )


def _binding_coordinate(binding: ExpertRuntimeBinding) -> ExpertCoordinate:
    return (
        binding.coordinate.package_id,
        binding.coordinate.package_version,
        binding.expert_id,
    )
