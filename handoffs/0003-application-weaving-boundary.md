# Handoff 0003: Application weaving product boundary

**Date:** 2026-07-16  
**Plan step:** Product boundary and Phase 5 definition  
**Status:** Complete  
**Previous handoff:** `0002-prototype-map-and-contract-foundation.md`

## Objective

Correct the product architecture before further migration: define “weaving FAM into the PC” as permissioned intelligence operating through the user's existing applications, rather than a background model service limited to chat, CLI, or applications with custom plugins.

## Scope completed

- Defined the Universal Application Fabric and four user access surfaces: FAM Shell, FAM Console, application surfaces, and CLI/local API.
- Defined a tiered application-integration ladder covering native semantic connectors, OS/tool APIs, Linux accessibility, and restricted screen/input fallback.
- Made observation, proposal, modification, execution, confirmation, and postcondition checking separate authorities and lifecycle stages.
- Added the dynamic Application Capability Registry to the architecture.
- Moved the Application Fabric and FAM Shell MVP before full expert-registry and model-library expansion in the Master Plan.
- Expanded Phase 2 contracts and Phase 4 Core lifecycle requirements to include applications, permissions, approvals, actions, and postconditions.
- Renamed the empty source component boundary from `connectors` to `applications`; native connectors remain one integration mechanism inside the broader fabric.
- Recorded the durable product and component decision in ADR 0003.

## Explicitly not completed

- No application capability, observation, action, permission, or postcondition Python contracts were implemented; these remain Phase 2.4 and 2.5.
- No desktop, accessibility, D-Bus, portal, application, vision, or input adapter was implemented.
- FAM Shell and FAM Console were specified but not scaffolded.
- No application was observed or controlled.
- The immediate controlled-migration step remains Phase 1.5.

## Architecture and decisions

ADR 0003 makes external applications first-class capability providers. A native connector is preferred but cannot be required for basic usefulness. FAM selects the highest-fidelity available path for each operation and may combine paths within one task.

The Application Capability Registry describes what an application instance can currently observe or do; it does not grant authority. Core must combine originating intent, an explicit permission grant, reversibility, confirmation policy, preconditions, postconditions, and required verification before execution.

The Application Fabric is now Phase 5, immediately after the fake-driven FAM Core lifecycle. The previous phases 5 through 9 were renumbered 6 through 10. Later phases 11 through 14 retain their numbers.

## Files changed

| Path | Purpose |
|---|---|
| `docs/architecture/APPLICATION_WEAVING.md` | Canonical product, integration ladder, capability model, lifecycle, optimization, and acceptance demonstration |
| `docs/decisions/0003-universal-application-fabric.md` | Durable Application Fabric and component-boundary decision |
| `MASTER_PLAN.md` | Weaving invariant, application contracts, Core states, new Phase 5, and reordered later phases |
| `AGENTS.md` | Durable implementation and security rules for application weaving |
| `docs/PROJECT_STRUCTURE.md` | `applications/` ownership, client boundary, adapter scope, and dependency direction |
| `README.md` | User-facing FAM weaving definition and architecture link |
| `src/fam_os/applications/` | Broader Application Fabric component ownership |
| `src/fam_os/connectors/` | Removed empty source boundary; superseded by `applications/` |
| `handoffs/README.md` | Current numbered handoff example |

## Public interfaces

No executable public API was added. The following protocol families are now required before implementation:

- Application identity and instance
- Capability and capability registry
- Observation
- Action proposal and action result
- Permission grant and scope
- Confirmation requirement and decision
- Reversibility and compensating action
- Preconditions and postconditions
- Local intent, progress, approval, and result event transport

## Validation

```bash
cd <REPO_ROOT>/FAM_OS
PYTHONPATH=src python3 -m unittest discover -s tests -v
```

Result: 14 tests passed, 0 failures.

```bash
cd <REPO_ROOT>
python3 -m unittest discover -s tests -v
```

Result: all 10 parent prototype tests passed.

```bash
cd <REPO_ROOT>/FAM_OS
python3 -m compileall -q src tests
```

Result: completed successfully with no syntax errors.

```bash
cd <REPO_ROOT>/FAM_OS
PYTHONPATH=src python3 -c "import importlib.util; import fam_os.applications; assert importlib.util.find_spec('fam_os.connectors') is None; print(fam_os.applications.__name__)"
```

Result: `fam_os.applications`.

```bash
cd <REPO_ROOT>
npx -y larry-dev@latest setup
```

Result: 94 files indexed, 7 artifacts written, verification clean.

The codebase knowledge graph was refreshed in fast mode and found the new `fam_os.applications` package boundary.

## Evidence and artifacts

- `docs/architecture/APPLICATION_WEAVING.md`
- `docs/decisions/0003-universal-application-fabric.md`
- Parent `RESIDENT_NEURAL_FABRIC.md`, especially the Semantic State and Intent Bus and reference connector proposal

## Known limitations and risks

- “Universal” describes the fabric architecture, not a guarantee that every action in every application is controllable.
- Accessibility quality varies, and custom canvases may expose little structured state.
- Screen/input fallback is costly and fragile and will require stricter policy plus postcondition verification.
- Application adapters may expose sensitive state; observation grants need the same rigor as action grants.
- The exact FAM Shell technology and local transport are intentionally undecided until their contracts and Linux constraints are measured.

## Operational notes

This change modified architecture, project rules, and an empty Python package boundary only. It started no services, controlled no applications, changed no machine permissions, and downloaded no dependencies or models.

## Recommended next entry point

Continue Phase 1.5 exactly as recorded in the Master Plan and handoff 0002: add the typed hardware-profile contract and read-only Linux hardware adapter. Preserve ADR 0003 while migrating; application contracts begin in Phase 2.4 and 2.5 after prototype parity.
