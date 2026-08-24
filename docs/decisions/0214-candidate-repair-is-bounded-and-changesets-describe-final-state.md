# ADR 0214: Candidate repair is bounded and changesets describe final state

Status: Accepted

## Context

The natural engineering loop could create, edit, verify, preview, apply, and
deliver one generated candidate, but a failed signed verification stopped at a
diagnosed incident. Applying a repair as another candidate edit also meant the
same path could appear more than once in the edit history. A changeset built
directly from that history either rejected the duplicate path or described
intermediate mutations instead of the exact final state the owner would apply.
Untrusted verifier explanations also needed one common redaction boundary
before durable evidence or model disclosure.

## Decision

The ordinary natural loop may perform one deterministic verification-driven
repair under the task's remaining monotonic token, wall-time, command, file,
and storage budget. The initial failed verification is counted as a command.
Core records the incident and typed remediation proposal, reads the current
candidate through the bounded no-link context reader, provides only sanitized
verifier feedback as untrusted model data, binds the repair plan to that exact
candidate state, applies authorized edits durably, and reruns trusted signed
verification. A successful repaired verification produces typed remediation,
recovery-observation, report, and closure receipts.

Before an approval checkpoint, Core derives one final operation per changed
path by comparing the actual candidate to the original owner baseline. Every
final changed path must have appeared in applied authorized edit history.
Intermediate edits disappear from the owner-facing transaction; final content
operations retain the original owner digest as their stale-state precondition.
In-place file/directory kind changes, unowned build output, duplicate final
paths, and final state outside task bounds fail closed. The preview separately
discloses an executable-mode change even when final content and mode travel in
one patch operation.

Diagnostic redaction is now an inward Core policy reused by Bubblewrap, raw
shell receipts, verifier evidence, and repair prompts. Secret-bearing text is
replaced wholly by a digest-only marker; private host paths, ANSI sequences,
and control characters are removed. Repair prompts are count- and byte-bounded
and never receive raw stdout, stderr, credential values, or owner paths.

Only the repaired verification identifiers qualify the final changeset. The
initial failed run remains durable incident and budget evidence and can never
be counted as passing verification.

## Consequences

- A natural task can recover from one real signed candidate-verification
  failure and still reach an exact changeset checkpoint and local commit.
- Multiple authorized edits to one file no longer create duplicate or
  intermediate owner-workspace effects.
- Unexpected tool-created files cannot enter the final changeset merely because
  they exist in the candidate.
- Credential-like verifier or tool output cannot be persisted as diagnostic
  evidence or disclosed to the model by these paths.
- Phase 30.7 gains a real repair/remediation/recovery/report/closure branch at
  `source_composed` maturity.
- Documentation-bearing repair remains fail-closed because prior generated
  documentation receipts would become stale. A later decision must regenerate
  and rebind those outputs before repair can continue.
- The two typed recovery observations currently bind one successful repaired
  verification set. An independently repeated later observation, signed
  installation, live sandbox execution, and final scenario qualification
  remain required.

## Alternatives considered

- Build the changeset directly from every edit record. Rejected because repair
  legitimately creates intermediate versions of one path, while the owner must
  approve the exact final transaction.
- Discard the initial failed verification. Rejected because failures are
  required incident and monotonic-budget evidence.
- Let the model provide current-state hashes or select passing runs. Rejected
  because both are trusted Core decisions.
- Pass raw compiler or verifier output to the model. Rejected because tool
  output is untrusted and may contain credentials or private host paths.
- Repair documentation-bearing tasks without regeneration. Rejected because
  generated artifacts could describe the pre-repair candidate.

## Evidence

- `src/fam_os/core/engineering/candidate_squash.py`
- `src/fam_os/core/engineering/diagnostic_redaction.py`
- `src/fam_os/core/engineering/candidate_generation_service.py`
- `src/fam_os/core/engineering/candidate_verification_service.py`
- `src/fam_os/product/natural_engineering_repair.py`
- `src/fam_os/product/natural_engineering_execution.py`
- `src/fam_os/product/natural_engineering_incidents.py`
- `src/fam_os/adapters/filesystem/candidate_workspace.py`
- `tests/integration/test_natural_engineering_incident.py`
- `tests/unit/test_candidate_squash.py`
- `tests/unit/test_engineering_diagnostic_redaction.py`

## Superseded decisions

None. This extends ADR 0202's two-checkpoint natural lifecycle and ADR 0212's
typed incident evidence chain. It complements ADR 0213's separate pre-commit
rollback branch.
