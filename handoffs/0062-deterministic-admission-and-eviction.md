# Handoff 0062: Deterministic admission and eviction

**Date:** 2026-07-16  
**Plan step:** Phase 7.4  
**Status:** Complete  
**Previous handoff:** `0061-durable-expert-residency.md`

## Objective

Turn live memory, context-only estimates, weight-only estimates, and durable
residency into deterministic, explainable admission and safe eviction decisions.

## Scope completed

- Published strict admission request and decision roots.
- Added provenance-bearing weight estimates that structurally exclude context.
- Added a translator from linked live observation, context estimate, and
  residency catalog documents into one replay input.
- Implemented cold weight-plus-context and warm context-only incremental charges.
- Implemented fail-closed degraded/non-authoritative resource gates.
- Limited eviction to warm, positive-reclaim candidates and excluded the
  requested expert structurally.
- Implemented stable priority, oldest-use, expert-ID order and minimal covering
  prefix selection.
- Captured ten dual-profile decisions for all five current downloaded experts.

## Explicitly not completed

- Phase 7.5 owns the real constrained multi-expert CPU-only workload ceiling.
- Phase 7.6 owns GPU placement, weight splitting, VRAM, and transfer costs.
- Phase 7.7 owns SSD mmap/cache/I/O accounting; storage is not treated as RAM.
- This policy proposes eviction; `ResidencyEvictionCoordinator` owns the later
  durable persist-before-unload execution.
- The ten-percent reference weight expansion is a declared conservative bound,
  not provider-calibrated allocator evidence.

## Architecture and decisions

ADR 0061 separates weights from request context, uses the authoritative live
scope as the capacity boundary, and protects active/ambiguous residency. Stable
ordering is retention priority, age, then identity. The legacy Phase 1 placement
contract remains intact for compatibility; later runtime migration can translate
the new decision's ordered expert IDs into the execution boundary.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/scheduler/admission_contracts.py` | Strict input, weight, candidate, and decision contracts. |
| `src/fam_os/scheduler/admission_policy.py` | Pure deterministic policy. |
| `src/fam_os/scheduler/admission_inputs.py` | Captured-document translator. |
| `configs/admission/reference-weight-estimates.json` | Five context-free reference weight bounds. |
| `tools/capture_phase7_4_admission.py` | Dual-profile replay generator. |
| `tests/unit/test_deterministic_admission_policy.py` | Accounting, safety, order, and replay tests. |
| `tests/integration/test_reference_admission_replay.py` | Strict evidence and strong-model gates. |
| `docs/protocols/DETERMINISTIC_ADMISSION_AND_EVICTION.md` | Public policy protocol. |
| `docs/decisions/0061-separate-weight-context-and-stable-eviction.md` | Architectural decision. |

## Public interfaces

- `ADMISSION_CONTRACT_VERSION`
- `ResidentWeightEstimate`, `EvictionCandidate`, `AdmissionRequest`
- `AdmissionDecision`, `AdmissionStatus`, `WeightEstimateSource`
- `DeterministicAdmissionPolicy`, `build_admission_request`
- `fam.scheduler.admission-request/v1alpha1`
- `fam.scheduler.admission-decision/v1alpha1`

## Validation

Both `/usr/bin/python3` and `/tmp/fam-os-mcp-venv/bin/python` passed 653 tests
with three expected environment-dependent skips. All 58 strict schemas and
compileall passed. The size gate checked 370 source/tool Python files with no
implementation file over 300 lines and no function over 50 lines.

Ten strict reference replays decoded: all five experts were admitted by the
full workstation profile; the compatibility profile admitted Llama, Qwen, and
Nomic and rejected Laguna and Gemma. Laguna's total bound was 26,875,874,402
bytes and Gemma's was 26,497,225,737 bytes. Identical-input replay is byte
stable and tests prove active experts are never selected.

Larry refreshed 1,048 files / 2,822 symbols to 17,800 nodes / 58,501 edges. The
independent full graph refreshed to 17,832 nodes / 58,670 edges.

## Evidence and artifacts

- `artifacts/scheduler/phase7.4/reference-admission-replay/`
- `schemas/v1alpha1/fam.scheduler.admission-request.schema.json`
- `schemas/v1alpha1/fam.scheduler.admission-decision.schema.json`
- `docs/decisions/0061-separate-weight-context-and-stable-eviction.md`

## Known limitations and risks

- Warm admission conservatively charges the full new request context because the
  residency record does not yet expose reusable context bytes.
- Reclaimable bytes are provider-observed total residency and therefore only
  count after confirmed eviction; policy does not predict partial release.
- Retention priority defaults to 100 when callers provide no explicit value.
- A stale but structurally valid complete observation must still be rejected by
  the future orchestration freshness policy.

## Operational notes

No model was loaded, unloaded, downloaded, modified, or deleted. Evidence replay
used the already captured authoritative resource observations, current strict
context estimates, installed package artifact sizes, and the verified downloaded
model identities. `ollama list` confirmed both requested strong models remain
available locally.

## Recommended next entry point

Begin Phase 7.5. Build a real constrained 16 GiB CPU-only multi-expert workload
that repeatedly samples the authoritative FAM scope, executes admission and
residency transitions, proves the operating-system reserve, records peak RAM,
CPU, swap, load/eviction behavior, and rejects any hidden GPU use. Keep Laguna
and Gemma as explicit honest rejection/escalation cases for this constrained
profile; their full-workstation execution belongs to Phase 7.6 and the failed
smoke repair work remains a later quality rerun with complete verifier feedback.
