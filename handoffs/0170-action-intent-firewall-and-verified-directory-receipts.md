# Handoff 0170: Action-intent firewall and verified directory receipts

**Date:** 2026-07-18  
**Plan step:** Phases 4.10, 4.11, 5.13, 18.9, and 19.11; Phase 23 readiness  
**Status:** Corrective policy complete; Phase 23 remains open  
**Previous handoff:** `0169-installed-current-request-ordering-fix.md`

## Objective

Correct the installed policy defect that allowed an imperative machine request
to enter ordinary conversation inference and display model prose that implied an
action had completed without capability execution evidence.

## Scope completed

- Added a deterministic action-intent firewall before grounding, model
  selection, prompt assembly, and inference for Shell, Console, declared
  verifier, and delegated request entry points.
- Routed recognized actions through live Application Fabric capability
  resolution. Missing input returns `action_proposal`; missing authority returns
  `capability_unavailable`; neither path invokes a model.
- Added strict result kinds for conversation answers, grounded answers,
  non-executed action proposals, independently verified action receipts, and
  unavailable capabilities.
- Prevented an inference candidate from becoming an action receipt. Final policy
  requires a successful action event with one bound action-result reference and
  same-grant audit evidence for every execution step, then creates a fixed
  receipt independent of candidate prose.
- Added bounded, process-local pending create-directory context so an exact
  follow-up path continues the proposal under the same authenticated Console or
  Shell session.
- Added the owner-home `os.directory.create`, `os.directory.inspect`, and
  `os.directory.remove-empty` capabilities with exact preview, mandatory
  approval, descriptor-relative no-symlink traversal, mode `0700`, postcondition
  checks, path-free audit, and same-device/inode empty-directory reversal.
- Made Console and Shell distinguish model answers, grounded answers,
  non-executed proposals, unavailable capabilities, and verified receipts. Only
  verified receipts expose reversal; untraversed terminal branches render as
  `not taken`.
- Published side-by-side `v1alpha2` result/snapshot schema roots while preserving
  the exact generated `v1alpha1` artifacts. Added a narrow storage-read migration
  for the historical transitional result shape already written by an earlier
  installed release.
- Updated the Master Plan and integration coverage declaration with source and
  signed installed evidence.

## Explicitly not completed

- The firewall is a conservative deterministic vocabulary, not a claim that all
  possible natural-language imperatives are understood. Every newly admitted
  mutation capability must add explicit recognition and adversarial tests.
- Pending proposal parameters are intentionally volatile and do not survive a
  service restart.
- Restart during approval, uncertain-action reconciliation, clean-profile
  matrices, the 24-hour soak, independent security review, rollback, and removal
  remain Phase 23 work.
- This correction does not make ordinary conversation answers verified or
  hallucination-free; it prevents those answers from being represented as
  machine-action receipts.

## Architecture and decisions

ADR 0147 makes action intent authority-bearing. The trusted direction is natural
language to deterministic ingress policy to a live typed capability. Model
output is never parsed into execution authority and never constitutes an action
receipt.

The action-specific logic is split into named modules for recognition, ingress
routing, terminal admission results, deterministic receipt release, scoped
filesystem mechanics, and provider composition. The pre-existing production
gateway remains 352 lines because it is the lifecycle facade for local,
verified, delegated, remote, evidence, and recovery operations; extracting
those unrelated responsibilities in this corrective change would widen scope
and reduce traceability. All newly added policy modules remain below 300 lines
and the new orchestration functions remain focused.

