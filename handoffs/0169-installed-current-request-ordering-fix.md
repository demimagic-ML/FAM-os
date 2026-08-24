# Handoff 0169: Installed current-request ordering fix

**Date:** 2026-07-18  
**Plan step:** Phase 23.3 and 23.6 readiness  
**Status:** Complete regression repair; Phase 23 remains open  
**Previous handoff:** `0168-installed-conversation-first-console.md`

## Objective

Fix the installed Console behavior where a second local-machine question could
receive the previous turn's answer even though it had a distinct durable request
and candidate.

## Scope completed

- Confirmed that VS Code was absent from the failing request path. Both affected
  tasks were ordinary `conversation` requests with no application execution.
- Identified the source defect: `PreparedGenerationInput.user_prompt()` placed
  the active request before the previous conversation, leaving the old assistant
  answer as the final model input.
- Reordered supporting session memory and authorized application observations
  before an explicit `Current user request` section.
- Preserved the exact prompt for requests with no supporting context.
- Strengthened the system contract so earlier answers cannot be repeated unless
  requested and missing application/workspace context is reported instead of
  invented.
- Added unit and production-gateway regressions for ordering, plain requests,
  shared message rendering, workspace evidence discipline, and exact-session
  memory.
- Built, signed, installed, restarted, and diagnosed the corrected release.
- Replayed the exact two-turn scenario through one authenticated installed
  Console session using real `qwen3:1.7b` inference.

## Explicitly not completed

- No durable conversation ledger was added; default session memory remains
  process-only and bounded.
- No workspace was automatically selected or inferred.
- Phase 23 release matrices, 24-hour soak, security review, and fresh-user
  lifecycle qualification remain open.

## Architecture and decisions

ADR 0125 remains authoritative: session memory is bounded, volatile,
nonauthoritative, and exact-session scoped. This repair changes serialization,
not authority or retention. Supporting context must precede the active request
because recency-sensitive models otherwise treat an old assistant turn as the
instruction to continue. No public schema, component boundary, or persistent
format changed, so no new ADR was required.

## Files changed

| Path | Purpose |
|---|---|
| `src/fam_os/core/production/generation_input.py` | Put supporting context before the active request and strengthen evidence-safe conversation instructions. |
| `tests/unit/test_generation_input.py` | Cover plain, contextual, message, and workspace-safety prompt behavior. |
| `tests/unit/test_production_task_gateway.py` | Prove the real same-session gateway prompt ends with the new request. |
| `docs/operations/PHASE20_SESSION_MEMORY.md` | Document the current-request ordering invariant. |
| `MASTER_PLAN.md` | Record Phase 23 installed readiness evidence. |
| `handoffs/README.md` | Register this append-only handoff. |

## Public interfaces

No command, schema, transport, or persistence interface changed. The internal
model-input invariant is now: nonauthoritative memory, authorized observations,
then the explicitly labelled current user request.

## Validation

```bash
PYTHONPATH=src .verification-venv/bin/python -m unittest \
  tests.unit.test_generation_input \
  tests.unit.test_production_session_memory \
  tests.unit.test_production_task_gateway
```

Result: 24 tests passed.

```bash
PYTHONPATH=src:. .verification-venv/bin/python -m unittest discover -s tests
```

Result: 1,193 tests passed with two declared environment skips.

```bash
.verification-venv/bin/ruff check src tests tools
PYTHONPATH=src:. .verification-venv/bin/python \
  tools/render_contract_schemas.py --check
```

Result: Ruff passed and all 283 schema artifacts validated.

## Evidence and artifacts

- Installed release: `fam-os-current-test-20260718-16`.
- Signed bundle manifest SHA-256:
  `f16f4e317cea91f9c56e3eebfbdeb535900a56342d86f1246b61d60242f0e75f`.
- First installed request: `conversation-final-identity-20260718`.
- Second installed request: `conversation-final-workspace-20260718`.
- Second candidate:
  `candidate-conversation-final-workspace-20260718-2`.
- The second answer stated that no application or workspace context was selected,
  did not repeat the identity response, and invited the owner to provide one.
- Installation diagnosis reported healthy after the service restart.
- The ephemeral private release keys were removed; only public trust material
  remains in the owner installation.

## Known limitations and risks

- This remains prompt-policy enforcement over an unverified 1.7B response. It
  prevents the reproduced failure but does not turn ordinary conversation into
  deterministic or verified output.
- The current Console task scope identifies an application instance, not a
  first-class whole-workspace picker or filesystem index.

## Operational notes

The owner service `fam-os-current-test.service` is active on loopback Console
port 8765 and uses external Ollama at `127.0.0.1:11434`. Refresh the browser page
to start a new visible transcript; the server-side authenticated session remains
bounded by its normal process/session lifetime.

## Recommended next entry point

Continue Phase 23.1–23.3 from signed release
`fam-os-current-test-20260718-16`, beginning with the explicit whole-workspace
selection/indexing scenario and the clean installed profile matrix.
