#!/usr/bin/env python3
"""Run the physical Factory lifecycle with candidate-installed product code."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict, is_dataclass
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

import fam_os

if TYPE_CHECKING:
    from .factory_qualification import (
        FactoryQualificationPaths,
        run_factory_qualification,
    )
elif __package__:
    from .factory_qualification import (
        FactoryQualificationPaths,
        run_factory_qualification,
    )
else:
    from factory_qualification import (
        FactoryQualificationPaths,
        run_factory_qualification,
    )  # type: ignore[import-not-found]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--training-artifact", type=Path, required=True)
    parser.add_argument("--conversion-environment", type=Path, required=True)
    parser.add_argument("--conversion-manifest", type=Path, required=True)
    parser.add_argument("--llama-cpp", type=Path, required=True)
    parser.add_argument("--llama-cpp-revision", required=True)
    parser.add_argument("--model-directory", type=Path, required=True)
    parser.add_argument("--prompt-configuration", type=Path, required=True)
    parser.add_argument("--verifier-tests", type=Path, required=True)
    parser.add_argument("--ollama", type=Path, required=True)
    parser.add_argument("--ollama-url", required=True)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--attempt-id", required=True)
    parser.add_argument("--installation-prefix", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    evidence = run_factory_qualification(
        paths=FactoryQualificationPaths(
            arguments.training_artifact, arguments.conversion_environment,
            arguments.conversion_manifest, arguments.llama_cpp,
            arguments.model_directory, arguments.prompt_configuration,
            arguments.verifier_tests, arguments.ollama,
        ),
        run_id=arguments.run_id,
        llama_cpp_revision=arguments.llama_cpp_revision,
        ollama_url=arguments.ollama_url,
        release_attempt_id=arguments.attempt_id,
    )
    module_path = Path(fam_os.__file__).resolve()
    document = {
        "candidate_module": str(module_path),
        "candidate_module_from_install": module_path.is_relative_to(
            arguments.installation_prefix.resolve()
        ),
        "acceptance_composition_imported": _acceptance_composition_imported(),
        "factory_evidence": evidence,
        "passed": bool(
            evidence.get("passed")
            and module_path.is_relative_to(arguments.installation_prefix.resolve())
            and not _acceptance_composition_imported()
        ),
    }
    arguments.output.write_text(
        json.dumps(document, default=_json_default, indent=2, sort_keys=True) + "\n"
    )
    return 0 if document["passed"] else 2


def _json_default(value: object) -> object:
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Object of type {type(value).__name__} is not JSON serializable")


def _acceptance_composition_imported() -> bool:
    return any(name.startswith("tools.phase22_release_exit") for name in sys.modules)


if __name__ == "__main__":
    raise SystemExit(main())
