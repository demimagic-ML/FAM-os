# Handoff 0178: Phase 23 installed, hardware, and Console qualification

**Date:** 2026-07-18  
**Plan step:** Phase 23.3, 23.4, and 23.6 audit  
**Status:** 23.4 and 23.6 complete; 23.3 partial on physical remote only  
**Previous handoff:** `0177-production-action-restart-reconciliation.md`

## Objective

Audit the remaining installed Phase 23 paths against the real signed candidate,
repair product or harness gaps that could create false evidence, and qualify the
minimum CPU and full workstation without weakening acceptance.

## Gaps found

1. Production exact retrieval fallback existed only in a benchmark adapter.
   Moving it into the signed verifier changed verifier identity, so it needed a
   separate Core-owned exact-extraction boundary.
2. A full-profile temporary path exceeded Linux AF_UNIX limits. Startup then
   hid that exception by calling `shutdown()` on an unserved Console.
3. Candidate startup diagnosis lacked a stack dump, cleanup could leave a
   managed provider, and owner Ollama could repopulate GPU cache mid-run.
4. Factory qualification and the uncertain-action fault injector placed the
   checkout on `PYTHONPATH`. Root module checks passed, but final evidence still
   depended on a source-visible environment.
5. Console qualification checked presence rather than independently proving
   authority for resources, experts, permissions, memory, audit, and recovery.

## Scope completed

- Added Core-owned, query-bound, exact-source-line retrieval normalization while
  preserving the signed verifier module and its digest.
- Added explicit 107-byte Unix-socket validation and safe cleanup for partial
  product startup.
- Added direct candidate startup, failure stack dumps, orphan-provider cleanup,
  short private execution roots, and continuous owner-cache quiescence.
- Split Factory qualification into small external driver/suite modules that
  import only shipped product APIs; candidate evidence records that the Phase 22
  acceptance composition was not imported.
- Removed checkout source from the action fault injector and moved candidate
  identity validation before mutation.
- Extended installed Console evidence across signed catalog, provider residency,
  durable terminal results, permissions, action audit, document indexes across
  restart, and a missing-key recovery state.
- Cross-checked Console CPU, schedulable RAM, VRAM, storage, policy, catalog, and
  residency against independent host, cgroup, filesystem, NVIDIA, and Ollama
  observations in both hardware profiles.

## Installed evidence

`phase23-installed-20260718-11` passes all seven scenario groups from signed
release `fam-os-phase23-installed-20260718-11`:

- local verified inference and authoritative Console state;
- approval restart, uncertain-action recovery, and outbound/inbound MCP;
- whole-workspace indexing, query-bound grounding, and restart persistence;
- bounded escalation plus isolated `laguna-xs.2:q4_K_M` and `gemma4:26b`;
- media verification;
- complete private remote evidence with an explicit same-host limitation;
- real conversion, package, canary, activation, rollback, reactivation,
  retirement, audit retention, artifact/model removal, and no acceptance import.

The candidate is completely removed and the owner Console remains HTTP 200.

`phase23-hardware-20260718-06` passes both installed profiles. CPU compatibility
enforces 16 GiB maximum, 14 GiB high, CPU-only inference, zero swap/OOM/VRAM,
and one retained CPU. The full profile exposes 24 logical CPUs, 64 GiB-class
RAM, 2 TB-class storage, active RTX 5080 VRAM, no artificial memory ceiling, and
two retained CPUs. Both pass verified local work and grounded memory across
restart; the full profile passes Laguna and Gemma independently. Cleanup leaves
the managed provider inactive and the owner service preserved.

## Validation

- Focused production, startup-safety, installed-matrix, hardware-matrix,
  retrieval, service-storage, and Console-provider tests pass.
- Ruff passes on every changed source, tool, and test target.
- Strict mypy passes on the new retrieval, Factory qualification, Factory suite,
  Factory process, Factory scenario, and fault-injector boundaries. Older shared
  evidence clients still contain pre-existing untyped definitions and are not
  represented as strict-clean.
- Full-suite and schema/coverage validation must be rerun after this handoff and
  its final counts appended to the next handoff if they uncover a new change.

## Plan truth after this change

- Phase 23.4 is complete.
- Phase 23.6 is complete.
- Phase 23.3 is complete for every same-host installed scenario but remains
  partial because its remote scenario inherits the unsatisfied two-physical-host
  Phase 21.7 gate.
- Phase 23.5, 23.7, and 23.8 remain open.

## Recommended next entry point

Start the signed 24-hour installed soak for 23.5 while arranging the second
physical Linux host for 21.7/23.3 and an independent human reviewer for 23.7.
The final 23.8 lifecycle must use the post-soak release candidate and its final
trust key; earlier install/update/removal evidence cannot substitute for it.
