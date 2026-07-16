#!/usr/bin/env python3
"""Benchmark the four deterministic advisory micro-experts."""

import argparse
import hashlib
import json
from pathlib import Path

from fam_os.experts import (
    ComplexityMicroExpert, LanguageDetectionMicroExpert, MicroExpertBenchmarkReport,
    MicroExpertBenchmarkResult, RoutingMicroExpert, SafetyMicroExpert,
)
from fam_os.schemas import dumps_document


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    cases = json.loads(args.fixture.read_text())
    digest = hashlib.sha256(args.fixture.read_bytes()).hexdigest()
    experts = (
        ("routing", RoutingMicroExpert()), ("language", LanguageDetectionMicroExpert()),
        ("safety", SafetyMicroExpert()), ("complexity", ComplexityMicroExpert()),
    )
    results = tuple(_result(expert, cases[name], digest) for name, expert in experts)
    report = MicroExpertBenchmarkReport(
        "micro-classification-v1", results, 900_000,
        all(item.accuracy_millionths >= 900_000 for item in results),
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(dumps_document(report) + "\n")
    print(json.dumps({"output": str(args.output), "passed": report.passed}, indent=2))


def _result(expert, rows, digest):
    correct = sum(expert.advise(text).label == expected for text, expected in rows)
    return MicroExpertBenchmarkResult(
        expert.expert_id, len(rows), correct, correct * 1_000_000 // len(rows), digest,
    )


if __name__ == "__main__":
    main()
