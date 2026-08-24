# Handoff 0149: Production live-adaptation controls

## Plan step

Phase 20.7 — add visible disable, reset, drift, and rollback behavior.

## Result

Complete. The installed product now owns a durable, encrypted, owner-scoped
adaptation-control state and receipt ledger. Peer-authenticated FAM Shell and
authenticated, CSRF-protected FAM Console expose the same inspect, enable,
disable, evaluate, rollback, and reset operations.

Repeated terminal health samples compare candidates with the known-good
snapshot across verification quality, P95 latency, thermal state when
available, and policy conformance. A regressing candidate is durably marked
drifted and the known-good snapshot is restored atomically. Reset removes
learning records and every derived adaptation artifact while retaining terminal
results and control receipts. Advisory telemetry failures cannot fail inference
or undo an already committed result.

## Important implementation boundaries

- Request advice uses only the active health-approved snapshot.
- The latest verified, non-drifted snapshot may still be prompt-free prewarmed
  under resource policy before promotion.
- Enable, disable, reset, evaluate, and rollback require explicit confirmation
  and idempotent request identity.
- Adaptation never changes acceptance, permission, verification, or application
  action authority.
- Automatic health evaluation waits for at least two samples for both baseline
  and candidate.

## Major files

- `src/fam_os/product/adaptation_control.py`
- `src/fam_os/product/adaptation_health.py`
- `src/fam_os/product/live_adaptation.py`
- `src/fam_os/core/production/worker_registry.py`
- `tools/phase20_control_exit/`
- `tools/run_phase20_adaptation_control_exit.py`
- `docs/decisions/0131-live-adaptation-controls-are-durable-and-rollback-to-known-good.md`
- `docs/operations/PHASE20_ADAPTATION_CONTROLS.md`
- `artifacts/adaptation/phase20.7-control-and-rollback.json`

## Qualification evidence

The signed installed exit built and installed a fresh Ed25519-signed
seven-component release and proved:

- Shell and Console inspection plus confirmed control operations;
- two prompt-free prewarm events;
- a 2,048-token adapted canary and 32,768-token disabled baseline;
- healthy promotion followed by repeated quality, latency, thermal, and policy
  regression with automatic rollback;
- missing-confirmation denial, disabled-state restart persistence, confirmed
  manual rollback, and reset;
- retention of ten terminal results after reset;
- no plaintext test nonce in durable storage;
- healthy diagnosis and complete removal.

Raw evidence: `artifacts/adaptation/phase20.7-control-and-rollback.json`.

## Validation

```bash
PYTHONPATH=src:tools .verification-venv/bin/python tools/run_phase20_adaptation_control_exit.py
PYTHONPATH=src:tools .verification-venv/bin/python tools/run_phase20_live_adaptation_exit.py
PYTHONPATH=src .verification-venv/bin/python -m unittest discover -s tests
.verification-venv/bin/ruff check src tests tools
PYTHONPATH=src .verification-venv/bin/python -m mypy \
  src/fam_os/product/adaptation_control.py \
  src/fam_os/product/adaptation_health.py \
  src/fam_os/product/live_adaptation.py \
  src/fam_os/core/production/worker_registry.py
PYTHONPATH=src .verification-venv/bin/python tools/render_contract_schemas.py --check
git diff --check
```

Outcomes: both signed installed exits passed; the complete suite passed 1,004
tests with two declared skips; Ruff, affected Mypy targets, 211 rendered schema
artifacts, and whitespace validation passed.

## Design record

ADR 0131 records durable owner controls, two-sample health evaluation,
known-good rollback, the separation between prewarm eligibility and active
request advice, and the non-interference rule for advisory telemetry failures.

## Next step

Phase 21.1: inspect the Phase 12 trusted-fabric contracts and replace the
loopback demonstration boundary with a supervised persistent peer identity,
manual pairing ceremony, and mutually authenticated TLS transport composed into
the installed product. Physical two-machine qualification remains Phase 21.7.
