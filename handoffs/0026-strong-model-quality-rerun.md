# Handoff 0026: Strict strong-model full-workstation quality rerun

**Date:** 2026-07-16  
**Plan step:** Phase 2.14 post-baseline remediation  
**Status:** Complete  
**Previous handoff:** `0025-capability-access-grants.md`

## Objective

Repair the known full-workstation quality failure without weakening verification:
use the installed Laguna and Gemma stronger models, supply useful bounded repair
evidence, decompose the overloaded prompt, enforce every explicit requirement,
and retain independent full-machine resource evidence for both models.

## Scope completed

- Confirmed installed `laguna-xs.2:q4_K_M` and `gemma4:26b` model tags.
- Added immutable bounded `RepairContext` with explicit trusted-test disclosure
  and required input/output examples; the default remains empty.
- Added the exact trusted test source and four tricky cases to diagnostic repairs.
- Preserved the prior candidate, bounded verifier failure, and general guidance.
- Split the initial stable-toposort task into six numbered requirements.
- Raised strong-run context to 8,192 tokens and kept generation/attempts bounded.
- Injected normalized candidate source into verifier-owned tests.
- Added strict v2 AST checks for one named function, 50 lines, no set syntax, and
  no calls to `set`, `min`, or `sorted`.
- Added dynamic input-immutability checks while retaining stable-order,
  neighbor-only, disconnected, and cycle tests.
- Split the legacy parent functional parity fixture from the stricter FAM fixture.
- Detected and rejected an initial false-positive Laguna functional pass.
- Ran Laguna independently: strict initial failure followed by a passing repair.
- Ran Gemma independently: strict first-attempt pass.
- Captured a fresh privacy-reviewed full-workstation budget and separate raw reports.
- Proved CPU, RAM, VRAM, model residency, storage I/O, latency, failures, zero
  service swap, zero OOM kills, privacy scrubbing, and transient-service cleanup.
- Added ADR 0027, operations documentation, Master Plan step 2.14, and this handoff.

## Explicitly not completed

- The original failed baseline and config were not rewritten or reclassified.
- Disclosed-test results are not claimed as unseen-generalization estimates.
- No reference implementation was supplied to either model.
- No model was downloaded, deleted, fine-tuned, or modified.
- No GPU-only fit was forced; both models were allowed to use the full RAM/VRAM fabric.
- No verifier requirement was removed to obtain a pass.
- Phase 3.5 audit work remains in progress and is not marked complete by this handoff.

## Architecture and decisions

ADR 0027 makes test disclosure an explicit repair-policy choice. `RepairContext`
is empty by default, bounded, and immutable. This allows a diagnostic evaluator to
show exact tests while leaving hidden-test packages free to prohibit disclosure.

The first Laguna diagnostic passed the old functional fixture but called `set`
and `min`, directly violating the task. That report is retained as evidence of a
verifier gap. The strict v2 result is canonical because both behavior and declared
source constraints pass.

The parent RNF parity test now uses a separate copy of the prior functional fixture.
This preserves the frozen parent comparison while permitting FAM's active verifier
to become stricter.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/execution/repair_context.py` | Bounded explicit repair disclosure |
| `src/fam_os/core/execution/policy.py` | Repair context in execution policy |
| `src/fam_os/core/execution/prompts.py` | Test source/examples in repair prompt |
| `src/fam_os/core/execution/use_case.py` | Pass policy context into every repair |
| `src/fam_os/verification/python/script.py` | Candidate source for trusted AST checks |
| `tools/parity/historical_config.py` | Typed repair-example fixture loading |
| `tools/run_verified_parity.py` | Strict v2 bundle and diagnostic disclosure composition |
| `tests/fixtures/verification/stable_topological_sort_tests.py` | Strict functional/static/immutability gate |
| `tests/fixtures/verification/stable_topological_sort_parity_tests.py` | Frozen functional parity behavior |
| `tests/hardware/python_verifier_parity.py` | Parent comparison uses legacy fixture |
| `tests/unit/test_verified_code_execution.py` | Repair-context prompt evidence test |
| `configs/benchmarks/full-workstation-verified-smoke-laguna.json` | Independent Laguna workload |
| `configs/benchmarks/full-workstation-verified-smoke-gemma4-26b.json` | Independent Gemma workload |
| `docs/operations/FULL_WORKSTATION_SMOKE.md` | Strict post-baseline interpretation |
| `docs/decisions/0027-diagnostic-repair-context-and-strict-conformance.md` | Disclosure/conformance decision |
| `artifacts/workstation/20260716T122504578152Z/` | Fresh capture and raw reports |

## Public interfaces

- `RepairContext.trusted_test_source`
- `RepairContext.failure_examples`
- `VerifiedCodePolicy.repair_context`
- optional benchmark fixture field `repair_examples`
- verifier-internal `__FAM_CANDIDATE_SOURCE__`
- strict bundle identity `stable-toposort-v2`

## Validation

```bash
PYTHONPATH=src:. python3 -m unittest \
  tests.unit.test_verified_code_execution \
  tests.unit.test_supervisor_audit \
  tests.unit.test_jsonl_audit_sink \
  tests.unit.test_audited_lifecycle \
  tests.unit.test_audited_access \
  tests.unit.test_audited_constrained
