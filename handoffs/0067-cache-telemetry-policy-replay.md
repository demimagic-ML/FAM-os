# Handoff 0067: Tier-separated cache telemetry and offline policy replay

**Date:** 2026-07-16  
**Plan step:** Phase 7.9  
**Status:** Complete  
**Previous handoff:** `0066-intel-npu-micro-expert.md`

## Objective

Represent cache state without blending resource domains and make historical
scheduler decisions executable, digest-bound offline regressions.

## Scope completed

- Added immutable, sequence-linked cache snapshots with cold, warm, and active
  states; bytes, hits/misses, access time, reload cost, eviction permission, and
  source-evidence digest.
- Separated host page cache, provider weights, accelerator weights, and compiled
  NPU state into independent tiers.
- Added tier-local pressure, protected artifacts, ordered eviction recommendations,
  reclaim accounting, and explicit unsatisfied outcomes.
- Implemented stable ordering by oldest access, hits, reload cost, and identity.
- Added digest-bound replay records and an aggregate report requiring host
  admission, GPU placement, and cache retention coverage.
- Implemented replay through the actual three policy implementations, canonical
  input/output serialization, and byte equality without current-host discovery.
- Converted prior canonical Phase 7.4/7.6/7.7/7.8 evidence into 15 replay cases.
- Added strict schemas, fixtures, unit/integration tests, protocol documentation,
  ADR 0066, Master Plan closure, canonical artifacts, and this handoff.

## Explicitly not completed

- Cache decisions recommend candidates; they do not execute eviction or unload.
- The canonical snapshot covers FAM artifacts and honestly sets
  `current_host_state_complete=false`; unrelated OS cache is outside its scope.
- Replay proves exact-input determinism, not completeness of old observations.
- Prediction and prefetch are Phase 7.10 and remain open.

## Architecture and decisions

ADR 0066 prohibits scalar cache capacity across storage, host, GPU, and NPU
domains. A pressure request can reclaim bytes only from its own tier. Active,
cold, protected, non-evictable, and cross-tier entries are excluded.

Offline replay accepts serialized observations as its entire world. Each case
binds its input, recorded decision, and current-policy result by SHA-256. The
report rejects any replay that consulted current host state and requires all
three scheduler policy kinds.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/scheduler/cache_contracts.py` | Cache telemetry, pressure, and decision contracts. |
| `src/fam_os/scheduler/cache_policy.py` | Pure tier-local retention policy. |
| `src/fam_os/scheduler/replay_contracts.py` | Digest-bound replay records/report. |
| `tools/policy_replay/cases.py` | Historical canonical case composition. |
| `tools/policy_replay/engine.py` | Actual policy dispatch and canonical evidence. |
| `tools/run_scheduler_policy_replay.py` | Fifteen-case replay runner. |
| `tests/unit/test_cache_policy.py` | Stable ordering and tier isolation. |
| `tests/unit/test_policy_replay_contracts.py` | Fail-closed replay invariants. |
| `tests/integration/test_scheduler_policy_replay_evidence.py` | Canonical replay gates. |
| `docs/protocols/CACHE_TELEMETRY_POLICY_REPLAY.md` | Telemetry/replay protocol. |
| `docs/decisions/0066-separate-cache-tiers-and-replay-offline.md` | Cache/replay decision. |
| `artifacts/scheduler/phase7.9/canonical-policy-replay/` | Inputs and recorded/replayed outputs. |

## Public interfaces

- `CACHE_POLICY_CONTRACT_VERSION`, `CACHE_POLICY_VERSION`
- `CacheTier`, `CacheEntryState`, `CacheTelemetryEntry`, `CacheTelemetrySnapshot`
- `CacheTierPressure`, `CachePolicyRequest`, `CacheEvictionDecision`
- `CacheTierReclaim`, `CachePolicyDecision`
- `DeterministicCacheRetentionPolicy`
- `POLICY_REPLAY_CONTRACT_VERSION`, `SchedulerPolicyKind`
- `SchedulerPolicyReplayRecord`, `SchedulerPolicyReplayReport`
- four new `fam.scheduler.*` strict schema roots

## Canonical evidence

`artifacts/scheduler/phase7.9/canonical-policy-replay/` contains 15 case
directories plus the strict report and summary:

- ten Phase 7.4 host admission cases across both validation profiles;
- four Phase 7.6 GPU placement cases including Laguna and Gemma split-offload;
- one cache-retention case derived from Phase 7.7 page-cache evidence and final
  provider/GPU/NPU state;
- 15 recorded outputs equal their current replay outputs byte-for-byte;
- `current_host_state_consulted=false` for every case.

The cache case includes all four tiers but pressures only host page cache. Its
decision selects only the real warm page-cache artifact; zero accelerator,
provider, or NPU bytes are counted toward host page-cache pressure.

## Validation

Both supported Python environments passed 705 tests with three expected skips.
All 71 generated schemas and compileall passed. The size audit checked 393
source/tool Python files with no file above 300 lines and no function above 50.

Larry refreshed 1,175 files, 2,959 symbols, 21,107 graph nodes, and 65,712 edges.
This handoff itself is the one expected map-stale file.

## Known limitations and risks

- Hit/miss telemetry in the canonical cache case derives from one known cold and
  one known warm load; long-running production counters still need durable
  operational collection.
- Whole-artifact reclaim is conservative; partial page-cache eviction is not
  promised by the decision contract.
- Policy version changes must produce a new replay artifact and decision record,
  not silently rewrite this canonical run.

## Recommended next entry point

Begin Phase 7.10 with bounded predictive prefetch contracts. Predictions must
carry source history, confidence, expiry, byte/cost budgets, and a deterministic
admission result. Prefetch may only warm an otherwise admissible artifact, must
preserve OS reserve, must never evict active/protected work, and must expose
false-positive waste in evidence.
