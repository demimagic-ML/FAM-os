# Handoff 0054: Expert hardware compatibility

**Date:** 2026-07-16  
**Plan step:** Phase 6.4  
**Status:** Complete  
**Previous handoff:** `0053-package-trust-validation.md`

## Objective

Determine whether a current expert manifest fits one physical host and selected
effective profile without conflating permanent incompatibility, current
contention, optional CPU fallback, or later scheduler placement.

## Scope completed

- Strict `fam.expert.compatibility/v1alpha1` report schema.
- CPU architecture allowlist evaluation.
- Physical, profile, and current scheduler RAM checks using the larger of
  resident and minimum-system requirements.
- Separate storage capacity and current-free-space checks without treating SSD
  as RAM.
- Physical, profile, and current accelerator-memory checks for hard
  accelerator requirements.
- Explicit `compatible_cpu_only` degradation for optional unavailable or busy
  acceleration.
- `currently_constrained` status for capable hosts with temporary RAM, VRAM, or
  storage contention.
- Cross-inventory/resource-ID rejection and deterministic candidate resource
  IDs/reason codes.
- Tests across full-reference and compat-cpu-16gb budgets plus architecture,
  memory, storage, required accelerator, optional fallback, and contention.

## Explicitly not completed

- Runtime-specific GPU/NPU ABI compatibility, split placement, transfer cost,
  context allocation, cache, eviction, or activation; Phase 7 owns those live
  scheduling decisions.
- Package installation/lifecycle mutation; Phase 6.5 must consume compatibility
  evidence separately from trust evidence.
- Benchmark quality and routing selection.

## Architecture and decisions

ADR 0054 makes compatibility profile-specific and layered. Physical totals,
effective scheduler ceilings, and current availability have different meanings
and stable reason-code prefixes. Optional acceleration is an explicit CPU
fallback rather than silent capability loss. The evaluator returns candidates,
never a placement plan.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/experts/compatibility.py` | Pure host/profile compatibility evaluator. |
| `src/fam_os/experts/compatibility_contracts.py` | Versioned status/report evidence. |
| `src/fam_os/schemas/catalog.py` | Registers the strict compatibility report. |
| `schemas/v1alpha1/fam.expert.compatibility-report.schema.json` | Generated report schema. |
| `tests/unit/test_expert_hardware_compatibility.py` | Full/compat and failure-layer tests. |
| `docs/protocols/EXPERT_HARDWARE_COMPATIBILITY.md` | Compatibility semantics. |
| `docs/decisions/0054-profile-specific-expert-compatibility.md` | Durable layering decision. |

## Public interfaces

- `EXPERT_COMPATIBILITY_CONTRACT_VERSION`
- `ExpertCompatibilityStatus`
- `ExpertCompatibilityReport`
- `ExpertCompatibilityEvaluator.evaluate`

## Validation

```bash
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
PYTHONPATH=src python3 -m compileall -q src tests tools
PYTHONPATH=src:. python3 -m unittest discover -s tests
PYTHONPATH=src:. /tmp/fam-os-mcp-venv/bin/python -m unittest discover -s tests
python3 <AST module/function size gate>
```

Result: all 47 schemas and compileall passed. Both Python environments passed
576 tests with three expected environment-dependent skips each. The size gate
found no implementation file above 300 lines and no Python function above 50
lines across 350 inspected implementation files.
Larry indexed 820 files / 2,509 symbols with 11,412 nodes / 43,984 edges;
freshness and verification were clean. The code knowledge graph was refreshed
to the same 11,412-node / 43,984-edge source view.

## Evidence and artifacts

- `schemas/v1alpha1/fam.expert.compatibility-report.schema.json`
- `tests/unit/test_expert_hardware_compatibility.py`
- `docs/protocols/EXPERT_HARDWARE_COMPATIBILITY.md`
- `docs/decisions/0054-profile-specific-expert-compatibility.md`

## Known limitations and risks

- Manifest accelerator requirements currently describe memory/optionality, not
  a runtime/device-kind ABI. Phase 7 must check actual adapter support before
  choosing GPU or NPU placement.
- Storage compatibility covers package capacity/free space, not mmap/cache
  residency or I/O throughput; Phase 7 owns those budgets and measurements.
- `currently_constrained` is point-in-time evidence and must be reevaluated
  before activation.

## Operational notes

Evaluation is pure and read-only. No package, model, service, port, hardware
setting, or user data was changed.

## Recommended next entry point

Begin Phase 6.5. Read package validation and compatibility reports, local
registry coordinates, existing Supervisor lifecycle/audit patterns, and ADRs
0052-0054. Define durable installed-package state and atomic transactions that
require accepted trust plus non-incompatible hardware evidence, retain rollback
versions, and never delete the last known-good artifact before commit.
