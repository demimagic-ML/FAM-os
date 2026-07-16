#!/usr/bin/env python3
"""Install exact local reference expert definitions without copying Ollama models."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from fam_os.adapters.crypto import Ed25519PackageSignatureVerifier
from fam_os.adapters.filesystem import (
    DirectoryExpertManifestSource,
    JsonPackageLifecycleStateStore,
)
from fam_os.adapters.ollama import (
    OllamaModelArtifactStore,
    OllamaModelCatalog,
    OllamaSettings,
)
from fam_os.experts import (
    ExpertCompatibilityEvaluator,
    ExpertRuntimeBinding,
    validate_runtime_binding,
)
from fam_os.registry import PackageTrustPolicy
from fam_os.registry.lifecycle import ExpertPackageLifecycle
from fam_os.registry.validation import ExpertPackageValidator, PackageValidationRequest
from fam_os.scheduler.resources import EffectiveResourceBudget, HostInventory
from fam_os.schemas import loads_document


def install(args) -> dict[str, object]:
    manifests = DirectoryExpertManifestSource(args.package_root / "experts").load()
    bindings = _bindings(args.package_root / "bindings")
    policy = _load(args.package_root / "trust" / args.trust_policy, PackageTrustPolicy)
    inventory = _load(args.inventory, HostInventory)
    budget = _load(args.budget, EffectiveResourceBudget)
    catalog = OllamaModelCatalog(OllamaSettings(args.ollama_url, args.timeout_seconds))
    validator = ExpertPackageValidator(policy, Ed25519PackageSignatureVerifier())
    lifecycle = ExpertPackageLifecycle(
        JsonPackageLifecycleStateStore(args.state),
        OllamaModelArtifactStore(catalog),
    )
    lifecycle.recover()
    ordered = tuple(sorted(
        manifests,
        key=lambda item: (item.expert_id, item.package.package_version),
    ))
    for manifest in ordered:
        coordinate = (
            manifest.package.package_id,
            manifest.package.package_version,
        )
        binding = bindings[coordinate]
        validate_runtime_binding(manifest, binding)
        observed = catalog.observe(binding.artifact_ref)
        validation = validator.validate(PackageValidationRequest(manifest, observed.digest))
        compatibility = ExpertCompatibilityEvaluator().evaluate(manifest, inventory, budget)
        current = lifecycle.state_store.load()
        operation = (
            lifecycle.update
            if any(item.expert_id == manifest.expert_id for item in current.packages)
            else lifecycle.install
        )
        state = operation(manifest, binding.artifact_ref, validation, compatibility)
    final_state = lifecycle.state_store.load()
    installed = [
        _package_payload(item, bindings)
        for item in final_state.packages
        if (item.coordinate.package_id, item.coordinate.package_version) in bindings
    ]
    return {
        "schema_version": 1,
        "policy_id": policy.policy_id,
        "validation_profile_id": budget.validation_profile.profile_id,
        "state_revision": final_state.revision,
        "packages": installed,
    }


def _package_payload(package, bindings):
    binding = bindings[(
        package.coordinate.package_id,
        package.coordinate.package_version,
    )]
    return {
        "package_id": package.coordinate.package_id,
        "package_version": package.coordinate.package_version,
        "expert_id": package.expert_id,
        "model_ref": binding.artifact_ref,
        "trust": package.effective_trust.value,
        "compatibility": package.compatibility_status.value,
        "enabled": package.enabled,
    }


def _bindings(root):
    values = tuple(_load(path, ExpertRuntimeBinding) for path in sorted(root.glob("*.json")))
    result = {
        (value.coordinate.package_id, value.coordinate.package_version): value
        for value in values
    }
    if len(result) != len(values):
        raise ValueError("runtime binding coordinates must be unique")
    return result


def _load(path, expected_type):
    value = loads_document(path.read_text(encoding="utf-8"))
    if not isinstance(value, expected_type):
        raise ValueError(f"unexpected document type: {path}")
    return value


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--package-root", type=Path, default=Path("configs/packages"))
    parser.add_argument("--trust-policy", default="local-workstation-development.json")
    parser.add_argument("--inventory", type=Path, required=True)
    parser.add_argument("--budget", type=Path, required=True)
    parser.add_argument("--state", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument("--timeout-seconds", type=float, default=10.0)
    args = parser.parse_args()
    report = install(args)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
