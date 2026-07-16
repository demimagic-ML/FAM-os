#!/usr/bin/env python3
"""Run the live advisory-reasoning and deterministic-solver proof."""

import argparse
import hashlib
import json
from dataclasses import asdict
from pathlib import Path

from fam_os.adapters.ollama import OllamaModelCatalog, OllamaRuntime, OllamaSettings
from fam_os.adapters.ollama.math_reasoner import OllamaMathReasoner
from fam_os.experts.math_evidence import MathBenchmarkCaseResult, MathExpertEvidence
from fam_os.experts.math_experts import DeterministicMathSolver, MathSolverKind, MathSolverRequest


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--ollama-url", default="http://127.0.0.1:11434")
    args = parser.parse_args()
    fixture = json.loads(args.fixture.read_text())
    settings = OllamaSettings(args.ollama_url, 180)
    reasoner = OllamaMathReasoner(OllamaRuntime(settings), "llama3.2:3b")
    solver = DeterministicMathSolver()
    cases = tuple(_run_case(raw, reasoner, solver) for raw in fixture["cases"])
    evidence = MathExpertEvidence(
        "phase9.5-workstation-v1", "expert.math.llama3.2-reasoning",
        OllamaModelCatalog(settings).observe("llama3.2:3b").digest.value,
        "expert.math.deterministic-solvers-v1", _solver_digest(), cases,
        all(case.passed for case in cases),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(asdict(evidence), indent=2, sort_keys=True) + "\n")


def _run_case(raw, reasoner, solver):
    advice = reasoner.reason(raw["case_id"], raw["prompt"])
    request = MathSolverRequest(
        raw["case_id"], MathSolverKind(raw["kind"]), raw["expression"], raw["variable"],
    )
    result = solver.solve(request)
    expected = raw["expected_exact_result"]
    return MathBenchmarkCaseResult(raw["case_id"], advice, result, expected, result.exact_result == expected)


def _solver_digest() -> str:
    path = Path(__file__).parents[1] / "src/fam_os/experts/math_experts.py"
    return hashlib.sha256(path.read_bytes()).hexdigest()


if __name__ == "__main__":
    main()
