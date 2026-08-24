#!/usr/bin/env python3
"""Run physical specialist conversion, publication, canary, and lifecycle proof."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.phase22_release_exit.scenario import run_release_exit
from tools.phase22_release_exit.settings import SpecialistReleaseExitPaths


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--release-attempt-id", required=True)
    parser.add_argument("--training-artifact", type=Path, required=True)
    parser.add_argument("--conversion-environment", type=Path, required=True)
    parser.add_argument("--conversion-manifest", type=Path, required=True)
    parser.add_argument("--llama-cpp", type=Path, required=True)
    parser.add_argument("--llama-cpp-revision", required=True)
    parser.add_argument("--model-directory", type=Path, required=True)
    parser.add_argument("--prompt-configuration", type=Path, required=True)
    parser.add_argument("--verifier-tests", type=Path, required=True)
    parser.add_argument("--ollama", type=Path, default=Path("/usr/local/bin/ollama"))
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    arguments = parser.parse_args()
    evidence = run_release_exit(
        paths=SpecialistReleaseExitPaths(
            arguments.training_artifact.absolute(),
            arguments.conversion_environment.absolute(),
            arguments.conversion_manifest.absolute(),
            arguments.llama_cpp.absolute(),
            arguments.model_directory.absolute(),
            arguments.prompt_configuration.absolute(),
            arguments.verifier_tests.absolute(),
            arguments.ollama.absolute(),
        ),
        run_id=arguments.run_id,
        llama_cpp_revision=arguments.llama_cpp_revision,
        ollama_url=arguments.ollama_url,
        release_attempt_id=arguments.release_attempt_id,
    )
    print(json.dumps({
        "evidence": str(
            arguments.training_artifact.absolute()
            / f"release-{arguments.release_attempt_id}/release-evidence.json"
        ),
        "passed": evidence["passed"],
    }, sort_keys=True))
    return 0 if evidence["passed"] is True else 2


if __name__ == "__main__":
    raise SystemExit(main())
