#!/usr/bin/env python3
"""Run canonical JavaScript, TypeScript, and Rust verifier packages."""

import argparse
import json
import subprocess
from dataclasses import asdict
from pathlib import Path

from fam_os.adapters.language_tools import TemporaryToolchainVerifier, ToolGate


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    node, rustc = Path("/usr/bin/node"), Path.home() / ".cargo/bin/rustc"
    tsc = root / "tools/verifiers/typescript/node_modules/.bin/tsc"
    verifiers = (
        (TemporaryToolchainVerifier("javascript", "js", _version(node), (
            ToolGate("javascript.syntax", (str(node), "--check", "{candidate}")),
            ToolGate("javascript.tests", (str(node), "{candidate}"), True),
        ), trusted_fixture_execution=True), "function add(a, b) { return a + b; }\nif (add(2,3) !== 5) throw Error('failed');\n", "function broken( {"),
        (TemporaryToolchainVerifier("typescript", "ts", _version(tsc), (
            ToolGate("typescript.strict", (str(tsc), "--noEmit", "--strict", "--target", "ES2022", "{candidate}")),
        )), "function add(a: number, b: number): number { return a + b; }\n", "const value: string = 1;\n"),
        (TemporaryToolchainVerifier("rust", "rs", _version(rustc), (
            ToolGate("rust.compile", (str(rustc), "--edition=2021", "--crate-type", "lib", "{candidate}")),
            ToolGate("rust.test-build", (str(rustc), "--edition=2021", "--test", "{candidate}", "-o", "{cwd}/tests")),
            ToolGate("rust.tests", ("{cwd}/tests",), True),
        ), trusted_fixture_execution=True), "pub fn add(a: i32, b: i32) -> i32 { a + b }\n#[test] fn works(){ assert_eq!(add(2,3),5); }\n", "pub fn broken( -> i32 { 1 }\n"),
    )
    reports = {}
    acceptance = True
    for verifier, good, bad in verifiers:
        positive = verifier.verify(f"{verifier.language_id}-good", good)
        negative = verifier.verify(f"{verifier.language_id}-bad", bad)
        reports[verifier.language_id] = {"positive": asdict(positive), "negative": asdict(negative)}
        acceptance &= positive.passed and not negative.passed
    document = {"phase": "8.4", "reports": reports, "acceptance": acceptance}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(json.dumps(document, indent=2, sort_keys=True))
    return 0 if acceptance else 1


def _version(executable: Path) -> str:
    return subprocess.check_output((str(executable), "--version"), text=True).strip()


if __name__ == "__main__":
    raise SystemExit(main())