The storage compatibility repair does not weaken public decoding. Public
`v1alpha1` schemas remain exact; only the encrypted repository read boundary
recognizes the one historical transitional shape and migrates it to a
conversation or grounded answer. It can never invent an action receipt.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/production/action_intent.py` | Deterministic action recognition and bounded pending context. |
| `src/fam_os/core/production/action_ingress_router.py` | Fail-closed capability resolution before inference. |
| `src/fam_os/core/production/action_ingress_result.py` | Typed model-free admission outcomes. |
| `src/fam_os/core/production/gateway.py` | Apply the firewall to every production request ingress. |
| `src/fam_os/core/contracts/result.py` | Strict result-kind taxonomy and receipt invariants. |
| `src/fam_os/core/lifecycle/final_service.py` | Derive final kind from the executed plan and verified evidence. |
| `src/fam_os/core/lifecycle/action_receipt_policy.py` | Require audited execution evidence and derive fixed receipt content. |
| `src/fam_os/core/production/application_reversal.py` | Replace preparation candidates with deterministic action receipts. |
| `src/fam_os/adapters/linux/scoped_directories.py` | Owner-root descriptor-relative create and safe empty-directory reversal. |
| `src/fam_os/product/composition/owner_filesystem.py` | Live filesystem capability provider and exact previews. |
| `src/fam_os/product/storage/contract_payload.py` | Narrow repository-only historical result migration. |
| `src/fam_os/shell/contracts.py` | Strict Shell result-kind projection. |
| `src/fam_os/console/static/task_updates.js` | Truthful user-visible outcome labels and reversal eligibility. |
| `schemas/v1alpha2/fam.core.task-result.schema.json` | Current Core result wire root. |
| `schemas/v1alpha2/fam.shell.snapshot.schema.json` | Current Shell snapshot wire root. |
| `tests/integration/test_verified_directory_action.py` | No-model action, denial, follow-up, receipt, audit, and reversal proof. |
| `tests/unit/test_action_intent_firewall.py` | Imperative, paraphrase, and non-action adversarial cases. |
| `tests/unit/test_scoped_directories.py` | Scope, symlink, identity, nonempty, and replacement safety. |
| `docs/protocols/ACTION_INTENT_FIREWALL.md` | Normative action and result policy. |
| `docs/decisions/0147-action-intent-is-authority-bearing-and-fails-closed.md` | Durable authority-boundary decision. |
| `configs/integration/coverage.json` | Truthful current maturity and remaining gaps. |
| `artifacts/product/phase23/action-intent-firewall.json` | Signed installed request and reversal evidence. |

## Public interfaces

- Added `ResultKind`: `conversation_answer`, `grounded_answer`,
  `action_proposal`, `action_receipt`, and `capability_unavailable`.
- Added `fam.core.task-result/v1alpha2`.
- Added `fam.shell.snapshot/v1alpha2`.
- Preserved exact decoding and generated artifacts for both corresponding
  `v1alpha1` roots.
- Added installed capabilities `os.directory.inspect`, `os.directory.create`,
  and `os.directory.remove-empty`, owner-scoped to the discovered home root.
- No command-line syntax or Console endpoint changed.

## Validation

```bash
PYTHONPATH=src:. .verification-venv/bin/python -m unittest discover -s tests
```

Result: 1,212 tests passed with two declared environment skips.

```bash
PYTHONPATH=src:. .verification-venv/bin/python -m unittest \
  tests.unit.test_action_intent_firewall \
  tests.unit.test_core_contracts \
  tests.unit.test_core_final_result_policy \
  tests.unit.test_contract_payload_migration \
  tests.unit.test_console_task_updates \
  tests.unit.test_scoped_directories \
  tests.integration.test_verified_directory_action \
  tests.integration.test_production_verifier_bindings
```

Result: 39 focused policy tests passed, including model prose with passing
acceptance but no action execution evidence.

```bash
.verification-venv/bin/ruff check src tests tools
PYTHONPATH=src:. .verification-venv/bin/python \
  tools/render_contract_schemas.py --check
