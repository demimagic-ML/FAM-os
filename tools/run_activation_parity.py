"""Measure one route-and-expert activation policy through FAM_OS ports."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from fam_os.core.activation import ActivationProbeOutcome, ExpertActivationProbe
from fam_os.core.contracts import TaskRequest
from fam_os.core.execution.placement import PlacementExecutor
from fam_os.core.execution.policy import GenerationSettings
from fam_os.experts import ExpertDescriptor, ExpertTier
from fam_os.routing import ModelRouterSettings, ModelTaskRouter
from fam_os.scheduler import PlacementPlan
from fam_os.supervisor.contracts import ResourceSnapshot
from tools.parity.composition import BenchmarkComposition, load_benchmark_composition
from tools.parity.profile_service import ProfiledOllamaService, ProfiledServiceSettings
from tools.parity.historical_config import ActivationFixture, load_activation_fixture
from tools.parity.report_writer import captured_at, write_report
from tools.parity.serialization import (
    loaded_models_payload,
    metrics_payload,
    resource_payload,
    routing_payload,
)
from tools.parity.static_policy import StaticExpertCatalog, StaticPlacementPlanner


def run_activation_parity(
    config_path: Path,
    output_dir: Path,
    composition: BenchmarkComposition,
) -> tuple[Path, dict[str, Any]]:
    fixture = load_activation_fixture(config_path)
    service_settings = ProfiledServiceSettings(
        fixture.base_url, fixture.timeout_seconds, composition
    )
    with ProfiledOllamaService(service_settings) as service:
        router_expert, code_expert = _experts(fixture)
        catalog = StaticExpertCatalog((router_expert, code_expert))
        evictions = (router_expert.expert_id,) if fixture.evict_kernel else ()
        plan = PlacementPlan(
            code_expert.expert_id,
            composition.placement_budget(fixture.context_tokens),
            evictions,
        )
        planner = StaticPlacementPlanner((plan,))
        placement = PlacementExecutor(service.runtime, catalog, planner)
        router = ModelTaskRouter(
            service.runtime,
            ModelRouterSettings(
                fixture.kernel_model,
                context_tokens=fixture.context_tokens,
                keep_alive=fixture.keep_alive,
            ),
        )
        probe = ExpertActivationProbe(service.runtime, router, catalog, placement)
        outcome = probe.execute(
            TaskRequest("activation-parity", fixture.prompt, ("code",)),
            code_expert.expert_id,
            GenerationSettings(fixture.max_output_tokens, fixture.keep_alive),
        )
        resources = service.snapshot()
    report = _report(config_path, fixture, composition, outcome, resources)
    output = write_report(output_dir, f"activation-{fixture.policy_name}", report)
    return output, report


def _experts(fixture: ActivationFixture) -> tuple[ExpertDescriptor, ExpertDescriptor]:
    context = fixture.context_tokens
    router = ExpertDescriptor(
        "router",
        fixture.kernel_model,
        ExpertTier.MICRO,
        ("routing",),
        context,
        1,
    )
    expert = ExpertDescriptor(
        "code-expert",
        fixture.expert_model,
        ExpertTier.ECONOMICAL,
        ("code",),
        context,
        1,
    )
    return router, expert


def _report(
    config_path: Path,
    fixture: ActivationFixture,
    composition: BenchmarkComposition,
    outcome: ActivationProbeOutcome,
    resources: ResourceSnapshot | None,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "benchmark": "phase1-activation-parity",
        "captured_at": captured_at(),
        "source_config": str(config_path.resolve()),
        "policy": fixture.policy_name,
        "context_tokens": fixture.context_tokens,
        "evict_kernel_before_expert": fixture.evict_kernel,
        "profile_source": str(composition.profile_path) if composition.profile_path else None,
        "budget_source": str(composition.budget_path) if composition.budget_path else None,
        "constraints": composition.constraints_payload(),
        "status": outcome.status.value,
        "routing": routing_payload(outcome.routing),
        "expert_id": outcome.expert_id,
        "expert_metrics": metrics_payload(outcome.metrics),
        "unverified_candidate": outcome.candidate,
        "evicted_expert_ids": list(outcome.evicted_expert_ids),
        "loaded_after_routing": loaded_models_payload(outcome.loaded_after_routing),
        "loaded_after_placement": loaded_models_payload(outcome.loaded_after_placement),
        "loaded_after_expert": loaded_models_payload(outcome.loaded_after_expert),
        "resources": resource_payload(resources),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--effective-budget", type=Path, required=True)
    args = parser.parse_args()
    composition = load_benchmark_composition(args.profile, args.effective_budget)
    output, report = run_activation_parity(args.config, args.output_dir, composition)
    print(json.dumps({"output": str(output), "policy": report["policy"]}, indent=2))


if __name__ == "__main__":
    main()
