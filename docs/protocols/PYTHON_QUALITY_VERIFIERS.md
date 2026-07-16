# Python quality verifiers

Phase 8.3 composes four independent gates. Syntax parses without candidate
execution and applies the safe-AST policy. Unit tests use verifier-owned tests
inside the required sandbox. Mypy runs in strict mode. Ruff performs static
analysis. `PythonQualityReport.passed` is true only when all four pass; an error
or unavailable analyzer never degrades into a pass.

Mypy and Ruff are declared in the `verification` project extra and run against a
private temporary file with bounded time and output. Their output is evidence,
not repair instructions with authority to change acceptance.

Canonical evidence is
`artifacts/verification/phase8.3/python-quality-verifiers.json`. Mypy 1.20.2 and
Ruff 0.15.22 accept the typed clean fixture and reject independent type/static
defects. The corrected Bubblewrap-plus-systemd-scope unit-test gate passes, so
the clean fixture satisfies all four gates while each negative remains withheld.
