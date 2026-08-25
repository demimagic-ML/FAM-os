#!/usr/bin/env python3
"""Run identical, stateful FAM_OS coding-agent cases against one local model."""

from __future__ import annotations

import argparse
import json
import os
import statistics
import tempfile
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

from fam_os.adapters.ollama import OllamaRuntime, OllamaSettings
from fam_os.core.agent import (
    AgentAuthorityProfile,
    AgentToolDescriptor,
    AgentToolEffect,
    AgentToolRegistry,
    IterativeAgentSettings,
    IterativeModelAgent,
)
from fam_os.product.agent_command_tools import WorkspaceCommandTools
from fam_os.product.agent_model_scorecard import SCORECARD_VERSION
from fam_os.product.agent_turn_store import SQLiteAgentTurnStore
from fam_os.product.agent_workspace_tools import WorkspaceAgentTools
from fam_os.product.storage.database import ProductionDatabase, StorageSettings


@dataclass(frozen=True)
class CaseResult:
    name: str
    passed: bool
    seconds: float
    model_steps: int
    detail: str


def _command_descriptor(name: str) -> AgentToolDescriptor:
    return AgentToolDescriptor(
        name, "Run an argv command in the workspace. Use verify_command for the final check.",
        AgentToolEffect.COMMAND, {
            "type": "object", "properties": {
                "command": {"type": "array", "items": {"type": "string"}},
                "timeout_seconds": {"type": "number"},
            }, "required": ["command"],
        },
    )


def _registry(root: Path, *, commands: bool = False) -> AgentToolRegistry:
    registry = AgentToolRegistry()
    WorkspaceAgentTools(root).register(registry)
    if commands:
        runner = WorkspaceCommandTools(root)
        registry.register(_command_descriptor("run_command"), runner.run_command)

        def verify(arguments):
            output = runner.run_command(arguments)
            if "status=completed" not in output or "exit_code=0" not in output:
                raise RuntimeError(output)
            return output

        registry.register(_command_descriptor("verify_command"), verify)
    return registry


def _run(
    runtime, model_ref: str, database, root: Path, name: str, objective: str,
    validator, *, commands: bool = False, thread: str | None = None,
    maximum_steps: int = 48,
):
    started = time.perf_counter()
    outcome = IterativeModelAgent(
        runtime,
        IterativeAgentSettings(
            model_ref, maximum_steps=maximum_steps, context_tokens=32_768,
            maximum_output_tokens=2_048,
        ),
        _registry(root, commands=commands),
        SQLiteAgentTurnStore(database, str(root)),
        completion_validator=validator,
    ).run(
        thread_id=thread or f"eval-thread-{name}",
        turn_id=f"eval-turn-{name}-{time.time_ns()}", objective=objective,
        profile=AgentAuthorityProfile.WORKSPACE,
    )
    return outcome, time.perf_counter() - started


def _evaluate_case(name, operation):
    try:
        outcome, seconds, passed, detail = operation()
        return CaseResult(name, passed, seconds, outcome.model_steps, detail)
    except Exception as error:
        return CaseResult(name, False, 0.0, 0, f"{type(error).__name__}: {error}"[:2_000])


