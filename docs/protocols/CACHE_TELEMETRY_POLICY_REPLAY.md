# Cache telemetry and scheduler policy replay

## Purpose

Phase 7.9 makes cache state explicit and makes scheduler decisions reproducible
offline. It does not use one blended cache number. Host filesystem pages,
provider-resident weights, accelerator weights, and compiled NPU artifacts have
different capacity domains and eviction mechanisms, so each remains a separate
`CacheTier`.

## Cache telemetry

`CacheTelemetrySnapshot` is an immutable, sequence-linked observation. Each
entry records:

- artifact identity and resource tier;
- cold, warm, or active state;
- artifact and currently observed bytes;
- hit and miss counts;
- last access and measured reload cost;
- whether policy may evict it;
- the SHA-256 digest of the source evidence.

Cold entries have zero observed bytes and cannot be evicted. Active entries are
never evictable. Warm entries require positive observed bytes and an access
timestamp. The snapshot declares whether it covers all current host cache state;
the canonical replay correctly records `false` because it covers FAM evidence,
not unrelated operating-system caches.

## Deterministic retention

`DeterministicCacheRetentionPolicy` evaluates pressure independently by tier.
It selects only warm, evictable, unprotected entries from the pressured tier.
The stable ordering is:

1. oldest access;
2. lowest hit count;
3. lowest reload cost;
4. artifact identity.

Selection stops after the tier's requested bytes are covered. The decision
retains whole-entry reclaim estimates and explicitly reports unsatisfied
pressure. It recommends eviction; it does not perform I/O or unload a model.

## Offline policy replay

The canonical runner loads only immutable Phase 7.4, 7.6, 7.7, and 7.8
artifacts. It never discovers current hardware. For every case it writes:

- canonical serialized input;
- the previously recorded decision;
- the output of the current real policy implementation;
- SHA-256 digests of all three documents;
- whether recorded and replayed outputs match byte-for-byte.

The report requires host admission, GPU placement, and cache retention cases.
It rejects any record claiming offline replay while consulting current host
state.

## Canonical replay

```bash
PYTHONPATH=src:. python3 tools/run_scheduler_policy_replay.py \
  --output artifacts/scheduler/phase7.9/canonical-policy-replay
```

The canonical report contains 15 matching cases: ten minimum/full host-memory
admission cases, four full-workstation GPU placements, and one cache-retention
case derived from real cold/warm SSD paging plus final GPU/NPU state. The cache
case contains all four tiers but applies pressure only to host page cache,
proving that accelerator or provider bytes are not counted toward that target.

## Boundary

Replay demonstrates deterministic policy behavior for exact historical inputs.
It does not prove that the original observations were complete beyond their
declared scope, execute selected evictions, or predict future demand. Phase 7.10
owns bounded predictive prefetching; it must consume this telemetry without
bypassing admission or reserve policy.
