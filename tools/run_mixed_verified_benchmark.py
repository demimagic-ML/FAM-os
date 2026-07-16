#!/usr/bin/env python3
"""Compose and execute the Phase 9.1 cross-family verified benchmark."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from fam_os.experts import (
    BenchmarkTaskFamily, ExpertTier, MixedBenchmarkCaseResult,
    MixedBenchmarkReport, MixedBenchmarkSuite, StrongRegressionRunRef,
    validate_mixed_report,
)
from fam_os.schemas import dumps_document, loads_document
from fam_os.verification import RetrievalCitation, RetrievalCitationVerifier, RetrievalClaim, RetrievedSource
from fam_os.verification.math_contracts import MathVerificationRequest
from fam_os.verification.math_sympy import SympyMathVerifier


FIXTURES = {
    BenchmarkTaskFamily.KERNEL_ONLY: Path("tests/fixtures/mixed_benchmark/kernel-only.json"),
    BenchmarkTaskFamily.CODE: Path("tests/fixtures/verification/stable_topological_sort_tests.py"),
    BenchmarkTaskFamily.MATHEMATICS: Path("tests/fixtures/mixed_benchmark/math.json"),
    BenchmarkTaskFamily.RETRIEVAL: Path("tests/fixtures/mixed_benchmark/retrieval.json"),
    BenchmarkTaskFamily.APPLICATION: Path("tests/fixtures/mixed_benchmark/application.json"),
}


def run(args) -> MixedBenchmarkReport:
    suite = loads_document(args.suite.read_text())
    if not isinstance(suite, MixedBenchmarkSuite):
        raise ValueError("mixed benchmark suite document required")
    _verify_fixtures(suite)
    strong = tuple(_strong(path) for path in (args.laguna_report, args.gemma_report))
    results = tuple(_case(case, strong) for case in suite.cases)
    report = MixedBenchmarkReport(
        suite.suite_id, suite.suite_version, results, strong,
        all(item.passed for item in results),
    )
    validate_mixed_report(suite, report)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(dumps_document(report) + "\n")
    return report


def _verify_fixtures(suite) -> None:
    for case in suite.cases:
        if _digest_file(FIXTURES[case.family]) != case.fixture_sha256:
            raise ValueError(f"fixture digest mismatch: {case.case_id}")


def _case(case, strong) -> MixedBenchmarkCaseResult:
    if case.family is BenchmarkTaskFamily.KERNEL_ONLY:
        passed, evidence = _kernel()
        return _result(case, passed, evidence)
    if case.family is BenchmarkTaskFamily.CODE:
        selected = next((item for item in strong if item.verified), strong[0])
        return _result(case, selected.verified, selected.report_sha256, selected)
    if case.family is BenchmarkTaskFamily.MATHEMATICS:
        passed, evidence = _math()
        return _result(case, passed, evidence)
    if case.family is BenchmarkTaskFamily.RETRIEVAL:
        passed, evidence = _retrieval()
        return _result(case, passed, evidence)
    passed, evidence = _application()
    return _result(case, passed, evidence)


def _result(case, passed, digest, strong=None):
    if strong is None:
        return MixedBenchmarkCaseResult(case.case_id, passed, case.acceptance_id, digest)
    return MixedBenchmarkCaseResult(
        case.case_id, passed, case.acceptance_id, digest, strong.expert_id,
        ExpertTier.ESCALATION, strong.model_ref,
    )


def _kernel():
    fixture = json.loads(FIXTURES[BenchmarkTaskFamily.KERNEL_ONLY].read_text())
    observed = hashlib.sha256(fixture["input"].encode()).hexdigest()
    return observed == fixture["expected_sha256"], _digest_json({"observed": observed})


def _math():
    fixture = json.loads(FIXTURES[BenchmarkTaskFamily.MATHEMATICS].read_text())
    request = MathVerificationRequest(
        "mixed-math", fixture["candidate"], fixture["reference"], fixture["variable"],
        tuple(fixture["samples"]), fixture["absolute_tolerance"], fixture["precision_digits"],
    )
    report = SympyMathVerifier().verify(request)
    return report.passed, _digest_json(report)


def _retrieval():
    fixture = json.loads(FIXTURES[BenchmarkTaskFamily.RETRIEVAL].read_text())
    content, quote = fixture["content"], fixture["quote"]
    source = RetrievedSource("mixed-source", "fixture://retrieval", content, _digest_text(content), "fixture-capture")
    start = content.index(quote)
    citation = RetrievalCitation("mixed-citation", source.source_id, start, start + len(quote), _digest_text(quote))
    claim = RetrievalClaim(fixture["claim_id"], (citation.citation_id,))
    report = RetrievalCitationVerifier().verify("mixed-retrieval", (source,), (citation,), (claim,))
    return report.passed, _digest_json(report)


def _application():
    command = ("python3", "-m", "unittest", "tests.integration.test_application_action_safety_end_to_end")
    completed = subprocess.run(command, capture_output=True, text=True, timeout=30)
    evidence = {"returncode": completed.returncode, "stdout": completed.stdout, "stderr": completed.stderr}
    return completed.returncode == 0, _digest_json(evidence)


def _strong(path: Path) -> StrongRegressionRunRef:
    report = json.loads(path.read_text())
    package = report["package_evidence"]
    return StrongRegressionRunRef(
        package["model_ref"], package["expert_id"], package["artifact_digest"],
        _digest_file(path), bool(report["result"]["verified"]),
    )


def _digest_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _digest_text(value: str) -> str:
    return hashlib.sha256(value.encode()).hexdigest()


def _digest_json(value) -> str:
    from dataclasses import asdict, is_dataclass
    payload = asdict(value) if is_dataclass(value) else value
    return _digest_text(json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite", type=Path, required=True)
    parser.add_argument("--laguna-report", type=Path, required=True)
    parser.add_argument("--gemma-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run(args)
    print(json.dumps({"output": str(args.output), "passed": report.passed}, indent=2))


if __name__ == "__main__":
    main()