def evaluate(model_ref: str, endpoint: str) -> tuple[CaseResult, ...]:
    runtime = OllamaRuntime(OllamaSettings(endpoint, 600))
    with tempfile.TemporaryDirectory(prefix="fam-agent-eval-") as directory:
        base = Path(directory)
        database = ProductionDatabase(StorageSettings(
            base / "state" / "agent.sqlite3", os.geteuid(),
        ))
        database.open()
        try:
            cases = []

            def read_file():
                root = base / "read"
                root.mkdir()
                (root / "answer.txt").write_text("ORBIT-417", "utf-8")
                outcome, seconds = _run(
                    runtime, model_ref, database, root, "read", "Read answer.txt and report its exact code.",
                    lambda results: None if any(r.tool_id == "read_file" and "ORBIT-417" in r.output for r in results) else "Read answer.txt before finishing.",
                )
                return outcome, seconds, "ORBIT-417" in outcome.response.content, outcome.response.content
            cases.append(_evaluate_case("read_file", read_file))

            def create_directory():
                root = base / "mkdir"
                root.mkdir()
                outcome, seconds = _run(
                    runtime, model_ref, database, root, "mkdir", "Create a new folder named reports and confirm it exists.",
                    lambda _results: None if (root / "reports").is_dir() else "reports does not exist yet.",
                )
                return outcome, seconds, (root / "reports").is_dir(), outcome.response.content
            cases.append(_evaluate_case("create_directory", create_directory))

            def multi_edit():
                root = base / "edit"
                root.mkdir()
                outcome, seconds = _run(
                    runtime, model_ref, database, root, "edit",
                    "Create alpha.txt, beta.txt, and gamma.txt containing ALPHA, BETA, and GAMMA respectively.",
                    lambda _results: None if all(
                        (root / name).read_text("utf-8") == content
                        for name, content in (("alpha.txt", "ALPHA"), ("beta.txt", "BETA"), ("gamma.txt", "GAMMA"))
                        if (root / name).is_file()
                    ) and all((root / name).is_file() for name in ("alpha.txt", "beta.txt", "gamma.txt")) else "All three exact files are required.",
                )
                passed = all((root / name).is_file() for name in ("alpha.txt", "beta.txt", "gamma.txt"))
                return outcome, seconds, passed, outcome.response.content
            cases.append(_evaluate_case("multi_file_edit", multi_edit))

            def continue_plan():
                root = base / "plan"
                root.mkdir()
                thread = "eval-thread-plan"
                _run(runtime, model_ref, database, root, "plan-first", "Plan how to create planned.txt containing CONTEXT-KEPT. Do not edit yet.", lambda _results: None, thread=thread)
                outcome, seconds = _run(
                    runtime, model_ref, database, root, "plan-second", "Do it now.",
                    lambda _results: None if (root / "planned.txt").is_file() and (root / "planned.txt").read_text("utf-8") == "CONTEXT-KEPT" else "Execute the accepted plan from the goal ledger.", thread=thread,
                )
                return outcome, seconds, (root / "planned.txt").is_file(), outcome.response.content
            cases.append(_evaluate_case("continue_accepted_plan", continue_plan))

            def recover_missing():
                root = base / "recover"
                root.mkdir()
                (root / "fallback.txt").write_text("RECOVERED", "utf-8")
                def validator(results):
                    failed = any(
                        r.tool_id == "run_command" and not r.succeeded
                        for r in results
                    )
                    read = any(r.tool_id == "read_file" and "RECOVERED" in r.output for r in results)
                    return None if failed and read else "Attempt the named missing command once, then recover by reading fallback.txt."
                outcome, seconds = _run(
                    runtime, model_ref, database, root, "recover",
                    "Run definitely-missing-fam-command once. When it fails, do not install anything; read fallback.txt and report its content.", validator, commands=True,
                )
                return outcome, seconds, "RECOVERED" in outcome.response.content, outcome.response.content
            cases.append(_evaluate_case("missing_executable_recovery", recover_missing))

            def approval_resume():
                root = base / "approval"
                root.mkdir()
                thread = "eval-thread-approval"
                _run(runtime, model_ref, database, root, "approval-plan", "Prepare a plan to create approved.txt containing APPROVED-RESUME. Wait for approval.", lambda _results: None, thread=thread)
                outcome, seconds = _run(
                    runtime, model_ref, database, root, "approval-resume", "Approval granted. Resume the accepted work.",
                    lambda _results: None if (root / "approved.txt").is_file() else "Resume the accepted plan and create approved.txt.", thread=thread,
                )
                return outcome, seconds, (root / "approved.txt").is_file(), outcome.response.content
            cases.append(_evaluate_case("approval_resume", approval_resume))

            def fix_test():
                root = base / "fix"
                root.mkdir()
                (root / "calculator.py").write_text("def add(a, b):\n    return a - b\n", "utf-8")
                (root / "test_calculator.py").write_text("from calculator import add\nassert add(2, 3) == 5\n", "utf-8")
                outcome, seconds = _run(
                    runtime, model_ref, database, root, "fix-test",
                    "Run test_calculator.py, diagnose the failure, fix calculator.py, and verify the test passes.",
                    lambda results: None if any(r.tool_id == "verify_command" and r.succeeded for r in results) else "A successful verify_command is required.", commands=True,
                )
                passed = (root / "calculator.py").is_file() and "a + b" in (root / "calculator.py").read_text("utf-8")
                return outcome, seconds, passed, outcome.response.content
            cases.append(_evaluate_case("fix_failing_test", fix_test))

            def long_horizon():
                root = base / "long"
                root.mkdir()
                for index in range(1, 21):
                    (root / f"item-{index:02d}.txt").write_text(f"TOKEN-{index:02d}", "utf-8")
                def validator(results):
                    paths = {
                        r.output.split("\n", 3)[-1] for r in results if r.tool_id == "read_file" and r.succeeded
                    }
                    return None if len(paths) >= 20 else f"Read every item file; only {len(paths)} distinct contents observed."
                outcome, seconds = _run(
                    runtime, model_ref, database, root, "long",
                    "Read all twenty item-01.txt through item-20.txt files, then report the first and last token without losing this goal.", validator, maximum_steps=48,
                )
                return outcome, seconds, "TOKEN-01" in outcome.response.content and "TOKEN-20" in outcome.response.content, outcome.response.content
            cases.append(_evaluate_case("long_horizon_20_tools", long_horizon))
            return tuple(cases)
        finally:
            database.close()


def _write_scorecard(path: Path, model_ref: str, results: tuple[CaseResult, ...]) -> None:
    try:
        document = json.loads(path.read_text("utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        document = {"version": SCORECARD_VERSION, "models": []}
    models = [item for item in document.get("models", []) if item.get("model_ref") != model_ref]
    durations = [item.seconds for item in results if item.seconds > 0]
    models.append({
        "model_ref": model_ref,
        "passed_cases": sum(item.passed for item in results),
        "total_cases": len(results),
        "median_seconds": statistics.median(durations) if durations else 0.0,
        "evaluated_at": datetime.now(timezone.utc).isoformat(),
        "cases": [asdict(item) for item in results],
    })
    document = {"version": SCORECARD_VERSION, "models": models}
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n", "utf-8")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--model", required=True)
    parser.add_argument("--endpoint", default="http://127.0.0.1:11434")
    parser.add_argument("--scorecard", type=Path, required=True)
    args = parser.parse_args()
    results = evaluate(args.model, args.endpoint)
    _write_scorecard(args.scorecard, args.model, results)
    print(json.dumps({"model": args.model, "cases": [asdict(item) for item in results]}, indent=2))
    return 0 if all(item.passed for item in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
