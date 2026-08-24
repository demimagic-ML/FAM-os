"""Signed expert-scope authority for physical runtime model entries."""

from __future__ import annotations

from dataclasses import dataclass

from fam_os.core.production.contracts import ModelIntent, RuntimeModelEntry
from fam_os.core.engineering import EngineeringAuthority
from fam_os.core.production.model_catalog_archive import AvailableExperts
from fam_os.experts import ExpertManifest, ExpertRuntimeBinding


@dataclass(frozen=True, slots=True)
class RuntimeExpertScope:
    model_ref: str
    intents: tuple[ModelIntent, ...]
    verifier_ids: tuple[str, ...]
    advisory_authorities: tuple[EngineeringAuthority, ...] = ()


_CAPABILITY_PREFIXES = {
    ModelIntent.CONVERSATION: ("language.",),
    ModelIntent.GROUNDED_QUESTION: ("language.", "retrieval."),
    ModelIntent.READ_ONLY_TASK: ("language.",),
    ModelIntent.CODE: ("code.",),
    ModelIntent.APPLICATION_MUTATION: ("code.",),
    ModelIntent.MATH: ("math.",),
    ModelIntent.RETRIEVAL: ("retrieval.",),
    ModelIntent.MEDIA: ("vision.",),
    ModelIntent.ADMINISTRATION: ("language.",),
}


def validated_expert_scopes(
    document,
    available: AvailableExperts,
    configured_refs: set[str],
) -> tuple[
    dict[str, RuntimeExpertScope],
    dict[str, tuple[ExpertManifest, ExpertRuntimeBinding]],
]:
    scopes: dict[str, RuntimeExpertScope] = {}
    selected: dict[str, tuple[ExpertManifest, ExpertRuntimeBinding]] = {}
    for model in document.get("models", ()):
        model_ref = model["model_ref"]
        for configured in model.get("expert_scopes", ()):
            expert_id = configured["expert_id"]
            if expert_id in scopes:
                raise ValueError("runtime expert scopes must identify unique experts")
            pair = _selected_pair(configured, expert_id, available)
            scope = _validated_scope(model_ref, configured, pair[0])
            if pair[1].artifact_ref != model_ref:
                raise ValueError("runtime expert scope model binding does not match")
            scopes[expert_id] = scope
            selected[expert_id] = pair
    _require_every_model_scoped(configured_refs, scopes)
    return scopes, selected


def require_aggregate_scopes(
    entries: dict[str, RuntimeModelEntry],
    scopes: dict[str, RuntimeExpertScope],
) -> None:
    for model_ref, entry in entries.items():
        model_scopes = tuple(
            scope for scope in scopes.values() if scope.model_ref == model_ref
        )
        if not model_scopes:
            raise ValueError(f"runtime model {model_ref!r} has no signed expert scopes")
        scoped_intents = {
            intent for scope in model_scopes for intent in scope.intents
        }
        if set(entry.intents) != scoped_intents:
            raise ValueError(
                f"runtime model {model_ref!r} aggregate intents do not match "
                "signed expert scopes"
            )
        scoped_verifiers = {
            verifier_id for scope in model_scopes for verifier_id in scope.verifier_ids
        }
        if set(entry.verifier_ids) != scoped_verifiers:
            raise ValueError(
                f"runtime model {model_ref!r} aggregate verifiers do not match "
                "signed expert scopes"
            )


def _selected_pair(configured, expert_id: str, available: AvailableExperts):
    coordinate = (
        configured.get("package_id"),
        configured.get("package_version"),
        expert_id,
    )
    pair = available.get(coordinate)
    if pair is None:
        raise ValueError("runtime expert scope lacks its exact signed package binding")
    return pair


def _validated_scope(
    model_ref: str, configured, manifest: ExpertManifest,
) -> RuntimeExpertScope:
    expert_id = configured["expert_id"]
    intents = tuple(ModelIntent(value) for value in configured["intents"])
    verifier_ids = tuple(configured.get("verifier_ids", ()))
    advisory_authorities = tuple(
        EngineeringAuthority(value)
        for value in configured.get("advisory_authorities", ())
    )
    if not intents:
        raise ValueError("runtime expert scope intents must not be empty")
    if len(set(intents)) != len(intents):
        raise ValueError("runtime expert scope intents must be unique")
    if len(set(verifier_ids)) != len(verifier_ids):
        raise ValueError("runtime expert scope verifier IDs must be unique")
    if len(set(advisory_authorities)) != len(advisory_authorities):
        raise ValueError("runtime expert advisory authorities must be unique")
    _require_supported_intents(expert_id, intents, manifest)
    _require_engineering_advice(expert_id, advisory_authorities, manifest)
    _require_exact_verifiers(expert_id, verifier_ids, manifest)
    return RuntimeExpertScope(
        model_ref, intents, verifier_ids, advisory_authorities,
    )


def _require_engineering_advice(
    expert_id: str,
    authorities: tuple[EngineeringAuthority, ...],
    manifest: ExpertManifest,
) -> None:
    if not authorities:
        return
    if not any(capability.startswith("code.") for capability in manifest.capabilities):
        raise ValueError(
            f"runtime expert {expert_id!r} lacks a code capability for "
            "engineering advice"
        )


def _require_supported_intents(
    expert_id: str,
    intents: tuple[ModelIntent, ...],
    manifest: ExpertManifest,
) -> None:
    unsupported = tuple(
        intent for intent in intents
        if not any(
            capability.startswith(prefix)
            for prefix in _CAPABILITY_PREFIXES[intent]
            for capability in manifest.capabilities
        )
    )
    if unsupported:
        raise ValueError(
            f"runtime expert {expert_id!r} lacks capabilities for intents: "
            + ", ".join(item.value for item in unsupported)
        )


def _require_exact_verifiers(
    expert_id: str,
    verifier_ids: tuple[str, ...],
    manifest: ExpertManifest,
) -> None:
    configured = set(verifier_ids)
    required = set(manifest.required_verifier_ids)
    undeclared = sorted(configured - required)
    if undeclared:
        raise ValueError(
            f"runtime expert {expert_id!r} claims undeclared verifiers: "
            + ", ".join(undeclared)
        )
    omitted = sorted(required - configured)
    if omitted:
        raise ValueError(
            f"runtime expert {expert_id!r} omits required verifiers: "
            + ", ".join(omitted)
        )


def _require_every_model_scoped(
    configured_refs: set[str], scopes: dict[str, RuntimeExpertScope],
) -> None:
    unscoped_refs = sorted(
        configured_refs - {scope.model_ref for scope in scopes.values()}
    )
    if unscoped_refs:
        raise ValueError(
            "signed runtime catalog models lack exact expert scopes: "
            + ", ".join(unscoped_refs)
        )
