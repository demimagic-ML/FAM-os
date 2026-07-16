# Deterministic admission and eviction

Phase 7.4 decides whether one expert may enter the authoritative FAM host-memory
scope. It is a pure policy: it records evictions but does not unload models.
Residency coordination owns the later persist-before-unload mutation.

## Inputs

An admission request binds one completed live observation, one residency catalog
revision, one requested expert, a weight-only estimate, and one context-only
estimate. Weight provenance must explicitly exclude context bytes. Context
estimates must explicitly exclude model weights. A cold expert charges both;
a warm expert charges context only because its observed resident allocation is
already present in the live scope's `current_bytes`.

Phase 7.4 budgets unified host RAM only. It neither counts SSD model storage as
RAM nor claims a CPU/GPU split. Accelerator placement and transfer costs belong
to Phase 7.6.

## Fail-closed gates

The policy rejects a degraded observation or non-authoritative memory scope
without proposing evictions. Baseline and complete observations may replay, but
production decision-time callers should use the newest linked complete sample.

Only warm experts with positive provider-observed reclaimable bytes are eligible.
Active and evicting records are never selected. The requested expert is excluded
structurally.

## Stable order

Eligible candidates sort by:

1. ascending retention priority (lower means easier to evict);
2. oldest `last_used_at` first;
3. lexical expert ID as the final tie-break.

The policy selects the smallest prefix whose recorded reclaimable bytes covers
the shortfall. If no safe prefix covers it, admission is rejected. The request
and decision are strict documents, so identical captured inputs and decision ID
produce byte-identical output.

## Reference evidence

`configs/admission/reference-weight-estimates.json` derives a context-free
conservative weight bound from package artifact storage plus ten percent runtime
expansion. This is declared policy evidence, not a claim that file bytes equal
allocator bytes. Later provider calibration can replace it with
`observed_weight_only` evidence.

The dual-profile replay in
`artifacts/scheduler/phase7.4/reference-admission-replay/` admits all five
downloaded reference experts on the full workstation. The constrained 16 GiB
profile admits the three smaller experts and correctly rejects Laguna and Gemma;
it does not lower their quality or disguise their memory requirement.