```

Result: Ruff passed and all 285 schema artifacts validated.

```bash
PYTHONPATH=src:. .verification-venv/bin/mypy \
  src/fam_os/core/contracts/result.py \
  src/fam_os/core/contracts/legacy_result.py \
  src/fam_os/shell/contracts.py \
  src/fam_os/shell/legacy_snapshot.py \
  src/fam_os/schemas/catalog.py \
  src/fam_os/core/lifecycle/action_receipt_policy.py \
  src/fam_os/core/lifecycle/final_service.py \
  src/fam_os/core/production/action_intent.py \
  src/fam_os/core/production/action_ingress_result.py \
  src/fam_os/core/production/action_ingress_router.py \
  src/fam_os/core/production/gateway.py \
  src/fam_os/core/production/application_intent.py \
  src/fam_os/core/production/application_plan_compiler.py \
  src/fam_os/core/production/application_admission.py \
  src/fam_os/core/production/application_gateway.py \
  src/fam_os/core/production/application_worker.py \
  src/fam_os/core/production/application_reversal.py \
  src/fam_os/adapters/linux/scoped_directories.py \
  src/fam_os/product/composition/owner_filesystem.py \
  src/fam_os/product/storage/contract_payload.py \
  src/fam_os/core/production/terminal_projection.py
```

Result: no issues in 21 source files.

Exact comparisons against Git `HEAD` also confirmed that the two affected
`v1alpha1` generated schema artifacts are byte-for-byte unchanged.

## Evidence and artifacts

- Final installed release: `fam-os-current-test-20260718-20`.
- Bundle manifest SHA-256:
  `89184d37de1c0350eaa63fbc2a3ae2d0671e7e0783956569af65a36ecbc8574c`.
- The user service is active, diagnosis is healthy, and Console returns HTTP
  200 on `http://127.0.0.1:8765`.
- Installed create request `installed20-create-55c45ecd` and reversal request
  `installed20-undo-f1dc8db7` both returned verified `action_receipt`; the create
  receipt carried five candidate, acceptance, action-result, and audit evidence
  references; the test directory was absent after reversal and its raw path was
  absent from audit.
- Four installed delete/restart/send/download paraphrases returned withheld
  `capability_unavailable` with “No action was attempted.”
- Installed pending request `installed20-followup-e4de775b` consumed parent-path
  request `installed20-followup-1ae39545`, showed the exact target, and denial left
  no directory.
- Raw evidence: `artifacts/product/phase23/action-intent-firewall.json`.
- Decision: `docs/decisions/0147-action-intent-is-authority-bearing-and-fails-closed.md`.
- Protocol: `docs/protocols/ACTION_INTENT_FIREWALL.md`.

The first signed update attempt was rejected before activation because the
offline wheelhouse lacked the newly declared SymPy dependency; atomic update
preserved the previous release. A subsequent release exposed an existing
historical stored-result shape that had been labelled `v1alpha1`; the service
failed closed until the narrow repository migration was added. Release 18
proved the migration, and release 19 added the expanded adversarial intent
vocabulary. The final policy audit then found that the generic assembler still
needed explicit action-result and audit evidence. Release 20 closes that last
contract-level path and is the only release claimed as final evidence. These
failed or superseded attempts are retained as evidence rather than reported as
successful qualification.

The ephemeral private signing key was removed after final installation. Only
the public verification key and signed bundle remain in the local build area.

## Known limitations and risks

- Deterministic recognition deliberately prefers false-positive refusal over
  letting plausible machine actions reach a model, but phrasing outside the
  current vocabulary may still be treated as conversation. New capabilities
  require explicit ingress grammar and regression cases.
- Pending parameter state is bounded to 128 sessions, expires after 15 minutes,
  and is lost on restart. It confers no authority by itself.
- The owner filesystem provider admits one empty-directory operation only; it
  is not general filesystem authority.
- Phase 23 remains open and the integration coverage manifest correctly stays
  `integration_incomplete`.

## Operational notes

The active owner service is `fam-os-current-test.service`. Its release link is
`/home/demimagic/.local/share/fam-os-current/active`, its Console is
`http://127.0.0.1:8765`, and its external local Ollama endpoint remains
`http://127.0.0.1:11434`.

## Recommended next entry point

Continue Phase 23.1–23.3 from signed release
`fam-os-current-test-20260718-20`. First run the clean built-release profiles,
then the complete installed scenario matrix. Preserve the action-intent and
receipt invariants in ADR 0147 while adding each new application mutation.
