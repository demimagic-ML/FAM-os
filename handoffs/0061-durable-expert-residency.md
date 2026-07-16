# Handoff 0061: Durable expert residency

**Date:** 2026-07-16  
**Plan step:** Phase 7.3  
**Status:** Complete  
**Previous handoff:** `0060-context-memory-estimation.md`

## Objective

Make cold, warm, active, and evicting expert residency durable, request-aware,
provider-reconciled, and safe across crashes and ambiguous unload failures.

## Scope completed

- Published strict revisioned residency catalog, record, identity, and lease
  contracts with structural state invariants.
- Defined cold as provider-confirmed absence and made the bootstrap factory name
  require that trust boundary explicitly.
- Implemented provider reconciliation for cold/warm/active/evicting records.
- Implemented unique expiring request leases and warm/active transitions.
- Implemented persist-before-provider eviction and exact eviction identity.
- Implemented three-way ambiguous failure recovery: present restores warm, absent
  completes cold, observation failure stays evicting.
- Added in-memory CAS and private cross-process-locked atomic JSON repositories.
- Added strict revision, identity, symlink, regular-file, permission, fsync, and
  atomic-replace persistence gates.
- Captured a live isolated Qwen sequence through all six transition points with
  provider-confirmed unload and full-reference cgroup resource evidence.

## Explicitly not completed

- Phase 7.4 owns which warm experts to admit or evict.
- A weight-only residency estimate is still required for admission arithmetic;
  provider resident observations remain evidence, not automatically immutable
  weight bytes.
- Multi-runtime loading semantics beyond current inference-triggered load remain
  adapter work.
- Long-term transition audit history is not embedded into the state catalog; the
  current record retains the latest revision/reason and live evidence retains the
  complete demonstrated sequence.

## Architecture and decisions

ADR 0060 separates package installation from runtime residency, makes request
leases the definition of active, and makes provider-confirmed absence the only
route to cold. State is persisted before unload so crash recovery can reconcile
an interrupted eviction without allowing a new lease.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/scheduler/residency_contracts.py` | State, lease, record, and catalog invariants. |
| `src/fam_os/scheduler/residency_ports.py` | Repository/runtime ports and stable errors. |
| `src/fam_os/scheduler/residency_service.py` | Transitions, reconciliation, and eviction coordination. |
| `src/fam_os/scheduler/residency_repository.py` | In-memory CAS repository. |
| `src/fam_os/adapters/filesystem/residency_state.py` | Private locked atomic JSON repository. |
| `tools/run_residency_lifecycle_smoke.py` | Isolated full-profile live lifecycle. |
| `tests/unit/test_expert_residency_service.py` | Transition/recovery/lease tests. |
| `tests/unit/test_residency_state_repository.py` | Persistence and adversarial path tests. |
| `tests/integration/test_residency_lifecycle_evidence.py` | Strict live artifact gate. |
| `docs/protocols/EXPERT_RESIDENCY_LIFECYCLE.md` | Lifecycle protocol. |
| `docs/decisions/0060-durable-reconciled-expert-residency.md` | Durable state decision. |

## Public interfaces

- `EXPERT_RESIDENCY_CONTRACT_VERSION`
- `ExpertResidencyState`, `ResidencyTransitionReason`
- `ExpertResidencyIdentity`, `ResidencyLease`, `ExpertResidencyRecord`
- `ExpertResidencyCatalog`, `initial_cold_residency_catalog`
- `ExpertResidencyRepository`, `ModelResidencyRuntime`
- `ExpertResidencyService`, `ResidencyEvictionCoordinator`
- `InMemoryExpertResidencyRepository`, `JsonExpertResidencyRepository`
- `fam.scheduler.expert-residency/v1alpha1`
- `tools/run_residency_lifecycle_smoke.py`

## Validation

```bash
PYTHONPATH=src:. python3 -m unittest discover -s tests
PYTHONPATH=src:. /tmp/fam-os-mcp-venv/bin/python -m unittest discover -s tests
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
PYTHONPATH=src:. python3 -m compileall -q src tests tools
python3 <AST implementation file/function size gate>
PYTHONPATH=src:. python3 <strict live residency evidence gate>
systemctl --user list-units 'fam-residency-smoke*' --all --no-legend --no-pager
larry index
codebase-memory-mcp index_repository full
```

Result: both Python environments passed 643 tests with three expected
environment-dependent skips. All 56 strict schemas and compileall passed. The
size gate checked 366 source/tool Python files with no implementation file over
300 lines and no function over 50 lines. Six strict live catalogs decoded at
revisions 0-5 with states cold, warm, active, warm, evicting, cold. The canonical
run recorded provider absence before final cold, 4,028,870 service CPU
microseconds, 346,484,736 peak service memory bytes, private mode-0600 final
state, and inactive cleanup. Larry refreshed 1,015 files / 2,797 symbols to
17,154 nodes / 56,979 edges. The independent graph refreshed to 17,187 nodes /
57,179 edges.

## Evidence and artifacts

- `artifacts/scheduler/phase7.3/qwen-residency-lifecycle-canonical/`
- `artifacts/scheduler/phase7.3/qwen-residency-lifecycle/` (earlier diagnostic)
- `schemas/v1alpha1/fam.scheduler.expert-residency.schema.json`
- `docs/decisions/0060-durable-reconciled-expert-residency.md`

## Known limitations and risks

- An active provider disappearance remains a hard conflict requiring request
  failure handling; it is intentionally not rewritten as cold.
- The latest transition reason is durable, but a production audit sink must retain
  longer history when later policy begins autonomous eviction.
- Lease expiration depends on a trusted scheduler clock and explicit sweep.
- Live Qwen's second run reused host file cache, so its lower memory peak is not a
  cold-load performance comparison; it is lifecycle correctness evidence.

## Operational notes

The canonical run started a separate `fam-residency-smoke` user service on port
11512, loaded the already downloaded Qwen model, confirmed unload, and stopped
the service. It did not access, unload, or alter the user's main Ollama service;
no model was downloaded, copied, modified, or deleted.

## Recommended next entry point

Begin Phase 7.4. Read handoffs 0059-0061, live resource/context/residency schemas,
expert manifest requirements, package benchmark metadata, and current Phase 1
placement compatibility contracts. First define deterministic admission inputs,
decision reasons, weight-only accounting, and stable eviction ordering before
executing any eviction.
