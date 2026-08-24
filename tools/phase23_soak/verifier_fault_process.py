#!/usr/bin/env python3
"""Activate and run the signed installed Python verifier for fault injection."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import fam_os
from fam_os.adapters.bubblewrap import BubblewrapSandboxRunner
from fam_os.console.verification_document import declaration_from_document
from fam_os.product.composition.verifier_unit import production_verifier_catalog
from fam_os.verification.domain_adapters import ProductionVerifierAdapters


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("crash", "healthy"), required=True)
    parser.add_argument("--output", type=Path, required=True)
    arguments = parser.parse_args()
    tests = (
        "import time\ntime.sleep(60)\nassert add(2, 3) == 5\n"
        if arguments.mode == "crash"
        else "assert add(2, 3) == 5\nassert add(-1, 1) == 0\n"
    )
    declaration = declaration_from_document(
        f"phase23-soak-verifier-{arguments.mode}",
        "Verify a fixed candidate through the installed signed package.",
        {
            "kind": "python_tests",
            "bundle_id": f"phase23-soak-{arguments.mode}-v1",
            "test_source": tests,
        },
    )
    activation_outcome = production_verifier_catalog().activate(declaration)
    activation = activation_outcome.activation
    if activation is None:
        raise RuntimeError(
            "installed verifier activation failed: "
            + activation_outcome.reason_code
        )
    result = ProductionVerifierAdapters(BubblewrapSandboxRunner()).verify(
        activation, declaration,
        "def add(left, right):\n    return left + right\n",
        f"verification-phase23-soak-{arguments.mode}",
    )
    package = activation.package
    report = package.package_report
    document = {
        "candidate_module": str(Path(fam_os.__file__).resolve()),
        "mode": arguments.mode,
        "activation_trust": (
            report.effective_trust.value
            if report.effective_trust is not None else "rejected"
        ),
        "release_id": package.release_id,
        "signer_key_id": package.signer_key_id,
        "verifier_id": package.manifest.verifier_id,
        "status": result.status.value,
        "passed": result.status.value == "passed",
        "feedback": result.feedback,
        "facts": {fact.name: fact.value for fact in result.facts},
    }
    arguments.output.write_text(json.dumps(document, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
