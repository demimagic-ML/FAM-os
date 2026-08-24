# ADR 0210: Generated documentation is rehashed before it can gate apply

Status: Accepted

## Context

Generated documentation contracts from ADR 0199 described sources, output,
ownership, and regeneration, but a model- or client-supplied receipt could not
be trusted merely because it was schema-valid. The active changeset also had no
stale-output gate.

## Decision

Only an internal trusted generator adapter may attach a generation request and
receipt. Before persistence, Core resolves every path inside the exact candidate
without symlinks, re-hashes all declared sources and output, and requires real
ownership and authoritative-regeneration instruction files. The receipt must
match the request exactly under the existing governed-documentation contract.

Attached records are owner-bound AEAD immutable task records. Before any
changeset apply, Core recomputes current source and output digests for every
attached generated artifact, persists a staleness report, and blocks if a
source is changed/missing or the output differs.

Satisfied requirement traces must point to real candidate requirement,
implementation, and test paths and to evidence already stored for the same
task. Console and Shell expose these records read-only; they cannot submit a
receipt or trace.

## Consequences

- Schema-valid but fabricated generation receipts are insufficient.
- Generated output drift blocks the same ordinary apply path as review
  findings.
- Ownership and regeneration instructions are enforceable candidate files.
- Traceability cannot cite an arbitrary receipt string as satisfied evidence.
- Phase 30.6 remains open for signed generator recipes/adapters, policy-selected
  required artifact kinds, actual generation execution, regeneration, and
  installed qualification.

## Alternatives considered

- Trust hashes supplied by the generator. Rejected because the generator is an
  untrusted effect producer.
- Detect staleness only after apply. Rejected because stale generated output
  must not enter the owner workspace.
- Let clients upload traceability records. Rejected because path existence and
  evidence provenance must be resolved inside Core.

## Evidence

- `src/fam_os/product/engineering_documentation_api.py`
- `src/fam_os/adapters/sqlite/engineering_documentation.py`
- `src/fam_os/product/engineering_loop_api.py`
- `tests/unit/test_product_engineering_documentation_api.py`
- `tests/unit/test_governed_documentation.py`
- `tests/integration/test_console_engineering_loop.py`
- `tests/unit/test_fam_shell_engineering_loop_transport.py`

## Superseded decisions

None. This operationalizes generated-content consequences from ADR 0199.
