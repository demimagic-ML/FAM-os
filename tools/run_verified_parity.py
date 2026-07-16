"""Run migrated verified escalation through one admitted hardware profile."""

from __future__ import annotations

import argparse
import json
from dataclasses import asdict
from pathlib import Path
from typing import Any
from typing import TYPE_CHECKING

from fam_os.adapters.bubblewrap.runner import BubblewrapSandboxRunner
from fam_os.core.contracts import TaskRequest
from fam_os.core.execution import (
    RepairContext,
    VerifiedCodeExecution,
    VerifiedCodePolicy,
)
from fam_os.core.execution.contracts import VerifiedExecutionOutcome
from fam_os.core.execution.placement import PlacementExecutor
from fam_os.core.execution.policy import GenerationSettings
from fam_os.core.ports.inference import LoadedModel
from fam_os.experts import ExpertDescriptor, ExpertTier
from fam_os.routing import ModelRouterSettings, ModelTaskRouter
from fam_os.scheduler import PlacementPlan
from fam_os.supervisor.contracts import ResourceSnapshot
from fam_os.verification.python import (
    PythonVerifier,
    TrustedPythonTests,
    load_trusted_python_tests,
)
from tools.parity.composition import BenchmarkComposition, load_benchmark_composition
from tools.parity.budget import budgeted_attempts
from tools.parity.profile_service import ProfiledOllamaService, ProfiledServiceSettings
from tools.parity.historical_config import VerifiedFixture, load_verified_fixture
from tools.parity.report_writer import captured_at, write_report
from tools.parity.serialization import (
    loaded_models_payload,
    metrics_payload,
    resource_payload,
    routing_payload,
    verification_payload,
)
from tools.parity.static_policy import StaticExpertCatalog, StaticPlacementPlanner

if TYPE_CHECKING:
    from tools.workstation.evidence import WorkstationEvidenceCollector


def run_verified_parity(
    config_path: Path,
    trusted_tests_path: Path,
    output_dir: Path,
    composition: BenchmarkComposition,
    evidence_collector: WorkstationEvidenceCollector | None = None,
) -> tuple[Path, dict[str, Any]]:
    fixture = load_verified_fixture(config_path)
    service_settings = ProfiledServiceSettings(
        fixture.base_url, fixture.timeout_seconds, composition
    )
    with ProfiledOllamaService(service_settings) as service:
        if evidence_collector is not None:
            evidence_collector.capture_before(service)
        outcome, attempt_budget = _execute(service, fixture, trusted_tests_path)
        loaded = service.runtime.loaded_models()
        resources = service.snapshot()
        evidence = (
            evidence_collector.finish(service, loaded, resources)
            if evidence_collector is not None
            else None
        )
    report = _report(
        config_path,
        trusted_tests_path,
        fixture,
        composition,
        outcome,
        loaded,
        resources,
    )
    report["global_attempt_budget"] = asdict(attempt_budget)
    if evidence is not None:
        _scrub_local_paths(report, config_path, trusted_tests_path, composition)
        report["benchmark"] = "phase2-full-workstation-smoke"
        report["workstation_evidence"] = evidence
        report["smoke_checks"] = _smoke_checks(report, evidence)
    prefix = "workstation-smoke" if evidence is not None else "verified-parity"
    output = write_report(output_dir, prefix, report)
    return output, report


def _scrub_local_paths(
    report: dict[str, Any],
    config_path: Path,
    tests_path: Path,
    composition: BenchmarkComposition,
) -> None:
    report["source_config"] = config_path.name
    report["trusted_tests"] = tests_path.name
    report["profile_source"] = (
        composition.profile_path.name if composition.profile_path else None
    )
    report["budget_source"] = (
        composition.budget_path.name if composition.budget_path else None
    )
    report["privacy_review"] = {
        "local_paths_redacted": True,
        "retained_source_identity": "filename_only",
    }


def _smoke_checks(
    report: dict[str, Any], evidence: dict[str, object]
) -> dict[str, object]:
    availability = evidence["measurement_availability"]
    attempts = report["attempts"]
    checks = {
        "verified_quality": bool(report["result"]["verified"]),
        "cpu_recorded": bool(availability["cpu"]),
        "ram_recorded": bool(availability["ram"]),
        "vram_recorded": bool(availability["vram"]),
        "model_transfers_recorded": bool(availability["model_transfers"]),
        "ssd_io_recorded": bool(availability["ssd_io"]),
        "latency_recorded": all(item["metrics"] is not None for item in attempts),
        "failures_recorded": all(item["verification"] is not None for item in attempts),
    }
    return {"passed": all(checks.values()), "checks": checks}


def _execute(
    service: ProfiledOllamaService,
    fixture: VerifiedFixture,
    trusted_tests_path: Path,
) -> tuple[VerifiedExecutionOutcome, object]:
    tests = load_trusted_python_tests(trusted_tests_path, "stable-toposort-v2")
    use_case, economical, escalation, ledger = _use_case(
        service, fixture, tests, service.settings.composition
    )
    request = TaskRequest(
        "verified-parity",
        fixture.prompt,
        ("python",),
        verification_required=True,
    )
    outcome = use_case.execute(request, _policy(fixture, economical, escalation, tests))
    return outcome, ledger.snapshot()


