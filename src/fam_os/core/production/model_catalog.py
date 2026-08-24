"""Release-configured catalog bound to locally present Ollama manifests."""

from __future__ import annotations

from dataclasses import dataclass, replace
from pathlib import Path

from fam_os.core.production.contracts import ModelIntent, RuntimeModelEntry
from fam_os.core.engineering import EngineeringAuthority
from fam_os.core.production.model_catalog_archive import (
    load_signed_expert_archive,
)
from fam_os.core.production.model_catalog_config import (
    catalog_document,
    catalog_entries,
)
from fam_os.core.production.model_catalog_scopes import (
    require_aggregate_scopes,
    validated_expert_scopes,
)
from fam_os.product.release_trust import verify_installed_release
from fam_os.product.update_contracts import ComponentKind


@dataclass(frozen=True, slots=True)
class RuntimeModelProvenance:
    model_ref: str
    expert_id: str
    package_ref: str
    runtime_binding_ref: str
    intents: tuple[ModelIntent, ...] = ()
    verifier_ids: tuple[str, ...] = ()
    advisory_authorities: tuple[EngineeringAuthority, ...] = ()


class RuntimeModelCatalog:
    def __init__(
        self,
        entries: tuple[RuntimeModelEntry, ...],
        provenances: tuple[RuntimeModelProvenance, ...] = (),
    ) -> None:
        if len({entry.model_ref for entry in entries}) != len(entries):
            raise ValueError("runtime model references must be unique")
        if len({item.expert_id for item in provenances}) != len(provenances):
            raise ValueError("runtime model provenance expert IDs must be unique")
        model_refs = {entry.model_ref for entry in entries}
        if any(item.model_ref not in model_refs for item in provenances):
            raise ValueError("runtime model provenance must reference a catalog model")
        entry_map = {entry.model_ref: entry for entry in entries}
        for provenance in provenances:
            _require_provenance_scope(entry_map[provenance.model_ref], provenance)
        self._entries = entries
        self._provenances = provenances
        self._available_verifier_ids: frozenset[str] | None = None

    @classmethod
    def from_source(cls, config_path: Path, source_root: Path) -> "RuntimeModelCatalog":
        document = catalog_document(config_path.read_text(encoding="utf-8"))
        return cls(catalog_entries(document, source_root))

    @classmethod
    def from_signed_release(
        cls,
        release_root: Path,
        trust_root: Path,
        source_root: Path,
    ) -> "RuntimeModelCatalog":
        release = verify_installed_release(release_root, trust_root)
        component = next(
            item for item in release.components if item.kind is ComponentKind.EXPERT
        )
        archive = release_root / component.kind.value / component.name
        serialized, available = load_signed_expert_archive(archive)
        document = catalog_document(serialized)
        configured_refs = {
            item["model_ref"] for item in document.get("models", ())
        }
        scopes, selected = validated_expert_scopes(
            document, available, configured_refs,
        )
        bound_refs = {binding.artifact_ref for _, binding in selected.values()}
        unbound_refs = sorted(configured_refs - bound_refs)
        if unbound_refs:
            raise ValueError(
                "signed runtime catalog models lack expert bindings: "
                + ", ".join(unbound_refs)
            )
        entries = catalog_entries(document, source_root, bound_refs)
        entry_map = {entry.model_ref: entry for entry in entries}
        require_aggregate_scopes(entry_map, scopes)
        configured_refs = {entry.model_ref for entry in entries}
        provenances = tuple(
            RuntimeModelProvenance(
                binding.artifact_ref, binding.expert_id,
                f"{binding.coordinate.package_id}@{binding.coordinate.package_version}",
                f"ollama.local/v1:{binding.artifact_id}",
                scopes[binding.expert_id].intents,
                scopes[binding.expert_id].verifier_ids,
                scopes[binding.expert_id].advisory_authorities,
            )
            for _, binding in sorted(selected.values(), key=lambda item: item[1].expert_id)
            if binding.artifact_ref in configured_refs
        )
        return cls(entries, provenances)

    def entries(self) -> tuple[RuntimeModelEntry, ...]:
        return self._entries

    def get(self, model_ref: str) -> RuntimeModelEntry | None:
        return next((entry for entry in self._entries if entry.model_ref == model_ref), None)

    def for_intent(self, intent: ModelIntent) -> tuple[RuntimeModelEntry, ...]:
        return tuple(entry for entry in self._entries if intent in entry.intents)

    def provenances(self) -> tuple[RuntimeModelProvenance, ...]:
        return self._provenances

    def enabled(self, expert_ids: set[str]) -> "RuntimeModelCatalog":
        provenances = tuple(
            item for item in self._provenances if item.expert_id in expert_ids
        )
        entries = []
        for entry in self._entries:
            scopes = tuple(
                item for item in provenances if item.model_ref == entry.model_ref
            )
            if not scopes:
                continue
            if any(not item.intents for item in scopes):
                entries.append(entry)
                continue
            intents = tuple(
                intent for intent in entry.intents
                if any(intent in item.intents for item in scopes)
            )
            if not intents:
                continue
            verifier_ids = tuple(
                verifier_id for verifier_id in entry.verifier_ids
                if any(verifier_id in item.verifier_ids for item in scopes)
            )
            entries.append(replace(
                entry, intents=intents, verifier_ids=verifier_ids,
            ))
        enabled = RuntimeModelCatalog(
            tuple(entries), provenances,
        )
        if self._available_verifier_ids is not None:
            enabled.require_available_verifiers(self._available_verifier_ids)
        return enabled

    def require_available_verifiers(self, verifier_ids) -> None:
        available = frozenset(verifier_ids)
        for entry in self._entries:
            self._require_entry_verifiers(entry, available)
        self._available_verifier_ids = available

    def validate_runtime_model(self, entry: RuntimeModelEntry) -> None:
        if self._available_verifier_ids is not None:
            self._require_entry_verifiers(entry, self._available_verifier_ids)

    def validate_runtime_install(
        self, entry: RuntimeModelEntry, provenance: RuntimeModelProvenance,
    ) -> None:
        if provenance.model_ref != entry.model_ref:
            raise ValueError("runtime model provenance reference does not match")
        _require_provenance_scope(entry, provenance)
        current = self.get(entry.model_ref)
        owners = {
            item.expert_id for item in self._provenances
            if item.model_ref == entry.model_ref
        }
        if current is not None and provenance.expert_id not in owners:
            raise ValueError(
                f"runtime model {entry.model_ref!r} is already owned by another "
                "catalog expert"
            )
        self.validate_runtime_model(entry)

    def entry_for_provenance(
        self, provenance: RuntimeModelProvenance,
    ) -> RuntimeModelEntry:
        entry = self.get(provenance.model_ref)
        if entry is None:
            raise KeyError("runtime model provenance is not present")
        if not provenance.intents:
            return entry
        return replace(
            entry, intents=provenance.intents,
            verifier_ids=provenance.verifier_ids,
        )

    def install_runtime_model(
        self, entry: RuntimeModelEntry, provenance: RuntimeModelProvenance,
    ) -> None:
        self.validate_runtime_install(entry, provenance)
        entries = {
            item.model_ref: item for item in self._entries
        }
        provenances = {item.expert_id: item for item in self._provenances}
        previous = provenances.get(provenance.expert_id)
        entries[entry.model_ref] = entry
        provenances[provenance.expert_id] = provenance
        if previous is not None and previous.model_ref != provenance.model_ref:
            remaining_refs = {item.model_ref for item in provenances.values()}
            if previous.model_ref not in remaining_refs:
                entries.pop(previous.model_ref, None)
        self._entries = tuple(entries[name] for name in sorted(entries))
        self._provenances = tuple(
            provenances[name] for name in sorted(provenances)
        )

    def remove_runtime_model(self, model_ref: str) -> bool:
        present = any(item.model_ref == model_ref for item in self._entries)
        self._entries = tuple(
            item for item in self._entries if item.model_ref != model_ref
        )
        self._provenances = tuple(
            item for item in self._provenances if item.model_ref != model_ref
        )
        return present

    @staticmethod
    def _require_entry_verifiers(
        entry: RuntimeModelEntry, available: frozenset[str],
    ) -> None:
        missing = sorted(set(entry.verifier_ids) - available)
        if missing:
            raise ValueError(
                f"runtime model {entry.model_ref!r} requires unavailable verifiers: "
                + ", ".join(missing)
            )

