"""Validate and seal the content-free signed-installed Phase 22 exit record."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from fam_os.product.bundle_installation import SignedBundleInstallation
from fam_os.product.update_contracts import SignedReleaseManifest
from fam_os.schemas import loads_document
from tools.phase22_release_exit.evidence import write_release_evidence


def finalize_phase22_exit(
    *, training_evidence_path: Path, release_evidence_path: Path,
    installation_prefix: Path, release_manifest_path: Path, output_path: Path,
) -> dict[str, object]:
    training = _document(training_evidence_path)
    release = _document(release_evidence_path)
    installation = SignedBundleInstallation(installation_prefix, {})
    diagnosis = installation.diagnose()
    manifest_value = loads_document(release_manifest_path.read_text("utf-8"))
    if not isinstance(manifest_value, SignedReleaseManifest):
        raise RuntimeError("signed installed release manifest is invalid")
    product_runtime = release.get("product_runtime")
    if not isinstance(product_runtime, dict):
        raise RuntimeError("release evidence lacks product runtime identity")
    module_value = product_runtime.get("module_path")
    if not isinstance(module_value, str):
        raise RuntimeError("release product module path is invalid")
    module_path = Path(module_value).resolve(strict=True)
    installed_runtime = module_path.is_relative_to(installation_prefix.resolve())
    checks = _phase_checks(training, release)
    checks.update({
        "installed_runtime": installed_runtime,
        "signed_install_healthy": diagnosis.healthy,
        "signed_release_complete": len(manifest_value.components) == 7,
        "signed_release_matches_diagnosis": (
            diagnosis.release_id == manifest_value.release_id
        ),
    })
    installation.remove()
    complete_removal = not installation_prefix.exists()
    checks["complete_signed_install_removal"] = complete_removal
    document: dict[str, object] = {
        "checks": checks,
        "contract_version": "fam.factory.phase22-exit/v1alpha1",
        "evaluation_decision_sha256": _nested_text(
            training, "evaluation", "decision_sha256",
        ),
        "passed": all(checks.values()),
        "release_evidence_sha256": _sha(release_evidence_path),
        "run_id": _text(training, "run_id"),
        "sealed_suite_sha256": _nested_text(
            training, "sealed_suite", "sha256",
        ),
        "signed_installation": {
            "component_count": len(manifest_value.components),
            "diagnosed_file_count": len(diagnosis.files),
            "module_path_before_removal": str(module_path),
            "module_sha256": _text(product_runtime, "module_sha256"),
            "release_id": manifest_value.release_id,
            "release_manifest_sha256": _sha(release_manifest_path),
            "signer_key_id": manifest_value.signer_key_id,
        },
        "training_evidence_sha256": _sha(training_evidence_path),
    }
    write_release_evidence(output_path, document)
    return document


def _phase_checks(
    training: dict[str, object], release: dict[str, object],
) -> dict[str, bool]:
    return {
        "activation_allowed": _nested_bool(release, "activation", "activate"),
        "adapter_promotable": _nested_bool(
            training, "evaluation", "promotable",
        ),
        "artifact_removed": _nested_bool(
            release, "retirement", "artifact_removed",
        ),
        "audit_retained": _bool(release, "audit_retained"),
        "canary_completed": _nested_text(
            release, "canary", "status",
        ) == "completed",
        "canary_outputs_discarded": _nested_bool(
            release, "canary", "outputs_discarded",
        ),
        "canary_passed": (
            _nested_integer(release, "canary", "case_count")
            == _nested_integer(release, "canary", "passed_case_count")
            and _nested_integer(release, "canary", "verifier_failure_count") == 0
        ),
        "conversion_completed": _nested_text(
            release, "conversion", "status",
        ) == "completed",
        "conversion_network_denied": _nested_bool(
            release, "conversion", "network_denied",
        ),
        "held_out_discarded": _nested_bool(
            training, "evaluation", "held_out_plaintext_discarded",
        ),
        "package_installed_disabled": _nested_bool(
            release, "package", "installed_disabled",
        ),
        "physical_checkpoint_passed": _bool(training, "passed"),
        "reactivated": _integer(release, "reactivated_lifecycle_revision") > 0,
        "release_checkpoint_passed": _bool(release, "passed"),
        "retirement_removed_runtime": _nested_bool(
            release, "retirement", "runtime_model_removed",
        ),
        "rollback_removed_runtime": _nested_bool(
            release, "rollback", "runtime_model_removed",
        ),
        "training_base_frozen": _nested_bool(
            training, "training", "base_weights_frozen",
        ),
        "training_held_out_absent": _nested_bool(
            training, "training", "held_out_absent",
        ),
        "training_network_denied": _nested_bool(
            training, "training", "network_denied",
        ),
    }


def _document(path: Path) -> dict[str, object]:
    if not path.is_file() or path.is_symlink():
        raise ValueError("Phase 22 evidence path is unavailable or unsafe")
    value = json.loads(path.read_text("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("Phase 22 evidence document is invalid")
    return value


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _value(document: dict[str, object], *names: str) -> object:
    value: object = document
    for name in names:
        if not isinstance(value, dict) or name not in value:
            raise ValueError(f"Phase 22 evidence lacks {'.'.join(names)}")
        value = value[name]
    return value


def _text(document: dict[str, object], name: str) -> str:
    value = _value(document, name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Phase 22 evidence {name} is invalid")
    return value


def _nested_text(document: dict[str, object], parent: str, name: str) -> str:
    value = _value(document, parent, name)
    if not isinstance(value, str) or not value:
        raise ValueError(f"Phase 22 evidence {parent}.{name} is invalid")
    return value


def _bool(document: dict[str, object], name: str) -> bool:
    value = _value(document, name)
    if not isinstance(value, bool):
        raise ValueError(f"Phase 22 evidence {name} is invalid")
    return value


def _nested_bool(document: dict[str, object], parent: str, name: str) -> bool:
    value = _value(document, parent, name)
    if not isinstance(value, bool):
        raise ValueError(f"Phase 22 evidence {parent}.{name} is invalid")
    return value


def _integer(document: dict[str, object], name: str) -> int:
    value = _value(document, name)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"Phase 22 evidence {name} is invalid")
    return value


def _nested_integer(document: dict[str, object], parent: str, name: str) -> int:
    value = _value(document, parent, name)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"Phase 22 evidence {parent}.{name} is invalid")
    return value
