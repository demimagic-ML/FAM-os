#!/usr/bin/env python3
"""Run the signed installed Phase 23.5 soak or a non-qualifying preflight."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from tools.phase23_soak.contracts import SoakSettings
from tools.phase23_soak.scenario import run_installed_soak


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--output-root", type=Path, required=True)
    parser.add_argument("--duration-seconds", type=float, default=86_400)
    parser.add_argument("--request-interval-seconds", type=float, default=300)
    parser.add_argument("--connector-interval-seconds", type=float, default=14_400)
    parser.add_argument("--daemon-restart-interval-seconds", type=float, default=21_600)
    parser.add_argument("--provider-crash-interval-seconds", type=float, default=28_800)
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11435")
    parser.add_argument("--owner-ollama-url", default="http://127.0.0.1:11434")
    parser.add_argument(
        "--source-model-root", type=Path,
        default=Path("/usr/share/ollama/.ollama/models"),
    )
    parser.add_argument(
        "--light-model-pressure", action="store_true",
        help="Use only the economical model; this can never pass Phase 23.5.",
    )
    arguments = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    document = run_installed_soak(SoakSettings(
        repository=repository,
        output_root=arguments.output_root.absolute(),
        run_id=arguments.run_id,
        duration_seconds=arguments.duration_seconds,
        request_interval_seconds=arguments.request_interval_seconds,
        connector_interval_seconds=arguments.connector_interval_seconds,
        daemon_restart_interval_seconds=arguments.daemon_restart_interval_seconds,
        provider_crash_interval_seconds=arguments.provider_crash_interval_seconds,
        ollama_url=arguments.ollama_url,
        owner_ollama_url=arguments.owner_ollama_url,
        source_model_root=arguments.source_model_root.absolute(),
        full_model_pressure=not arguments.light_model_pressure,
    ))
    print(json.dumps({
        "evidence": str(arguments.output_root.absolute() / "installed-soak.json"),
        "preflight_passed": document["preflight_passed"],
        "qualification_passed": document["qualification_passed"],
    }, sort_keys=True))
    return 0 if document["preflight_passed"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
