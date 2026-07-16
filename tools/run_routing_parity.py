"""Run the frozen 24-case router workload through migrated FAM_OS ports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from fam_os.routing.evaluation import (
    RoutingCaseResult,
    RoutingModelSummary,
    evaluate_routing_model,
    parse_routing_cases,
    summarize_routing_model,
)
from fam_os.routing.inference import ModelRouterSettings
from tools.parity.composition import BenchmarkComposition, load_benchmark_composition
from tools.parity.profile_service import ProfiledOllamaService, ProfiledServiceSettings
from tools.parity.report_writer import captured_at, write_report


def run_routing_parity(
    config_path: Path,
    output_dir: Path,
    composition: BenchmarkComposition,
) -> tuple[Path, dict[str, Any]]:
    from tools.parity.historical_config import load_routing_fixture

    fixture = load_routing_fixture(config_path)
    cases = parse_routing_cases(
        fixture.tasks_file.read_text(encoding="utf-8").splitlines()
    )
    report: dict[str, Any] = {
        "schema_version": 1,
        "benchmark": "phase1-routing-parity",
        "started_at": captured_at(),
        "source_config": str(config_path.resolve()),
        "profile_source": str(composition.profile_path) if composition.profile_path else None,
        "budget_source": str(composition.budget_path) if composition.budget_path else None,
        "constraints": composition.constraints_payload(),
        "models": [],
    }
    service_settings = ProfiledServiceSettings(
        fixture.base_url, fixture.timeout_seconds, composition
    )
    with ProfiledOllamaService(service_settings) as service:
        for model_ref in fixture.models:
            settings = ModelRouterSettings(
                model_ref=model_ref,
                context_tokens=fixture.context_tokens,
                max_output_tokens=100,
                keep_alive=fixture.keep_alive,
                temperature=fixture.temperature,
                seed=fixture.seed,
            )
            results = evaluate_routing_model(service.runtime, settings, cases)
            summary = summarize_routing_model(model_ref, results)
            report["models"].append(_model_payload(summary, results))
            service.runtime.unload(model_ref)
        from tools.parity.serialization import resource_payload

        report["resources"] = resource_payload(service.snapshot())
    report["finished_at"] = captured_at()
    output = write_report(output_dir, "routing-parity", report)
    return output, report


def _model_payload(
    summary: RoutingModelSummary,
    results: tuple[RoutingCaseResult, ...],
) -> dict[str, Any]:
    return {
        "summary": {
            "model": summary.model_ref,
            "accuracy": summary.accuracy,
            "correct": summary.correct,
            "total": summary.total,
            "valid_json_rate": summary.structured_rate,
            "mean_wall_seconds": summary.mean_wall_seconds,
            "mean_load_seconds": summary.mean_load_seconds,
            "mean_generation_tokens_per_second": summary.mean_generation_tokens_per_second,
            "by_expected_route": {
                item.route.value: {"correct": item.correct, "total": item.total}
                for item in summary.by_expected_route
            },
        },
        "results": [_case_payload(result) for result in results],
    }


def _case_payload(result: RoutingCaseResult) -> dict[str, Any]:
    metrics = result.metrics
    return {
        "task_id": result.case.case_id,
        "expected_route": result.case.expected_route.value,
        "predicted_route": result.predicted_route.value if result.predicted_route else None,
        "correct": result.correct,
        "valid_json": result.structured,
        "response": result.response,
        "wall_seconds": metrics.wall_seconds,
        "load_seconds": metrics.load_seconds,
        "prompt_tokens": metrics.prompt_tokens,
        "output_tokens": metrics.output_tokens,
        "generation_tokens_per_second": metrics.generation_tokens_per_second,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--effective-budget", type=Path, required=True)
    args = parser.parse_args()
    composition = load_benchmark_composition(args.profile, args.effective_budget)
    output, report = run_routing_parity(args.config, args.output_dir, composition)
    summary = report["models"][0]["summary"]
    print(json.dumps({"output": str(output), "summary": summary}, indent=2))


if __name__ == "__main__":
    main()
