#!/usr/bin/env python3
"""Capture symbolic and high-precision numerical verifier evidence."""

import argparse
import json
import sympy
from dataclasses import asdict
from pathlib import Path

from fam_os.verification import MathVerificationRequest
from fam_os.verification.math_sympy import SympyMathVerifier


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    verifier = SympyMathVerifier()
    identity = verifier.verify(MathVerificationRequest(
        "identity", "(x+1)**2", "x**2+2*x+1", "x",
        ("-100", "-0.25", "0", "3.5", "100"), "1e-50", 80,
    ))
    wrong = verifier.verify(MathVerificationRequest(
        "wrong", "sin(x)", "x", "x", ("0", "0.5", "1"), "1e-30", 80,
    ))
    document = {
        "phase": "8.5", "sympy_version": sympy.__version__,
        "identity": asdict(identity), "wrong": asdict(wrong),
        "acceptance": identity.passed and not wrong.passed and wrong.counterexample_point is not None,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(json.dumps(document, indent=2, sort_keys=True))
    return 0 if document["acceptance"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