def _use_case(
    service: ProfiledOllamaService,
    fixture: VerifiedFixture,
    tests: TrustedPythonTests,
    composition: BenchmarkComposition,
) -> tuple[VerifiedCodeExecution, ExpertDescriptor, ExpertDescriptor, object]:
    router_expert, economical, escalation = _experts(fixture)
    catalog = StaticExpertCatalog((router_expert, economical, escalation))
    budget = composition.placement_budget(fixture.context_tokens)
    evictions = (
        (economical.expert_id, router_expert.expert_id)
        if fixture.evict_before_escalation
        else ()
    )
    planner = StaticPlacementPlanner(
        (
            PlacementPlan(economical.expert_id, budget),
            PlacementPlan(escalation.expert_id, budget, evictions),
        )
    )
    placement = PlacementExecutor(service.runtime, catalog, planner)
    router = ModelTaskRouter(
        service.runtime,
        ModelRouterSettings(
            fixture.kernel_model,
            context_tokens=fixture.context_tokens,
            keep_alive=fixture.keep_alive,
        ),
    )
    verifier = PythonVerifier(BubblewrapSandboxRunner(), tests)
    budgeted, ledger = budgeted_attempts(service, fixture, verifier)
    use_case = VerifiedCodeExecution(router, catalog, placement, budgeted)
    return use_case, economical, escalation, ledger


def _policy(
    fixture: VerifiedFixture,
    economical: ExpertDescriptor,
    escalation: ExpertDescriptor,
    tests: TrustedPythonTests,
) -> VerifiedCodePolicy:
    return VerifiedCodePolicy(
        economical_expert_id=economical.expert_id,
        generation=GenerationSettings(fixture.max_output_tokens, fixture.keep_alive),
        repair_attempts=fixture.repair_attempts,
        escalate_on_failure=fixture.escalate_on_failure,
        escalation_expert_id=escalation.expert_id,
        escalation_repair_attempts=fixture.escalation_repair_attempts,
        repair_guidance=fixture.repair_guidance,
        repair_context=RepairContext(tests.source, fixture.repair_examples),
    )


def _experts(
    fixture: VerifiedFixture,
) -> tuple[ExpertDescriptor, ExpertDescriptor, ExpertDescriptor]:
    context = fixture.context_tokens
    router = ExpertDescriptor(
        "router", fixture.kernel_model, ExpertTier.MICRO, ("routing",), context, 1
    )
    economical = ExpertDescriptor(
        "economical",
        fixture.economical_model,
        ExpertTier.ECONOMICAL,
        ("code",),
        context,
        1,
        ("python-tests-v1",),
    )
    escalation = ExpertDescriptor(
        "escalation",
        fixture.escalation_model,
        ExpertTier.ESCALATION,
        ("code",),
        context,
        1,
        ("python-tests-v1",),
    )
    return router, economical, escalation


def _report(
    config_path: Path,
    tests_path: Path,
    fixture: VerifiedFixture,
    composition: BenchmarkComposition,
    outcome: VerifiedExecutionOutcome,
    loaded: tuple[LoadedModel, ...],
    resources: ResourceSnapshot | None,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "benchmark": "phase1-verified-parity",
        "captured_at": captured_at(),
        "source_config": str(config_path.resolve()),
        "trusted_tests": str(tests_path.resolve()),
        "context_tokens": fixture.context_tokens,
        "profile_source": str(composition.profile_path) if composition.profile_path else None,
        "budget_source": str(composition.budget_path) if composition.budget_path else None,
        "constraints": composition.constraints_payload(),
        "routing": routing_payload(outcome.routing),
        "status": outcome.status.value,
        "result": {
            "status": outcome.result.status.value,
            "verified": outcome.result.verified,
            "content": outcome.result.content,
            "reason": outcome.result.reason,
        },
        "attempts": [
            {
                "attempt_id": attempt.attempt_id,
                "kind": attempt.kind.value,
                "expert_id": attempt.expert_id,
                "model_ref": attempt.model_ref,
                "candidate": attempt.candidate,
                "metrics": metrics_payload(attempt.metrics),
                "verification": verification_payload(attempt.verification),
            }
            for attempt in outcome.attempts
        ],
        "evicted_expert_ids": list(outcome.evicted_expert_ids),
        "loaded_models": loaded_models_payload(loaded),
        "resources": resource_payload(resources),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--trusted-tests", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--profile", type=Path, required=True)
    parser.add_argument("--effective-budget", type=Path, required=True)
    args = parser.parse_args()
    composition = load_benchmark_composition(args.profile, args.effective_budget)
    output, report = run_verified_parity(
        args.config, args.trusted_tests, args.output_dir, composition
    )
    print(
        json.dumps(
            {"output": str(output), "status": report["status"], "result": report["result"]},
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