def _require_provenance_scope(
    entry: RuntimeModelEntry, provenance: RuntimeModelProvenance,
) -> None:
    if provenance.verifier_ids and not provenance.intents:
        raise ValueError("runtime model provenance verifiers require scoped intents")
    if not provenance.intents:
        return
    if len(set(provenance.intents)) != len(provenance.intents):
        raise ValueError("runtime model provenance intents must be unique")
    if len(set(provenance.verifier_ids)) != len(provenance.verifier_ids):
        raise ValueError("runtime model provenance verifier IDs must be unique")
    if len(set(provenance.advisory_authorities)) != len(
        provenance.advisory_authorities
    ):
        raise ValueError("runtime model advisory authorities must be unique")
    unsupported_intents = sorted(
        set(provenance.intents) - set(entry.intents), key=lambda item: item.value,
    )
    if unsupported_intents:
        raise ValueError(
            "runtime model provenance claims unsupported intents: "
            + ", ".join(item.value for item in unsupported_intents)
        )
    unsupported_verifiers = sorted(
        set(provenance.verifier_ids) - set(entry.verifier_ids),
    )
    if unsupported_verifiers:
        raise ValueError(
            "runtime model provenance claims unsupported verifiers: "
            + ", ".join(unsupported_verifiers)
        )
