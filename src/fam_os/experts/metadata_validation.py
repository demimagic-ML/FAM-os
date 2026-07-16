"""Cross-document validation for routing embeddings and benchmark evidence."""

from __future__ import annotations

from fam_os.experts.benchmark_metadata import ExpertBenchmarkRun
from fam_os.experts.routing_metadata import ExpertRoutingEmbedding


STABLE_TOPOSORT_REQUIREMENTS = frozenset((
    "stable_order.input_order",
    "neighbor_only.initialization",
    "cycle_detection.value_error",
    "input_immutability",
    "forbidden_calls.no_set_min_sorted",
))


def validate_routing_benchmark_links(
    embeddings: tuple[ExpertRoutingEmbedding, ...],
    runs: tuple[ExpertBenchmarkRun, ...],
) -> None:
    by_id = {run.run_id: run for run in runs}
    if len(by_id) != len(runs):
        raise ValueError("benchmark run IDs must be unique")
    for embedding in embeddings:
        for run_id in embedding.benchmark_run_ids:
            run = by_id.get(run_id)
            if run is None:
                raise ValueError("routing embedding references an unknown benchmark run")
            if run.coordinate != embedding.coordinate or run.expert_id != embedding.expert_id:
                raise ValueError("routing embedding benchmark belongs to another expert package")


def require_stable_toposort_regression(
    run: ExpertBenchmarkRun,
    expected_model_ref: str,
) -> None:
    from fam_os.experts.benchmark_metadata import require_full_host_evidence

    require_full_host_evidence(run)
    if run.suite_id != "stable-toposort" or run.suite_version != "2":
        raise ValueError("strong-model evidence requires stable-toposort suite version 2")
    if run.acceptance_policy_id != "stable-toposort-v2":
        raise ValueError("strong-model evidence requires strict v2 acceptance policy")
    if not STABLE_TOPOSORT_REQUIREMENTS.issubset(run.strict_requirement_ids):
        raise ValueError("strong-model evidence omits strict task requirements")
    if any(attempt.model_ref != expected_model_ref for attempt in run.attempts):
        raise ValueError("independent strong-model run cannot mix model references")


def require_successful_stable_toposort_regression(
    run: ExpertBenchmarkRun,
    expected_model_ref: str,
) -> None:
    from fam_os.experts.benchmark_metadata import BenchmarkOutcome

    require_stable_toposort_regression(run, expected_model_ref)
    if run.outcome is BenchmarkOutcome.FAILED:
        raise ValueError("strong-model regression did not pass strict verification")
