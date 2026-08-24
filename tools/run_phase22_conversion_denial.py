"""Prove a non-promotable adapter cannot enter runtime conversion."""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import asdict
from pathlib import Path

from fam_os.adapters.training.conversion_environment import (
    LlamaCppConversionEnvironmentProbe,
)
from fam_os.expert_factory import ConversionOutputType
from fam_os.product.composition.core_storage import CoreStorageComposition
from fam_os.product.factory_conversion import ProductFactoryConversions
from fam_os.product.owner_identity import local_owner_id
from fam_os.product.storage import OwnerKeyStore, ProductionDatabase, SecureStorage, StorageSettings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--training-artifact", type=Path, required=True)
    parser.add_argument("--environment", type=Path, required=True)
    parser.add_argument("--wheelhouse-manifest", type=Path, required=True)
    parser.add_argument("--llama-cpp", type=Path, required=True)
    parser.add_argument("--revision", required=True)
    parser.add_argument("--ollama", type=Path, default=Path("/usr/local/bin/ollama"))
    arguments = parser.parse_args()
    artifact = arguments.training_artifact.absolute()
    state = artifact / "state"
    database = ProductionDatabase(StorageSettings(state / "fam.sqlite3", os.geteuid()))
    opened = SecureStorage(
        database, OwnerKeyStore(state / "master.key", os.geteuid()),
    ).open()
    if opened.recovery_required or opened.cipher is None:
        raise RuntimeError("conversion denial storage is unavailable")
    repositories = CoreStorageComposition(
        database, opened.cipher, local_owner_id(os.geteuid()),
    ).repositories()
    probe = LlamaCppConversionEnvironmentProbe(
        environment_directory=arguments.environment.absolute(),
        wheelhouse_manifest=arguments.wheelhouse_manifest.absolute(),
        llama_cpp_directory=arguments.llama_cpp.absolute(),
        expected_revision=arguments.revision,
        ollama=arguments.ollama.absolute(),
    )
    service = ProductFactoryConversions(repositories, probe)
    try:
        environment = service.probe_environment()
        decision = repositories.factory_evaluations.decisions()[-1]
        denied = False
        reason = ""
        try:
            service.issue(
                request_id="phase22-nonpromotable-denial",
                evaluation_id=decision.evaluation_id,
                environment_sha256=environment.manifest_sha256,
                base_output_type=ConversionOutputType.BF16,
                adapter_output_type=ConversionOutputType.F16,
                runtime_model_ref="fam-code-specialist:canary",
                maximum_output_bytes=8_000_000_000,
                maximum_wall_seconds=3600,
                maximum_ram_bytes=32 * 1024**3,
                maximum_cpu_cores=12,
                one_use_conversion_id="phase22-conversion-denied",
                lifetime_seconds=3600, confirmed=True,
            )
        except PermissionError as error:
            denied = True
            reason = str(error)
        evidence = {
            "contract_version": "fam.factory.conversion-denial/v1alpha1",
            "environment": _json(asdict(environment)),
            "decision_id": decision.decision_id,
            "decision_sha256": decision.decision_sha256,
            "promotable": decision.promotable,
            "denied_before_approval": denied,
            "reason": reason,
            "approval_count": len(repositories.factory_conversions.approvals()),
            "passed": denied and not decision.promotable
            and not repositories.factory_conversions.approvals(),
        }
    finally:
        database.close()
    output = artifact / "conversion-denial-evidence.json"
    output.write_text(json.dumps(evidence, indent=2, sort_keys=True) + "\n")
    print(json.dumps({"evidence": str(output), "passed": evidence["passed"]}))
    return 0 if evidence["passed"] is True else 1


def _json(value: object) -> object:
    from datetime import datetime
    from enum import Enum

    if isinstance(value, Enum):
        return value.value
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {str(key): _json(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_json(item) for item in value]
    return value


if __name__ == "__main__":
    raise SystemExit(main())
