"""Read-only unfamiliar-repository analysis and restart-safe task graph tests."""

from dataclasses import replace
from datetime import timedelta
import json
from pathlib import Path
import tempfile
import unittest

from fam_os.adapters.filesystem.engineering_task_graph import (
    JsonlEngineeringTaskGraphRepository,
)
from fam_os.core.engineering.repository import (
    ArchitectureArea,
    BoundedRepositoryPlanner,
    EngineeringTaskGraphEvent,
    EngineeringTaskGraphEventKind,
    EngineeringTaskGraphService,
    EngineeringTaskStepState,
    RepositoryContextTrust,
)
from tests.contract.schema_repository_fixtures import (
    NOW,
    analysis_request,
    repository_evidence,
    task_graph,
    task_graph_event,
)


class FakeRepositoryEvidenceAdapter:
    def __init__(self, evidence) -> None:
        self.evidence = evidence
        self.calls = []
        self.mutations = 0

    def observe(self, request):
        self.calls.append(request.request_id)
        return self.evidence


def event(sequence, step, kind, *, checkpoint=False, terminal=False):
    return EngineeringTaskGraphEvent(
        f"event-{sequence}", "graph-repository-1", "task-repository-1",
        sequence, NOW + timedelta(seconds=sequence), kind, step,
        EngineeringTaskStepState.SUCCEEDED,
        300 - sequence, 100_000 - sequence, 20_000 - sequence,
        (f"evidence-{sequence}",), "completed", checkpoint, terminal,
    )


class RepositoryIntelligenceTests(unittest.TestCase):
    def test_unfamiliar_repository_trace_and_decision_complete_design_are_read_only(self) -> None:
        request = analysis_request()
        adapter = FakeRepositoryEvidenceAdapter(repository_evidence())
        evidence = adapter.observe(request)
        planner = BoundedRepositoryPlanner()

        analysis = planner.analyze(request, evidence, completed_at=NOW)
        proposal = planner.propose(request, analysis, evidence, created_at=NOW)

        self.assertEqual(
            ("symbol-controller", "symbol-service", "symbol-adapter"),
            tuple(item.symbol_id for item in analysis.implementation_path),
        )
        self.assertEqual(("tests/test_service.py",), analysis.affected_test_paths)
        self.assertEqual(set(ArchitectureArea), {item.area for item in proposal.decisions})
        self.assertFalse(analysis.mutation_performed)
        self.assertFalse(proposal.mutation_performed)
        self.assertEqual(0, adapter.mutations)

    def test_repository_instructions_comments_and_metadata_remain_untrusted_context(self) -> None:
        evidence = repository_evidence()
        self.assertTrue(all(
            item.trust is RepositoryContextTrust.UNTRUSTED_CONTEXT
            for item in evidence.context_records
        ))
        planner = BoundedRepositoryPlanner()
        analysis = planner.analyze(analysis_request(), evidence, completed_at=NOW)
        proposal = planner.propose(
            analysis_request(), analysis, evidence, created_at=NOW,
        )
        security = next(
            item for item in proposal.decisions
            if item.area is ArchitectureArea.SECURITY_BOUNDARIES
        )
        self.assertIn("untrusted context", security.decision)
        self.assertNotIn("delete tests", security.decision)
        self.assertFalse(proposal.mutation_performed)

    def test_declared_bounds_and_missing_symbol_fail_closed(self) -> None:
        evidence = repository_evidence()
        with self.assertRaisesRegex(ValueError, "observation bounds"):
            replace(
                evidence,
                bounds=replace(evidence.bounds, maximum_symbols=1),
            )
        request = replace(analysis_request(), entry_symbol_ids=("missing",))
        with self.assertRaisesRegex(ValueError, "entry symbol"):
            BoundedRepositoryPlanner().analyze(request, evidence, completed_at=NOW)

    def test_append_only_graph_survives_restart_and_enforces_monotonic_budget(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "engineering-graph.jsonl"
            graph = task_graph()
            first_repository = JsonlEngineeringTaskGraphRepository(path)
            first_service = EngineeringTaskGraphService(first_repository)
            self.assertTrue(first_service.append(graph, task_graph_event()))
            self.assertTrue(first_service.append(
                graph,
                event(1, "observe", EngineeringTaskGraphEventKind.STEP_COMPLETED),
            ))

            restarted = JsonlEngineeringTaskGraphRepository(path)
            self.assertEqual(2, len(restarted.history(graph.graph_id)))
            with self.assertRaisesRegex(ValueError, "budget cannot increase"):
                EngineeringTaskGraphService(restarted).append(
                    graph,
                    replace(
                        event(2, "trace", EngineeringTaskGraphEventKind.STEP_COMPLETED),
                        remaining_wall_seconds=400,
                    ),
                )
            self.assertEqual(2, len(restarted.history(graph.graph_id)))

    def test_checkpoint_and_terminal_are_append_only_and_tamper_evident(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory).resolve() / "engineering-graph.jsonl"
            graph = task_graph()
            repository = JsonlEngineeringTaskGraphRepository(path)
            service = EngineeringTaskGraphService(repository)
            events = (
                task_graph_event(),
                event(1, "observe", EngineeringTaskGraphEventKind.STEP_COMPLETED),
                event(2, "analyze", EngineeringTaskGraphEventKind.STEP_COMPLETED),
                event(3, "trace", EngineeringTaskGraphEventKind.STEP_COMPLETED),
                event(
                    4, "design", EngineeringTaskGraphEventKind.CHECKPOINT_REACHED,
                    checkpoint=True,
                ),
                event(
                    5, "terminal", EngineeringTaskGraphEventKind.TERMINATED,
                    terminal=True,
                ),
            )
            for item in events:
                self.assertTrue(service.append(graph, item))
            with self.assertRaisesRegex(ValueError, "cannot advance"):
                service.append(graph, replace(events[-1], sequence=6, event_id="late"))

            records = path.read_text(encoding="utf-8").splitlines()
            document = json.loads(records[1])
            document["event"]["payload"]["reason_code"] = "tampered"
            records[1] = json.dumps(document, sort_keys=True, separators=(",", ":"))
            path.write_text("\n".join(records) + "\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "digest"):
                JsonlEngineeringTaskGraphRepository(path).history(graph.graph_id)


if __name__ == "__main__":
    unittest.main()
