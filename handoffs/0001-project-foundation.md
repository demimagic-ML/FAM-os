# Handoff 0001: FAM_OS project foundation

**Date:** 2026-07-16  
**Plan step:** Phase 0  
**Status:** Complete  
**Previous handoff:** Parent prototype `../../HANDOFF.md` outside FAM_OS

## Objective

Create the canonical FAM_OS project boundary and governance before continuing RNF implementation.

## Scope completed

- Defined FAM_OS as an OS intelligence service above Linux.
- Defined the deterministic privileged supervisor and unprivileged intelligence boundary.
- Established rules prohibiting god scripts and mixed-responsibility modules.
- Defined component ownership and dependency direction.
- Created a phase-gated master implementation plan.
- Created append-only handoff and ADR processes.
- Preserved the parent RNF prototype as migration evidence rather than silently moving it.

## Explicitly not completed

- No prototype source was moved.
- No new runtime behavior was implemented.
- No package skeletons were created beyond governance and documentation directories.
- The parent prototype was not marked read-only; that occurs after Phase 1 parity.

## Architecture and decisions

ADR 0001 accepts a user-space OS intelligence service. Linux remains the machine authority. The FAM Supervisor is deterministic and minimal. Generative models run only in isolated user-space services.

The term “FAM Core” replaces “resident neural kernel” when referring to the AI coordinator, avoiding confusion with the Linux kernel.

## Existing prototype evidence

The parent workspace has already demonstrated:

- Granite 2.5B routing accuracy of 95.8% over 24 balanced tasks.
- Granite CPU-only operation at 24.2 tokens/s and 2.30 GB peak memory.
- Simultaneous Granite plus Qwen Coder 14.8B operation under a 16 GiB cgroup.
- A 2K context reducing persistent 14B peak usage to 13.90 GiB.
- Granite plus Qwen Coder 7.6B at 6.24 GiB peak and 9.3 tokens/s.
- Deterministic sandbox verification, bounded repair, model eviction, and 14B escalation.
- A verified final code candidate released only after deterministic tests passed.

The prototype also proved that both 7B and 14B experts can generate plausible but incorrect code, making verification a core fabric rather than an optional feature.

## Files changed

| Path | Purpose |
|---|---|
| `FAM_OS/AGENTS.md` | Binding implementation rules |
| `FAM_OS/MASTER_PLAN.md` | Authoritative phased plan |
| `FAM_OS/README.md` | Project entry point |
| `FAM_OS/docs/PROJECT_STRUCTURE.md` | Intended modular structure |
| `FAM_OS/docs/decisions/0001-user-space-os-intelligence-service.md` | Foundational architecture decision |
| `FAM_OS/handoffs/README.md` | Handoff workflow |
| `FAM_OS/handoffs/HANDOFF_TEMPLATE.md` | Required handoff structure |
| `FAM_OS/handoffs/0001-project-foundation.md` | Initial history and next entry point |

## Public interfaces

No runtime interface was added. Governance interfaces added:

- Master-plan status format
- Handoff sequence and template
- ADR sequence and format
- Component-boundary vocabulary

## Validation

```bash
find FAM_OS -type f -maxdepth 4 | sort
```

Expected result: all foundation documents are present with no implementation source added.

## Evidence and artifacts

- Parent design: `../../RESIDENT_NEURAL_FABRIC.md`
- Parent prototype handoff: `../../HANDOFF.md`
- Parent results: `../../EXPERIMENT_RESULTS.md`
- Parent raw results: `../../artifacts/benchmarks/`
- Foundational decision: `docs/decisions/0001-user-space-os-intelligence-service.md`

## Known limitations and risks

- The current implementation remains outside the canonical FAM_OS boundary.
- Prototype modules mix adapters and orchestration and must not be copied blindly.
- Current verification covers one Python task and is not a hardened hostile multi-tenant boundary.
- Ollama observes host RAM rather than the imposed cgroup ceiling, so FAM_OS needs its own scheduler.

## Operational notes

The constrained prototype service should be inactive when work is not running:

```bash
../../scripts/rnf-cpu-server status
```

No service or model state was changed by this foundation step.

## Recommended next entry point

Advance Phase 1.1 and 1.2 together:

1. Read the parent `HANDOFF.md` and `EXPERIMENT_RESULTS.md`.
2. Inventory the parent prototype files and public behavior.
3. Write `FAM_OS/docs/migration/PROTOTYPE_MIGRATION_MAP.md`.
4. Assign every prototype behavior to one FAM_OS component.
5. Define parity tests before moving any implementation source.