```

Result: all 33 focused execution/audit tests passed in 0.055 seconds.

```bash
FAM_VERIFIER_PARITY=1 PYTHONPATH=src:.. \
  python3 -m unittest tests.hardware.python_verifier_parity -v
```

Result: both live parent/migrated functional parity tests passed. Rechecking the
first Laguna diagnostic against strict v2 failed with `set, min, and sorted are
forbidden`, proving that the false positive no longer passes.

```bash
PYTHONPATH=src:. python3 -m unittest discover -s tests
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
python3 -m compileall -q src tools tests
```

Result: all 311 tests passed in 0.230 seconds, all 35 generated schemas matched,
and compilation completed successfully. The Phase 3.4 suite contained 287 tests.

An AST audit found no `src/` or `tools/` module at or above 300 lines and no
function at or above 50 lines.

Larry refreshed 456 files and verified clean. The codebase graph was refreshed
in fast mode with 6,890 nodes and 20,524 edges.

The two canonical strong reports passed a scan for home path, username,
user-cgroup identity, NVMe device names, and PCI addresses. After each run,
`fam-parity-ollama.service` was `not-found`, `inactive`, and `dead`.

## Evidence and artifacts

- Fresh capture: `artifacts/workstation/20260716T122504578152Z/`
- Strict Laguna: `workstation-smoke-20260716-122820-440726.json`
- Strict Gemma: `workstation-smoke-20260716-122945-696264.json`
- Pre-strict rejected diagnostic: `workstation-smoke-20260716-122554-234520.json`
- Decision: `docs/decisions/0027-diagnostic-repair-context-and-strict-conformance.md`

### Laguna strict result

- Status: `verified_after_repair`.
- Initial: 11.04 seconds, 357 prompt tokens, 301 output tokens; correctly rejected.
- Repair: 9.72 seconds, 1,486 prompt tokens, 438 output tokens; passed.
- Model residency: 23,523,688,048 bytes total; 13,483,219,353 accelerator bytes.
- Maximum boundary-sampled GPU use: 15,557,722,112 bytes.
- Service CPU: 44,237,587 microseconds; peak charged RAM 3,152,941,056 bytes.
- Storage-window read/write: 1,732,894,720 / 50,495,488 bytes.
- Swap and OOM kills: zero.

### Gemma strict result

- Status: `verified` on the initial attempt.
- Inference: 54.82 seconds including 33.93 seconds load; 43.35 tokens/second.
- Model residency: 18,538,393,761 bytes total; 12,255,294,913 accelerator bytes.
- Maximum boundary-sampled GPU use: 14,135,853,056 bytes.
- Service CPU: 61,851,424 microseconds; peak charged RAM 20,408,229,888 bytes.
- Storage-window read/write: 18,315,386,880 / 120,209,408 bytes.
- Swap and OOM kills: zero.

## Known limitations and risks

- Full test disclosure can encourage test-specific solutions; these reports measure
  repairability and requirement conformance, not hidden-test generalization.
- AST bans are specific to this benchmark contract and are not a universal Python policy.
- Root-storage I/O deltas still include unrelated host activity during each window.
- GPU maximum is the maximum of two boundary samples, not high-frequency telemetry.
- Ollama `resident_bytes` is model-residency metadata and must not be equated with
  cgroup-charged system RAM.
- The active Phase 3.5 audit implementation has passing focused tests but still
  needs contract finalization, full integration evidence, documentation, ADR, and handoff.

## Operational notes

The fresh profile exposed 24 logical CPUs (22 schedulable), 54,132,932,608
scheduler RAM bytes after 12 GiB headroom, 14,958,067,712 scheduler RTX bytes
after reserve, and the NVMe cache tier. Both transient services enforced zero
swap and were collected. The main Ollama service and existing applications were
not replaced.

## Recommended next entry point

Resume Phase 3.5. First finish operation-ID linkage tests for the partial audit
contracts in `src/fam_os/supervisor/audit_contracts.py`, then rerun the live
audited-service smoke. Complete immutable/tamper-evident ledger documentation,
ADR 0028, handoff 0027, canonical boundary status, and Master Plan closure before
starting Phase 3.6.
