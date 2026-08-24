#!/usr/bin/env python3
"""Restrict a stopped candidate state to one signed installed expert."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

import fam_os
from fam_os.product.composition.storage_unit import ProductStorageUnit


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-root", type=Path, required=True)
    parser.add_argument("--model-ref", required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    unit = ProductStorageUnit(arguments.state_root.absolute(), os.geteuid())
    storage = unit.start()
    try:
        if storage.recovery_required or unit.core is None:
            raise RuntimeError("candidate storage requires recovery")
        repository = unit.core.repositories().expert_enablement
        enabled_before = repository.enabled_models()
        selected = tuple(
            (provenance, model) for provenance, model in enabled_before
            if model.model_ref == arguments.model_ref
        )
        if len(selected) != 1:
            raise RuntimeError(
                "signed catalog did not contain exactly one requested expert"
            )
        for provenance, model in enabled_before:
            repository.set_enabled(
                provenance.expert_id, model.model_ref == arguments.model_ref,
            )
        enabled_after = repository.enabled_models()
        if tuple(model.model_ref for _, model in enabled_after) != (arguments.model_ref,):
            raise RuntimeError("candidate expert restriction did not persist exactly")
        document = {
            "candidate_module": str(Path(fam_os.__file__).resolve()),
            "enabled_before": [model.model_ref for _, model in enabled_before],
            "enabled_after": [model.model_ref for _, model in enabled_after],
            "selected_expert_id": selected[0][0].expert_id,
        }
        arguments.output.write_text(
            json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8",
        )
    finally:
        unit.stop()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
