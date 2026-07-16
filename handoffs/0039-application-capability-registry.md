# Handoff 0039: Dynamic Application Capability Registry

**Date:** 2026-07-16  
**Plan step:** Phase 5.1  
**Status:** Complete  
**Previous handoff:** `0038-core-lifecycle-matrix.md`

## Objective

Implement a transport-neutral dynamic registry with atomic connector-owned
capability replacement, deterministic lookup/snapshots/events, and collision
protection.

## Scope completed

- Atomic register, same-connector replace, unregister, and availability updates.
- Global entry, instance ownership, and instance/capability collision rejection.
- Deterministic instance lookup and sorted immutable snapshots.
- Strict revisioned register/replace/remove/availability events.
- Idempotent remove and availability behavior.
- Concurrent distinct registration coverage.
- Rollback when collision or event construction fails.

## Explicitly not completed

- Authenticated local transport or persistence.
- MCP, VS Code, D-Bus, accessibility, or screen adapters.

## Architecture and decisions

ADR 0039 makes connector registration the atomic ownership unit. Event creation
precedes state mutation, and no transport implementation enters the registry.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/applications/registry.py` | Dynamic registry, snapshots, and events. |
| `src/fam_os/applications/__init__.py` | Public exports. |
| `tests/unit/test_application_capability_registry.py` | Atomicity, collision, concurrency, and event tests. |
| `tests/architecture/test_application_registry_boundary.py` | Transport/Core boundary guard. |
| `docs/protocols/APPLICATION_CAPABILITY_REGISTRY.md` | Registry protocol. |
| `docs/decisions/0039-atomic-connector-owned-capability-registry.md` | Durable decision. |
| `docs/protocols/APPLICATION_CONTRACTS.md`, `README.md`, `MASTER_PLAN.md` | Status/docs. |

## Validation

```bash
PYTHONPATH=src python3 -m unittest tests.unit.test_application_capability_registry tests.architecture.test_application_registry_boundary
PYTHONPATH=src python3 -m unittest discover -s tests
PYTHONPATH=src:. python3 tools/render_contract_schemas.py --check
PYTHONPATH=src python3 -m compileall -q src tests tools
larry index . && larry health .
```

Result: 9 focused and 412 total tests passed; 35 schemas matched; compile and AST
gates passed; Larry indexed 555 files / 1,543 symbols; graph has 7,752 nodes /
26,366 edges; health is clean.

## Known limitations and risks

- Registry state/events are process-local.
- Authentication and transport session ownership remain Phase 5.2.

## Operational notes

No external services or application processes were used.

## Recommended next entry point

Begin Phase 5.2 with Unix-domain peer-authenticated framed transport behind the
existing contracts. Keep wire parsing, session auth, dispatch, and registry
coordination in separate modules.
