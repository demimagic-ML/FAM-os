# ADR 0174: Engineering operational proof requires soak and independent review

Status: Accepted

## Context

Source tests or a short installed matrix cannot prove long-running cleanup,
interruption behavior, broad parser safety, credential boundaries, privileged
execution, or self-modification safety.

## Decision

Installed engineering qualification is a fail-closed aggregate. A passing
record requires both named hardware profiles, all dependency and language
profiles, installed end-to-end scenarios, every enumerated adversarial category,
a minimum 86,400-second mixed pressure soak with zero leaked candidates, an
independent signed human review of the six required security areas, and a digest
of the installed-only coverage manifest.

The contract rejects a passed soak shorter than 24 hours and rejects a passed
qualification missing any required proof. Source and acceptance evidence may be
preserved but cannot populate `operationally_proven` coverage.

## Consequences

- Phase 31 cannot be completed by an AI self-review or accelerated test.
- Partial installed evidence remains useful but is labeled incomplete.
- Coverage changes occur only after the aggregate prerequisites exist.

## Evidence

- `src/fam_os/core/engineering/security_qualification.py`
- `src/fam_os/core/engineering/security_coverage.py`
- `tests/security/test_engineering_adversarial.py`
- `tools/run_phase31_signed_engineering.py`

## Superseded decisions

None.
